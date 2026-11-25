# Shared runtime for every studio GPU job (packed by vs-gpu; runs inside the Kaggle kernel and its
# per-GPU child processes). Provides: report(), gpu_info(), is_t4(), pick_dtype(), shard(), load_pipe().
# Kaggle free tier = 2x Tesla T4 (sm75, 14.6 GB each): fast fp16 tensor cores, bf16 only emulated.
import json, os, pathlib, subprocess, sys, time

SHARD = int(os.environ.get("VS_SHARD", "-1"))          # >= 0 inside a per-GPU child process


def report(**kw):
    p = OUT / ("report.json" if SHARD < 0 else f"report.shard{SHARD}.json")
    d = json.loads(p.read_text()) if p.exists() else {}
    d.update(kw); d["elapsed_s"] = round(time.time() - _T0, 1); p.write_text(json.dumps(d, indent=2))


def _vram_peak():           # benchmark: peak VRAM per visible GPU, written at exit of every (child) process
    try:
        import torch
        if torch.cuda.is_available():
            report(**{"vram_peak_gb": [round(torch.cuda.max_memory_allocated(i) / 2**30, 2)
                                       for i in range(torch.cuda.device_count())]})
    except Exception:
        pass


def _watchdog(limit_s):    # hard job budget: never let a stuck job burn GPU quota (Kaggle allows 12 h)
    import threading
    def fire():
        report(error=f"job exceeded its budget of {limit_s} s and was stopped (raise max_job_s only if needed)",
               timed_out=True)
        _vram_peak(); os._exit(5)
    t = threading.Timer(limit_s, fire); t.daemon = True; t.start()


import atexit
atexit.register(_vram_peak)
if SHARD < 0 and not os.environ.get("VS_FAKE_GPUS"):
    _watchdog(int(PARAMS.get("max_job_s", 3600)))


def step_guard(total_steps, budget_s, label="item", weights=None):
    """diffusers callback_on_step_end: stop on NaN/inf latents and when the projected time of this item exceeds
    budget_s (early failure detection, measured per step). weights = relative cost per step (2 with CFG, 1
    without) so the projection stays right when CFG is switched off part-way. Raises FloatingPointError /
    TimeoutError."""
    t0 = time.time()
    w = list(weights or [1] * total_steps)
    stats = {"steps": 0, "denoise_s": 0.0}
    def cb(pipe, step, ts, kw):
        import torch
        lat = kw.get("latents")
        if lat is not None and not torch.isfinite(lat).all():
            raise FloatingPointError(f"{label}: non-finite latents at step {step}")
        el = time.time() - t0
        proj = el / sum(w[:step + 1]) * sum(w)
        if step >= 1 and proj > budget_s:
            raise TimeoutError(f"{label}: {el / (step + 1):.1f} s/step, projected {proj:.0f} s > budget {budget_s} s")
        stats.update(steps=step + 1, denoise_s=round(el, 1))
        return kw
    cb.stats = stats
    return cb


def gpu_info():
    if os.environ.get("VS_FAKE_GPUS"):       # CPU self-test of packing and fan-out (tests/test_gpu_runtime.sh)
        return {"n": int(os.environ["VS_FAKE_GPUS"]), "name": "fake", "vram_gb": 14.6, "cc": 7.5}
    import torch
    n = torch.cuda.device_count()
    if not n:
        return {"n": 0}
    p = torch.cuda.get_device_properties(0)
    return {"n": n, "name": p.name, "vram_gb": round(p.total_memory / 2**30, 1), "cc": p.major + p.minor / 10}


def is_t4():
    g = gpu_info()
    return g.get("n", 0) > 0 and g["cc"] < 8.0


def pick_dtype(fp16_safe):
    """fp16 on T4 for models known to be fp16-safe (4-8x faster than emulated bf16); bf16 otherwise.
    PARAMS["dtype"] = fp16 | bf16 | fp32 overrides."""
    import torch
    want = PARAMS.get("dtype", "auto")
    if want in ("fp16", "bf16", "fp32"):
        return {"fp16": torch.float16, "bf16": torch.bfloat16, "fp32": torch.float32}[want]
    if is_t4():
        return torch.float16 if fp16_safe else torch.bfloat16
    return torch.bfloat16


class _Done(Exception):
    pass


def shard(items):
    """Small models: one process per GPU, items split round-robin (2x throughput on 2x T4).
    Returns this process's items; in the parent it waits for the children, merges reports and stops the job."""
    n = gpu_info().get("n", 0)
    if SHARD >= 0:
        return items[SHARD::int(os.environ["VS_NSHARD"])]
    if n < 2 or len(items) < 2 or not PARAMS.get("parallel", True):
        return items
    tmp = pathlib.Path("/kaggle/temp"); tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "vs_params.json").write_text(json.dumps(PARAMS))
    (tmp / "vs_child.py").write_text(
        "import base64, json, pathlib, time\n_T0 = time.time()\n"
        "IN = pathlib.Path('/kaggle/working/in'); OUT = pathlib.Path('/kaggle/working/out')\n"
        "PARAMS = json.load(open('/kaggle/temp/vs_params.json'))\n"
        f"_COMMON_B64 = {_COMMON_B64!r}\n_JOB_B64 = {_JOB_B64!r}\n"
        "exec(base64.b64decode(_COMMON_B64).decode())\n"
        "exec(compile(base64.b64decode(_JOB_B64).decode(), 'job.py', 'exec'))\n")
    procs = [subprocess.Popen([sys.executable, str(tmp / "vs_child.py")],
                              env={**os.environ, "VS_SHARD": str(i), "VS_NSHARD": str(n), "CUDA_VISIBLE_DEVICES": str(i)})
             for i in range(n)]
    codes = [p.wait() for p in procs]
    shards = []
    for i in range(n):
        f = OUT / f"report.shard{i}.json"
        if f.exists():
            shards.append(json.loads(f.read_text())); f.unlink()
    report(parallel_gpus=n, shards=shards, shard_exit_codes=codes)
    if codes and all(codes):
        report(error=f"every GPU worker failed: exit codes {codes}")
    elif any(codes):                          # partial result: keep what was made, vs-produce falls back for the rest
        report(warning=f"a GPU worker failed: exit codes {codes}")
    raise _Done()


def load_pipe(cls, repo, revision, dtype, fp8_ok=True, prefer=None, **kw):
    """Big diffusion models on 2x T4, best strategy first:
       1) device_map='balanced' — text encoder on one T4, transformer + VAE on the other (no CPU round-trips)
       2) fp8 weight storage for the transformer + model CPU offload on one T4
       3) sequential CPU offload (slowest, always fits)
    PARAMS["placement"] = balanced | offload | sequential forces one."""
    import torch
    force = prefer or PARAMS.get("placement")
    errors = []
    if (force in (None, "balanced")) and gpu_info().get("n", 0) >= 2:
        try:
            pipe = cls.from_pretrained(repo, revision=revision, torch_dtype=dtype, device_map="balanced", **kw)
            fp8 = fp8_ok and gpu_info()["vram_gb"] < 20 and hasattr(pipe, "transformer")
            if fp8:   # measured: Z-Image's 6B transformer alone (12 GB bf16) + attention overflows a 14.6 GB T4
                pipe.transformer.enable_layerwise_casting(storage_dtype=torch.float8_e4m3fn, compute_dtype=dtype)
                torch.cuda.empty_cache()
            report(placement="balanced (2 GPUs)" + (" + fp8 transformer weights" if fp8 else ""))
            return pipe
        except Exception as e:
            errors.append(f"balanced: {type(e).__name__}: {str(e)[:200]}")
    if force in (None, "offload"):
        try:
            pipe = cls.from_pretrained(repo, revision=revision, torch_dtype=dtype, **kw)
            if fp8_ok and gpu_info()["vram_gb"] < 20 and hasattr(pipe, "transformer"):
                pipe.transformer.enable_layerwise_casting(storage_dtype=torch.float8_e4m3fn, compute_dtype=dtype)
            pipe.enable_model_cpu_offload(gpu_id=0)
            report(placement="fp8 transformer + model CPU offload (1 GPU)", placement_errors=errors)
            return pipe
        except Exception as e:
            errors.append(f"offload: {type(e).__name__}: {str(e)[:200]}")
    pipe = cls.from_pretrained(repo, revision=revision, torch_dtype=dtype, **kw)
    pipe.enable_sequential_cpu_offload()
    report(placement="sequential CPU offload", placement_errors=errors)
    return pipe


def vae_tiling(pipe):
    for name in ("vae",):
        m = getattr(pipe, name, None)
        for fn in ("enable_tiling", "enable_slicing"):
            try:
                getattr(m, fn)()
            except Exception:
                pass


def looks_broken(arr):
    """NaN/black output check (fp16 overflow shows up as black frames)."""
    import numpy as np
    a = np.asarray(arr, dtype=np.float32)
    return (not np.isfinite(a).all()) or float(a.mean()) < 2.0
