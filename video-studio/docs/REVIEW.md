# Tool selection, security and licence review

Source list: [zhuyansen/awesome-claude-video-skills](https://github.com/zhuyansen/awesome-claude-video-skills)
(548 repos, list licence CC0-1.0, data generated 2026-11-24; 530 graded "safe", 18 "caution").
Reviewed 2026-11-25. 17 shortlisted repos were cloned and read: README, SKILL.md files, every
install/setup script, package manifests, and a pattern scan for `curl|sh`, install hooks,
`eval`, obfuscation, key handling and telemetry.

## Selection rules

1. Free and local first; anything online or paid is opt-in and named as such.
2. One engine per job, no duplicates; prefer permissive licences.
3. Works with Codex (agent-neutral skills, or adaptable ones).
4. Arabic must work: RTL layout, shaping, voice, subtitles.

## Chosen

| Tool / skill | Version pinned | Licence | Runs | Review notes |
|---|---|---|---|---|
| heygen-com/hyperframes (6 core skills + CLI) | v0.9.93 | Apache-2.0 | local (Chrome) | Clean scripts. **Telemetry** and a usage "beacon" → disabled and removed from the skills. Optional HeyGen cloud/credits → policy block forbids unless asked. GSAP dependency: free "no-charge" licence (commercial use allowed, not OSI). |
| adithya-s-k/manim_skill (manim-composer, manimce-best-practices) | cef04501 | MIT | local | Docs only, no scripts. ManimGL skill skipped (duplicate engine). |
| Manim Community | 0.22.1 | MIT | local | Needs LaTeX for formulas. Own venv (needs PyAV ≥15). |
| vincentsch/explainroo (skill + npx CLI) | 195f918a / 0.6.2 | MIT | local (Kokoro, Whisper, Chrome) | Optional paid connectors (ElevenLabs, Cartesia, OpenRouter, Blotato) need keys the studio never sets. Downloads ~860 MB of models once. No Arabic voice. |
| sudadom/arabic-motion-graphics-skill | adapted | MIT | — | Instructions + Remotion templates; rules kept, rendering moved to HyperFrames (avoids Remotion's company licence). |
| TurkiHassan/arabic-launch-video (voiceover scripts, rules) | adapted | MIT | — | Gemini/ElevenLabs paths removed; Piper engine added; edge-tts proxy fix; mixer creates its output folder. Key-file helper not shipped. |
| JohnHeibel/ClaudeAnimationBase (kit) | adapted | MIT (p5 LGPL-2.1, p5.brush MIT, puppeteer-core Apache-2.0) | local (Chrome) | No install scripts (`npm ci --ignore-scripts`). Ships the Clawd mascot; the skill requires original characters. |
| Piper TTS + voices | 1.8.0 | GPL-3.0 (program) | offline | Run as a separate tool; outputs are not GPL. `ar_JO-kareem` dataset licence unstated; `en_US-lessac` under the Blizzard-2013 dataset licence (non-commercial terms) — flagged. |
| edge-tts | 7.3.1 | LGPL-3.0 | **online** (Microsoft) | Free, unofficial, no key. Opt-in for a warmer Arabic voice. |
| faster-whisper + Whisper models | 1.2.1 | MIT | offline | Models from Hugging Face (MIT). PyAV pinned <15 (API change). |
| auto-editor | 29.3.1 | Unlicense | local | Its pip package downloads its own release binary from GitHub on first run (upstream's official release). Own venv. |
| ffmpeg / libass | system | LGPL/GPL | local | Must be built with libass, fribidi, harfbuzz for Arabic subtitles. |
| Fonts: Cairo, Amiri, Noto | — | OFL-1.1 | — | |

## Rejected

| Repo | Why |
|---|---|
| OpenMontageInc/OpenMontage | AGPL-3.0 and graded "caution"; overlaps everything above |
| HibaBenzahra/HibAi-Editing-Studio | proprietary licence, no redistribution or modification |
| 0xpratzyy/subtle | transcription and placement need Apple Silicon (mlx-whisper, Apple Vision) |
| kaomei/stickman-video-director | needs a paid image model (gpt-image-2 / Gemini / Google Flow) |
| remotion-dev/skills, AgriciDaniel/claude-shorts, wshuyi/remotion-video-skill | Remotion: duplicate engine; free only for individuals and companies ≤3 people |
| diffusionstudio/lottie | Lottie JSON for apps; MP4 needs extra tooling; HyperFrames covers motion graphics |
| iart-ai/motion-skills | an index of 19 separate packs; overlaps HyperFrames |
| znyupup/ai-video-editing-skill | Chinese vlog workflow that needs a vision API |
| GTAI-1/flow-mcp, ffroliva/gflow-cli | Google Flow subscription |

## Findings during testing (fixed in this studio)

- libass draws لا and أ/إ/آ as empty boxes with Noto Sans Arabic, Cairo and Kacst; Noto Naskh
  Arabic, Amiri and DejaVu Sans are correct → subtitle default is Noto Naskh / Amiri.
- libass reverses word order when a colour tag sits mid-line in RTL text → Arabic captions use
  whole-chunk events.
- Whisper smears word timings across pauses → line breaks are snapped to `silencedetect` pauses.
- Words sliding in from the right overlap their neighbour in RTL lines → words rise in place.
- faster-whisper breaks with PyAV ≥15 while Manim requires it → separate virtualenvs.
- Node's `fetch` ignores `HTTPS_PROXY` → `NODE_USE_ENV_PROXY=1` in `env.sh`; Hugging Face's Xet
  transfer needs extra hosts → `HF_HUB_DISABLE_XET=1`.
- HyperFrames templates load GSAP from a CDN → studio projects use a local `assets/gsap.min.js`.
