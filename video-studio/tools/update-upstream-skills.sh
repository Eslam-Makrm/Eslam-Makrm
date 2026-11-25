#!/usr/bin/env bash
# Re-vendor the pinned upstream skills into <repo>/.claude/skills and apply the studio patches.
#   tools/update-upstream-skills.sh          (bump the refs below deliberately, after a review)
# Sparse git checkouts of exact refs; nothing is executed from the downloaded code.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"; SKILLS="$(cd "$HERE/.." && pwd)/.claude/skills"
HF_REF="v0.9.93"                                            # heygen-com/hyperframes, Apache-2.0
MANIM_SKILL_REF="cef045011722d285692e3381d12d4d637da56e18"  # adithya-s-k/manim_skill, MIT
EXPLAINROO_REF="195f918a2dbecdda83e4f0741229a63fe2ab45e0"   # vincentsch/explainroo, MIT
fetch() {  # repo ref path...
  local repo="$1" ref="$2"; shift 2; local tmp; tmp="$(mktemp -d)"
  git -C "$tmp" init -q && git -C "$tmp" remote add origin "https://github.com/$repo.git"
  git -C "$tmp" sparse-checkout set "$@" && git -C "$tmp" fetch -q --depth 1 origin "$ref" && git -C "$tmp" checkout -q FETCH_HEAD
  for p in "$@"; do n="$(basename "$p")"; rm -rf "${SKILLS:?}/$n"; cp -R "$tmp/$p" "$SKILLS/$n"; echo "  $n  ($repo@${ref:0:10})"; done
  rm -rf "$tmp"
}
fetch heygen-com/hyperframes "$HF_REF" skills/hyperframes skills/hyperframes-cli skills/hyperframes-registry \
  skills/media-use skills/reverse-any-video skills/style-sampling
fetch adithya-s-k/manim_skill "$MANIM_SKILL_REF" skills/manim-composer skills/manimce-best-practices
fetch vincentsch/explainroo "$EXPLAINROO_REF" skills/explainroo
python3 "$HERE/patch-upstream.py" "$SKILLS"
