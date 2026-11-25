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
| Colab backup: notebook build, every cell executed with stubbed `nvidia-smi`/`google.colab`, result import, zip-slip refused, committed notebooks current (`tests/test_colab.sh`) | **PASS** (CPU; not yet run on a real Colab T4) |
| `vs-produce --gpu colab`: notebook written → result imported → film finished (`tests/test_produce_colab.sh`) | **PASS** (CPU) |
| vs-camera move / parallax / grade | **PASS** (4 s 720p parallax in ~4 s on 4 cores; frames checked by eye) |
| vs-qc on phase-1 lesson | **PASS** (Arabic WER 8 %, −14.0 LUFS) |
| vs-lipsync2d (Arabic Piper line) | **PASS** (34 cues / 4.8 s in 1.4 s) |
| One-prompt production, CPU route (`samples/08`) | **PASS**: 21.7 s 9:16 Arabic ad, QC PASS (WER 7 %, OCR 1.00 on titles), AI-video shot fell back to keyframe + parallax |
| `tests/run-all.sh --skip-story` (phase-1 engines + camera, 2D lip sync, one-prompt ad, Kaggle API) | **PASS 10/10** |

## T4 model plan (reliability first)

The objective is a reliable, repeatable studio on the free tier, not the biggest model. On 2× Tesla T4
(14.6 GB each, sm75, no native bf16):

| Need | Default (T4) | Optional heavy mode (`gpu.allow_heavy`) | Automatic fallback |
|---|---|---|---|
| Image | SDXL base 1.0 fp16, one copy per T4 | Z-Image-Turbo 6B (2 GPUs + fp8 weights) | SDXL |
| Text-to-video | Wan2.1-T2V-1.3B, 832×480, 81 f, 20 steps, one T4 + model offload | Wan2.2-TI2V-5B | SDXL keyframe + parallax |
| Image-to-video (recurring characters) | SDXL keyframe + parallax camera move | Wan2.2-TI2V-5B i2v | — |
| Voice | Chatterbox Multilingual (one copy per T4) | — | Piper (CPU) |
| Lip sync | MuseTalk 1.5 fp16 (one T4) | — | voice-over on B-roll |

### T4 fit table: configurations measured NOT to fit (do not resubmit)

| Configuration | Measured on T4 | Status |
|---|---|---|
| Z-Image-Turbo bf16 on one T4 (model CPU offload) | OOM in attention, 13.9/14.6 GB | does not fit |
| Z-Image-Turbo bf16, `device_map="balanced"` over 2 T4 | OOM on GPU 0 (12 GB transformer + 1.46 GB attention) | does not fit |
| Wan2.2-5B, balanced + fp8, fp16 | denoise OK (7.8 s/step) but VAE decode ~62 min and black frames | unusable; heavy mode now uses one T4 + offload |
| any preset `hq` (1280×704, 121 f) | not run: projected hours per clip | bigger GPUs only |

## GPU model tests on Kaggle T4 (actual results)

| Job | Run | Result |
|---|---|---|
| probe | 2026-11-25 | **PASS** — 2× T4, 14.5 fp16 TFLOPS, 92 MB/s HF download |
| Z-Image-Turbo, single T4, bf16, model CPU offload (first version) | 2026-11-25 | **FAIL** — loaded in 246 s, then CUDA out of memory in attention (13.9 of 14.6 GB used). Led to the balanced 2-GPU placement, fp8 fallback and SDXL fallback |
| image.py v2 (Z-Image balanced over 2× T4 → SDXL fallback) | 2026-11-25 `vs-t4-image` | **FAIL** — load 267 s; Z-Image OOM on GPU 0 (12 GB transformer + 1.46 GB attention); SDXL fallback crashed (`enable_vae_tiling` removed in diffusers 0.43). Fixed in 61049c8 (fp8 transformer weights in balanced mode, `vae_tiling()`); retest `vs-t4-image2` **PENDING** |
| tts_chatterbox.py (2 lines over 2× T4) | 2026-11-25 `vs-t4-tts` | **PARTIAL** — `excited` line generated (model load 39 s, 20.4 s per line, 1.5 min job); the other worker crashed: both downloaded pkuseg's model into `~/.pkuseg` at once (`FileExistsError`). Fixed in 00e4db8 (fetched once before fan-out); retest **PENDING** |
| tts_chatterbox.py retest (3 lines over 2× T4) | 2026-11-25 `vs-t4-tts2` | **PASS** — all 3 lines; both GPU workers OK. Load 35 s, 20.5 s per Arabic line (5.2–5.5 s audio), 3.3 s for the English line; peak VRAM 3.2 GB per T4; 2.2 min job, 0.04 GPU-h. Checked by transcription (Whisper medium): Arabic calm 1/9 words wrong (name ليلى → لينا), excited 1/8 (القصة → قصة), English exact; ≈ −18 LUFS before the studio's −14 LUFS mix. Audio not listened to by a human yet |
| image.py SDXL primary | 2026-11-25 `vs-t4-sdxl` 14:00, `bench-sdxl` 15:31 and 16:17 UTC | **NOT RUN** ×3 — each stayed queued 45 min without a T4 and was deleted by the queue timeout (0 GPU-h used); retries continue |
| video.py Wan2.1-1.3B text-to-video (t4 preset, 2 clips) | 2026-11-25 `vs-t4-wan13` 14:45, `bench-wan13` 17:02 UTC | **NOT RUN** — first try queued 45 min, deleted; second try queued at the time of writing |
| image.py Z-Image retest | 2026-11-25 `vs-t4-image2` | **NOT RUN** — queued 2 h without a T4; deleted (heavy mode, deprioritised) |
| video.py text-to-video (Wan2.2-5B, t4-fast 832×480×49 f, 16 steps) | 2026-11-25 `vs-t4-video` | **FAIL** — load 284 s; denoising **7.8 s/step (2 min for 16 steps)**, but the VAE decode took ~62 min (VAE ended up off-GPU under `device_map="balanced"`) and the fp16 output was black; the bf16 rebuild then hit OOM on GPU 1 (first pipeline not freed). 70 GPU-minutes. Fixed in 00e4db8: one T4 with model CPU offload (VAE on GPU, no fp8), NaN latents stop the run at the failing step, hooks removed before the bf16 rebuild; retest **PENDING** |
| video.py image-to-video, lipsync_musetalk.py | — | **PENDING** (queued after the image retest; they need its keyframes) |

GPU used by all runs so far: 1.57 h of the 30 h weekly quota.

Next round (T4-first defaults, running): Chatterbox retest (3 lines, Arabic calm/excited + English), SDXL as
primary (3 images), Wan2.1-1.3B text-to-video (2 clips, t4 preset), MuseTalk on an SDXL portrait. Reusable as
`tests/gpu-bench.sh` (writes `bench.jsonl` with time, VRAM peak and quota per job, plus contact sheets).

### Kaggle queue investigation (2026-11-25)

What the account shows (`GetAcceleratorQuotaStatistics`, `ListKernels`, `GetKernelSessionStatus`):
- From 13:11 UTC on, every T4 batch job except one sat in state QUEUED (empty status) for 45 min–2 h with
  `timeReserved: 0s` — Kaggle never assigned a GPU, so nothing was wrong inside the jobs and no quota was used.
- The exception: the TTS job submitted at 13:57 started at once while an image job submitted at 13:11 was still
  queued. So the queue is not strictly first-in-first-out per account and not caused by our own slot use
  (no other session was active; `ListKernels` lists only studio kernels).
- Jobs before 12:00 UTC started within a minute. The stalls coincide with US daytime (≈14:00–22:00 UTC),
  when free T4 demand is highest — a likely but unconfirmed cause.

Interactive vs API: an API-submitted kernel is a *batch* session — the same thing as **Save Version → Save &
Run All** in the web UI; batch and interactive sessions draw on the same 30 h weekly GPU quota but have
separate concurrency limits (1 interactive, 2 batch measured here). Kaggle's documentation pages are rendered by
JavaScript and could not be read automatically, and nothing official states whether interactive sessions are
served before batch ones. The API cannot open an interactive session, so this can only be checked by hand:
while a studio job shows QUEUED, open kaggle.com → Code → New Notebook → Settings → Accelerator **GPU T4 ×2**
and see whether the session starts. If it starts, interactive sessions are served first and the notebook can
be used like the Colab backup (paste a `colab/*.ipynb` job cell; it writes to `/kaggle/working/out`). If it also
waits, the shortage is Kaggle-wide and the remedy is to retry outside US daytime or use Colab.

Mitigations in place: `vs-gpu run --queue-timeout` (default 45 min, deletes the queued kernel so it never holds a
slot), retry rounds 30 min apart in long chains, `vs-produce --async`, and the Colab manual backup below.

## Colab manual backup (`vs-colab`, `colab/*.ipynb`)

Kaggle stays the automated provider; Colab is a **manual** fallback that a person runs, because Colab's free
tier forbids remote control and favours people working in the notebook UI (Colab FAQ, read 2026-11-25:
restricted on free runtimes — SSH/remote desktops, bypassing the notebook UI for a web UI, distributed workers;
banned everywhere — multiple accounts to dodge limits, deepfakes, proxies, mining). Free Colab gives
usually one T4, ≤ 12 h per runtime, idle timeouts and unpublished, changing limits.

- `vs-colab build JOB.py NB.ipynb --params … --input … [--ask FILE]` packs **the same job code** that goes to
  Kaggle (`_boot.tmpl` + `_common.py` + job + params + inputs) into one notebook; `/kaggle/working` and
  `/kaggle/temp` are mapped onto `/content`, so the jobs run unchanged. The person presses Run all; the
  notebook downloads `vs-result-NAME.zip` and releases the GPU (`runtime.unassign()`).
- `vs-colab import ZIP OUT` unpacks it into the layout `vs-gpu fetch` writes (paths escaping OUT refused).
- `vs-produce DIR --gpu colab` writes `build/colab/NAME.ipynb` for each GPU stage, exits 75, and continues
  after import; routes are recorded as `…@colab-t4`.
- Ready-made notebooks (rebuild with `colab/build.sh` after changing a job; `tests/test_colab.sh` fails if
  stale): `colab/sdxl.ipynb` (3 SDXL test images), `colab/wan21-1.3b.ipynb` (2 Wan2.1-1.3B clips, t4 preset),
  `colab/musetalk.ipynb` (asks for a face image, uses the Chatterbox Arabic sample as audio).
- Colab's free VM has ~12.7 GB RAM (Kaggle 31 GB): Wan's 11 GB UMT5 text encoder cannot sit in RAM beside the
  transformer for CPU offload, so `video.py` switches to **low-RAM mode** below 20 GB host RAM — prompts are
  encoded first with the encoder on the GPU, the encoder is freed, and the pipeline runs on the embeddings.
  Not yet verified on a real Colab runtime.

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
