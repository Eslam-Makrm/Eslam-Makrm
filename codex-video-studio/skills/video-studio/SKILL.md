---
name: video-studio
description: Start here for any video request — the router and house rules of this free, local AI video studio. Picks the right skill and engine for educational videos and lessons, animated stories, motion graphics, Arabic voiceovers, social media videos (Reels, TikTok, Shorts), video editing and automatic subtitles; holds platform presets, the delivery checklist and the free-only policy. Use for "make a video", "اعمل فيديو", "$video-studio", or when unsure which video skill applies.
---

# Codex Video Studio

A free, local, open-source production system. Everything below runs on this computer: no
accounts, no API keys, no paid credits. Set up once with `install.sh` from the studio repo;
every session starts with:

```bash
source ~/.video-studio/env.sh      # VS_HOME, CODEX_HOME, $VS_PY, $VS_MANIM, $HF_CLI, model paths
```

## Route the request

| The person wants | Engine | Skill(s) to read |
|---|---|---|
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
  OpenRouter images/clips, Gemini TTS, Blotato, paid music) unless the person asks for one.
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
(`vs-verify`, `vs-hf-check`). Skills: `$CODEX_HOME/skills`. Work in a project folder per video.
