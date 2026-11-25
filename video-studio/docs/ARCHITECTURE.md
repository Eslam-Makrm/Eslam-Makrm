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
| GPU backend | Kaggle (free, 30 h/week) via `vs-gpu` | private script kernels on T4×2 / L4: Z-Image-Turbo, Wan2.2-TI2V-5B, Chatterbox, MuseTalk |
| Orchestration | `vs-produce` + `production.json` | gen → voice → shots → edit → qc, resumable, per-shot fallbacks logged to `build/route.json` |

## How the cloud GPU is driven (no browser, no clicks)

`vs-gpu` talks to `https://api.kaggle.com/v1/kernels.KernelsApiService/*` directly (SaveKernel,
GetKernelSessionStatus, ListKernelSessionOutput, GetAcceleratorQuotaStatistics). The API token is a
**network secret**: the proxy injects `Authorization: Bearer …` for api.kaggle.com, so the token never
enters the session. (The official `kaggle` CLI can't be used for auth here: it verifies the token by
sending it in a request *body*, which the proxy can't fill.) Job + params + inputs (≤25 MB, base64) are
packed into one private script; outputs are fetched from `www.kaggleusercontent.com`.

## Integration tests

| Test | Result |
|---|---|
| Skills load in Claude Code from `.claude/skills` | **PASS** (listed by the session after restructure) |
| `install.sh --system --gpu-client` on a fresh cloud machine | **PASS** (fixed: PyAV pin had no wheel; kaggle 2.2.5 missing `six`) |
| `vs-doctor --smoke --gpu` | **PASS** 50 / FAIL 1 (the Kaggle GPU grant, below) |
| Kaggle API auth via proxy, quota | **PASS**: 30 h GPU + 20 h TPU per week, refresh Sat 00:00 UTC |
| Kaggle job submit → run → status → download | **PASS** (probe kernel, 46 s round trip) |
| Kaggle grants GPU + internet to the job | **BLOCKED**: account not phone-verified; job ran on CPU with no internet. Detected and reported automatically |
| Z-Image / Wan2.2 / Chatterbox / MuseTalk jobs on GPU | **NOT YET RUN** (blocked by the line above) |
| vs-camera move / parallax / grade | **PASS** (4 s 720p parallax in ~4 s on 4 cores; frames checked by eye) |
| vs-qc on phase-1 lesson | **PASS** (Arabic WER 8 %, −14.0 LUFS) |
| vs-lipsync2d (Arabic Piper line) | **PASS** (34 cues / 4.8 s in 1.4 s) |
| One-prompt production, CPU route (`samples/08`) | **PASS**: 21.7 s 9:16 Arabic ad, QC PASS (WER 7 %, OCR 1.00 on titles), AI-video shot fell back to keyframe + parallax |
| `tests/run-all.sh --skip-story` | see the commit message of the run |

## Licences (checked on Hugging Face model cards / LICENSE files)

| Component | Licence |
|---|---|
| Wan2.2-TI2V-5B(-Diffusers) | Apache-2.0 |
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

- Kaggle free tier: 30 GPU-h/week; each job pays ~3–6 min start-up + model download → batch per production.
- MuseTalk job clones the upstream repo at `main` and runs its weight-download script: pin a commit and
  review the script at the first GPU run.
- Chatterbox pins torch 2.6; the job installs it `--no-deps` on Kaggle's newer torch — verify at first run.
- Claude cannot hear audio: QC uses Whisper WER and loudness; a human listen is still asked for.
