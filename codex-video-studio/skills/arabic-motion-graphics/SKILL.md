---
name: arabic-motion-graphics
description: Arabic-first motion graphics with correct right-to-left text — reels, explainers, promos, logo reveals, kinetic typography, end cards and animated social posts — built in HyperFrames (HTML + GSAP) and rendered locally to MP4. Use whenever a video's on-screen text is Arabic, for "موشن جرافيك", "فيديو إعلاني", "ريلز عربي", or any Arabic title/caption animation.
---

# Arabic motion graphics (RTL, HyperFrames)

Adapted for Codex from `sudadom/arabic-motion-graphics-skill` (MIT, see
`LICENSE.upstream-sudadom`): same style, pacing and RTL rules, but built on HyperFrames (one
local, Apache-2.0 renderer for the whole studio) instead of Remotion. Layout rules for Arabic
copy come from `TurkiHassan/arabic-launch-video` (MIT).

Read first: `/hyperframes` (the render contract) and `references/rtl-arabic.md` (always).

| File | Read when |
|---|---|
| `references/rtl-arabic.md` | before writing any Arabic text animation |
| `references/arabic-layout-rules.md` | laying out Arabic headlines, numbers, mixed Latin |
| `references/styles.md` | choosing one of three visual styles |
| `references/structures.md` | writing the beat sheet |
| `references/pacing.md` | durations and holds |
| `references/transitions.md` | scene transitions |
| `templates/rtl-reel-9x16/` | starting a vertical reel (tested: hook → idea → features → end card) |

## 1. Brief (ask only what is missing, max 3 questions)
Goal (promo / explainer / hook reel / occasion / logo reveal) · format (9:16 default, 4:5, 1:1,
16:9) · length · copy (hook, problem, features, CTA, handle) · brand colours/font · MSA or one
dialect · audio (none / their track / voiceover). With no one to ask: choose, state, continue.

## 2. Voice first when there is narration
Write and generate the voiceover with `arabic-voiceover` **before** animating; its line
durations set every scene's start and length.

## 3. Build
```bash
source ~/.video-studio/env.sh
cp -r "$CODEX_HOME/skills/arabic-motion-graphics/templates/rtl-reel-9x16" my-reel
cp "$VS_HOME/vendor/gsap.min.js" my-reel/assets/ && cp "$VS_HOME/vendor/Cairo.ttf" my-reel/assets/fonts/
cd my-reel   # edit index.html (scene hosts, audio) and compositions/*.html
```
For a new 16:9 or a non-template project: `$HF_CLI init NAME --skip-skills --skill=hyperframes`,
then copy `gsap.min.js` and a font in as above and point the `<script>` at `assets/gsap.min.js`
(works offline and behind strict networks).

Rules that the template already follows:
- `dir="rtl" lang="ar"` on every text container; Latin/handles in `<bdi dir="ltr">`.
- Words rise/fade in place, in reading order; panels and pills enter from the right, exit left.
- Never split Arabic into letters; typewriter = a right-to-left `clip-path` mask on the whole line.
- No `letter-spacing` on Arabic; line-height 1.3–1.5; one digit system per video (١٢٣ or 123).
- 9:16 safe area: text inside x 100–910, y 250–1570 (right 170 px stays clear of TikTok/Shorts
  buttons). `$HF_CLI check` reports `outside_safe_zone` per platform — fix those.
- Voice lines are `<audio id="voN" class="clip">` on their own track; `data-duration` = file length.

## 4. Check, look, render
```bash
vs-hf-check .                          # errors + warnings only
$HF_CLI snapshot --review              # optional frame review (see /hyperframes references/review.md)
$HF_CLI render -o out/reel.mp4
vs-verify out/reel.mp4                 # look at the contact sheet: shaping, order, safe zones
```
Then, if wanted, burned captions with `auto-subtitles` (`--style reel --lang ar`) and a final
loudness pass with `video-editing`. Deliver the MP4, a poster frame and the project folder.

Never copy another creator's characters, illustrations, logos or footage; analyse a reference
for structure and pacing, then build an original piece.
