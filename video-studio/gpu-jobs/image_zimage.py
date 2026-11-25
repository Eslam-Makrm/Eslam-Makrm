# GPU job: text-to-image with Z-Image-Turbo (Tongyi-MAI, Apache-2.0), batched.
# PARAMS: {"items":[{"id":"shot01","prompt":"...","negative":"","width":1280,"height":720,"seed":7}], "steps":8}
# Reference-consistent characters: put the character bible's canonical description in every prompt and
# keep the seed per character; QC (DINOv2) re-rolls frames that drift.
import subprocess, sys, torch
REV = "f332072aa78b"                       # pinned model revision (licence checked: apache-2.0)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "diffusers==0.43.0", "accelerate", "transformers"], check=True)
from diffusers import ZImagePipeline
t = time.time()
dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
pipe = ZImagePipeline.from_pretrained("Tongyi-MAI/Z-Image-Turbo", revision=REV, torch_dtype=dtype)
pipe.enable_model_cpu_offload()            # fits 16 GB T4 and 24 GB L4
report(load_s=round(time.time() - t, 1), dtype=str(dtype))
done = []
for it in PARAMS["items"]:
    s = time.time()
    img = pipe(prompt=it["prompt"], height=it.get("height", 720), width=it.get("width", 1280),
               num_inference_steps=PARAMS.get("steps", 8), guidance_scale=0.0,
               generator=torch.Generator("cuda").manual_seed(it.get("seed", 0))).images[0]
    img.save(OUT / f"{it['id']}.png"); done.append({"id": it["id"], "s": round(time.time() - s, 1)})
    report(images=done)
