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
# Wan2.1-1.3B on T4 (measured 2026-11-25, 832x480x81, full CFG, model CPU offload): 63-71 s/step, 14.0 GB peak ->
#   ~24 min per clip, aborted by the guard. Now: prompts encoded first (UMT5 freed), whole 1.3B model resident on
#   the GPU (no offload), 49 frames by default, optional CFG cut-off (cfg_until: fraction of steps that use CFG; the
#   rest run one pass instead of two), optional First-Block-Cache (cache: threshold, diffusers built-in, no new
#   model), one clip per T4 (2 in parallel), memory freed after a failed clip. probe items (probe: true) time a few
#   steps of a configuration without decoding, for benchmarks.
#
# Presets (per-item width/height/frames override them). Wan generates 16 fps; vs-produce conforms the frame rate.
#   t4       832x480, 49 frames (3.1 s @16), 20 steps  — default on T4
#   t4-long  832x480, 81 frames (5.1 s @16), 20 steps  — ~1.7x the time of t4
#   t4-fast  832x480, 33 frames (2.1 s @16), 16 steps  — drafts and short cutaways
#   hq       1280x704, 121 frames, 30 steps            — only on bigger GPUs (L4/A100); hours per clip on T4
import os, subprocess, sys
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "diffusers==0.43.0", "accelerate", "transformers", "ftfy",
                "imageio-ffmpeg"], check=True)
import torch
from diffusers.utils import export_to_video, load_image

PRESETS = {"t4": (832, 480, 49, 20), "t4-long": (832, 480, 81, 20), "t4-fast": (832, 480, 33, 16),
           "hq": (1280, 704, 121, 30)}
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
ITEMS = PARAMS["items"]
if model == "wan21-1.3b" and len(ITEMS) > 1:
    ITEMS = shard(ITEMS)                 # one process per T4: two clips at once (parent waits, then stops here)


def host_ram_gb():
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30
    except (ValueError, OSError):
        return 64.0


LOW_RAM = bool(PARAMS.get("low_ram", host_ram_gb() < 20))
TEXT_FIRST = LOW_RAM or model == "wan21-1.3b"   # encode prompts, free the 11 GB encoder, then load the rest
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
        for it in ITEMS:
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
    vae = AutoencoderKLWan.from_pretrained(repo, subfolder="vae", revision=rev, torch_dtype=torch.float32)
    if TEXT_FIRST:
        if not EMB:
            t = time.time(); pre_encode(dtype); report(encode_s=round(time.time() - t, 1))
        if model == "wan21-1.3b":       # 2.6 GB transformer + VAE stay on the GPU: no CPU round-trips per step
            t2v = WanPipeline.from_pretrained(repo, revision=rev, vae=vae, text_encoder=None, torch_dtype=dtype).to("cuda")
            report(placement="whole model on one T4 (prompts encoded first, text encoder freed)")
        else:
            t2v = load_pipe(WanPipeline, repo, rev, dtype, fp8_ok=False, prefer=PARAMS.get("placement", "offload"),
                            vae=vae, text_encoder=None)
    else:
        # Measured on 2x T4 (balanced + fp8): denoise 7.8 s/step, but the VAE landed off-GPU (decode ~62 min) and
        # fp16 output was black. So: one T4 with model CPU offload, VAE on the GPU, no fp8.
        t2v = load_pipe(WanPipeline, repo, rev, dtype, fp8_ok=False, prefer=PARAMS.get("placement", "offload"), vae=vae)
    vae_tiling(t2v)
    i2v = WanImageToVideoPipeline(**t2v.components) if model == "wan22-5b" else None
    return t2v, i2v


CACHE = {"thr": None}


def set_cache(tr, thr):
    """First-Block-Cache (diffusers built-in): skip the rest of the transformer when the first block barely changes."""
    if thr == CACHE["thr"]:
        if thr:
            tr._reset_stateful_cache()
        return
    try:
        tr.disable_cache()
    except Exception:
        pass
    if thr:
        from diffusers.hooks import FirstBlockCacheConfig
        tr.enable_cache(FirstBlockCacheConfig(threshold=float(thr)))
    CACHE["thr"] = thr


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
    if TEXT_FIRST:                           # embeddings made by pre_encode (text encoder already freed)
        pe, ne = EMB[it["id"]]
        txt = dict(prompt_embeds=pe.to("cuda", dtype), negative_prompt_embeds=ne.to("cuda", dtype))
    else:
        txt = dict(prompt=it["prompt"], negative_prompt=it.get("negative", NEG))
    steps = PARAMS.get("probe_steps", 4) if it.get("probe") else it.get("steps", PARAMS.get("steps", PS))
    cfg = it.get("cfg", 5.0)
    cut = int(round(steps * float(it.get("cfg_until", PARAMS.get("cfg_until", 1.0))))) if cfg > 1 else 0
    kw = dict(**txt, height=h, width=w, num_frames=f, guidance_scale=cfg if cut else 1.0,
              num_inference_steps=steps, generator=torch.Generator("cpu").manual_seed(it.get("seed", 0)))
    if it.get("probe"):
        kw["output_type"] = "latent"
    weights = [2 if i < cut else 1 for i in range(steps)]
    g = step_guard(steps, it.get("budget_s", PARAMS.get("item_budget_s", 1500)), it["id"], weights)

    def cb(pipe, i, t, k):
        k = g(pipe, i, t, k)
        if i + 1 >= cut:
            pipe._guidance_scale = 1.0       # CFG off for the remaining steps: one transformer pass instead of two
        return k
    kw["callback_on_step_end"] = cb; LAST.update(guard=g, passes=sum(weights), cut=cut, steps=steps)
    set_cache(t2v.transformer, it.get("cache", PARAMS.get("cache")))
    if it.get("image") and i2v is not None and model == "wan22-5b":
        frames = i2v(image=load_image(str(IN / it["image"])).resize((w, h)), **kw).frames[0]
    else:
        frames = t2v(**kw).frames[0]
    return frames, (w, h, f)


def timing(total):
    st = LAST["guard"].stats
    return {"steps": LAST["steps"], "cfg_steps": LAST["cut"], "cache": CACHE["thr"], "denoise_s": st["denoise_s"],
            "s_per_step": round(st["denoise_s"] / max(1, st["steps"]), 2),
            "s_per_pass": round(st["denoise_s"] / max(1, LAST["passes"]), 2), "decode_s": round(total - st["denoise_s"], 1),
            "vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2)}


def free():
    import gc
    gc.collect(); torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()


t = time.time()
dtype = pick_dtype(fp16_safe=True)
pipes = build(dtype)
report(load_s=round(time.time() - t, 1), dtype=str(dtype), model=model, preset=preset, low_ram=LOW_RAM,
       host_ram_gb=round(host_ram_gb(), 1))
done, redo, failed, probes = [], [], [], []
try:
    from torch.nn.attention import SDPBackend  # which attention kernels this torch build offers on T4
    report(sdpa={"flash": torch.backends.cuda.flash_sdp_enabled(), "mem_efficient": torch.backends.cuda.mem_efficient_sdp_enabled(),
                 "torch": torch.__version__})
except Exception:
    pass
for it in ITEMS:
    s = time.time(); free()
    try:
        frames, dims = render(pipes, it, dtype)
    except FloatingPointError as e:
        redo.append(it); report(clips=done, broken_fp16=[r["id"] for r in redo], nan=str(e)); free(); continue
    except TimeoutError as e:                # too slow for this hardware: give up on this clip, keep quota
        failed.append({"id": it["id"], "why": str(e)}); report(clips=done, failed=failed); free(); continue
    except torch.OutOfMemoryError as e:
        failed.append({"id": it["id"], "why": "out of GPU memory: " + str(e)[:160]}); report(clips=done, failed=failed)
        free(); continue
    if it.get("probe"):
        probes.append({"id": it["id"], "size": f"{dims[0]}x{dims[1]}", "frames": dims[2], **timing(time.time() - s)})
        report(probes=probes); continue
    if looks_broken(frames[len(frames) // 2]):
        redo.append(it); report(clips=done, broken_fp16=[r["id"] for r in redo]); continue
    export_to_video(frames, str(OUT / f"{it['id']}.mp4"), fps=PARAMS.get("fps", 16))
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
        export_to_video(frames, str(OUT / f"{it['id']}.mp4"), fps=PARAMS.get("fps", 16))
        done.append({"id": it["id"], "s": round(time.time() - s, 1), "dtype": "bf16-retry", **timing(time.time() - s)}); report(clips=done)
if not done and not probes:
    report(error="no clip was produced: " + "; ".join(f"{f['id']}: {f['why']}" for f in failed))
