# Codex Video Studio environment — `source ~/.video-studio/env.sh` before running studio tools.
export VS_HOME="${VS_HOME:-$HOME/.video-studio}"
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export HF_HOME="$VS_HOME/models/hf"           # Whisper models (faster-whisper) live here
export HF_HUB_DISABLE_XET=1                    # plain HTTPS downloads (works behind strict proxies)
export HF_HUB_DISABLE_TELEMETRY=1
export HYPERFRAMES_TELEMETRY_DISABLED=1
export DO_NOT_TRACK=1
export PIPER_VOICES="$VS_HOME/models/piper"
export VS_PY="$VS_HOME/venv/bin/python"          # whisper, piper, edge-tts
export VS_MANIM="$VS_HOME/venv-manim/bin/manim"  # manim (own venv: needs a newer PyAV)
export VS_AUTOEDITOR="$VS_HOME/venv-editor/bin/auto-editor"
export HF_CLI="node $CODEX_HOME/skills/hyperframes/scripts/plugin-cli.mjs"   # HyperFrames CLI, pinned by the skill
case ":$PATH:" in *":$VS_HOME/bin:"*) ;; *) export PATH="$VS_HOME/bin:$PATH" ;; esac
export NODE_USE_ENV_PROXY=1                   # Node fetch honours HTTPS_PROXY when one is set (no effect otherwise)
