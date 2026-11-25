"""CPU check of the Wan2.2-TI2V image-to-video wiring in gpu-jobs/video.py (no GPU, no model download).
Builds tiny random models shaped like Wan2.2-TI2V-5B (48-channel latents, expand_timesteps=True), takes
video.py's own make_i2v() and runs 2 denoising steps from a keyframe. Needs torch + diffusers==0.43.0."""
import ast, os, sys, torch
from PIL import Image
from diffusers import WanPipeline, AutoencoderKLWan, WanTransformer3DModel, UniPCMultistepScheduler
from transformers import UMT5Config, UMT5EncoderModel

src = open(os.path.join(os.path.dirname(__file__), "..", "gpu-jobs", "video.py")).read()
fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "make_i2v")
ns = {"model": "wan22-5b"}; exec(compile(ast.Module([fn], []), "video.py", "exec"), ns)

torch.manual_seed(0)
vae = AutoencoderKLWan(base_dim=3, z_dim=48, in_channels=12, out_channels=12, is_residual=True, patch_size=2,
                       latents_mean=[0.0] * 48, latents_std=[1.0] * 48, dim_mult=[1, 1, 1, 1], num_res_blocks=1,
                       scale_factor_spatial=16, scale_factor_temporal=4, temperal_downsample=[False, True, True])
tr = WanTransformer3DModel(patch_size=(1, 2, 2), num_attention_heads=2, attention_head_dim=12, in_channels=48,
                           out_channels=48, text_dim=32, freq_dim=256, ffn_dim=32, num_layers=2,
                           cross_attn_norm=True, qk_norm="rms_norm_across_heads", rope_max_seq_len=32)
te = UMT5EncoderModel(UMT5Config(vocab_size=64, d_model=32, d_kv=8, d_ff=32, num_layers=1, num_heads=4))
t2v = WanPipeline(tokenizer=None, text_encoder=te, vae=vae, scheduler=UniPCMultistepScheduler(), transformer=tr,
                  expand_timesteps=True)                      # as Wan2.2-TI2V-5B's model_index.json
i2v = ns["make_i2v"](t2v)
assert i2v.config.expand_timesteps, "make_i2v lost expand_timesteps"
pe = torch.randn(1, 8, 32)
out = i2v(image=Image.new("RGB", (32, 32), (200, 30, 30)), prompt_embeds=pe, negative_prompt_embeds=torch.zeros_like(pe),
          height=32, width=32, num_frames=5, num_inference_steps=2, guidance_scale=1.0,
          generator=torch.Generator("cpu").manual_seed(0), output_type="np").frames[0]
assert out.shape == (5, 32, 32, 3), out.shape
ns["model"] = "wan21-1.3b"; assert ns["make_i2v"](t2v) is None
print("PASS test_i2v_tiny: wan22-5b image-to-video wiring OK", out.shape)
