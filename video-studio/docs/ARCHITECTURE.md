# Architecture and verification status (2026-11-25)

Decision (by the owner): Claude is the only agent. No OpenAI / ChatGPT / Codex / Sora / image_gen,
no paid APIs. Free open-source tools on CPU, open models on free cloud GPU. Phase B + automated Phase C′.
Earlier Codex-based plans (`GAP-ANALYSIS.md`, `CLOUD-ARCHITECTURE.md`) are kept for history only.

## Layers

| Layer | Where | What |
|---|---|---|
| Agent | Claude Code (cloud session, environment "Eslam-Makrm video studio") | writes script/storyboard/production.json, renders code-drawn shots, drives tools, judges QC |
| Skills | `.claude/skills/` (21) | instructions Claude loads automatically in this repo |
| CPU tools | `~/.video-studio` (from `install.sh`) | ffmpeg, HyperFrames, Manim, p5 kit, Piper, Whisper, ONNX depth/DINOv2, Tesseract-ara, Rhubarb |
| GPU backend | Kaggle (free, 30 h/week) via `vs-gpu` | private script kernels on 2× Tesla T4: Z-Image-Turbo (→ SDXL), Wan2.2-TI2V-5B (→ Wan2.1-1.3B), Chatterbox, MuseTalk |
| Orchestration | `vs-produce` + `production.json` | gen → voice → shots → edit → qc, resumable, per-shot fallbacks logged to `build/route.json` |

## How the cloud GPU is driven (no browser, no clicks)

`vs-gpu` talks to `https://api.kaggle.com/v1/kernels.KernelsApiService/*` directly (SaveKernel,
GetKernelSessionStatus, ListKernelSessionOutput, GetAcceleratorQuotaStatistics). The API token is a
**network secret**: the proxy injects `Authorization: Bearer …` for api.kaggle.com, so the token never
enters the session. (The official `kaggle` CLI can't be used for auth here: it verifies the token by
sending it in a request *body*, which the proxy can't fill.) Job + params + inputs (≤25 MB, base64) are
packed into one private script; outputs are fetched from `www.kaggleusercontent.com`.

## Running on Kaggle's free 2× Tesla T4 (no dependency on L4)

T4 = Turing sm75, 14.6 GB, 65 TFLOPS fp16 tensor (14.5 measured on a plain matmul), **no native bf16**
(torch emulates it, several times slower). Every job is packed with `gpu-jobs/_common.py`:

| Technique | Where | Why |
|---|---|---|
| fp16 compute where the model tolerates it, bf16 only where it must | video (Wan, fp16 + automatic bf16 redo of black/NaN clips), SDXL, MuseTalk | 4–8× faster than emulated bf16 on T4 |
| `device_map="balanced"` over both GPUs | Z-Image (Qwen3-4B text encoder ↔ 6B transformer), Wan2.2 (UMT5-XXL ↔ 5B transformer) | the pair doesn't fit one 14.6 GB card; splitting avoids CPU round-trips |
| fp8 weight storage (`enable_layerwise_casting`) + model CPU offload | automatic fallback when balanced placement fails | halves transformer memory on one T4 |
| sequential CPU offload | last resort | always fits, slowest |
| VAE tiling/slicing | image + video | VAE decode is the usual OOM point |
| one process per GPU (`shard()`) | SDXL, Chatterbox (small models) | both T4s work in parallel → ~2× throughput |
| T4 video preset | 832×480, 81 frames (3.4 s @24), 20 steps; `t4-fast` 49 frames/16 steps | 720p/121 frames would take hours per clip on T4 (estimated) |
| light models | SDXL (images), Wan2.1-T2V-1.3B (text-to-video) | used when the big model can't run reliably |
| Kaggle limits handled | 1 interactive + **2 batch GPU sessions max**; stuck queued kernels hold slots → `vs-gpu cancel`; `vs-produce --async` to avoid waiting | measured on this account |

## Integration tests

| Test | Result |
|---|---|
| Skills load in Claude Code from `.claude/skills` | **PASS** (listed by the session after restructure) |
| `install.sh --system --gpu-client` on a fresh cloud machine | **PASS** (fixed: PyAV pin had no wheel; kaggle 2.2.5 missing `six`) |
| `vs-doctor --smoke --gpu` | **PASS** 50 / FAIL 1 (the Kaggle GPU grant, below) |
| Kaggle API auth via proxy, quota | **PASS**: 30 h GPU + 20 h TPU per week, refresh Sat 00:00 UTC |
| Kaggle job submit → run → status → download | **PASS** (probe kernel, 46 s round trip) |
| Kaggle grants GPU + internet to the job | **PASS** after the owner's phone verification: 2× Tesla T4 (14.6 GB each), 14.5 fp16 TFLOPS, torch 2.11+cu130, HF downloads 92 MB/s, 31 GB RAM, 19.5 GB disk. Before verification jobs ran on CPU without internet — detected and reported automatically |
| Parallel GPU sessions | an L4 job submitted alongside a T4 job got no GPU, and the T4 job then sat "queued" for 2 h holding a slot; Kaggle refused new jobs with *"Maximum batch GPU session count of 2 reached"* until the stuck kernel was deleted → submit sequentially; `vs-gpu cancel` added |
| GPU runtime packing + 2-GPU fan-out (CPU self-test, `tests/test_gpu_runtime.sh`) | **PASS** |
| `vs-produce --async` (stub backend, `tests/test_produce_async.sh`) | **PASS** |
| vs-camera move / parallax / grade | **PASS** (4 s 720p parallax in ~4 s on 4 cores; frames checked by eye) |
| vs-qc on phase-1 lesson | **PASS** (Arabic WER 8 %, −14.0 LUFS) |
| vs-lipsync2d (Arabic Piper line) | **PASS** (34 cues / 4.8 s in 1.4 s) |
| One-prompt production, CPU route (`samples/08`) | **PASS**: 21.7 s 9:16 Arabic ad, QC PASS (WER 7 %, OCR 1.00 on titles), AI-video shot fell back to keyframe + parallax |
| `tests/run-all.sh --skip-story` (phase-1 engines + camera, 2D lip sync, one-prompt ad, Kaggle API) | **PASS 10/10** |

## GPU model tests on Kaggle T4 (actual results)

| Job | Run | Result |
|---|---|---|
| probe | 2026-11-25 | **PASS** — 2× T4, 14.5 fp16 TFLOPS, 92 MB/s HF download |
| Z-Image-Turbo, single T4, bf16, model CPU offload (first version) | 2026-11-25 | **FAIL** — loaded in 246 s, then CUDA out of memory in attention (13.9 of 14.6 GB used). Led to the balanced 2-GPU placement, fp8 fallback and SDXL fallback |
| image.py v2 (Z-Image over 2× T4 → SDXL fallback) | submitted 2026-11-25 as `vs-t4-image` | see the GPU ledger below |
| video.py (Wan2.2-5B t4 preset / Wan2.1-1.3B) | — | **PENDING** (not yet run; one batch job at a time) |
| tts_chatterbox.py (Arabic, emotion 0.35 / 0.85, English) | — | **PENDING** |
| lipsync_musetalk.py | — | **PENDING** |

### GPU ledger
<!-- updated by hand from report.json of each run -->

## Licences (checked on Hugging Face model cards / LICENSE files)

| Component | Licence |
|---|---|
| Wan2.2-TI2V-5B(-Diffusers), Wan2.1-T2V-1.3B(-Diffusers) | Apache-2.0 |
| SDXL base 1.0 / sdxl-vae-fp16-fix | OpenRAIL++ (commercial use with use restrictions) / MIT |
| Z-Image-Turbo | Apache-2.0 |
| Chatterbox (incl. multilingual) / chatterbox-tts 0.1.7 | MIT |
| MuseTalk 1.5 | MIT (bundled sd-vae/Whisper keep their own) |
| Depth-Anything-V2-Small, DINOv2-small (ONNX exports) | Apache-2.0 |
| Rhubarb Lip Sync 1.14.0 | MIT (deps MIT/BSD/Boost) |
| HyperFrames skills v0.9.93 · manim_skill · explainroo | Apache-2.0 · MIT · MIT |
| Kaggle client 2.2.5 | Apache-2.0 (installed; auth bypassed by `vs-gpu`) |

Rejected: LTX-2 (revenue-capped), HunyuanVideo (territorial), FLUX.1-dev/Kontext, FLUX.2-klein-9B,
Qwen-Image 2.x, XTTS-v2, Wav2Lip, InsightFace-based ID tools, Habibi Unified/SAU/UAE (non-commercial);
Colab automation (forbidden on the free tier).

## Known limits

- Kaggle free tier: 30 GPU-h/week, 2 batch GPU sessions; each job pays start-up + model download
  (Z-Image: 246 s measured) → batch per production, submit sequentially.
- MuseTalk job is pinned to commit 2536eaf and downloads weights from official Hugging Face itself (upstream
  script used a third-party mirror and Google Drive); its mmcv/mmpose install is verified at the first GPU run.
- Chatterbox pins torch 2.6; the job installs it `--no-deps` on Kaggle's newer torch — verify at first run.
- Claude cannot hear audio: QC uses Whisper WER and loudness; a human listen is still asked for.
