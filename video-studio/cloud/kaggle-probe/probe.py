# Kaggle GPU probe for Codex Video Studio: reports what the free GPU session really provides.
# Runs inside a Kaggle kernel; writes /kaggle/working/probe.json (downloaded by vs-kaggle-probe).
import json, os, shutil, subprocess, time, urllib.request
t0 = time.time()
def sh(c):
    try: return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=120).stdout.strip()
    except Exception as e: return f"error: {e}"
r = {"nvidia_smi": sh("nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader"),
     "cpu": os.cpu_count(), "ram_gb": round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1),
     "disk_free_gb": round(shutil.disk_usage("/kaggle/working").free / 2**30, 1),
     "python": sh("python --version"), "ffmpeg": sh("ffmpeg -version | head -1")}
try:
    import torch
    r["torch"] = torch.__version__; r["cuda"] = torch.cuda.is_available()
    if r["cuda"]:
        r["gpus"] = [{"name": torch.cuda.get_device_name(i), "vram_gb": round(torch.cuda.get_device_properties(i).total_memory / 2**30, 1),
                      "bf16": torch.cuda.is_bf16_supported()} for i in range(torch.cuda.device_count())]
        a = torch.randn(4096, 4096, device="cuda", dtype=torch.float16); torch.cuda.synchronize(); s = time.time()
        for _ in range(50): a @ a
        torch.cuda.synchronize(); r["fp16_tflops"] = round(50 * 2 * 4096**3 / (time.time() - s) / 1e12, 1)
except Exception as e: r["torch_error"] = str(e)
try:  # model download speed from Hugging Face (public 4.5 MB file; indicative only)
    s = time.time(); n = 0
    with urllib.request.urlopen("https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B/resolve/main/google/umt5-xxl/spiece.model", timeout=60) as f:
        while (b := f.read(1 << 20)): n += len(b)
    r["hf_download_MBps"] = round(n / 2**20 / (time.time() - s), 1)
except Exception as e: r["hf_download_error"] = str(e)
r["seconds"] = round(time.time() - t0, 1)
json.dump(r, open("/kaggle/working/probe.json", "w"), indent=2); print(json.dumps(r, indent=2))
