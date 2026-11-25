# GPU job: text-to-image, tuned for Kaggle's 2x Tesla T4 (14.6 GB each, sm75).
# PARAMS: {"model": "sdxl" | "zimage", "items": [{"id","prompt","negative","width","height","seed"}], "steps": N,
#          "item_budget_s": 240, "max_job_s": 3600}
#   sdxl    DEFAULT on T4. SDXL base 1.0 (OpenRAIL++) + fp16-fix VAE (MIT): native fp16, ~7 GB, one copy per T4 so
#           both GPUs work in parallel, 28 steps. Reliable on the free tier.
#   zimage  ADVANCED (optional). Z-Image-Turbo 6B (Apache-2.0): 12 GB transformer — on T4 it needs both GPUs +
#           fp8 weights (OOM in bf16, measured). Falls back to SDXL automatically on any failure.
# Every image is checked for NaN/black output (fp16 overflow) and retried once in a safer mode.
import os, subprocess, sys
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "diffusers==0.43.0", "accelerate", "transformers",
                "safetensors"], check=True)
import torch
MODELS = {"zimage": ("Tongyi-MAI/Z-Image-Turbo", "f332072aa78b"),
          "sdxl": ("stabilityai/stable-diffusion-xl-base-1.0", "462165984030")}
model = PARAMS.get("model") or ("sdxl" if is_t4() else "zimage")


def gen_zimage(items):
    from diffusers import ZImagePipeline
    t = time.time()
    dtype = pick_dtype(fp16_safe=False)          # Z-Image is trained in bf16; fp16 only if PARAMS dtype=fp16
    pipe = load_pipe(ZImagePipeline, *MODELS["zimage"], dtype)
    vae_tiling(pipe)
    report(load_s=round(time.time() - t, 1), dtype=str(dtype), model="z-image-turbo")
    done = []
    for it in items:
        s = time.time()
        g = torch.Generator("cpu").manual_seed(it.get("seed", 0))
        img = pipe(prompt=it["prompt"], height=it.get("height", 720), width=it.get("width", 1280),
                   num_inference_steps=PARAMS.get("steps", 8), guidance_scale=0.0, generator=g).images[0]
        if looks_broken(img):
            raise RuntimeError(f"{it['id']}: black/NaN output")
        img.save(OUT / f"{it['id']}.png"); done.append({"id": it["id"], "s": round(time.time() - s, 1)})
        report(images=done)


def gen_sdxl(items):
    from diffusers import StableDiffusionXLPipeline, AutoencoderKL
    items = shard(items)                         # one SDXL copy per T4
    t = time.time()
    vae = AutoencoderKL.from_pretrained("madebyollin/sdxl-vae-fp16-fix", revision="207b116dae70", torch_dtype=torch.float16)
    pipe = StableDiffusionXLPipeline.from_pretrained(MODELS["sdxl"][0], revision=MODELS["sdxl"][1], vae=vae,
                                                     torch_dtype=torch.float16, variant="fp16").to("cuda")
    vae_tiling(pipe)                             # diffusers 0.43: tiling lives on the VAE
    report(load_s=round(time.time() - t, 1), dtype="torch.float16", model="sdxl-base-1.0")
    done = []
    neg = "blurry, lowres, deformed, extra fingers, watermark, text, logo"
    steps = PARAMS.get("steps_sdxl", 28)
    done, failed = [], []
    for it in items:
        w, h = it.get("width", 1344), it.get("height", 768)
        w, h = (1344, 768) if w > h else ((768, 1344) if h > w else (1024, 1024))   # SDXL-native buckets
        for attempt in range(2):                 # one retry with another seed on NaN/black output
            s = time.time()
            try:
                img = pipe(prompt=it["prompt"], negative_prompt=it.get("negative", neg), width=w, height=h,
                           num_inference_steps=steps, guidance_scale=6.0,
                           callback_on_step_end=step_guard(steps, PARAMS.get("item_budget_s", 240), it["id"]),
                           generator=torch.Generator("cuda").manual_seed(it.get("seed", 0) + attempt)).images[0]
            except (FloatingPointError, TimeoutError) as e:
                failed.append({"id": it["id"], "why": str(e)}); break
            if not looks_broken(img):
                img.save(OUT / f"{it['id']}.png")
                done.append({"id": it["id"], "s": round(time.time() - s, 1), "size": f"{w}x{h}", "attempt": attempt + 1})
                break
        else:
            failed.append({"id": it["id"], "why": "black/NaN output twice"})
        report(images=done, failed=failed)


err = None
if model == "zimage":
    try:
        gen_zimage(PARAMS["items"])
    except Exception as e:                       # OOM or broken output on this GPU → light model, same items
        err = f"{type(e).__name__}: {str(e)[:300]}"
    if err:                                      # outside the except block so the Z-Image pipeline is freed
        import gc; gc.collect(); torch.cuda.empty_cache()
        report(zimage_failed=err, fallback="sdxl")
        PARAMS["items"] = [it for it in PARAMS["items"] if not (OUT / f"{it['id']}.png").exists()]
        PARAMS["model"] = "sdxl"                 # per-GPU children re-run this file: send them straight to SDXL
        gen_sdxl(PARAMS["items"])
else:
    gen_sdxl(PARAMS["items"])
