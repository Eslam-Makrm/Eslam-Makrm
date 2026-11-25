---
name: ai-generation
description: Generate AI images, AI video (text-to-video and image-to-video), expressive Arabic/English speech and realistic lip sync with open-source models on Kaggle's free GPU, fully automated from this session (vs-gpu submits, waits and downloads — no browser). Models are Z-Image-Turbo (SDXL as light fallback), Wan2.2-TI2V-5B (Wan2.1-1.3B light), Chatterbox Multilingual and MuseTalk 1.5, all tuned for Kaggle's free 2× T4 and licensed for commercial use. Use when a shot needs a generated picture or real motion, for "generate an image/video", "AI video", "صورة بالذكاء الاصطناعي", "فيديو بالذكاء الاصطناعي", or when video-producer routes a shot to ai-image / ai-video.
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
| `image.py` | `zimage`: Z-Image-Turbo 6B (Apache-2.0) · `sdxl`: SDXL base 1.0 (OpenRAIL++) + fp16-fix VAE (MIT) | `{"model","items":[{"id","prompt","width","height","seed"}],"steps"}` | Z-Image split over both T4s; on OOM/broken output → **SDXL automatically** (fp16, one copy per T4, parallel) |
| `video.py` | `wan22-5b`: Wan2.2-TI2V-5B (Apache-2.0, text+image-to-video) · `wan21-1.3b`: Wan2.1-T2V-1.3B (Apache-2.0, light, text-only) | `{"model","preset":"t4"\|"t4-fast"\|"hq","items":[{"id","prompt","image"?,"frames","seed"}]}` | preset `t4` = 832×480, 81 frames (3.4 s), 20 steps, fp16 + bf16 redo of broken clips; `vs-produce` upscales to the delivery size. `hq` (720p, 121 f) is for bigger GPUs only |
| `tts_chatterbox.py` | Chatterbox Multilingual 0.5B (MIT) | `{"lang","voice"?,"lines":[{"id","text","exaggeration","cfg"}]}` | one copy per T4, lines split across both |
| `lipsync_musetalk.py` | MuseTalk 1.5 (MIT; pinned 2536eaf, weights from official HF) | `{"items":[{"id","video","audio"}],"fp16":true}` | fp16, one T4 |
| `probe.py` | — | — | GPU, VRAM, TFLOPS, HF download speed |

In `production.json → gpu`: `image_model` (zimage|sdxl), `video_model` (wan22-5b|wan21-1.3b),
`video_preset` (t4|t4-fast|hq), `accelerator` (default NvidiaTeslaT4 — never depend on L4).

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
Character consistency: generate the **keyframe** with the character-bible prompt, then animate it
(image-to-video) — never text-to-video for recurring characters.

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
