# Codex Video Studio

A free, local, open-source AI video production system operated from **OpenAI Codex**.
استوديو فيديو مجاني ومحلي يعمل داخل Codex: دروس تعليمية، قصص متحركة، موشن جرافيك، تعليق صوتي عربي،
فيديوهات للسوشيال ميديا، مونتاج، وترجمة تلقائية.

No accounts, no API keys, no paid credits. Every render, voice and transcript runs on your computer.

## What it makes

| Need | Engine (licence) | Skill |
|---|---|---|
| Educational videos | Manim (MIT) · explainroo + Kokoro (MIT / Apache-2.0) | `manimce-best-practices`, `manim-composer`, `explainroo` |
| Animated stories | p5.js + p5.brush kit (LGPL / MIT) | `animated-stories` |
| Motion graphics | HyperFrames (Apache-2.0) + GSAP | `hyperframes`, `hyperframes-registry`, `hyperframes-cli`, `arabic-motion-graphics` |
| Arabic voiceovers | Piper (GPL-3.0, offline) · edge-tts (free, online) | `arabic-voiceover` |
| Social media videos | HyperFrames 9:16 · reframe | `arabic-motion-graphics`, `video-editing`, `video-studio` presets |
| Video editing | ffmpeg · auto-editor (Unlicense) | `video-editing` |
| Automatic subtitles | faster-whisper (MIT) · libass | `auto-subtitles` |
| Routing, presets, QC | — | `video-studio` (start here) |

15 skills in total: 9 upstream (pinned, installed with Codex's `$skill-installer`, then adapted)
and 6 written or adapted for this studio. See [docs/REVIEW.md](docs/REVIEW.md) for how the
tools were chosen and the security and licence review.

## Install

```bash
git clone <this repo> && cd <repo>/codex-video-studio
./install.sh --system      # first time: also apt/brew packages (ffmpeg, LaTeX, fonts, cairo/pango)
./install.sh               # later runs / no sudo
tests/run-all.sh           # renders one real MP4 per skill into ./samples-out and verifies each
```

Needs: Node 20+, Python 3.10+, ffmpeg with libass, git, Chrome or Chromium; LaTeX for Manim
formulas. About 4 GB on disk with models. Installs into `~/.codex/skills` and `~/.video-studio`.
Run `codex` once before installing so its built-in `$skill-installer` is unpacked (otherwise the
installer falls back to a pinned `git` sparse checkout).

## Use it in Codex

```
$video-studio  اعمل ريلز عربي ٢٠ ثانية عن تطبيقي مع تعليق صوتي وترجمة
$video-studio  a 30-second Manim lesson on the Pythagorean theorem, Arabic narration
$animated-stories  a 15-second bedtime story about a lost cloud, no text
$auto-subtitles  add Arabic captions to talk.mp4 for TikTok
$video-editing  remove the silences from lecture.mp4, then make a 9:16 version
```

Every session's tools come from `source ~/.video-studio/env.sh` (the skills say so).

## Samples (rendered by the tests on a 4-core CPU, no GPU)

| File | Skill | What it shows |
|---|---|---|
| `samples/01-motion-graphics-promo.mp4` | hyperframes | 12 s 16:9 promo, 3 scenes |
| `samples/02-arabic-social-reel.mp4` | arabic-motion-graphics + arabic-voiceover | 20.5 s 9:16 RTL reel, Piper Arabic voice, −14 LUFS |
| `samples/03-arabic-reel-subtitled.mp4` | auto-subtitles | Whisper → burned Arabic reel captions |
| `samples/04-educational-lesson-ar.mp4` | manim + arabic-voiceover | 22.5 s Pythagoras lesson, LaTeX + Arabic text |
| `samples/05-explainer-en.mp4` | explainroo | 30 s narrated explainer (Kokoro), SRT/VTT |
| `samples/06-edited-9x16.mp4` | video-editing | silence cut, trim, crossfade join, 9:16 reframe |
| `samples/07-animated-story.mp4` | animated-stories | 8 s painted story, original character |

## Layout

```
install.sh            installer (idempotent; pinned versions at the top)
patch-upstream.py     adapts the upstream skills for Codex (free-only, no telemetry)
skills/               the 6 studio skills (copied to ~/.codex/skills)
bin/                  env.sh, vs-verify (MP4 checks + contact sheet), vs-hf-check
examples/             source of every sample (HyperFrames, Manim, explainroo, p5)
tests/run-all.sh      regenerates and verifies every sample
docs/REVIEW.md        tool selection, security and licence review
samples/              rendered sample MP4s + contact sheets
```

## Licences and limits

- Your videos are yours. Tools keep their own licences (see `docs/REVIEW.md`).
- Piper's Arabic voice `ar_JO-kareem` has no stated dataset licence and the English `lessac`
  voice uses the Blizzard-2013 dataset licence (non-commercial terms): fine for personal and educational use; check before commercial use,
  or use edge-tts / your own recording.
- edge-tts is free but sends text to Microsoft's online speech service.
- Rendering is CPU-bound: HyperFrames ≈ 2–3× real time, Manim fast, the painted story kit
  several seconds per frame without a GPU.
