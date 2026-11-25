# Video Studio

A free, open-source AI video production studio **operated by Claude**: one prompt in, a finished,
quality-checked MP4 out. Educational videos, animated stories, realistic AI shots, advertisements and
social media content, in Arabic and English.
استوديو فيديو مجاني ومفتوح المصدر يديره Claude: اكتب طلبك مرة واحدة واحصل على فيديو MP4 جاهز ومفحوص.

## How it works

```
 your prompt ──► Claude (video-producer skill): brief → script (tashkeel) → storyboard → production.json
                    │
                    ├─ code-drawn shots on CPU: HyperFrames (motion graphics, Arabic RTL), Manim (lessons),
                    │  p5.brush (painted stories)
                    ├─ AI shots on Kaggle's free 2× Tesla T4 (vs-gpu, automated, T4-first): SDXL images,
                    │  Wan2.1-1.3B text-to-video, Chatterbox voice, MuseTalk; heavy modes Z-Image / Wan2.2-5B
                    └─ vs-produce: voice → shots (camera moves, 2.5D parallax) → transitions → grade →
                       music ducking → −14 LUFS → subtitles → cover → vs-qc gate → out/*.mp4
```

| Capability | Engine | Runs on | Skill |
|---|---|---|---|
| One prompt → finished video | vs-produce + production.json | CPU + Kaggle | `video-producer` |
| AI images / text-to-video / image-to-video | SDXL, Wan2.1-1.3B (defaults); Z-Image-Turbo, Wan2.2-TI2V-5B i2v (optional heavy) | Kaggle 2× T4 | `ai-generation` |
| Consistent characters | bible + references + image-to-video + DINOv2 check | Kaggle + CPU | `character-bible` |
| Arabic/English voice with emotion | Chatterbox Multilingual (MIT) · Piper (CPU) · edge-tts (online, opt-in) | Kaggle / CPU | `arabic-voiceover`, `ai-generation` |
| Lip sync | Rhubarb (2D, CPU) · MuseTalk 1.5 (real faces, GPU) | CPU / Kaggle | `lip-sync` |
| Script + storyboard | Claude | — | `video-producer` |
| Camera moves, parallax, transitions, grades | vs-camera (Depth-Anything-V2-Small ONNX), ffmpeg xfade | CPU | `cinematic-camera` |
| Automated QC | vs-qc: format, black/freeze, loudness, WER, OCR, DINOv2 | CPU | `video-qc` |
| Motion graphics / Arabic RTL | HyperFrames + GSAP | CPU | `hyperframes`, `arabic-motion-graphics` |
| Lessons | Manim, explainroo | CPU | `manimce-best-practices`, `explainroo` |
| Painted stories | p5.js + p5.brush kit | CPU | `animated-stories` |
| Editing, subtitles | ffmpeg, auto-editor, faster-whisper | CPU | `video-editing`, `auto-subtitles` |

21 skills in `../.claude/skills` (9 vendored upstream at pinned refs, see `UPSTREAM.md`).

## Setup (once per machine; automatic in the configured Claude cloud environment)

```bash
cd video-studio
./install.sh --system --gpu-client     # tools, models (~4 GB), fonts, Kaggle client
source ~/.video-studio/env.sh && vs-doctor --smoke --gpu
```
Cloud GPU: a free Kaggle account, **phone-verified** (Kaggle only grants GPU + internet to verified
accounts), its API token saved as the environment's network secret for `api.kaggle.com`, and
`KAGGLE_USERNAME` set. Quota: 30 GPU-hours/week (verified on the account, resets Saturday 00:00 UTC).
Everything is tuned for the free **2× Tesla T4**: reliable light models by default, heavy ones opt-in
(`gpu.allow_heavy`), per-job time budgets and early abort; nothing depends on L4. Benchmark: `tests/gpu-bench.sh`. Long GPU work: `vs-produce DIR --async` submits and returns; rerun later.

## Use

Just ask Claude: *"اعمل ريلز إعلاني ٢٠ ثانية لتطبيق قارئ لتعليم الأطفال القراءة"* or *"a 90-second
lesson on photosynthesis in English"*. Outputs land in `videos/<slug>/out/` (MP4, SRT, cover, contact
sheet, QC report, route log).

## Tools (`bin/`, installed to `~/.video-studio/bin`)

`vs-produce` (`--async`, `--gpu colab`) · `vs-gpu` (`quota/run/submit/status/fetch/cancel`) · `vs-colab` (manual Colab backup: `build/import`, notebooks in `colab/`) · `vs-camera` · `vs-qc` · `vs-lipsync2d` · `vs-verify` · `vs-hf-check` · `vs-doctor`
GPU job scripts: `gpu-jobs/`. Regression suite: `tests/run-all.sh`.

## Samples (all rendered and verified in a Claude cloud session, 4 CPU cores)

| File | What it shows |
|---|---|
| `samples/01…07` | phase-1 engines: promo, Arabic reel + voice, auto-subtitles, Manim lesson, explainer, editing, painted story |
| `samples/voice/*.wav` | Chatterbox Multilingual on Kaggle T4: Arabic calm, Arabic excited, English (raw, before the −14 LUFS mix) |
| `samples/08-qari-ad-one-prompt.mp4` | **one prompt → 21.7 s Arabic ad reel**: 3 HyperFrames shots + painted still with parallax (AI-video fallback), Piper voice, transitions, subtitles; QC PASS (speech WER 7 %, −14.0 LUFS) |

## Licences and limits

All models used are licensed for commercial use (licences re-checked on their model cards, see
`docs/ARCHITECTURE.md`). Piper's `ar_JO-kareem` voice has no stated dataset licence — prefer Chatterbox
for commercial work. Free-tier limits: 30 Kaggle GPU-hours/week; a 5-s 720p AI clip costs minutes of GPU.
