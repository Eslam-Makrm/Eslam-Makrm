# GPU job: lip-sync a face video or still to speech with MuseTalk 1.5 (Tencent Lyra Lab, MIT).
# PARAMS: {"items":[{"id":"shot03","video":"face.mp4" or "face.png","audio":"vo3.wav"}]}  (files in IN/)
# T4: fp16 inference (--use_float16), single GPU (~5 GB).
# Consent rule: only faces the person owns, AI-generated people, or people who agreed in writing.
#
# Reviewed 2026-11-25 at commit 2536eaf: upstream download_weights.sh routes Hugging Face through a
# third-party mirror (hf-mirror.com) and pulls a Google Drive file; requirements.txt pins TensorFlow 2.12
# and old diffusers. This job therefore downloads every weight itself from the official sources and installs
# only what inference needs. Weights: MuseTalk (MIT), sd-vae-ft-mse (MIT), whisper-tiny (Apache-2.0),
# face-parsing BiSeNet (WTFPL re-upload), resnet18 (BSD-3). S3FD face detector (BSD-3, via torch hub).
import os, subprocess, sys, urllib.request
SRC, REF = "https://github.com/TMElyralab/MuseTalk.git", "2536eaf06b85f775d8e04b7fd81bf6699155a58d"
W = "/kaggle/temp/MuseTalk"
subprocess.run(["git", "clone", "-q", SRC, W], check=True)
subprocess.run(["git", "-C", W, "checkout", "-q", REF], check=True)
pip = [sys.executable, "-m", "pip", "install", "-q"]
subprocess.run(pip + ["diffusers==0.30.2", "accelerate", "einops", "omegaconf", "ffmpeg-python", "moviepy",
                      "soundfile", "librosa", "imageio[ffmpeg]", "huggingface_hub"], check=True)
# Measured 2026-11-25 on Kaggle (Python 3.13, torch 2.11): openmim crashes on import (pkgutil.ImpImporter is gone)
# and mmcv 2.1 has no build for this stack, so mmpose/DWPose cannot be installed. MuseTalk only uses DWPose to
# refine the face crop; upstream already falls back to the S3FD face box when landmarks are unusable. Patch:
# drop the mmpose import + model and always use the face box (bbox_shift still applies). No extra model.
PRE = f"{W}/musetalk/utils/preprocessing.py"
src = open(PRE).read()
for line in ("from mmpose.apis import inference_topdown, init_model\n", "from mmpose.structures import merge_data_samples\n",
             "model = init_model(config_file, checkpoint_file, device=device)\n"):
    assert line in src, f"MuseTalk changed upstream: {line!r} not found"
    src = src.replace(line, "")
src += """

def get_landmark_and_bbox(img_list, upperbondrange=0):   # video-studio patch: S3FD face box, no mmpose
    frames = read_imgs(img_list)
    coords_list = []
    for fr in frames:
        f = fa.get_detections_for_batch(np.asarray([fr]))[0]
        if f is None:
            coords_list.append(coord_placeholder)
            continue
        x1, y1, x2, y2 = [int(v) for v in f]
        coords_list.append((x1, max(0, y1 + int(upperbondrange)), x2, y2))
    return coords_list, frames
"""
open(PRE, "w").write(src)
import shutil
if not shutil.which("ffmpeg"):                  # MuseTalk shells out to ffmpeg for frames and the final mux
    import imageio_ffmpeg
    os.makedirs("/kaggle/temp/bin", exist_ok=True)
    if not os.path.exists("/kaggle/temp/bin/ffmpeg"):
        os.symlink(imageio_ffmpeg.get_ffmpeg_exe(), "/kaggle/temp/bin/ffmpeg")
    os.environ["PATH"] = "/kaggle/temp/bin:" + os.environ["PATH"]
from huggingface_hub import hf_hub_download
M = f"{W}/models"
for repo, files, sub in [
    ("TMElyralab/MuseTalk", ["musetalkV15/musetalk.json", "musetalkV15/unet.pth"], ""),
    ("stabilityai/sd-vae-ft-mse", ["config.json", "diffusion_pytorch_model.bin"], "sd-vae"),
    ("openai/whisper-tiny", ["config.json", "pytorch_model.bin", "preprocessor_config.json"], "whisper"),
]:
    for f in files:
        hf_hub_download(repo, f, local_dir=f"{M}/{sub}" if sub else M)
# face-parsing BiSeNet weights (HF re-upload, WTFPL; upstream uses a Google Drive link)
import os
os.makedirs(f"{M}/face-parse-bisent", exist_ok=True)
try:
    hf_hub_download("ManyOtherFunctions/face-parse-bisent", "79999_iter.pth", local_dir=f"{M}/face-parse-bisent")
except Exception as e:
    report(face_parse_warning=f"BiSeNet weights not found on HF ({e}); review a source before production use")
urllib.request.urlretrieve("https://download.pytorch.org/models/resnet18-5c106cde.pth", f"{M}/face-parse-bisent/resnet18-5c106cde.pth")
import yaml
cfg = {it["id"]: {"video_path": str(IN / it["video"]), "audio_path": str(IN / it["audio"])} for it in PARAMS["items"]}
open(f"{W}/vs_task.yaml", "w").write(yaml.safe_dump(cfg))
t = time.time()
subprocess.run([sys.executable, "-m", "scripts.inference", "--inference_config", "vs_task.yaml", "--result_dir", str(OUT),
                "--unet_model_path", "models/musetalkV15/unet.pth", "--unet_config", "models/musetalkV15/musetalk.json",
                "--version", "v15", *(["--use_float16"] if PARAMS.get("fp16", True) else [])], cwd=W, check=True)
report(lipsync_s=round(time.time() - t, 1), outputs=[str(p.relative_to(OUT)) for p in OUT.rglob("*.mp4")], musetalk_ref=REF,
       face_crop="S3FD face box (DWPose landmarks unavailable on this image)")
