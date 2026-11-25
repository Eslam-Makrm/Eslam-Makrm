#!/usr/bin/env bash
# Wan2.2-TI2V image-to-video wiring on CPU with tiny random models. Needs a Python with torch + diffusers==0.43.0:
#   VS_TORCH_PY=/path/to/python tests/test_i2v_tiny.sh     (skips with exit 0 when none is available)
PY="${VS_TORCH_PY:-}"
if [ -z "$PY" ] || ! "$PY" -c "import torch, diffusers" 2>/dev/null; then
  echo "SKIP test_i2v_tiny (set VS_TORCH_PY to a python with torch + diffusers==0.43.0)"; exit 0; fi
exec "$PY" -I "$(dirname "$0")/test_i2v_tiny.py"
