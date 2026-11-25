---
name: ai-generation
description: Generate AI images, AI video (text-to-video and image-to-video), expressive Arabic/English speech and realistic lip sync with open-source models on Kaggle's free GPU, fully automated from this session (vs-gpu submits, waits and downloads — no browser). Models are Z-Image-Turbo, Wan2.2-TI2V-5B, Chatterbox Multilingual and MuseTalk 1.5 — all licensed for commercial use. Use when a shot needs a generated picture or real motion, for "generate an image/video", "AI video", "صورة بالذكاء الاصطناعي", "فيديو بالذكاء الاصطناعي", or when video-producer routes a shot to ai-image / ai-video.
---

# AI generation on the free cloud GPU (Kaggle)

```bash
source ~/.video-studio/env.sh
vs-gpu quota                                            # GPU hours left this week (30 h/week, resets Saturday 00:00 UTC)
vs-gpu run $VS_REPO/gpu-jobs/<job>.py OUT_DIR --params @params.json [--input file]... [--accelerator NvidiaL4]
```

`vs-gpu run` packs the job + params + inputs into one private Kaggle script, runs it on a T4 (default,
16 GB, fp16) or L4 (24 GB, bf16, faster), waits, downloads `OUT_DIR/*` plus `report.json` (timings) and
`kaggle.log`. The Kaggle token is a network secret injected by the proxy; `KAGGLE_USERNAME` is set in the
environment. Inside `video-producer`, `vs-produce` calls these jobs for you, batched.

## Jobs (`$VS_REPO/gpu-jobs/`)

| Job | Model (licence) | Params | Notes |
|---|---|---|---|
| `image_zimage.py` | Z-Image-Turbo 6B (Apache-2.0) | `{"items":[{"id","prompt","width","height","seed"}],"steps":8}` | ~1280×720 keyframes; strong at photoreal + Arabic-free text; batch many per job |
| `video_wan22.py` | Wan2.2-TI2V-5B (Apache-2.0) | `{"items":[{"id","prompt","image"?, "frames":121,"width":1280,"height":704,"seed"}],"steps":30,"fps":24}` | 5 s 720p clips; `image` = keyframe in inputs → image-to-video (best consistency); frames 4k+1 |
| `tts_chatterbox.py` | Chatterbox Multilingual (MIT) | `{"lang":"ar","voice"?: "ref.wav","lines":[{"id","text","exaggeration","cfg"}]}` | emotion: exaggeration 0.25 calm → 1.0 dramatic; lower cfg to 0.3 when > 0.65 |
| `lipsync_musetalk.py` | MuseTalk 1.5 (MIT) | `{"items":[{"id","video","audio"}]}` | re-mouths a face video/still to the voice; consented or AI-generated faces only |
| `probe.py` | — | — | reports GPU, VRAM, bf16, TFLOPS, HF download speed |

## Prompts that work (Wan / Z-Image)

Subject + action + setting + light + lens + camera move, concrete and visual:
"a young Egyptian chef plates koshari in a sunlit kitchen, steam rising, 50mm, shallow depth of field,
slow dolly-in". Camera words Wan follows: *static shot, slow dolly-in, pull back, pan left, tracking shot,
orbit around, crane up, handheld*. Avoid text in generated images (render titles with HyperFrames).
Character consistency: generate the **keyframe** with the character-bible prompt, then animate it
(image-to-video) — never text-to-video for recurring characters.

## Budget and timing (free tier)

30 GPU-hours/week. Measured/estimated per item on T4: image ≈ 10–20 s, 5-s 720p clip several minutes,
TTS line ≈ 5–10 s, plus ~3–6 min per job for start-up and model download — so **batch**: one job for all
images, one for all clips. `vs-gpu quota` before big runs; L4 for video when available.

## When the GPU is unavailable

Kaggle needs a **phone-verified** account for GPU + internet. `vs-gpu` reports "Kaggle gave this session no
GPU" and `vs-produce` falls back automatically (keyframe + parallax camera move, Piper voice) and records it
in `build/route.json`. Tell the person what fell back and why.

## Never

OpenAI / ChatGPT / Codex / Sora / image_gen, paid APIs, Colab automation (its free tier forbids it), real
people's likeness without consent, non-commercial models (FLUX.1-dev/Kontext-dev, FLUX.2-klein-9B,
Qwen-Image 2.x, XTTS, Wav2Lip, InsightFace-based ID tools, Habibi Unified/SAU/UAE).
