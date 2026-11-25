# GPU job: text-to-image with Z-Image-Turbo (Tongyi-MAI, Apache-2.0), batched.
# PARAMS: {"items":[{"id":"shot01","prompt":"...","negative":"","width":1280,"height":720,"seed":7}], "steps":8}
# Reference-consistent characters: put the character bible's canonical description in every prompt and
# keep the seed per character; QC (DINOv2) re-rolls frames that drift.
import os, subprocess, sys
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
import torch
REV = "f332072aa78b"                       # pinned model revision (licence checked: apache-2.0)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "diffusers==0.43.0", "accelerate", "transformers"], check=True)
from diffusers import ZImagePipeline
t = time.time()
dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
pipe = ZImagePipeline.from_pretrained("Tongyi-MAI/Z-Image-Turbo", revision=REV, torch_dtype=dtype)
VRAM = torch.cuda.get_device_properties(0).total_memory / 2**30
if VRAM < 20:   # T4 (15 GB): keep the 6B transformer's weights in fp8, compute in bf16/fp16 → ~half the memory
    pipe.transformer.enable_layerwise_casting(storage_dtype=torch.float8_e4m3fn, compute_dtype=dtype)
pipe.enable_model_cpu_offload()            # text encoder and transformer take turns on the GPU
if hasattr(pipe, "vae"):
    try: pipe.vae.enable_tiling()
    except Exception: pass
report(load_s=round(time.time() - t, 1), dtype=str(dtype), vram_gb=round(VRAM, 1), fp8_storage=VRAM < 20,
       gpu=torch.cuda.get_device_name(0))
done = []
for it in PARAMS["items"]:
    s = time.time()
    img = pipe(prompt=it["prompt"], height=it.get("height", 720), width=it.get("width", 1280),
               num_inference_steps=PARAMS.get("steps", 8), guidance_scale=0.0,
               generator=torch.Generator("cuda").manual_seed(it.get("seed", 0))).images[0]
    img.save(OUT / f"{it['id']}.png"); done.append({"id": it["id"], "s": round(time.time() - s, 1)})
    report(images=done)
