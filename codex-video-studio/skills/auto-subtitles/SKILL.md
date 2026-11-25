---
name: auto-subtitles
description: Automatic subtitles and captions, fully local — transcribe any video or audio with Whisper (faster-whisper, Arabic and 90+ languages), write SRT for upload and styled ASS, and burn captions into the MP4 (clean, boxed, word-highlight or big reel captions; right-to-left Arabic handled correctly). Use for "subtitles", "captions", "ترجمة/ترجمة نصية", "add captions to my reel", "transcribe this video", "SRT".
---

# Automatic subtitles (local Whisper)

Everything runs on this machine; no audio leaves it and no key is needed.
Run with the studio Python (it has faster-whisper):

```bash
source ~/.video-studio/env.sh
SUB="$CODEX_HOME/skills/auto-subtitles/scripts/subtitle.py"
$VS_PY "$SUB" input.mp4 --lang ar --style reel --burn out/input-subtitled.mp4
```

Outputs next to the input (or in `--out-dir`): `NAME.words.json` (word timings), `NAME.srt`
(for YouTube/TikTok/Instagram upload), `NAME.ass` (styled), and the burned MP4 with `--burn`.

## Choose

| Need | Flags |
|---|---|
| Lesson, interview, 16:9 | `--style clean` (default) |
| Busy or bright footage | `--style box` |
| English reel, word highlighted as spoken | `--style word` or `--style reel` |
| Arabic reel | `--style reel --lang ar` (1–3 word chunks that pop in on the voice) |
| Only an SRT, no burn-in | omit `--burn` |
| You already have an SRT (e.g. `make_srt.py`) | `--srt file.srt --burn out.mp4` (exact script text, no Whisper) |
| Fast draft | `--model small`; best quality: default `large-v3-turbo` |

`--lang` defaults to auto-detect; set `ar`/`en` when you know it (faster, fewer mistakes).

## Work loop

1. `--transcribe-only` first on anything important; read the transcript.
2. Fix names and terms: `--vocab "Codex, HyperFrames"` biases spelling; `--replace heard=Shown`
   (repeatable) fixes what is still wrong, also inside a word (Arabic prefixes survive).
   To restyle without re-transcribing, pass `--words NAME.words.json` (you may edit that file).
3. Burn, then **look at frames** (`ffmpeg -ss T -i out.mp4 -frames:v 1 f.png`, or `vs-verify`):
   letters joined, no empty boxes, right-to-left order, nothing under platform buttons.
4. Deliver the MP4 and the SRT.

## Hard-won rules (tested)

- **Arabic fonts in libass** (ffmpeg's caption renderer): Noto Naskh Arabic, Amiri and DejaVu
  Sans render correctly. Noto Sans Arabic, Cairo and Kacst draw لا and أ/إ/آ as empty boxes.
  The script defaults to Noto Naskh Arabic and warns for anything else. (In HyperFrames/HTML,
  Chrome shapes Cairo fine; this applies only to burned-in ASS captions.)
- **No inline colour tags in RTL lines**: libass reorders the words wrongly when a tag sits
  mid-line. That is why Arabic word/reel styles show short chunks instead of a moving highlight.
- Whisper smears word timings across pauses; the script snaps line breaks to real pauses
  (ffmpeg `silencedetect`), so captions appear when the voice starts.
- Diacritics (tashkeel) are stripped for reading unless `--keep-tashkeel` (useful for lessons).
- 9:16 captions sit at 20% from the bottom, above the platform caption/UI band.
- For captions designed into a HyperFrames film (animated, branded), use HyperFrames'
  caption blocks instead (`/hyperframes` → `references/captions.md`), with this tool's
  `NAME.words.json` as the timing source.
