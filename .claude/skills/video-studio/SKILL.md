---
name: video-studio
description: Start here for any video request — the router and house rules of this free, open-source AI video studio operated by Claude. Picks the right skill and engine for educational videos and lessons, animated stories, motion graphics, Arabic voiceovers, social media videos (Reels, TikTok, Shorts), video editing and automatic subtitles; holds platform presets, the delivery checklist and the free-only policy. Use for "make a video", "اعمل فيديو", "$video-studio", or when unsure which video skill applies.
---

# Video Studio

A free, open-source production system operated by Claude. Everything runs on this machine's CPU,
except AI images/video/expressive voices/realistic lip sync, which run on open models on the person's
free Kaggle GPU (automated by `vs-gpu`). No paid credits, no OpenAI/ChatGPT/Codex services.
**A complete video from one prompt → `video-producer`.** Set up once with `video-studio/install.sh
--system --gpu-client`; every session starts with:

```bash
source ~/.video-studio/env.sh      # VS_HOME, VS_SKILLS, $VS_PY, $VS_MANIM, $HF_CLI, model paths
```

## Route the request

| The person wants | Engine | Skill(s) to read |
|---|---|---|
| **A whole video from a topic or brief** (ad, lesson, story, realistic short, reel) | all of the below | **`video-producer`** |
| AI image, AI video (text/image-to-video), expressive Arabic/English TTS | open models on Kaggle GPU | `ai-generation` |
| Same character across scenes | reference sheet + image-to-video + DINOv2 check | `character-bible` |
| Camera moves, parallax, transitions, colour grade | vs-camera (CPU) | `cinematic-camera` |
| Talking character / dubbing a face | Rhubarb (2D, CPU) · MuseTalk (GPU) | `lip-sync` |
| Automated quality check | vs-qc | `video-qc` |
| Math, science, step-by-step proofs, graphs | Manim | `manimce-best-practices`, `manim-composer` |
| Explainer / tutorial with diagrams and an English (or es/fr/it/pt/hi/ja/zh) voice | explainroo | `explainroo` |
| Arabic lesson or explainer | Manim or HyperFrames + Piper | `arabic-voiceover` → `manimce-best-practices` or `arabic-motion-graphics` |
| Animated story, fable, kids' cartoon | p5.brush kit | `animated-stories` (+ `arabic-voiceover`) |
| Motion graphics, promo, logo reveal, kinetic type, data viz | HyperFrames | `hyperframes`, `hyperframes-registry`, `hyperframes-cli` |
| Any of the above with Arabic on screen | HyperFrames | `arabic-motion-graphics` (RTL rules) |
| Reels / TikTok / Shorts | HyperFrames 9:16 (or reframe) | `hyperframes` (types/vertical), `arabic-motion-graphics`, `video-editing` |
| Narration on a video, Arabic or English | Piper (offline) / edge-tts (online) | `arabic-voiceover` |
| Subtitles, captions, transcript, SRT | faster-whisper + libass | `auto-subtitles` |
| Cut, trim, join, silence removal, reframe, music, loudness | ffmpeg + auto-editor | `video-editing` |
| Rebuild/restyle an existing video | HyperFrames | `reverse-any-video`, `style-sampling` |

One engine per film. Mix engines only by rendering parts separately and joining them with
`video-editing` (`edit.py join`).

## Free-only policy (the person's standing rule)

- Never call, configure or suggest a paid service (HeyGen cloud/Pro, ElevenLabs, Cartesia,
  OpenRouter images/clips, Gemini TTS, Blotato, paid music) or any OpenAI/ChatGPT/Codex/Sora/image_gen
  path. Cloud GPU = Kaggle's free quota only (Colab's free tier forbids automation).
  If a skill offers one, pick its free local path and say so in one line.
- `edge-tts` is free but online (text goes to Microsoft); prefer Piper unless the person wants
  the warmer voice. HyperFrames telemetry and usage beacons stay off (`env.sh`).
- Licences: Piper's Arabic voice (ar_JO-kareem) has no stated dataset licence and the English
  lessac voice uses the Blizzard-2013 dataset licence (non-commercial terms) — fine for personal/educational work; ask before commercial use.
  Fonts shipped: Cairo, Noto, Amiri (all OFL). Music: only what the person supplies or CC0.

## Platform presets

| Platform | Size | Length | Notes |
|---|---|---|---|
| Reels / TikTok / Shorts | 1080×1920, 30 fps | 15–60 s | hook in 2 s; text inside x 100–910, y 250–1570; captions on |
| Instagram feed / LinkedIn | 1080×1350 (4:5) | 15–90 s | captions on |
| Square | 1080×1080 | ≤60 s | |
| YouTube / lessons | 1920×1080, 30 fps | any | chapters + SRT |

All deliveries: H.264 + AAC, yuv420p, `+faststart`, loudness −14 LUFS (true peak ≤ −1.5 dB).

## Delivery checklist (every video)

1. Plan in words first (story / beat sheet / script); voice before animation when narrated.
2. Engine check passes (`vs-hf-check`, `explainroo check`, Manim renders clean).
3. `vs-verify OUT.mp4` → right size, length, audio present, motion, −14 LUFS; **open the contact
   sheet and look**: text shaped and in order (Arabic), nothing cut off, nothing under UI.
4. Intelligibility: transcribe the final audio (`auto-subtitles --transcribe-only`) and compare
   with the script.
5. Tell the person: file paths (MP4, SRT, cover), length, what was checked, what you could not
   check (you cannot hear audio), and one concrete next step (cut-down, vertical version, A/B hook).

## Where things are

`$VS_HOME` (~/.video-studio): `venv` (whisper, piper, edge-tts), `venv-manim`, `venv-editor`
(auto-editor), `models/` (Piper voices, Whisper), `vendor/` (gsap.min.js, Cairo.ttf), `bin/`
(`vs-verify`, `vs-hf-check`). Skills: `$VS_SKILLS` (= <repo>/.claude/skills). Work in a project folder per video
(`videos/<slug>/`). Tools: `vs-produce`, `vs-gpu`, `vs-camera`, `vs-qc`, `vs-lipsync2d`, `vs-doctor`.
