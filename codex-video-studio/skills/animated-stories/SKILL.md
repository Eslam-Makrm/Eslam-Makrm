---
name: animated-stories
description: Hand-painted 2D animated stories and cartoon shorts written as code (p5.js + p5.brush watercolour, ink and boiling lines), with original characters, storyboarded shot by shot and rendered locally to MP4. Use for "animated story", "قصة متحركة", "cartoon", "kids story", "short animated film", fables, bedtime stories, character shorts — optionally narrated with arabic-voiceover.
---

# Animated stories (painted 2D, p5.brush)

Adapted for Codex from `JohnHeibel/ClaudeAnimationBase` (MIT, `LICENSE.upstream-JohnHeibel`).
The kit is in `kit/`; `kit/ANIMATION_GUIDE.md` holds the rules, workflow and full API — **read
all of it before drawing**. Where it says "Claude" or "the model", that is you.

**Characters:** the kit ships *Clawd* (`kit/src/clawd.js`), the mascot of another company's
product. Use it only as a rig/acting reference. Every story for the person gets **original
characters** — design them in your scene file from the kit's primitives (`paint`, `ellPts`,
`inkLine`, `ribbon`, `glow`, eyes/mouth patterns), like `examples/seed.js` (a tested 8 s short).
Never draw trademarked or copyrighted characters.

## Start a story
```bash
source ~/.video-studio/env.sh
cp -r "$CODEX_HOME/skills/animated-stories/kit" my-story && cd my-story
npm ci --ignore-scripts            # p5, p5.brush, puppeteer-core (no install scripts needed)
# write src/scenes/story.js; set duration/bpm in src/config.js
```
Chrome: the renderer finds Google Chrome/Chromium; otherwise pass `--chrome=<path>` or set
`CHROME_PATH`. Without a GPU add `--soft-gl` (works; seconds per frame — keep watercolour
`fill`/`bleed` modest and prefer `wash`).

## Work loop (from the guide, condensed)
1. **Logline and storyboard in words** (guide: "Plan"): who wants what, the event of every shot,
   the colour arc, transitions. Show it to the person unless told not to stop.
2. Build shot by shot. Each shot fn paints the whole frame and is a pure function of time.
3. Check cheaply before rendering: `node render.mjs --sheet=0.5,1.5,... --soft-gl --out=out/check/a.jpg`
   and `--strip=2.0:2.5` for motion. Look at them; fix readability (character size, contrast).
4. Render in parallel and encode:
   `node render.mjs --frames --workers=4 --soft-gl && node render.mjs --encode --out=out/story.mp4`
   (`--audio=assets/voice.mp3` muxes narration or music; `--fps=24` default).
5. `vs-verify out/story.mp4`, look at the sheet, deliver.

## Narration, subtitles, languages
- Narrated story: write the lines first with `arabic-voiceover` (Piper/edge-tts, Arabic or
  English), set `PROJECT.duration` from the voice, time events to line starts, then mix with
  `mix_voiceover.py` or `--audio`.
- The guide's "no text" rule stands: tell the story in pictures; add captions afterwards with
  `auto-subtitles` if the platform needs them.
- Longer films: render chapters as separate projects and `join` them with `video-editing`.
