# Arabic narration that sounds فصحى, not machine

Everything here was learned from rejected takes. The voice drives the timing of the whole
video, so it is written and generated **before** the storyboard.

## 1. Write the lines

- **One line per scene**, 5-6 lines for 20-30 s. Aim for 2-5 s of speech each; the hook ≤ 2.5 s.
- **Spoken, not written**: short clauses, the verb early, one idea per line. Read it aloud
  in your head at an announcer's pace (≈ 2.3-2.8 words/second after tempo).
- **Quote the product's own words** where you can (its tagline, button labels).
- **Full tashkeel on every letter that carries a vowel**, including case endings. The
  diacritics are what hold the model in فصحى; an undiacritized line drifted into an Egyptian
  read and was rejected.
- **Brand and English words spelled as spoken**: آبْ سْتُورْ, جُوجِل بْلَايْ, تِيك تُوك.
  Short Latin acronyms (PDF, AI) may stay Latin — check the read.
- **Numbers as words**, fully voweled: أَرْبَعَةٌ وَثَلَاثُونَ دَرْسًا — never digits in the voice text.
- **End of sentence = waqf**: the last word before a full stop is read with sukun anyway; write
  it with its case vowel or sukun, but do not put tanween-alif where a stop is intended.
- **The app name**: add the vowels you want heard (قُدْرَة), and keep it identical across lines.
- **No instructions inside the text.** "بصوت حماسي: …" gets read aloud. Tone is chosen by voice,
  not by prompt.

Save the lines as a JSON array: `voice-lines.json`. Show them to the user before spending
quota; they may want a word changed.

## 2. Pick the engine (free only in this studio)

| Engine | Cost / setup | Quality in فصحى | Use when |
|---|---|---|---|
| **Piper** `ar_JO-kareem-medium` (`piper_tts_lines.py`) | free, fully offline, already installed | clear, even, slightly flat; good with full tashkeel | default; anything private; no network |
| **edge-tts** `ar-SA-HamedNeural` / `ar-SA-ZariyahNeural` (`edge_tts_lines.py`) | free, no key, but **online** (Microsoft service, text leaves the machine) | more natural prosody than Piper | the person wants a warmer read and accepts the online step |
| **espeak-ng** `-v ar` | free, offline, robotic | low | last-resort placeholder/scratch track only |
| **The person's own recording** | free | best | always offer it |

Paid engines (Gemini, ElevenLabs, HeyGen voices) are **not** part of this studio: never call
them, ask for keys, or suggest them unless the person explicitly asks for a paid option.

Engine notes:
- Keep one engine and one voice for the whole video so it stays one person.
- If a line comes out much longer than its text, the engine read something extra (often a
  bracket, a digit or Latin text). Fix the text and redo only that line with `--only N`.
- Piper tempo: `--length-scale 1.05`–`1.1` slows it slightly for teaching content.

## 3. Clean and pace

```bash
S="$VS_SKILLS/arabic-voiceover/scripts"   # VS_SKILLS = <repo>/.claude/skills (env.sh)
bash $S/prep_voice.sh RAW_DIR COMPOSITION_DIR 1.2     # trim edges, tempo (Piper 1.0, edge-tts 1.0-1.05, own voice 1.0)
python3 $S/tighten_pauses.py COMPOSITION_DIR/assets/voice --keep 0.2 --keep-last 0.3
```

`tighten_pauses.py` cuts every comma/colon breath longer than 0.2 s down to 0.2 s. In the
Qudrah Academy ad it took speech from 27.1 s to 25.6 s without touching a word. Keep a slightly
longer beat (0.3 s) in the last line between the name and the CTA.

If the total is still too long for the target length: shorten words (not tempo past 1.2 —
faster than that sounds rushed in Arabic), or drop one clause the screen already shows.

## 4. You cannot hear it — check by ear-proxy, then say so

Run the voice back through Whisper (`auto-subtitles` skill, `subtitle.py --transcribe-only`)
and compare the transcript with the script: a word Whisper cannot recover is usually a word a
listener will stumble on. Then tell the person plainly that you cannot listen to audio, and ask
them to play the lines (or the first render) and confirm: فصحى not dialect, the product name, numbers, and English words.
Offer to redo single lines. Common fixes:

| Heard | Fix |
|---|---|
| dialect vowels, "ج" as "g" | add missing tashkeel, especially case endings; re-generate |
| name mispronounced | respell phonetically with vowels; keep that spelling everywhere |
| a number read oddly | write it as words with vowels |
| rushed ending | lower tempo for that line only (re-run prep on it), or trim words |
| long gap mid-line | re-run `tighten_pauses.py` with `--keep 0.15` |

## 5. Own voice (user records)

Give them the diacritized script as a numbered list and ask them to record each line
separately on their phone (Voice Memos), quiet room, phone 20 cm away, a breath of silence
before and after, and send `vo1…voN`. Run the same `prep_voice.sh` with tempo 1.0 and
`tighten_pauses.py`. Human voice beats every engine; offer it to anyone hesitant about AI voices.

## 6. Subtitles (recommended for social)

Most social video is watched muted. After the final mix, `make_srt.py` writes Arabic
subtitles from the same lines (tashkeel stripped, RTL-marked) — upload the `.srt` next to the
video on YouTube/TikTok/LinkedIn.
