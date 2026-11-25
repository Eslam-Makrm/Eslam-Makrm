---
name: lip-sync
description: Lip synchronization — 2D cartoon mouths from any voice (Rhubarb Lip Sync, CPU, works for Arabic) for animated-stories and HyperFrames characters, and realistic re-mouthing of a face video or portrait to new speech (MuseTalk 1.5 on Kaggle's free GPU). Use for "lip sync", "مزامنة الشفاه", "make the character talk", "talking head", "dub this face".
---

# Lip sync

## 2D characters (CPU, instant)

```bash
source ~/.video-studio/env.sh
vs-lipsync2d voice.wav mouth.json [--text line.txt]     # 34 cues for 4.8 s of Arabic in 1.4 s
```
Cues use 9 shapes: **A** closed (م ب ف-like closures) · **B** slightly open (most consonants) · **C** open ·
**D** wide (ا) · **E** rounded (و) · **F** puckered · **G** teeth on lip (ف) · **H** tongue (ل) · **X** rest.
Draw the 9 mouths in the character rig and show the cue active at time t:

```js
// animated-stories (p5): mouth shape at time t (seconds)
const cues = MOUTH.mouthCues;                 // paste or fetch mouth.json
function mouthAt(t){ let lo=0,hi=cues.length-1; while(lo<hi){const m=(lo+hi+1)>>1; if(cues[m].start<=t) lo=m; else hi=m-1;} return cues[lo].value; }
```
HyperFrames: one `tl.set("#mouth", {attr:{href:"#mouth-"+c.value}}, c.start)` per cue. Offset the cues by
the shot's narration start (`vo_lead`, 0.25 s in vs-produce).

## Real or AI-generated faces (GPU, Kaggle)

```bash
vs-gpu run $VS_REPO/gpu-jobs/lipsync_musetalk.py out/ --params '{"items":[{"id":"p1","video":"face.mp4","audio":"vo1.wav"}]}' \
  --input face.mp4 --input vo1.wav
```
MuseTalk 1.5 (MIT) re-renders the mouth region at 30 fps; audio-driven, so it works with Arabic. Best on
front-facing, well-lit faces, 256–512 px face size. Then use the result as a `clip` shot.
**Consent:** only the person's own face, AI-generated people, or people who agreed in writing; never
public figures; label synthetic presenters where platforms require it.
