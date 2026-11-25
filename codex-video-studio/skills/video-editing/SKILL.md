---
name: video-editing
description: Edit existing footage locally with ffmpeg and auto-editor — remove silences and dead air, trim, join clips from any tool with crossfades, reframe 16:9 into 9:16/1:1/4:5 for social, normalize loudness to -14 LUFS, change speed, add a logo or a ducked music bed, export thumbnails. Use for "cut", "trim", "join/merge clips", "remove silences", "make it vertical", "مونتاج", "قص الفيديو", or any finishing step after rendering.
---

# Video editing (ffmpeg + auto-editor)

```bash
source ~/.video-studio/env.sh
E="$VS_PY $CODEX_HOME/skills/video-editing/scripts/edit.py"
$E probe in.mp4                                   # duration, size, fps, audio?
$E silence talk.mp4 out/tight.mp4 --margin 0.15   # remove dead air (auto-editor)
$E trim in.mp4 out/cut.mp4 --start 2.5 --end 14
$E join out/film.mp4 intro.mp4 tight.mp4 outro.mp4 --xfade 0.5   # any sources, normalized
$E reframe out/film.mp4 out/film-9x16.mp4 --to 9:16 --mode blur  # or crop / pad
$E loudness out/film-9x16.mp4 out/final.mp4 --lufs -14
$E music out/final.mp4 out/final-music.mp4 --track bed.mp3 --volume 0.25 --duck
$E overlay in.mp4 out/logo.mp4 --image logo.png --pos tr --scale 0.12
$E speed in.mp4 out/fast.mp4 --factor 1.25
$E thumb out/final.mp4 out/thumb.jpg --at 1.0
vs-verify out/final.mp4                           # streams, duration, motion, loudness, contact sheet
```

Every output is H.264/AAC yuv420p with `+faststart`.

## How to work

1. `probe` every input first; say what you found (lengths, sizes, which clips have no sound).
2. Plan the cut as a short list (clip, in, out, transition) and show it unless told not to stop.
3. Cut, join, reframe, then loudness **last** (after music) so the final level is -14 LUFS.
4. `vs-verify` the result and look at the contact sheet before delivering.

## Choosing

- **Talking head / lesson recording**: `silence` first (margin 0.15–0.25 s keeps breaths natural;
  raise `--threshold` for noisy rooms), then `auto-subtitles`.
- **Clips from different tools** (HyperFrames, Manim, explainroo, phone): `join` handles size,
  fps, sample rate and missing audio. Crossfade 0.4–0.6 s; `--transition` accepts any ffmpeg
  `xfade` name (fade, wipeleft, slideup, circleopen, dissolve...).
- **16:9 → vertical**: `--mode blur` keeps the whole picture (diagrams, text); `crop` fills the
  frame (people, action); `pad` for archival letterbox.
- **Cutting by words** in your own recording: explainroo's `cut` (`/explainroo`, `docs cut`),
  or transcribe with `auto-subtitles` and trim on the word times in `NAME.words.json`.
- **Timeline edits, overlays, titles over footage, colour looks**: HyperFrames (`/hyperframes`,
  footage as `<video>` clips; grades through `npx hyperframes media-treatment`).

Music: only tracks the person supplies or that are clearly licensed for their use (CC0 / their
own). Never download music from the web without a licence the person accepts.
