# GPU job: text-to-video and image-to-video, tuned for Kaggle's 2x Tesla T4 (14.6 GB each, sm75).
# PARAMS: {"model": "wan22-5b" | "wan21-1.3b", "preset": "t4" | "t4-fast" | "hq",
#          "items": [{"id","prompt","image"? (keyframe in IN/ -> image-to-video),"frames","width","height","seed"}],
#          "steps": N, "fps": 24, "dtype": "auto"|"fp16"|"bf16"}
#
#   wan22-5b   Wan2.2-TI2V-5B (Apache-2.0): text- AND image-to-video. T4 plan: UMT5 text encoder on GPU1,
#              transformer + VAE on GPU0 (device_map="balanced"), fp16 compute (T4 has no native bf16),
#              VAE tiling; fallback fp8 weights + CPU offload. Black/NaN frames -> that clip is redone in bf16.
#   wan21-1.3b Wan2.1-T2V-1.3B (Apache-2.0): light text-to-video at 480p, ~3x faster; no image-to-video.
#
# Presets (per-item width/height/frames override them):
#   t4       832x480, 81 frames (3.4 s @24), 20 steps  — default on T4; vs-produce upscales to the delivery size
#   t4-fast  832x480, 49 frames (2.0 s), 16 steps      — drafts and short cutaways
#   hq       1280x704, 121 frames (5 s), 30 steps      — only on bigger GPUs (L4/A100); hours per clip on T4
import os, subprocess, sys
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "diffusers==0.43.0", "accelerate", "transformers", "ftfy",
                "imageio-ffmpeg"], check=True)
import torch
from diffusers.utils import export_to_video, load_image

PRESETS = {"t4": (832, 480, 81, 20), "t4-fast": (832, 480, 49, 16), "hq": (1280, 704, 121, 30)}
REPOS = {"wan22-5b": ("Wan-AI/Wan2.2-TI2V-5B-Diffusers", "b8fff7315c76"),
         "wan21-1.3b": ("Wan-AI/Wan2.1-T2V-1.3B-Diffusers", "0fad780a534b")}
model = PARAMS.get("model", "wan22-5b")
preset = PARAMS.get("preset", "t4" if is_t4() else "hq")
PW, PH, PF, PS = PRESETS[preset]
NEG = "blurry, low quality, distorted face, extra limbs, watermark, text, subtitles, static frame, flicker"
if model == "wan21-1.3b" and any(it.get("image") for it in PARAMS["items"]):
    model = "wan22-5b"                       # only the 5B model can animate a keyframe
    report(note="image-to-video requested: using wan22-5b")


def build(dtype):
    from diffusers import WanPipeline, WanImageToVideoPipeline, AutoencoderKLWan
    repo, rev = REPOS[model]
    vae = AutoencoderKLWan.from_pretrained(repo, subfolder="vae", revision=rev, torch_dtype=torch.float32)
    t2v = load_pipe(WanPipeline, repo, rev, dtype, vae=vae)
    vae_tiling(t2v)
    i2v = WanImageToVideoPipeline(**t2v.components) if model == "wan22-5b" else None
    return t2v, i2v


def snap(v, m):
    return max(m, int(round(v / m)) * m)


def render(pipes, it, dtype):
    t2v, i2v = pipes
    w, h = it.get("width", PW), it.get("height", PH)
    if h > w and (w, h) == (PW, PH):
        w, h = h, w                          # vertical
    if "width" not in it and "height" not in it and it.get("vertical"):
        w, h = PH, PW
    w, h = snap(w, 32), snap(h, 32)
    f = it.get("frames", PF); f = (f - 1) // 4 * 4 + 1
    kw = dict(prompt=it["prompt"], negative_prompt=it.get("negative", NEG), height=h, width=w, num_frames=f,
              guidance_scale=it.get("cfg", 5.0), num_inference_steps=PARAMS.get("steps", PS),
              generator=torch.Generator("cpu").manual_seed(it.get("seed", 0)))
    if it.get("image") and i2v is not None:
        frames = i2v(image=load_image(str(IN / it["image"])).resize((w, h)), **kw).frames[0]
    else:
        frames = t2v(**kw).frames[0]
    return frames, (w, h, f)


t = time.time()
dtype = pick_dtype(fp16_safe=True)
pipes = build(dtype)
report(load_s=round(time.time() - t, 1), dtype=str(dtype), model=model, preset=preset)
done, redo = [], []
for it in PARAMS["items"]:
    s = time.time()
    frames, dims = render(pipes, it, dtype)
    if looks_broken(frames[len(frames) // 2]):
        redo.append(it); report(clips=done, broken_fp16=[r["id"] for r in redo]); continue
    export_to_video(frames, str(OUT / f"{it['id']}.mp4"), fps=PARAMS.get("fps", 24))
    done.append({"id": it["id"], "s": round(time.time() - s, 1), "size": f"{dims[0]}x{dims[1]}", "frames": dims[2]})
    report(clips=done)
if redo and dtype == torch.float16:          # fp16 overflowed on these clips: rebuild once in bf16 (slower, exact)
    del pipes
    import gc; gc.collect(); torch.cuda.empty_cache()
    pipes = build(torch.bfloat16)
    for it in redo:
        s = time.time()
        frames, dims = render(pipes, it, torch.bfloat16)
        export_to_video(frames, str(OUT / f"{it['id']}.mp4"), fps=PARAMS.get("fps", 24))
        done.append({"id": it["id"], "s": round(time.time() - s, 1), "dtype": "bf16-retry"}); report(clips=done)
