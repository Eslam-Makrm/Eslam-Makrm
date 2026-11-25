#!/usr/bin/env bash
# CPU test of vs-produce --async with a stub GPU backend: run 1 submits and exits 75 (pending),
# run 2 sees "running" and exits 75 again, run 3 sees "complete", collects the image and finishes the film.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
source "${VS_HOME:-$HOME/.video-studio}/env.sh"
mkdir -p "$T/p" "$T/stub"
ffmpeg -v error -y -ss 5 -i "$HERE/samples/07-animated-story.mp4" -frames:v 1 "$T/stub/gen.png"
cat > "$T/stub/vs-gpu" <<STUB
#!/usr/bin/env bash
case "\$1" in
  quota)  echo '{"gpu_used_h": 0, "gpu_total_h": 30, "gpu_left_h": 30, "refresh": "x"}' ;;
  submit) echo "stub/vs-images" ;;
  status) cat "$T/stub/state" ;;
  fetch)  mkdir -p "\$3"; cp "$T/stub/gen.png" "\$3/s01.png"; echo '{"model":"stub-image"}' > "\$3/report.json" ;;
esac
STUB
chmod +x "$T/stub/vs-gpu"
cat > "$T/p/production.json" <<'J'
{"title": "async test", "slug": "async-test", "lang": "en", "format": "youtube", "voice": {"engine": "piper"},
 "subtitles": {"burn": false}, "gpu": {"image_model": "zimage"},
 "shots": [{"id": "s01", "engine": "ai-image", "prompt": "a sprout under the sun", "camera": {"move": "push-in"},
            "vo": "A small seed wakes up in the morning sun.", "dur": 3}]}
J
export VS_GPU_BIN="$T/stub/vs-gpu" KAGGLE_USERNAME=stub
echo queued > "$T/stub/state"
set +e
vs-produce "$T/p" --async >/dev/null 2>&1; c1=$?
echo running > "$T/stub/state"; vs-produce "$T/p" --async >/dev/null 2>&1; c2=$?
echo "complete" > "$T/stub/state"; vs-produce "$T/p" --async > "$T/log" 2>&1; c3=$?
set -e
echo "exit codes: $c1 $c2 $c3"
[ "$c1" = 75 ] && [ "$c2" = 75 ] && [ "$c3" = 0 ] && [ -s "$T/p/out/async-test.mp4" ] \
  && grep -q stub-image "$T/p/build/route.json" && echo "PASS vs-produce --async: submit, pending, collect, finish" \
  || { tail -20 "$T/log"; echo FAIL; exit 1; }
