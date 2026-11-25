# GPU probe job (vs-gpu run gpu-jobs/probe.py OUT): what does the free Kaggle session really provide?
import shutil, subprocess, urllib.request
def sh(c):
    try: return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=120).stdout.strip()
    except Exception as e: return f"error: {e}"
r = {"nvidia_smi": sh("nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader"),
     "cpu": os.cpu_count(), "ram_gb": round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1),
     "disk_free_gb": round(shutil.disk_usage("/kaggle/working").free / 2**30, 1),
     "python": sh("python --version"), "ffmpeg": sh("ffmpeg -version | head -1"),
     "pkgs": sh("pip list 2>/dev/null | grep -iE '^(torch|diffusers|transformers|accelerate|xformers) '")}
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
try:  # Hugging Face download speed (model weights come from there)
    s = time.time(); n = 0
    with urllib.request.urlopen("https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B/resolve/main/Wan2.2_VAE.pth", timeout=120) as f:
        while (b := f.read(1 << 22)) and n < 600 * 2**20: n += len(b)
    r["hf_download_MBps"] = round(n / 2**20 / (time.time() - s), 1)
except Exception as e: r["hf_download_error"] = str(e)
report(**r); print(r)
