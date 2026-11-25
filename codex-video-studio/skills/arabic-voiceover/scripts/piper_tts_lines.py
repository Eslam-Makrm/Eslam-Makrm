#!/usr/bin/env python3
"""Voice lines with Piper — free, fully offline neural TTS (no account, no key, no network).

Usage:
    python3 piper_tts_lines.py LINES.json OUT_DIR [--voice ar_JO-kareem-medium]
        [--length-scale 1.0] [--sentence-silence 0.2] [--only 2 4] [--dry-run]

LINES.json is a JSON array of strings, one per scene (fully diacritized فصحى for Arabic).
Writes OUT_DIR/vo1.wav ... voN.wav and prints each duration, the same layout the other
engines use, so prep_voice.sh / tighten_pauses.py / mix_voiceover.py work unchanged.

Voices live in $VS_HOME/models/piper (default ~/.video-studio/models/piper):
  ar_JO-kareem-medium  Arabic, male. Dataset license is not stated upstream; confirm
                       before commercial use (fine for personal/educational work).
  en_US-lessac-medium  English, female (Blizzard-2013 lessac dataset licence, non-commercial terms).
Add more from https://huggingface.co/rhasspy/piper-voices (check each MODEL_CARD).

--length-scale > 1 speaks slower (1.1 = 10% slower); Piper Arabic is clear but even in
pitch, so keep lines short and let the picture carry the energy.
"""
import argparse
import json
import os
import subprocess
import sys

VS_HOME = os.environ.get("VS_HOME", os.path.expanduser("~/.video-studio"))


def duration(path: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("lines")
    ap.add_argument("out_dir")
    ap.add_argument("--voice", default="ar_JO-kareem-medium")
    ap.add_argument("--length-scale", type=float, default=1.0)
    ap.add_argument("--sentence-silence", type=float, default=0.2)
    ap.add_argument("--only", type=int, nargs="*", help="1-based line numbers to (re)generate")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    lines = json.load(open(a.lines, encoding="utf-8"))
    which = a.only or list(range(1, len(lines) + 1))
    model = a.voice if a.voice.endswith(".onnx") else os.path.join(VS_HOME, "models", "piper", a.voice + ".onnx")
    if a.dry_run:
        for n in which:
            print(f"vo{n}: {lines[n - 1]}")
        print(f"{len(which)} line(s) with {model}")
        return
    if not os.path.exists(model):
        sys.exit(f"voice model not found: {model} — run the studio installer or download it from rhasspy/piper-voices")
    py = os.path.join(VS_HOME, "venv", "bin", "python")
    if not os.path.exists(py):
        py = sys.executable
    os.makedirs(a.out_dir, exist_ok=True)
    for n in which:
        path = os.path.join(a.out_dir, f"vo{n}.wav")
        subprocess.run([py, "-m", "piper", "-m", model, "-f", path,
                        "--length-scale", str(a.length_scale),
                        "--sentence-silence", str(a.sentence_silence)],
                       input=lines[n - 1].encode("utf-8"), check=True, capture_output=True)
        print(f"vo{n}: {duration(path):.2f}s", flush=True)


if __name__ == "__main__":
    main()
