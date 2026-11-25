---
name: video-qc
description: Automated visual and audio quality control for any finished video — format/preset, black and frozen frames, loudness (−14 LUFS, true peak), clipping, dead air, narration intelligibility (Whisper word error rate vs the script, Arabic tashkeel-aware), on-screen text OCR (Arabic + English), character consistency (DINOv2) — with a PASS/FAIL report that gates delivery. Use before delivering any video, for "check the video", "QC", "فحص الجودة", or when something looks or sounds off.
---

# Video QC

```bash
source ~/.video-studio/env.sh
vs-qc OUT.mp4 --preset reel|youtube|square|feed --lang ar [--script script.txt | --production production.json]
vs-verify OUT.mp4            # streams, motion, loudness + 12-tile contact sheet (OUT.sheet.jpg)
```
Writes `qc-report.md` / `qc-report.json`; exit 1 on any FAIL. `vs-produce` runs both automatically.

| Check | Gate | Fix when it fails |
|---|---|---|
| format | FAIL | wrong preset size/fps/codec → re-run `vs-produce` edit stage |
| black | FAIL | missing shot source / bad transition offset → check `build/plan.json` |
| freeze | WARN | expected on holds (Manim pauses); otherwise add a camera move |
| loudness | FAIL | re-run edit (two-pass loudnorm); check music volume |
| clipping / silence | WARN | lower music, close gaps (shorter `pad`) |
| speech (WER ≤15 % ar / ≤10 % en) | FAIL | mispronunciation: fix tashkeel, spell names as spoken, slower `length_scale`; re-voice that shot |
| text (OCR ≥0.6) | WARN | text too small/short-lived, low contrast, or Arabic shaping broken → look at the frame |
| character (≥0.55) | WARN | regenerate that keyframe with the character-bible prompt + reference |

**Numbers are not enough:** open the contact sheet and 2–3 full frames yourself — Arabic letters joined
and in order, nothing cut off or under platform UI, faces not distorted, no AI artefacts (extra fingers,
melted text). You cannot hear audio: say so and ask the person to listen once.
