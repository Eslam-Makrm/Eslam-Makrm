#!/usr/bin/env python3
"""Adapt the pinned upstream skills to this studio (Claude Code, free/open-source only, no telemetry).

Idempotent: safe to run after every install or update. Usage:
    python3 patch-upstream.py [CODEX_HOME/skills]
Each change is a plain-text replacement that is reported; a skill whose text changed upstream
is reported as "not found" instead of being half-patched.
"""
import os
import re
import sys

SKILLS = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills")

USAGE_NOTE = re.compile(r"\*\*Usage note:\*\* before the first one, tell the person once:.*?once as this skill starts\.\n", re.S)
STUDIO_NOTE = ("**Studio policy (video-studio, patched):** do not send the usage note: never run `npx hyperframes events` "
               "or `usage`; telemetry is disabled (`hyperframes telemetry disable`, `HYPERFRAMES_TELEMETRY_DISABLED=1`). "
               "Free, open-source paths only — no HeyGen sign-in, cloud render, credits or Pro features, and no OpenAI, "
               "ChatGPT, Codex (`--provider codex`, `image_gen`), Groq or other paid APIs. Pass `--local-only` to media-use "
               "resolve. AI images, video and expressive voices come from the studio's `ai-generation` skill (open models "
               "on free cloud GPUs). Run the CLI as `$HF_CLI` after `source ~/.video-studio/env.sh`. "
               "Offline/proxied machines: load GSAP from `assets/gsap.min.js` (copy from `$VS_HOME/vendor/`) and ship fonts "
               "in `assets/fonts/` with `@font-face`.\n")

MEDIA_POLICY = """
## Studio policy: free and open-source only
<!-- video-studio -->
In this studio pick the **free/local** column of the table below and nothing else, unless the
person explicitly asks for a paid or signed-in option:
- Voiceover: `arabic-voiceover` skill (Piper offline; edge-tts online, free) or `npx hyperframes tts` (Kokoro, on device, English).
- Transcripts / captions: `auto-subtitles` skill (faster-whisper) or `npx hyperframes transcribe`.
- Grades and looks: `npx hyperframes media-treatment`. Cutouts: `npx hyperframes remove-background`.
- Sound effects: bundled ones, or Openverse items under CC0 (record the credit anyway).
- Music: only tracks the person supplies or CC0. Images and logos: the person's own, theSVG, or drawn in code.
- AI images / video / expressive voice: the studio's `ai-generation` skill (open models on Kaggle's free GPU), never the `codex` provider.
Never run `auth login`, `media-use generate`, the `heygen` CLI, `--provider codex`, the OpenAI/Groq transcription APIs,
or anything that spends credits.
"""

PATCHES = [
    # (skill-relative file, kind, old/regex, new)
    ("*", "regex", USAGE_NOTE, STUDIO_NOTE),
    ("hyperframes/SKILL.md", "text",
     ' at the start of a new video, `npx hyperframes usage --json` reports the person\'s remaining plan usage (say "unknown" when it is).',
     ""),
    ("media-use/SKILL.md", "after-heading", "# Media in HyperFrames\n", MEDIA_POLICY),
]
HF_SKILLS = ["hyperframes", "hyperframes-cli", "hyperframes-registry", "media-use", "reverse-any-video", "style-sampling"]


def patch_file(path, kind, old, new):
    if not os.path.exists(path):
        return f"skip (missing) {path}"
    s = open(path, encoding="utf-8").read()
    if kind == "regex":
        if STUDIO_NOTE in s:
            return f"ok (already) {path}"
        s2, n = old.subn(new, s, count=1)
    elif kind == "after-heading":
        if "<!-- video-studio -->" in s:
            return f"ok (already) {path}"
        n = s.count(old)
        s2 = s.replace(old, old + new, 1)
    else:
        if old not in s:
            return f"ok (already or changed upstream) {path}"
        n = s.count(old)
        s2 = s.replace(old, new)
    if not n:
        return f"NOT FOUND in {path} — review this skill by hand"
    open(path, "w", encoding="utf-8").write(s2)
    return f"patched {path}"


def main():
    for rel, kind, old, new in PATCHES:
        targets = [os.path.join(SKILLS, s, "SKILL.md") for s in HF_SKILLS] if rel == "*" else [os.path.join(SKILLS, rel)]
        for t in targets:
            print(patch_file(t, kind, old, new))


if __name__ == "__main__":
    main()
