#!/usr/bin/env bash
# CPU self-test of the vs-gpu job runtime: packing, inputs, report(), and the 2-GPU fan-out (shard()).
# Runs the packed script locally under a scratch /kaggle tree with VS_FAKE_GPUS=2. No Kaggle time used.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; trap 'rm -rf "$T"; rm -rf /kaggle' EXIT
[ -e /kaggle ] && { echo "/kaggle exists; refusing to touch it"; exit 1; }
mkdir -p /kaggle/working /kaggle/temp
cat > "$T/job.py" <<'PY'
items = shard(PARAMS["items"])
for it in items:
    (OUT / f"{it['id']}.txt").write_text(f"{it['id']} by shard {SHARD} input={(IN / 'in.txt').read_text()}")
report(done=[it["id"] for it in items])
PY
echo hello > "$T/in.txt"
python3 - "$HERE/bin/vs-gpu" "$T/job.py" "$T/in.txt" "$T/packed.py" <<'PY'
import importlib.machinery, importlib.util, json, sys, shutil, os
loader = importlib.machinery.SourceFileLoader("vsgpu", sys.argv[1])
spec = importlib.util.spec_from_loader("vsgpu", loader); m = importlib.util.module_from_spec(spec); loader.exec_module(m)
job = sys.argv[2]; jd = os.path.dirname(job)
for f in ("_boot.tmpl", "_common.py"):
    shutil.copy(os.path.join(os.path.dirname(os.path.dirname(sys.argv[1])), "gpu-jobs", f), jd)
open(sys.argv[4], "w").write(m.pack(job, {"items": [{"id": f"i{k}"} for k in range(5)]}, [sys.argv[3]]))
PY
VS_FAKE_GPUS=2 python3 "$T/packed.py"
ls /kaggle/working/out; cat /kaggle/working/out/report.json; echo
n=$(ls /kaggle/working/out/i*.txt | wc -l); [ "$n" = 5 ] || { echo "FAIL: $n/5 items"; exit 1; }
grep -q "by shard 0" /kaggle/working/out/i0.txt && grep -q "by shard 1" /kaggle/working/out/i1.txt && grep -q "input=hello" /kaggle/working/out/i4.txt \
  && python3 -c "import json;d=json.load(open('/kaggle/working/out/report.json'));assert d['parallel_gpus']==2 and d['shard_exit_codes']==[0,0]" \
  && echo "PASS gpu runtime: packing, inputs, 2-way fan-out, report merge"
