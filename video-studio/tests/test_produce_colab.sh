#!/usr/bin/env bash
# CPU test of vs-produce --gpu colab (manual backup): run 1 writes build/colab/images.ipynb and exits 75;
# a result zip (as the notebook would download) is imported with vs-colab; run 2 uses it and finishes the film.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
source "${VS_HOME:-$HOME/.video-studio}/env.sh"
mkdir -p "$T/p" "$T/r"
cat > "$T/p/production.json" <<'J'
{"title": "colab test", "slug": "colab-test", "lang": "en", "format": "youtube", "voice": {"engine": "piper"},
 "subtitles": {"burn": false},
 "shots": [{"id": "s01", "engine": "ai-image", "prompt": "a sprout under the sun", "camera": {"move": "push-in"},
            "vo": "A small seed wakes up in the morning sun.", "dur": 3}]}
J
export KAGGLE_USERNAME=stub VS_GPU_BIN=/bin/false        # Kaggle must not be touched in colab mode
set +e; vs-produce "$T/p" --gpu colab > "$T/log1" 2>&1; c1=$?; set -e
nb=$(ls "$T"/p/build/colab/*.ipynb 2>/dev/null | head -1)
[ "$c1" = 75 ] && [ -n "$nb" ] || { cat "$T/log1"; echo "FAIL: run 1 exit $c1, notebook '$nb'"; exit 1; }
name=$(basename "$nb" .ipynb)
ffmpeg -v error -y -ss 5 -i "$HERE/samples/07-animated-story.mp4" -frames:v 1 "$T/r/s01.png"
echo '{"model":"sdxl","provider":"colab","images":[{"id":"s01"}]}' > "$T/r/report.json"
(cd "$T/r" && python3 -m zipfile -c "$T/vs-result-$name.zip" s01.png report.json)
vs-colab import "$T/vs-result-$name.zip" "$T/p/build/gen/$name" > /dev/null
set +e; vs-produce "$T/p" --gpu colab > "$T/log2" 2>&1; c2=$?; set -e
[ "$c2" = 0 ] && [ -s "$T/p/out/colab-test.mp4" ] && grep -q 'sdxl@colab-t4' "$T/p/build/route.json" \
  && echo "PASS vs-produce --gpu colab: notebook written, result imported, film finished" \
  || { tail -5 "$T/log2"; cat "$T/p/build/route.json"; ls "$T/p/out"; echo "FAIL: run 2 exit $c2"; exit 1; }
