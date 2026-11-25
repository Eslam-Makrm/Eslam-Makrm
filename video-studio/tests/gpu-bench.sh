#!/usr/bin/env bash
# Real-GPU benchmark of the T4 default stack on Kaggle (uses quota: ~0.5-1 GPU-hour).
#   tests/gpu-bench.sh OUT [tts image video lipsync]   (default: all, run one after another)
# Per job it records: exit code, wall time, quota before/after, and the job's report.json
# (load_s, per-item seconds, s/step, decode_s, vram_peak_gb, failures) into OUT/bench.jsonl,
# then makes contact sheets of the media so a human (or Claude) can judge quality.
# Run it in the background: it polls Kaggle locally and needs no Claude usage while it waits.
set -u
source ~/.video-studio/env.sh
OUT=$(realpath -m "${1:?usage: gpu-bench.sh OUT [jobs...]}"); shift; mkdir -p "$OUT"
JOBS=${*:-tts image video lipsync}; H=$(cd "$(dirname "$0")" && pwd); J=$VS_REPO/gpu-jobs; B=$H/gpu-bench
used() { vs-gpu quota | python3 -c 'import json,sys; print(json.load(sys.stdin)["gpu_used_h"])' 2>/dev/null || echo null; }
run() {  # name job dir params [inputs...]
  local n=$1 j=$2 d=$3 p=$4; shift 4; local a=(); for i in "$@"; do a+=(--input "$i"); done
  local q0 t0 rc; q0=$(used); t0=$(date +%s)
  vs-gpu run "$J/$j" "$OUT/$d" --params @"$p" "${a[@]}" --name "$n" --timeout 5400 > "$OUT/$d.log" 2>&1; rc=$?
  python3 - "$OUT/$d/report.json" "$n" "$rc" "$(( $(date +%s) - t0 ))" "$q0" "$(used)" >> "$OUT/bench.jsonl" <<'PY'
import json, sys
f, n, rc, wall, q0, q1 = sys.argv[1:]
try: r = json.load(open(f))
except Exception: r = {}
print(json.dumps({"job": n, "exit": int(rc), "wall_s": int(wall), "quota_used_h": [q0, q1], "report": r}, ensure_ascii=False))
PY
  echo "$n exit=$rc"
}
for job in $JOBS; do case $job in
  tts)   run bench-tts tts_chatterbox.py tts "$B/tts.json" ;;
  image) run bench-sdxl image.py image "$B/image-sdxl.json" ;;
  video) run bench-wan13 video.py video "$B/video-wan13.json" ;;
  lipsync)
    if [ -f "$OUT/image/presenter.png" ] && [ -f "$OUT/tts/calm.wav" ]; then
      echo '{"items":[{"id":"talk","video":"presenter.png","audio":"calm.wav"}],"max_job_s":2400}' > "$OUT/lp.json"
      run bench-lipsync lipsync_musetalk.py lipsync "$OUT/lp.json" "$OUT/image/presenter.png" "$OUT/tts/calm.wav"
    else echo "lipsync skipped: needs image/presenter.png and tts/calm.wav (run image and tts first)"; fi ;;
esac; done
for v in "$OUT"/video/*.mp4 "$OUT"/lipsync/*.mp4; do [ -f "$v" ] || continue
  ffmpeg -v error -y -i "$v" -vf "fps=2,scale=320:-1,tile=4x2" -frames:v 1 "${v%.mp4}.sheet.jpg"; done
echo "results: $OUT/bench.jsonl"
