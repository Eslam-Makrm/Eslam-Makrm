---
name: arabic-voiceover
description: Make Arabic (فصحى) or English narration with free voices and lay it on a video — write or polish the script, fully diacritize it, generate it offline with Piper (or free online edge-tts, or the person's own recording), pace it, duck the original sound and music under it, normalize to -14 LUFS, and export SRT. Use for "تعليق صوتي عربي", "أضف صوت على الفيديو", "Arabic voiceover", "narrate this video", or any video in this studio that needs a voice.
---

# Arabic voiceover (free engines)

Adapted from `TurkiHassan/arabic-launch-video` (MIT, see `LICENSE.upstream-TurkiHassan`):
the paid Gemini/ElevenLabs paths were removed and a fully offline Piper engine was added.

`S` = this skill's `scripts/` folder (`$VS_SKILLS/arabic-voiceover/scripts`).
Tools come from the studio install: `source ~/.video-studio/env.sh` first (it sets `VS_HOME`,
the venv and the model paths). Read `references/arabic-voice.md` before writing any line; every
rule there applies.

## 1. Ask only what is missing (in plain Arabic if the person writes Arabic)

1. **The video** (or "audio only"). Probe it: `ffprobe` duration and whether it has sound; pull
   a few frames (`ffmpeg -ss T -frames:v 1 f.png`) and look at them so the script matches the
   picture and its timing.
2. **The words**: their script, bullet points, or you write it from the video.
3. **Engine**: Piper (default, offline) · edge-tts (free, online, warmer) · their own recording.
4. **Original sound**: duck under the voice (default) · keep · mute. **Music**: their track or none.
5. **Subtitles**: yes (default for social) / no.

If the person said not to ask, pick the defaults, state them at the top of your reply and go on.

## 2. Script → timing plan

- One line per shot or idea, with the second it should start (from the frames you looked at).
- Budget ≈ 2.5 words/second. Lines must end before the video does; cut words, never rush.
- Full tashkeel, numbers as words, brand names spelled as spoken (`arabic-voice.md` §1).
- Show the diacritized lines with their start times; get an OK unless told not to stop.
- Save them as `voiceover/voice-lines.json` (a JSON array of strings).

## 3. Generate, clean, pace

```bash
source ~/.video-studio/env.sh
python3 "$S/piper_tts_lines.py" voiceover/voice-lines.json voiceover/raw            # offline (default)
#  warmer, online:  python3 "$S/edge_tts_lines.py" voiceover/voice-lines.json voiceover/raw --voice ar-SA-HamedNeural
#  own voice:       put their vo1.m4a … voN.m4a in voiceover/raw (convert to wav/mp3 first)
bash "$S/prep_voice.sh" voiceover/raw voiceover 1.0
python3 "$S/tighten_pauses.py" voiceover/assets/voice
```

Check intelligibility without ears: transcribe the lines back
(`python3 "$VS_SKILLS/auto-subtitles/scripts/subtitle.py" voiceover/assets/voice/vo1.mp3 --transcribe-only --lang ar`)
and compare with the script. Then say plainly that you cannot hear audio and ask the person to
listen to the lines and confirm pronunciation.

## 4. Mix onto the video

```bash
python3 "$S/mix_voiceover.py" --video INPUT.mp4 --voice-dir voiceover/assets/voice \
  --starts 0.5,4.2,9.0 --original duck [--music TRACK.mp3 --music-volume 0.3] \
  --out voiceover/output-ar.mp4
# audio only: omit --video and use --out voiceover/narration.m4a
```

The picture is copied untouched; the original sound and music dip under the voice; the result
is normalized to -14 LUFS. It warns if the voice runs past the end. For a HyperFrames film,
instead place each `assets/voice/voN.mp3` as an `<audio id="voN">` clip at its start time.

## 5. Subtitles and hand-off

```bash
python3 "$S/make_srt.py" voiceover/voice-lines.json voiceover/output-ar.timings.json voiceover/output-ar.srt
```

To burn them in, or for styled word-by-word captions, use the `auto-subtitles` skill with
`--srt voiceover/output-ar.srt`. Verify with `vs-verify voiceover/output-ar.mp4`, then give the
person the MP4 and SRT paths and offer to redo any single line.
