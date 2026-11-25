---
name: ai-generation
description: Generate AI images, AI video (text-to-video and image-to-video), expressive Arabic/English speech and realistic lip sync with open-source models on Kaggle's free GPU, fully automated from this session (vs-gpu submits, waits and downloads — no browser). T4 defaults chosen for reliability: SDXL images, Wan2.1-1.3B text-to-video, Chatterbox Multilingual voice, MuseTalk 1.5 lip sync; Z-Image-Turbo and Wan2.2-TI2V-5B are optional heavy modes; all tuned for Kaggle's free 2× T4 and licensed for commercial use. Use when a shot needs a generated picture or real motion, for "generate an image/video", "AI video", "صورة بالذكاء الاصطناعي", "فيديو بالذكاء الاصطناعي", or when video-producer routes a shot to ai-image / ai-video.
---

# AI generation on the free cloud GPU (Kaggle)

```bash
source ~/.video-studio/env.sh
vs-gpu quota                                            # GPU hours left this week (30 h/week, resets Saturday 00:00 UTC)
vs-gpu run $VS_REPO/gpu-jobs/<job>.py OUT_DIR --params @params.json [--input file]...
```

`vs-gpu run` packs the job + params + inputs into one private Kaggle script, runs it on Kaggle's free
2× Tesla T4 (14.6 GB each; everything is tuned for T4, nothing depends on L4), waits, downloads `OUT_DIR/*` plus `report.json` (timings) and
`kaggle.log`. The Kaggle token is a network secret injected by the proxy; `KAGGLE_USERNAME` is set in the
environment. Inside `video-producer`, `vs-produce` calls these jobs for you, batched.

## Jobs (`$VS_REPO/gpu-jobs/`), tuned for Kaggle's free 2× Tesla T4

Every job gets the shared runtime (`_common.py`): GPU detection, T4-aware dtype (fp16 where the model is
fp16-safe — T4 has no native bf16), `load_pipe` (text encoder on one T4 + transformer on the other via
`device_map="balanced"` → fallback fp8 weights + CPU offload → sequential offload), VAE tiling, black/NaN
output guard, and `shard()` which runs small models once per GPU in parallel.

| Job | Models (licence) | Params | T4 plan |
|---|---|---|---|
| `image.py` | **`sdxl` (default)**: SDXL base 1.0 (OpenRAIL++) + fp16-fix VAE (MIT) · `zimage` (heavy, optional): Z-Image-Turbo 6B (Apache-2.0) | `{"model","items":[{"id","prompt","width","height","seed"}],"item_budget_s","max_job_s"}` | SDXL fp16, one copy per T4 (parallel), NaN/black → 1 retry with another seed. Z-Image needs both T4s + fp8 weights (OOM in bf16, measured) and falls back to SDXL |
| `video.py` | **`wan21-1.3b` (default)**: Wan2.1-T2V-1.3B (Apache-2.0, text-only) · `wan22-5b` (heavy, `allow_heavy`): Wan2.2-TI2V-5B (Apache-2.0, text+image-to-video) | `{"model","preset":"t4"\|"t4-fast","items":[{"id","prompt","image"?,"frames","seed"}],"allow_heavy","item_budget_s","max_job_s"}` | one T4, model CPU offload, fp16, VAE tiling; preset `t4` = 832×480, 81 f (3.4 s), 20 steps; NaN latents stop a clip at that step and it is redone once in bf16; `vs-produce` upscales. `hq` is for bigger GPUs only |
| `tts_chatterbox.py` | Chatterbox Multilingual 0.5B (MIT) | `{"lang","voice"?,"lines":[{"id","text","exaggeration","cfg"}]}` | one copy per T4, lines split across both |
| `lipsync_musetalk.py` | MuseTalk 1.5 (MIT; pinned 2536eaf, weights from official HF) | `{"items":[{"id","video","audio"}],"fp16":true}` | fp16, one T4 |
| `probe.py` | — | — | GPU, VRAM, TFLOPS, HF download speed |

In `production.json → gpu`: `image_model` (sdxl|zimage), `video_model` (wan21-1.3b|wan22-5b),
`video_preset` (t4|t4-fast|hq), `allow_heavy` (false: zimage / wan22-5b are swapped for the light models on T4),
`accelerator` (default NvidiaTeslaT4 — never depend on L4).

## Reliability guards (every job)

- **Hard budget** `max_job_s` (default 3600): a watchdog inside the kernel stops the job and reports `timed_out`
  so a stuck run never burns quota; `vs-produce` sizes it from the number of items.
- **Queue timeout** (`vs-gpu run --queue-timeout`, default 45 min): a job Kaggle never starts is deleted so it
  stops holding one of the 2 free batch slots (measured: a queued T4 job can wait > 2 h); exit code 6 = retry later.
- **Per-step guard** (`step_guard`): NaN/inf latents or a projected item time above `item_budget_s` stop that
  item at the failing step (seconds, not an hour) and the job moves on.
- **Benchmarks in `report.json`**: `load_s`, per item `s` / `denoise_s` / `s_per_step` / `decode_s`,
  `vram_peak_gb` per GPU, `failed[]`. `tests/gpu-bench.sh OUT` runs the whole T4 default stack and also logs
  GPU-quota use per job.
- **Don't retry what can't fit**: configurations measured to exceed a T4 are listed in
  `docs/ARCHITECTURE.md` (T4 fit table) — don't resubmit them; use the light model or a fallback.

## Don't burn the session waiting

`vs-gpu run` polls Kaggle from a local process (no model usage). For long jobs use
`vs-produce DIR --async`: it submits the batched jobs, finishes every CPU stage it can, and exits 75; run
the same command later (or after other work) — it checks each job **once** and continues. Never write
polling loops of your own. Free accounts get **one GPU session at a time**: submit jobs sequentially.

## Prompts that work (Wan / Z-Image)

Subject + action + setting + light + lens + camera move, concrete and visual:
"a young Egyptian chef plates koshari in a sunlit kitchen, steam rising, 50mm, shallow depth of field,
slow dolly-in". Camera words Wan follows: *static shot, slow dolly-in, pull back, pan left, tracking shot,
orbit around, crane up, handheld*. Avoid text in generated images (render titles with HyperFrames).
Character consistency: generate the **keyframe** with the character-bible prompt; with the default (text-only)
video model recurring characters stay on keyframe + parallax camera moves; with `allow_heavy` the keyframe is
animated by Wan2.2-5B image-to-video. Never plain text-to-video for recurring characters.

## Budget and timing (free tier)

30 GPU-hours/week (verified). Each job pays start-up + model download (Z-Image: ~4 min measured at
92 MB/s), so **batch**: one job for all images, one for all clips, one for all voice lines. Per-item times
on T4 are recorded in each job's `report.json` — see `docs/ARCHITECTURE.md` for measured numbers.

## When the GPU is unavailable

Kaggle needs a **phone-verified** account for GPU + internet. `vs-gpu` reports "Kaggle gave this session no
GPU" and `vs-produce` falls back automatically (keyframe + parallax camera move, Piper voice) and records it
in `build/route.json`. Tell the person what fell back and why.

## Never

OpenAI / ChatGPT / Codex / Sora / image_gen, paid APIs, Colab automation (its free tier forbids it), real
people's likeness without consent, non-commercial models (FLUX.1-dev/Kontext-dev, FLUX.2-klein-9B,
Qwen-Image 2.x, XTTS, Wav2Lip, InsightFace-based ID tools, Habibi Unified/SAU/UAE).
