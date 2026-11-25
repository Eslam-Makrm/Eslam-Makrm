#!/usr/bin/env bash
# CPU self-test of the Colab backup (vs-colab): builds a notebook from a tiny job, executes every code cell
# the way Colab would (nvidia-smi and google.colab are stubbed), then imports the result zip — including a
# zip-slip entry that must be refused — and checks the committed notebooks are up to date with gpu-jobs/.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"
[ -e /kaggle ] || [ -e /content ] && { echo "/kaggle or /content exists; refusing to touch it"; exit 1; }
trap 'rm -rf "$T" /kaggle /content' EXIT
mkdir -p "$T/jobs" "$T/stub/google/colab" "$T/bin"
cp "$HERE/gpu-jobs/_boot.tmpl" "$HERE/gpu-jobs/_common.py" "$T/jobs/"
cat > "$T/jobs/job.py" <<'PY'
for it in shard(PARAMS["items"]):
    (OUT / f"{it['id']}.txt").write_text((IN / "face.png").read_text().strip() + "+" + (IN / "voice.wav").read_text().strip())
report(done=[it["id"] for it in PARAMS["items"]])
PY
echo face > "$T/face.png"; echo voice > "$T/voice.wav"
printf '#!/bin/sh\necho "GPU 0: Tesla T4 (stub)"\n' > "$T/bin/nvidia-smi"; chmod +x "$T/bin/nvidia-smi"
cat > "$T/stub/google/colab/__init__.py" <<PY
import pathlib, shutil
class files:
    @staticmethod
    def upload():
        return {"my face.png": pathlib.Path("$T/face.png").read_bytes()}   # odd name: notebook maps it
    @staticmethod
    def download(p):
        shutil.copy(p, "$T/")
class runtime:
    @staticmethod
    def unassign():
        pathlib.Path("$T/released").touch()
PY
touch "$T/stub/google/__init__.py"
python3 "$HERE/bin/vs-colab" build "$T/jobs/job.py" "$T/nb.ipynb" --name unit \
  --params '{"items":[{"id":"a"},{"id":"b"}],"_need_internet":false}' --input "$T/voice.wav" --ask face.png
python3 - "$T/nb.ipynb" > "$T/nb.py" <<'PY'
import json, sys
print("\n\n".join("".join(c["source"]) for c in json.load(open(sys.argv[1]))["cells"] if c["cell_type"] == "code"))
PY
(cd "$T" && VS_FAKE_GPUS=1 PATH="$T/bin:$PATH" PYTHONPATH="$T/stub" python3 "$T/nb.py")
[ -f "$T/released" ] || { echo "FAIL: GPU not released"; exit 1; }
python3 - "$T/vs-result-unit.zip" <<'PY'
import zipfile, sys
with zipfile.ZipFile(sys.argv[1], "a") as z:
    z.writestr("../evil.txt", "x")            # zip-slip: import must skip it
PY
python3 "$HERE/bin/vs-colab" import "$T/vs-result-unit.zip" "$T/res" > "$T/imp.json"
[ ! -e "$T/evil.txt" ] || { echo "FAIL: zip-slip entry written"; exit 1; }
grep -q "face+voice" "$T/res/a.txt" && grep -q "face+voice" "$T/res/b.txt" \
  && python3 -c "import json;d=json.load(open('$T/imp.json'));assert d['ok'] and d['report']['provider']=='colab', d" \
  || { echo "FAIL: results"; cat "$T/imp.json"; exit 1; }
# committed notebooks must match the current job code
cp -r "$HERE/colab" "$T/colab-committed"; bash "$HERE/colab/build.sh" 2>/dev/null
for f in "$HERE"/colab/*.ipynb; do cmp -s "$f" "$T/colab-committed/$(basename "$f")" \
  || { echo "FAIL: $(basename "$f") was stale (rebuilt now; commit it)"; exit 1; }; done
echo "PASS colab backup: notebook build, cells run, upload/download/release, import, zip-slip refused, notebooks current"
