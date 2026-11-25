# GPU job: image-to-video / text-to-video with Wan2.2-TI2V-5B (Wan-AI, Apache-2.0), batched.
# PARAMS: {"items":[{"id":"shot01","prompt":"...","image":"shot01.png" (optional, in IN/),
#          "frames":121,"width":1280,"height":704,"seed":7}], "steps":30, "fps":24}
# Frames must be 4k+1; 720p sizes 1280x704 / 704x1280. Camera language goes in the prompt
# ("slow dolly-in", "orbit left", "handheld"); the editor adds moves in post when the model's are weak.
import os, subprocess, sys
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
import torch
REV = "b8fff7315c76"
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "diffusers==0.43.0", "accelerate", "transformers", "ftfy", "imageio-ffmpeg"], check=True)
from diffusers import WanImageToVideoPipeline, WanPipeline, AutoencoderKLWan
from diffusers.utils import export_to_video, load_image
t = time.time()
dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
repo = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"
vae = AutoencoderKLWan.from_pretrained(repo, subfolder="vae", revision=REV, torch_dtype=torch.float32)
t2v = WanPipeline.from_pretrained(repo, vae=vae, revision=REV, torch_dtype=dtype)
i2v = WanImageToVideoPipeline(**t2v.components)          # same weights, image-conditioned
VRAM = torch.cuda.get_device_properties(0).total_memory / 2**30
if VRAM < 20:   # T4: fp8 weight storage for the 5B transformer
    t2v.transformer.enable_layerwise_casting(storage_dtype=torch.float8_e4m3fn, compute_dtype=dtype)
for p in (t2v, i2v): p.enable_model_cpu_offload()
try: vae.enable_tiling()
except Exception: pass
report(load_s=round(time.time() - t, 1), dtype=str(dtype), vram_gb=round(VRAM, 1), gpu=torch.cuda.get_device_name(0))
NEG = "blurry, low quality, distorted face, extra limbs, watermark, text, subtitles, static frame"
done = []
for it in PARAMS["items"]:
    s = time.time()
    kw = dict(prompt=it["prompt"], negative_prompt=it.get("negative", NEG), height=it.get("height", 704),
              width=it.get("width", 1280), num_frames=it.get("frames", 121), guidance_scale=it.get("cfg", 5.0),
              num_inference_steps=PARAMS.get("steps", 30), generator=torch.Generator("cuda").manual_seed(it.get("seed", 0)))
    if it.get("image"):
        frames = i2v(image=load_image(str(IN / it["image"])).resize((kw["width"], kw["height"])), **kw).frames[0]
    else:
        frames = t2v(**kw).frames[0]
    export_to_video(frames, str(OUT / f"{it['id']}.mp4"), fps=PARAMS.get("fps", 24))
    done.append({"id": it["id"], "s": round(time.time() - s, 1)}); report(clips=done)
