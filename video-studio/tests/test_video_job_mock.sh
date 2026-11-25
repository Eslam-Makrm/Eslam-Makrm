#!/usr/bin/env bash
# CPU test of gpu-jobs/video.py's control flow against a mocked torch/diffusers (no GPU, no downloads):
# text-first encoding, CFG cut-off (passes counted), First-Block-Cache switching, probe items, the per-step time
# guard (a slow item is dropped and the next one still runs), out-of-memory recovery and the report fields.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"
[ -e /kaggle ] && { echo "/kaggle exists; refusing to touch it"; exit 1; }
trap 'rm -rf "$T" /kaggle' EXIT
M="$T/mock"; mkdir -p "$M/torch/nn/attention" "$M/diffusers/utils" "$M/diffusers/hooks" "$M/transformers" /kaggle/working /kaggle/temp
cat > "$M/torch/__init__.py" <<'PY'
import types
float16, bfloat16, float32, float8_e4m3fn = "fp16", "bf16", "fp32", "fp8"
__version__ = "mock"
class OutOfMemoryError(RuntimeError): pass
class Generator:
    def __init__(self, dev): pass
    def manual_seed(self, s): return self
class _T:
    def to(self, *a, **k): return self
def isfinite(x): return types.SimpleNamespace(all=lambda: True)
def no_grad():
    import contextlib; return contextlib.nullcontext()
PEAK = [0.0]
class cuda:
    @staticmethod
    def is_available(): return True
    @staticmethod
    def device_count(): return 1
    @staticmethod
    def max_memory_allocated(i=0): return PEAK[0] * 2**30
    @staticmethod
    def reset_peak_memory_stats(): PEAK[0] = 0.0
    @staticmethod
    def empty_cache(): pass
    @staticmethod
    def is_bf16_supported(including_emulation=False): return True
class backends:
    class cuda:
        flash_sdp_enabled = staticmethod(lambda: False)
        mem_efficient_sdp_enabled = staticmethod(lambda: True)
PY
touch "$M/torch/nn/__init__.py"; echo "class SDPBackend: pass" > "$M/torch/nn/attention/__init__.py"
cat > "$M/diffusers/__init__.py" <<'PY'
import json, os, torch
LOG = []
class AutoencoderKLWan:
    @classmethod
    def from_pretrained(cls, *a, **k): return cls()
class _Tr:
    def __init__(self): self.cache = None
    def enable_cache(self, cfg):
        if self.cache: raise ValueError("cache already enabled")
        self.cache = cfg.threshold; LOG.append(f"cache on {cfg.threshold}")
    def disable_cache(self):
        if not self.cache: raise ValueError("no cache")
        self.cache = None; LOG.append("cache off")
    def _reset_stateful_cache(self): LOG.append("cache reset")
class WanPipeline:
    def __init__(self, **k): self.transformer = _Tr(); self.components = {}
    @classmethod
    def from_pretrained(cls, repo, **k):
        LOG.append("load text_encoder=" + ("None" if k.get("text_encoder", "x") is None else "yes")); return cls()
    def to(self, d): LOG.append("to " + d); return self
    def encode_prompt(self, **k): return torch._T(), torch._T()
    def __call__(self, prompt=None, prompt_embeds=None, num_inference_steps=20, guidance_scale=5.0, num_frames=49,
                 callback_on_step_end=None, **k):
        assert prompt is None and prompt_embeds is not None, "text-first: embeddings expected"
        if num_frames == 77:
            raise torch.OutOfMemoryError("mock OOM")
        self._guidance_scale = guidance_scale; passes = 0
        for i in range(num_inference_steps):
            passes += 2 if self._guidance_scale > 1 else 1
            os.environ["MOCK_T"] = str(float(os.environ.get("MOCK_T", "0")) + (50 if num_frames == 81 else 1))
            callback_on_step_end(self, i, i, {"latents": None})
        LOG.append(f"passes {passes}"); torch.PEAK[0] = 5.5
        import numpy as np
        class R: frames = [[np.full((4, 4, 3), 128, np.uint8)] * num_frames]
        return R()
class WanImageToVideoPipeline(WanPipeline): pass
PY
cat > "$M/diffusers/utils/__init__.py" <<'PY'
def export_to_video(frames, path, fps=16): open(path, "w").write(f"{len(frames)} frames @{fps}")
def load_image(p): return None
PY
cat > "$M/diffusers/hooks/__init__.py" <<'PY'
class FirstBlockCacheConfig:
    def __init__(self, threshold=0.05): self.threshold = threshold
PY
echo "class UMT5EncoderModel:
    @classmethod
    def from_pretrained(cls, *a, **k): return cls()" > "$M/transformers/__init__.py"
# the job with its pip line removed; mock clock = MOCK_T so the time guard is deterministic
sed 's/^subprocess.run(\[sys.executable, "-m", "pip".*$/pass/; /^                "imageio-ffmpeg"\], check=True)$/d' "$HERE/gpu-jobs/video.py" > "$T/video.py"
python3 - "$HERE/bin/vs-gpu" "$T/video.py" "$T/packed.py" <<'PY'
import importlib.machinery, importlib.util, json, os, shutil, sys
loader = importlib.machinery.SourceFileLoader("vsgpu", sys.argv[1])
spec = importlib.util.spec_from_loader("vsgpu", loader); m = importlib.util.module_from_spec(spec); loader.exec_module(m)
jd = os.path.dirname(sys.argv[2])
for f in ("_boot.tmpl", "_common.py"):
    shutil.copy(os.path.join(os.path.dirname(os.path.dirname(sys.argv[1])), "gpu-jobs", f), jd)
items = [{"id": "p-full", "prompt": "a", "probe": True},
         {"id": "p-cut", "prompt": "a", "probe": True, "cfg_until": 0.5, "cache": 0.05},
         {"id": "slow", "prompt": "a", "frames": 81},
         {"id": "oom", "prompt": "a", "frames": 77},
         {"id": "kite", "prompt": "a", "cfg_until": 0.5}]
open(sys.argv[3], "w").write(m.pack(sys.argv[2], {"model": "wan21-1.3b", "preset": "t4", "item_budget_s": 300,
                                                   "probe_steps": 4, "_need_internet": False, "items": items}, []))
PY
cat > "$T/run.py" <<PY
import os, sys, time
sys.path.insert(0, "$M")
time.time = lambda: float(os.environ.get("MOCK_T", "0"))
exec(open("$T/packed.py").read())
PY
set +e; VS_FAKE_GPUS=1 python3 "$T/run.py" > "$T/out.log" 2>&1; rc=$?; set -e
python3 - /kaggle/working/out/report.json "$rc" "$T/out.log" <<'PY'
import json, sys
r = json.load(open(sys.argv[1])); print(json.dumps({k: r.get(k) for k in ("placement", "probes", "clips", "failed")}, indent=1))
assert sys.argv[2] == "0", open(sys.argv[3]).read()[-2000:]
assert r["placement"].startswith("whole model on one T4")
p = {x["id"]: x for x in r["probes"]}
assert p["p-full"]["cfg_steps"] == 4 and p["p-cut"]["cfg_steps"] == 2 and p["p-cut"]["cache"] == 0.05
f = {x["id"]: x["why"] for x in r["failed"]}
assert "projected" in f["slow"] and "out of GPU memory" in f["oom"], f
c = r["clips"][0]; assert c["id"] == "kite" and c["frames"] == 49 and c["steps"] == 20 and c["cfg_steps"] == 10, c
assert open("/kaggle/working/out/kite.mp4").read() == "49 frames @16"
PY
echo "PASS video.py (mocked): text-first, CFG cut-off, cache switch, probes, time guard, OOM recovery"
