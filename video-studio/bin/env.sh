# Video Studio environment — `source ~/.video-studio/env.sh` before running studio tools.
# (install.sh fills in @VS_SKILLS@ and @VS_REPO@ with absolute paths.)
export VS_HOME="${VS_HOME:-$HOME/.video-studio}"
export VS_SKILLS="${VS_SKILLS:-@VS_SKILLS@}"      # <repo>/.claude/skills, loaded by Claude Code
export VS_REPO="${VS_REPO:-@VS_REPO@}"            # <repo>/video-studio (examples, job templates, tests)
export HF_HOME="$VS_HOME/models/hf"           # Whisper models (faster-whisper) live here
export HF_HUB_DISABLE_XET=1                    # plain HTTPS downloads (works behind strict proxies)
export HF_HUB_DISABLE_TELEMETRY=1
export HYPERFRAMES_TELEMETRY_DISABLED=1
export DO_NOT_TRACK=1
export PIPER_VOICES="$VS_HOME/models/piper"
export VS_PY="$VS_HOME/venv/bin/python"          # whisper, piper, edge-tts
export VS_MANIM="$VS_HOME/venv-manim/bin/manim"  # manim (own venv: needs a newer PyAV)
export VS_AUTOEDITOR="$VS_HOME/venv-editor/bin/auto-editor"
export VS_AI_PY="$VS_HOME/venv-ai/bin/python"    # CPU AI helpers: depth, CLIP, DINOv2, QC
export VS_GPU_PY="$VS_HOME/venv-gpu/bin/python"  # Kaggle client (free cloud GPU backend)
export HF_CLI="node $VS_SKILLS/hyperframes/scripts/plugin-cli.mjs"   # HyperFrames CLI, pinned by the skill
case ":$PATH:" in *":$VS_HOME/bin:"*) ;; *) export PATH="$VS_HOME/bin:$PATH" ;; esac
export NODE_USE_ENV_PROXY=1                   # Node fetch honours HTTPS_PROXY when one is set (no effect otherwise)
# Kaggle: the API token is a network secret the proxy injects for api.kaggle.com; the client only
# needs a placeholder to start. Never put a real token here.
export KAGGLE_API_TOKEN="${KAGGLE_API_TOKEN:-proxy-injected}"
