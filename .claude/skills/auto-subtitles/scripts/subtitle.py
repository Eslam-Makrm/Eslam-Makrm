#!/usr/bin/env python3
"""Automatic subtitles, fully local: faster-whisper -> SRT + styled ASS -> burned-in MP4.

Usage:
    python3 subtitle.py INPUT [--lang ar|en|auto] [--model large-v3-turbo|small|medium]
        [--style clean|box|word|reel] [--burn OUT.mp4] [--srt EXISTING.srt]
        [--out-dir DIR] [--max-chars 42] [--replace heard=Shown ...] [--keep-tashkeel]
        [--font "Noto Naskh Arabic"] [--transcribe-only]

INPUT is any video or audio ffmpeg can read. Writes next to it (or in --out-dir):
  NAME.words.json  word timings from Whisper (edit these and rerun with --words to restyle)
  NAME.srt         plain subtitles for YouTube/TikTok/Instagram upload
  NAME.ass         styled subtitles (libass: Arabic shaping + right-to-left handled correctly)
and with --burn, an MP4 with the captions drawn into the picture (audio copied untouched).

Styles
  clean  white text, soft shadow, bottom centre (lessons, interviews)
  box    white text on a translucent dark box (busy footage)
  word   LTR: the line stays up, the spoken word highlighted in the accent colour.
         RTL (Arabic): 1-4 word chunks that pop in on the voice (libass-safe, see write_ass)
  reel   big bold 1-3 word chunks in the lower third (9:16 shorts); LTR chunks highlight the word

--srt skips transcription and only styles/burns an existing SRT (e.g. from make_srt.py).
Models are cached in $HF_HOME (set by ~/.video-studio/env.sh); nothing leaves the machine.
"""
import argparse
import json
import os
import re
import subprocess
import sys

TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
ARABIC = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
RLE, PDF = "‫", "‬"
LIBASS_SAFE_ARABIC = ("Noto Naskh Arabic", "Amiri", "DejaVu Sans")


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def probe_size(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:stream_side_data=rotation", "-of", "json", path],
                         capture_output=True, text=True).stdout
    try:
        s = json.loads(out)["streams"][0]
        w, h = int(s["width"]), int(s["height"])
        rot = abs(int(next((d.get("rotation", 0) for d in s.get("side_data_list", [])), 0)))
        return (h, w) if rot in (90, 270) else (w, h)
    except (KeyError, IndexError, ValueError):
        return (1920, 1080)


def transcribe(path, lang, model_name, vocab):
    from faster_whisper import WhisperModel  # imported late: --srt mode needs no model
    model = WhisperModel(model_name, device="auto", compute_type="int8")
    segments, info = model.transcribe(
        path, language=None if lang == "auto" else lang, word_timestamps=True,
        vad_filter=True, initial_prompt=vocab or None, beam_size=5)
    words = []
    for seg in segments:
        for w in seg.words or []:
            t = w.word.strip()
            if t:
                words.append({"start": round(w.start, 3), "end": round(w.end, 3), "word": t})
    return words, info.language


def apply_replacements(words, pairs):
    """heard=Shown. Matches inside a word too, so Arabic prefixes survive (ومنتاج -> ومونتاج)."""
    for pair in pairs or []:
        heard, shown = pair.split("=", 1)
        for w in words:
            if heard in w["word"]:
                w["word"] = w["word"].replace(heard, shown)
    return words


def silences(path, noise_db=-35, min_len=0.22):
    """Pauses in the audio as [(start, end)], from ffmpeg silencedetect."""
    log = subprocess.run(["ffmpeg", "-v", "info", "-i", path, "-vn", "-af",
                          f"silencedetect=noise={noise_db}dB:d={min_len}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    starts = [float(m) for m in re.findall(r"silence_start: ([0-9.]+)", log)]
    ends = [float(m) for m in re.findall(r"silence_end: ([0-9.]+)", log)]
    return list(zip(starts, ends))


def snap_to_speech(words, pauses, reach=0.8):
    """Whisper often smears word timings across pauses (no gaps, words stretched or shifted).
    For each real pause, move the nearest word boundary (within `reach` s) onto it: the word
    before ends where the pause starts, the word after starts where it ends. Captions then
    appear when the voice starts, and lines break where the speaker breathes."""
    if not words:
        return words
    for a, b in pauses:
        mid = (a + b) / 2
        if b <= words[0]["start"] + reach and a < words[0]["start"] + 0.5:
            words[0]["start"] = round(min(max(words[0]["start"], b), words[0]["end"] - 0.05), 3)
            continue
        best, dist = None, reach
        for i in range(len(words) - 1):
            d = abs((words[i]["end"] + words[i + 1]["start"]) / 2 - mid)
            if d < dist:
                best, dist = i, d
        if best is not None:
            prev, nxt = words[best], words[best + 1]
            prev["end"] = round(max(prev["start"] + 0.05, min(prev["end"], a)), 3)
            nxt["start"] = round(min(nxt["end"] - 0.05, max(nxt["start"], b)), 3)
    return words


def group_lines(words, max_chars, max_gap=0.35, max_dur=6.0):
    """Group words into caption lines: break on punctuation, pauses, length and duration."""
    lines, cur = [], []
    for w in words:
        if cur:
            text = " ".join(x["word"] for x in cur + [w])
            gap = w["start"] - cur[-1]["end"]
            if (len(text) > max_chars or gap > max_gap or w["end"] - cur[0]["start"] > max_dur
                    or re.search(r"[.!?؟。]$", cur[-1]["word"])):
                lines.append(cur)
                cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    return lines


def chunk(words, n):
    return [words[i:i + n] for i in range(0, len(words), n)]


def ts_srt(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def ts_ass(t):
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}"


def clean(text, keep_tashkeel):
    return text if keep_tashkeel else TASHKEEL.sub("", text)


def parse_srt(path):
    blocks = re.split(r"\n\s*\n", open(path, encoding="utf-8-sig").read().strip())
    cues = []
    for b in blocks:
        rows = [r for r in b.splitlines() if r.strip()]
        tline = next((r for r in rows if "-->" in r), None)
        if not tline:
            continue
        a, b2 = [x.strip().replace(",", ".") for x in tline.split("-->")]
        to_s = lambda x: sum(float(p) * m for p, m in zip(x.split(":"), (3600, 60, 1)))
        text = " ".join(rows[rows.index(tline) + 1:]).replace(RLE, "").replace(PDF, "")
        cues.append({"start": to_s(a), "end": to_s(b2), "text": text})
    return cues


def write_srt(cues, path, rtl):
    with open(path, "w", encoding="utf-8") as f:
        for i, c in enumerate(cues, 1):
            text = f"{RLE}{c['text']}{PDF}" if rtl else c["text"]
            f.write(f"{i}\n{ts_srt(c['start'])} --> {ts_srt(c['end'])}\n{text}\n\n")


def ass_header(w, h, style, font, accent):
    vertical = h > w
    base = h / 1080 if not vertical else w / 1080
    size = {"clean": 56, "box": 54, "word": 66, "reel": 104}[style] * base
    margin_v = int((0.20 if vertical else 0.07) * h)  # 9:16: above the platform caption/UI band
    border_style, outline, shadow, back = 1, 3 * base, 1.5 * base, "&H64000000"
    if style == "box":
        border_style, outline, shadow, back = 3, 10 * base, 0, "&H8C000000"
    bold = -1 if style in ("reel", "word") else 0
    return (
        "[Script Info]\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\n"
        f"PlayResX: {w}\nPlayResY: {h}\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Main,{font},{size:.0f},&H00FFFFFF,{accent},&H00101010,{back},{bold},0,0,0,100,100,0,0,"
        f"{border_style},{outline:.1f},{shadow:.1f},2,{int(0.08 * w)},{int(0.08 * w)},{margin_v},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")


def ass_escape(t):
    return t.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def write_ass(path, w, h, style, font, accent_bgr, lines_words, cues, keep_tashkeel, rtl):
    """Write styled captions. Events never overlap (each ends where the next begins).

    Right-to-left text: libass reorders bidi runs wrongly when an override tag sits in the
    middle of a line, so RTL captions never use inline tags. `word`/`reel` show the spoken
    1-3 word chunk on its own, popping in with a single leading tag (one run, correct order).
    Left-to-right text gets the per-word colour highlight."""
    hl = "{\\c" + accent_bgr + "}"
    rs = "{\\c&H00FFFFFF&}"
    pop = "{\\fscx88\\fscy88\\t(0,120,\\fscx100\\fscy100)}"
    events = []  # (start, end, text)
    if style in ("word", "reel") and lines_words:
        size = 3 if style == "reel" else 4
        groups = [c for ln in lines_words for c in chunk(ln, size)] if (rtl or style == "reel") else lines_words
        for g in groups:
            toks = [ass_escape(clean(x["word"], keep_tashkeel)) for x in g]
            if rtl:
                events.append([g[0]["start"], g[-1]["end"] + 0.25, pop + " ".join(toks)])
            else:
                for i, wd in enumerate(g):
                    end = g[i + 1]["start"] if i + 1 < len(g) else wd["end"] + 0.25
                    text = " ".join((hl + t + rs) if j == i else t for j, t in enumerate(toks))
                    events.append([wd["start"], end, text])
    else:
        events = [[c["start"], c["end"], ass_escape(c["text"])] for c in cues]
    events.sort(key=lambda e: e[0])
    for e, nxt in zip(events, events[1:]):
        e[1] = nxt[0] if nxt[0] - e[1] < 0.5 else min(e[1], nxt[0])  # no overlap; bridge short gaps
    with open(path, "w", encoding="utf-8") as f:
        f.write(ass_header(w, h, style, font, accent_bgr))
        for a, b, t in events:
            if b - a >= 0.04:
                f.write(f"Dialogue: 0,{ts_ass(a)},{ts_ass(b)},Main,,0,0,0,,{t}\n")


def fonts_dir():
    """Studio fonts (Cairo, Amiri) live in $VS_HOME/fonts; libass also sees system fonts."""
    d = os.path.join(os.environ.get("VS_HOME", os.path.expanduser("~/.video-studio")), "fonts")
    return d if os.path.isdir(d) else os.path.expanduser("~/.local/share/fonts")


def arabic_default_font():
    """Noto Naskh Arabic when the system has it (Linux: fonts-noto-core), else the studio's static Amiri."""
    try:
        out = subprocess.run(["fc-list", ":lang=ar", "family"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        out = ""
    return "Noto Naskh Arabic" if "Noto Naskh Arabic" in out else "Amiri"


def ffmpeg_path(p):
    """Escape a path for the ffmpeg subtitles= filter argument."""
    return p.replace("\\", "/").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("--lang", default="auto")
    ap.add_argument("--model", default=os.environ.get("VS_WHISPER_MODEL", "large-v3-turbo"))
    ap.add_argument("--style", default="clean", choices=["clean", "box", "word", "reel"])
    ap.add_argument("--burn", metavar="OUT.mp4")
    ap.add_argument("--srt", metavar="EXISTING.srt")
    ap.add_argument("--words", metavar="WORDS.json", help="reuse (edited) word timings, skip Whisper")
    ap.add_argument("--out-dir")
    ap.add_argument("--max-chars", type=int, default=0, help="default 42 (16:9) / 28 (9:16)")
    ap.add_argument("--replace", action="append", help="heard=Shown spelling fix (repeatable)")
    ap.add_argument("--vocab", help="names/brand words to bias Whisper's spelling")
    ap.add_argument("--keep-tashkeel", action="store_true")
    ap.add_argument("--font", default="")
    ap.add_argument("--accent", default="#FFB547", help="highlight colour for word/reel styles")
    ap.add_argument("--transcribe-only", action="store_true")
    a = ap.parse_args()

    base = os.path.splitext(os.path.basename(a.input))[0]
    out_dir = a.out_dir or os.path.dirname(os.path.abspath(a.input))
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, base)
    w, h = probe_size(a.input)
    max_chars = a.max_chars or (28 if h > w else 42)

    words, lines_words = [], []
    if a.srt:
        cues = parse_srt(a.srt)
        lang = "ar" if any(ARABIC.search(c["text"]) for c in cues) else "en"
    else:
        if a.words:
            words, lang = json.load(open(a.words, encoding="utf-8")), a.lang
        else:
            words, lang = transcribe(a.input, a.lang, a.model, a.vocab)
            words = snap_to_speech(words, silences(a.input))
            json.dump(words, open(stem + ".words.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        words = apply_replacements(words, a.replace)
        if a.transcribe_only:
            print(f"language={lang}")
            print(" ".join(x["word"] for x in words))
            return
        if lang == "auto":
            lang = "ar" if any(ARABIC.search(x["word"]) for x in words) else "en"
        lines_words = group_lines(words, max_chars)
        cues = [{"start": ln[0]["start"], "end": ln[-1]["end"] + 0.2,
                 "text": clean(" ".join(x["word"] for x in ln), a.keep_tashkeel)} for ln in lines_words]
        for c, nxt in zip(cues, cues[1:]):  # no overlaps
            c["end"] = min(c["end"], nxt["start"])

    rtl = lang == "ar"
    # libass (ffmpeg's subtitle renderer) is picky with Arabic fonts: tested on libass+HarfBuzz,
    # Noto Sans Arabic, Cairo and Kacst draw lam-alef (لا) and hamza forms with empty boxes.
    # Noto Naskh Arabic, Amiri and DejaVu Sans render correctly.
    font = a.font or (arabic_default_font() if rtl else "Noto Sans")
    if rtl and font not in LIBASS_SAFE_ARABIC:
        print(f"warning: '{font}' is not on the tested list for Arabic in libass "
              f"({', '.join(LIBASS_SAFE_ARABIC)}); check a frame for empty boxes", file=sys.stderr)
    hexc = a.accent.lstrip("#")
    accent_bgr = f"&H00{hexc[4:6]}{hexc[2:4]}{hexc[0:2]}&"
    write_srt(cues, stem + ".srt", rtl)
    write_ass(stem + ".ass", w, h, a.style, font, accent_bgr, lines_words, cues, a.keep_tashkeel, rtl)
    print(f"language={lang} cues={len(cues)} words={len(words)}")
    print(f"srt={stem}.srt\nass={stem}.ass")

    if a.burn:
        fontsdir = fonts_dir()
        vf = f"subtitles='{ffmpeg_path(stem + '.ass')}':fontsdir='{ffmpeg_path(fontsdir)}'"
        run(["ffmpeg", "-v", "error", "-y", "-i", a.input, "-vf", vf, "-c:v", "libx264", "-crf", "18",
             "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", a.burn])
        print(f"burned={a.burn}", flush=True)


if __name__ == "__main__":
    main()
