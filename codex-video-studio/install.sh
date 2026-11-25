#!/usr/bin/env bash
# Codex Video Studio installer — free, local, open-source video production for OpenAI Codex.
#
#   ./install.sh                 install everything (skills, tools, models, fonts)
#   ./install.sh --system        also install system packages (apt / brew; asks for sudo on Linux)
#   ./install.sh --no-models     skip model downloads (~2.5 GB: Whisper turbo + small, Piper, Kokoro)
#   ./install.sh --force-skills  reinstall the upstream skills even if they exist
#
# Installs into  $CODEX_HOME/skills  (default ~/.codex/skills)  and  $VS_HOME  (default ~/.video-studio).
# Re-running is safe: finished steps are skipped. Nothing paid is installed or configured.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
VS_HOME="${VS_HOME:-$HOME/.video-studio}"
SKILLS="$CODEX_HOME/skills"
SYSTEM=0; MODELS=1; FORCE=0
for a in "$@"; do case "$a" in
  --system) SYSTEM=1 ;; --no-models) MODELS=0 ;; --force-skills) FORCE=1 ;;
  -h|--help) sed -n 2,11p "$0"; exit 0 ;; *) echo "unknown option $a" >&2; exit 2 ;; esac; done

# Pinned upstream versions (reviewed: licence, scripts, network use). Bump deliberately.
HF_REF="v0.9.93"                                       # heygen-com/hyperframes, Apache-2.0
MANIM_SKILL_REF="cef045011722d285692e3381d12d4d637da56e18"  # adithya-s-k/manim_skill, MIT
EXPLAINROO_REF="195f918a2dbecdda83e4f0741229a63fe2ab45e0"   # vincentsch/explainroo, MIT
EXPLAINROO_VER="0.6.2"
PY_PKGS_MAIN="faster-whisper==1.2.1 piper-tts==1.8.0 edge-tts==7.3.1 av>=14,<15"
PY_PKGS_MANIM="manim==0.22.1"
PY_PKGS_EDITOR="auto-editor==29.3.1"
GSAP_VER="3.15.0"
FONTS_RAW="https://raw.githubusercontent.com/google/fonts/main/ofl"
PIPER_RAW="https://huggingface.co/rhasspy/piper-voices/resolve/main"

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
ok()   { printf '  ok   %s\n' "$*"; }
warn() { printf '  WARN %s\n' "$*" >&2; }
die()  { printf '  FAIL %s\n' "$*" >&2; exit 1; }
OS="$(uname -s)"

# ---------------------------------------------------------------- 1. system packages
if [ "$SYSTEM" = 1 ]; then
  say "System packages"
  if [ "$OS" = Linux ] && command -v apt-get >/dev/null; then
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
      ffmpeg git python3-venv python3-dev pkg-config libcairo2-dev libpango1.0-dev \
      texlive-latex-base texlive-latex-extra texlive-fonts-recommended texlive-science cm-super dvisvgm \
      espeak-ng fonts-noto-core fonts-hosny-amiri fonts-noto-color-emoji fontconfig
  elif [ "$OS" = Darwin ] && command -v brew >/dev/null; then
    brew install ffmpeg git python@3.12 node pkg-config cairo pango espeak-ng
    brew install --cask basictex || warn "install MacTeX/BasicTeX by hand for Manim formulas"
    brew install --cask font-noto-naskh-arabic font-amiri || true
  else
    warn "unknown platform: install ffmpeg (with libass), Python 3.10+, Node 20+, Chrome, LaTeX yourself"
  fi
fi

# ---------------------------------------------------------------- 2. prerequisites
say "Prerequisites"
command -v ffmpeg >/dev/null || die "ffmpeg missing (run with --system, or install it)"
ffmpeg -hide_banner -buildconf 2>/dev/null | grep -q -- --enable-libass || warn "ffmpeg lacks libass: burned-in subtitles will not work"
ok "ffmpeg $(ffmpeg -version | head -1 | cut -d' ' -f3)"
command -v node >/dev/null || die "Node.js 20+ missing (https://nodejs.org)"
[ "$(node -p 'process.versions.node.split(".")[0]')" -ge 20 ] || die "Node.js 20+ required (found $(node -v))"
ok "node $(node -v)"
PY="$(command -v python3.12 || command -v python3.13 || command -v python3.11 || command -v python3 || true)"
[ -n "$PY" ] || die "Python 3.10+ missing"
"$PY" -c 'import sys; assert sys.version_info >= (3,10)' || die "Python 3.10+ required"
ok "python $("$PY" --version 2>&1)"
command -v git >/dev/null || die "git missing"
CHROME="$(command -v google-chrome || command -v chromium || command -v chromium-browser || ls -d /Applications/Google\ Chrome.app 2>/dev/null || true)"
[ -n "$CHROME" ] && ok "chrome $CHROME" || warn "Chrome/Chromium not found: HyperFrames, explainroo and animated-stories need one"
command -v latex >/dev/null && ok "latex" || warn "LaTeX missing: Manim formulas (MathTex) will fail; plain Manim text still works"

mkdir -p "$SKILLS" "$VS_HOME"/{bin,models/piper,models/hf,vendor,fonts}

# ---------------------------------------------------------------- 3. upstream skills ($skill-installer)
say "Upstream skills → $SKILLS"
INSTALLER="$SKILLS/.system/skill-installer/scripts/install-skill-from-github.py"
install_skill() {  # repo ref path...
  local repo="$1" ref="$2"; shift 2
  for p in "$@"; do
    local name; name="$(basename "$p")"
    if [ -d "$SKILLS/$name" ] && [ "$FORCE" = 0 ]; then ok "$name (present)"; continue; fi
    rm -rf "${SKILLS:?}/$name"
    if [ -f "$INSTALLER" ]; then   # Codex's built-in $skill-installer
      "$PY" "$INSTALLER" --repo "$repo" --ref "$ref" --path "$p" >/dev/null && { ok "$name ($repo@${ref:0:10}, skill-installer)"; continue; }
      warn "skill-installer failed for $name; falling back to git"
    fi
    local tmp; tmp="$(mktemp -d)"
    git -C "$tmp" init -q && git -C "$tmp" remote add origin "https://github.com/$repo.git"
    git -C "$tmp" sparse-checkout set "$p" && git -C "$tmp" fetch -q --depth 1 origin "$ref" && git -C "$tmp" checkout -q FETCH_HEAD
    cp -R "$tmp/$p" "$SKILLS/$name" && rm -rf "$tmp" && ok "$name ($repo@${ref:0:10}, git)"
  done
}
[ -f "$INSTALLER" ] || warn "Codex's \$skill-installer not found (run \`codex\` once to unpack system skills); using git"
install_skill heygen-com/hyperframes "$HF_REF" skills/hyperframes skills/hyperframes-cli skills/hyperframes-registry \
  skills/media-use skills/reverse-any-video skills/style-sampling
install_skill adithya-s-k/manim_skill "$MANIM_SKILL_REF" skills/manim-composer skills/manimce-best-practices
install_skill vincentsch/explainroo "$EXPLAINROO_REF" skills/explainroo

say "Studio skills (adapted + new)"
for d in "$HERE"/skills/*/; do
  n="$(basename "$d")"; rm -rf "${SKILLS:?}/$n"; cp -R "$d" "$SKILLS/$n"; ok "$n"
done
say "Adapting upstream skills for Codex (free-only, no telemetry)"
"$PY" "$HERE/patch-upstream.py" "$SKILLS"

# ---------------------------------------------------------------- 4. Python tools (three venvs: PyAV pins differ)
say "Python tools → $VS_HOME"
mkvenv() { [ -x "$VS_HOME/$1/bin/python" ] || "$PY" -m venv "$VS_HOME/$1"; "$VS_HOME/$1/bin/pip" install -q --upgrade pip; }
mkvenv venv        && "$VS_HOME/venv/bin/pip"        install -q $PY_PKGS_MAIN   && ok "venv: $PY_PKGS_MAIN"
mkvenv venv-manim  && "$VS_HOME/venv-manim/bin/pip"  install -q $PY_PKGS_MANIM  && ok "venv-manim: $PY_PKGS_MANIM"
mkvenv venv-editor && "$VS_HOME/venv-editor/bin/pip" install -q $PY_PKGS_EDITOR && ok "venv-editor: $PY_PKGS_EDITOR"
"$VS_HOME/venv-editor/bin/auto-editor" --version >/dev/null 2>&1 && ok "auto-editor ready (it fetches its own release binary from GitHub once)"

# ---------------------------------------------------------------- 5. helpers, vendor files, fonts
say "Helpers, GSAP, fonts"
cp "$HERE/bin/env.sh" "$VS_HOME/env.sh"
for f in vs-verify vs-hf-check vs-doctor; do cp "$HERE/bin/$f" "$VS_HOME/bin/$f"; chmod +x "$VS_HOME/bin/$f"; done
if [ ! -f "$VS_HOME/vendor/gsap.min.js" ]; then
  tmp="$(mktemp -d)"; (cd "$tmp" && npm pack -s "gsap@$GSAP_VER" >/dev/null && tar xzf gsap-*.tgz)
  cp "$tmp/package/dist/gsap.min.js" "$VS_HOME/vendor/"; rm -rf "$tmp"
fi; ok "gsap $GSAP_VER (local copy, for offline renders)"
fetch() { [ -s "$2" ] || curl -sSfL -o "$2" "$1"; }
fetch "$FONTS_RAW/cairo/Cairo%5Bslnt%2Cwght%5D.ttf" "$VS_HOME/fonts/Cairo.ttf"
fetch "$FONTS_RAW/cairo/OFL.txt" "$VS_HOME/fonts/Cairo-OFL.txt"
fetch "$FONTS_RAW/amiri/Amiri-Regular.ttf" "$VS_HOME/fonts/Amiri-Regular.ttf"
fetch "$FONTS_RAW/amiri/Amiri-Bold.ttf" "$VS_HOME/fonts/Amiri-Bold.ttf"
fetch "$FONTS_RAW/amiri/OFL.txt" "$VS_HOME/fonts/Amiri-OFL.txt"
cp "$VS_HOME/fonts/Cairo.ttf" "$VS_HOME/vendor/Cairo.ttf"
if [ "$OS" = Darwin ]; then FD="$HOME/Library/Fonts"; else FD="$HOME/.local/share/fonts"; fi
mkdir -p "$FD" && cp "$VS_HOME"/fonts/*.ttf "$FD/" && { command -v fc-cache >/dev/null && fc-cache -f >/dev/null || true; }
ok "fonts: Cairo, Amiri (OFL) → $VS_HOME/fonts and $FD"

# ---------------------------------------------------------------- 6. models (free, local)
if [ "$MODELS" = 1 ]; then
  say "Models (one-time downloads)"
  for v in ar/ar_JO/kareem/medium/ar_JO-kareem-medium en/en_US/lessac/medium/en_US-lessac-medium; do
    b="$(basename "$v")"; fetch "$PIPER_RAW/$v.onnx" "$VS_HOME/models/piper/$b.onnx"; fetch "$PIPER_RAW/$v.onnx.json" "$VS_HOME/models/piper/$b.onnx.json"
  done; ok "Piper voices: ar_JO-kareem-medium, en_US-lessac-medium"
  HF_HOME="$VS_HOME/models/hf" HF_HUB_DISABLE_XET=1 "$VS_HOME/venv/bin/python" -c "
from faster_whisper import WhisperModel
for m in ('small', 'large-v3-turbo'): WhisperModel(m, device='cpu', compute_type='int8')" && ok "Whisper: small, large-v3-turbo"
  NODE_USE_ENV_PROXY=1 npx --yes "explainroo@$EXPLAINROO_VER" doctor --fetch >/dev/null 2>&1 && ok "explainroo: Kokoro voice + speech check" \
    || warn "explainroo doctor --fetch failed; run it by hand: npx --yes explainroo@$EXPLAINROO_VER doctor --fetch"
fi

# ---------------------------------------------------------------- 7. telemetry off, final check
say "Privacy"
node "$SKILLS/hyperframes/scripts/plugin-cli.mjs" telemetry disable >/dev/null 2>&1 && ok "HyperFrames telemetry disabled" || warn "could not disable HyperFrames telemetry (env.sh also sets HYPERFRAMES_TELEMETRY_DISABLED=1)"

say "Done"
cat <<EOF
  Skills:  $(ls "$SKILLS" | grep -v '^\.' | tr '\n' ' ')
  Tools:   $VS_HOME   (source $VS_HOME/env.sh in every session)
  Test:    $HERE/tests/run-all.sh      renders one real MP4 per skill into ./samples-out
  In Codex: start with  \$video-studio  and describe the video you want.
EOF
