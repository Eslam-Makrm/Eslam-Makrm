# GPU job: text-to-video and image-to-video, tuned for Kaggle's 2x Tesla T4 (14.6 GB each, sm75).
# PARAMS: {"model": "wan21-1.3b" | "wan22-5b", "preset": "t4" | "t4-fast" | "hq", "allow_heavy": false,
#          "item_budget_s": 1500, "max_job_s": 5400,
#          "items": [{"id","prompt","image"? (keyframe in IN/ -> image-to-video),"frames","width","height","seed"}],
#          "steps": N, "fps": 24, "dtype": "auto"|"fp16"|"bf16"}
#
#   wan21-1.3b DEFAULT on T4. Wan2.1-T2V-1.3B (Apache-2.0): light text-to-video at 480p; text-only.
#   wan22-5b   ADVANCED (optional, allow_heavy). Wan2.2-TI2V-5B (Apache-2.0): text- AND image-to-video.
#              Measured on T4 (balanced + fp8): 7.8 s/step, VAE decode off-GPU ~62 min, black fp16 output.
#   Both: one T4, model CPU offload (UMT5 encodes then swaps out), fp16 compute (T4 has no native bf16),
#   VAE tiling, per-step guard (NaN latents or projected time > item_budget_s stops the clip early),
#   clips with NaN are redone once in bf16; hard job budget max_job_s.
#   Low host RAM (< 20 GB, e.g. free Colab's 12.7 GB; or PARAMS low_ram): the 11 GB UMT5 text encoder would not
#   fit in RAM next to the transformer for CPU offload, so all prompts are encoded first with the encoder on the
#   GPU, the encoder is freed, and the pipeline is built without it (prompt embeddings passed in).
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
model = PARAMS.get("model") or ("wan21-1.3b" if is_t4() else "wan22-5b")
preset = PARAMS.get("preset", "t4" if is_t4() else "hq")
PW, PH, PF, PS = PRESETS[preset]
NEG = "blurry, low quality, distorted face, extra limbs, watermark, text, subtitles, static frame, flicker"
if model == "wan21-1.3b" and any(it.get("image") for it in PARAMS["items"]):
    if PARAMS.get("allow_heavy"):
        model = "wan22-5b"                   # only the 5B model can animate a keyframe
        report(note="image-to-video requested: using wan22-5b (allow_heavy)")
    else:
        report(note="wan21-1.3b is text-only: keyframes ignored (set allow_heavy for wan22-5b image-to-video)")


def host_ram_gb():
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30
    except (ValueError, OSError):
        return 64.0


LOW_RAM = bool(PARAMS.get("low_ram", host_ram_gb() < 20))
EMB = {}


def pre_encode(dtype):
    """Encode every prompt + negative with UMT5 on the GPU, then free it (low-RAM hosts)."""
    from diffusers import WanPipeline
    from transformers import UMT5EncoderModel
    repo, rev = REPOS[model]
    te_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported(including_emulation=True) else dtype
    te = UMT5EncoderModel.from_pretrained(repo, subfolder="text_encoder", revision=rev, torch_dtype=te_dtype,
                                          device_map="cuda", low_cpu_mem_usage=True)
    enc = WanPipeline.from_pretrained(repo, revision=rev, text_encoder=te, transformer=None, vae=None,
                                      torch_dtype=te_dtype)
    with torch.no_grad():
        for it in PARAMS["items"]:
            pe, ne = enc.encode_prompt(prompt=it["prompt"], negative_prompt=it.get("negative", NEG),
                                       do_classifier_free_guidance=True, num_videos_per_prompt=1, device="cuda",
                                       max_sequence_length=512)   # = WanPipeline.__call__ default
            if not (torch.isfinite(pe).all() and torch.isfinite(ne).all()):
                raise FloatingPointError(f"{it['id']}: non-finite text embeddings")
            EMB[it["id"]] = (pe.to("cpu"), ne.to("cpu"))
    del enc, te
    import gc; gc.collect(); torch.cuda.empty_cache()


def build(dtype):
    from diffusers import WanPipeline, WanImageToVideoPipeline, AutoencoderKLWan
    repo, rev = REPOS[model]
    if LOW_RAM:
        if not EMB:
            pre_encode(dtype)
        t2v = load_pipe(WanPipeline, repo, rev, dtype, fp8_ok=False, prefer=PARAMS.get("placement", "offload"),
                        vae=AutoencoderKLWan.from_pretrained(repo, subfolder="vae", revision=rev,
                                                             torch_dtype=torch.float32), text_encoder=None)
        vae_tiling(t2v)
        return t2v, (WanImageToVideoPipeline(**t2v.components) if model == "wan22-5b" else None)
    vae = AutoencoderKLWan.from_pretrained(repo, subfolder="vae", revision=rev, torch_dtype=torch.float32)
    # Measured on 2x T4 (balanced + fp8): denoise 7.8 s/step, but the VAE landed off-GPU (decode ~62 min) and
    # fp16 output was black. So: one T4 with model CPU offload (UMT5 encodes, then swaps out; the 5B transformer
    # fits in fp16), VAE on the GPU, no fp8 (fp8 is only needed for >10 GB transformers).
    t2v = load_pipe(WanPipeline, repo, rev, dtype, fp8_ok=False, prefer=PARAMS.get("placement", "offload"), vae=vae)
    vae_tiling(t2v)
    i2v = WanImageToVideoPipeline(**t2v.components) if model == "wan22-5b" else None
    return t2v, i2v


def snap(v, m):
    return max(m, int(round(v / m)) * m)


LAST = {}


def render(pipes, it, dtype):
    t2v, i2v = pipes
    w, h = it.get("width", PW), it.get("height", PH)
    if h > w and (w, h) == (PW, PH):
        w, h = h, w                          # vertical
    if "width" not in it and "height" not in it and it.get("vertical"):
        w, h = PH, PW
    w, h = snap(w, 32), snap(h, 32)
    f = it.get("frames", PF); f = (f - 1) // 4 * 4 + 1
    if LOW_RAM:                              # embeddings made by pre_encode (text encoder already freed)
        pe, ne = EMB[it["id"]]
        txt = dict(prompt_embeds=pe.to("cuda", dtype), negative_prompt_embeds=ne.to("cuda", dtype))
    else:
        txt = dict(prompt=it["prompt"], negative_prompt=it.get("negative", NEG))
    kw = dict(**txt, height=h, width=w, num_frames=f,
              guidance_scale=it.get("cfg", 5.0), num_inference_steps=PARAMS.get("steps", PS),
              generator=torch.Generator("cpu").manual_seed(it.get("seed", 0)))
    g = step_guard(kw["num_inference_steps"], PARAMS.get("item_budget_s", 1500), it["id"])
    kw["callback_on_step_end"] = g; LAST["guard"] = g
    if it.get("image") and i2v is not None and model == "wan22-5b":
        frames = i2v(image=load_image(str(IN / it["image"])).resize((w, h)), **kw).frames[0]
    else:
        frames = t2v(**kw).frames[0]
    return frames, (w, h, f)


def timing(total):
    st = LAST["guard"].stats
    return {"denoise_s": st["denoise_s"], "s_per_step": round(st["denoise_s"] / max(1, st["steps"]), 2),
            "decode_s": round(total - st["denoise_s"], 1)}


t = time.time()
dtype = pick_dtype(fp16_safe=True)
pipes = build(dtype)
report(load_s=round(time.time() - t, 1), dtype=str(dtype), model=model, preset=preset, low_ram=LOW_RAM,
       host_ram_gb=round(host_ram_gb(), 1))
done, redo, failed = [], [], []
for it in PARAMS["items"]:
    s = time.time()
    try:
        frames, dims = render(pipes, it, dtype)
    except FloatingPointError as e:
        redo.append(it); report(clips=done, broken_fp16=[r["id"] for r in redo], nan=str(e)); continue
    except TimeoutError as e:                # too slow for this hardware: give up on this clip, keep quota
        failed.append({"id": it["id"], "why": str(e)}); report(clips=done, failed=failed); continue
    if looks_broken(frames[len(frames) // 2]):
        redo.append(it); report(clips=done, broken_fp16=[r["id"] for r in redo]); continue
    export_to_video(frames, str(OUT / f"{it['id']}.mp4"), fps=PARAMS.get("fps", 24))
    done.append({"id": it["id"], "s": round(time.time() - s, 1), "size": f"{dims[0]}x{dims[1]}", "frames": dims[2],
                 **timing(time.time() - s)})
    report(clips=done)
if redo and dtype == torch.float16:          # fp16 overflowed on these clips: rebuild once in bf16 (slower, exact)
    for p in pipes:
        if p is not None:
            try: p.remove_all_hooks()
            except Exception: pass
    del pipes, p
    import gc; gc.collect(); torch.cuda.empty_cache()
    t = time.time(); pipes = build(torch.bfloat16); report(bf16_load_s=round(time.time() - t, 1))
    for it in redo:
        s = time.time()
        try:
            frames, dims = render(pipes, it, torch.bfloat16)
        except (FloatingPointError, TimeoutError) as e:
            failed.append({"id": it["id"], "why": "bf16: " + str(e)}); report(failed=failed); continue
        export_to_video(frames, str(OUT / f"{it['id']}.mp4"), fps=PARAMS.get("fps", 24))
        done.append({"id": it["id"], "s": round(time.time() - s, 1), "dtype": "bf16-retry", **timing(time.time() - s)}); report(clips=done)
if not done:
    report(error="no clip was produced: " + "; ".join(f"{f['id']}: {f['why']}" for f in failed))
