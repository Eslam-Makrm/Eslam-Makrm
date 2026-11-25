# Video Studio — operating notes for Claude

This repo is a free, open-source AI video production studio that Claude operates end to end.
Skills live in `.claude/skills/` (loaded automatically); tools and code in `video-studio/`.

- Any video request → follow the `video-producer` skill (one prompt → finished, QC-checked MP4).
  Unsure which engine → `video-studio` (router and house rules).
- Every shell: `source ~/.video-studio/env.sh`. If it is missing (fresh machine), run
  `video-studio/install.sh --system --gpu-client` (≈10 min), then `vs-doctor --gpu`.
- Work in `videos/<slug>/` with a `production.json`; build output is git-ignored. Commit only what the
  person wants to keep (final MP4s go to `video-studio/samples/` only for studio samples).
- AI images / video / expressive voices / realistic lip sync: open models on the person's free Kaggle GPU
  via `vs-gpu` (token = network secret for api.kaggle.com, `KAGGLE_USERNAME` env var). Check
  `vs-gpu quota` before big jobs. If Kaggle grants no GPU, `vs-produce` falls back to CPU routes and says so.
- Kaggle queued with no GPU → retry later, or the manual Colab backup: `vs-produce DIR --gpu colab` writes
  notebooks the person runs themselves, then `vs-colab import`.
- Never use OpenAI / ChatGPT / Codex / Sora / image_gen, HeyGen, ElevenLabs or any paid API; never automate
  Colab. Only commercially licensed models (see the `ai-generation` skill).
- Always look at the contact sheet before delivering; you cannot hear audio — say so.
- Regression suite: `video-studio/tests/run-all.sh [OUT] --skip-story`.
