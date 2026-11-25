#!/usr/bin/env bash
# Rebuild the Colab backup notebooks from gpu-jobs/ (run after changing a job, then commit colab/*.ipynb).
set -eu
H=$(cd "$(dirname "$0")/.." && pwd); C="$H/bin/vs-colab"; J="$H/gpu-jobs"; B="$H/tests/gpu-bench"
python3 "$C" build "$J/image.py" "$H/colab/sdxl.ipynb" --name sdxl --params @"$B/image-sdxl.json"
python3 "$C" build "$J/video.py" "$H/colab/wan21-1.3b.ipynb" --name wan21-1.3b --params @"$B/video-wan13.json"
python3 "$C" build "$J/lipsync_musetalk.py" "$H/colab/musetalk.ipynb" --name musetalk \
  --params '{"items":[{"id":"talk","video":"presenter.png","audio":"chatterbox-ar-calm.wav"}],"max_job_s":2400}' \
  --input "$H/samples/voice/chatterbox-ar-calm.wav" --ask presenter.png
