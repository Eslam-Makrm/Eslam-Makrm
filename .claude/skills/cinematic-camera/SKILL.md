---
name: cinematic-camera
description: Cinematic camera language for any shot — push-in, pull-out, pans, tilts, truck, crane, orbit, dolly-zoom, handheld — on stills (Ken Burns) or with 2.5D parallax from a depth map, plus scene transitions (fade, dissolve, wipes, slides, zoom, blur…) and colour grades (teal-orange, warm, noir, vintage…), grain, vignette and letterbox. CPU only. Use for "camera movement", "حركة كاميرا", "parallax", "Ken Burns", "transition", "color grade", "cinematic look", or when a still must feel like footage.
---

# Cinematic camera, transitions and looks

```bash
source ~/.video-studio/env.sh
vs-camera move     IMG OUT.mp4 --move push-in   --dur 5 --size 1920x1080 [--amount 0.1 --ease inout]
vs-camera parallax IMG OUT.mp4 --move orbit-left --dur 5 --size 1080x1920 [--strength 0.04]
vs-camera depth    IMG depth.png                # Depth-Anything-V2-Small (Apache-2.0), ~1 s
vs-camera grade    IN.mp4 OUT.mp4 --look teal-orange --grain 4 --vignette [--letterbox 2.39 --lut F.cube]
```
Measured: 4 s of 720p parallax renders in ~4 s on 4 CPU cores.

## Choosing the move (motivated, never random)

| Moment | Move | Amount |
|---|---|---|
| Reveal, establish, open a story | pull-out, crane-up, pan | 0.08–0.12 |
| Focus, emotion, "listen to this" | push-in / dolly-in (+parallax) | 0.06–0.10 |
| Show depth, premium product, landscape | orbit-left/right, truck (+parallax) | strength 0.03–0.05 |
| Unease, realisation | dolly-zoom (+parallax) | 0.08 |
| Documentary, live feel | handheld | 0.05 |
| Text-heavy frame | static or slow push-in 0.04 | — |

Shots of 2–6 s; ease `inout` for calm, `out` for impact openers. In AI video, write the move into the
prompt ("slow dolly-in") and add a post move only if the generated one is weak. Parallax works best with a
clear foreground subject; use plain `move` for flat graphics.

## Transitions (in production.json, per shot: `transition`, `transition_dur`)

`cut` (default between related shots, on action) · `fade`/`dissolve` 0.5–1.0 s (time passing, soft mood) ·
`fadeblack` (chapter, ending) · `smoothleft/right`, `slideleft` (energetic social) · `wipeleft`, `circleopen`
(playful, kids) · `zoomin`, `hblur` (whip-like energy) · `radial`, `pixelize` (sparingly). One family per
film; cuts on narration pauses; never a fancy transition on every shot.

## Looks (`grade.look`)

`teal-orange` ads/cinematic · `warm` stories/food · `cool` tech · `noir` drama · `bleach` gritty ·
`vintage` memories · `vivid` social · `neutral`. Add `grain` 2–4 for filmic texture, `vignette` for
focus, `letterbox: 2.39` for a cinema frame (16:9 only). Your own `.cube` LUT via `--lut`.
