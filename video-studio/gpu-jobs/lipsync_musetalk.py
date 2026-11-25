# GPU job: lip-sync a face video or still to speech with MuseTalk 1.5 (Tencent Lyra Lab, MIT).
# PARAMS: {"items":[{"id":"shot03","video":"face.mp4" or "face.png","audio":"vo3.wav"}]}  (files in IN/)
# Consent rule: only faces the person owns, AI-generated people, or people who agreed in writing.
#
# Reviewed 2026-11-25 at commit 2536eaf: upstream download_weights.sh routes Hugging Face through a
# third-party mirror (hf-mirror.com) and pulls a Google Drive file; requirements.txt pins TensorFlow 2.12
# and old diffusers. This job therefore downloads every weight itself from the official sources and installs
# only what inference needs. Weights: MuseTalk (MIT), sd-vae-ft-mse (MIT), whisper-tiny (Apache-2.0),
# DWPose (Apache-2.0), face-parsing BiSeNet (WTFPL re-upload), resnet18 (BSD-3).
import subprocess, sys, urllib.request
SRC, REF = "https://github.com/TMElyralab/MuseTalk.git", "2536eaf06b85f775d8e04b7fd81bf6699155a58d"
W = "/kaggle/temp/MuseTalk"
subprocess.run(["git", "clone", "-q", SRC, W], check=True)
subprocess.run(["git", "-C", W, "checkout", "-q", REF], check=True)
pip = [sys.executable, "-m", "pip", "install", "-q"]
subprocess.run(pip + ["diffusers==0.30.2", "accelerate", "einops", "omegaconf", "ffmpeg-python", "moviepy",
                      "soundfile", "librosa", "imageio[ffmpeg]", "huggingface_hub", "openmim"], check=True)
subprocess.run([sys.executable, "-m", "mim", "install", "-q", "mmengine", "mmcv==2.1.0", "mmdet==3.2.0", "mmpose==1.3.2"], check=False)
from huggingface_hub import hf_hub_download
M = f"{W}/models"
for repo, files, sub in [
    ("TMElyralab/MuseTalk", ["musetalkV15/musetalk.json", "musetalkV15/unet.pth"], ""),
    ("stabilityai/sd-vae-ft-mse", ["config.json", "diffusion_pytorch_model.bin"], "sd-vae"),
    ("openai/whisper-tiny", ["config.json", "pytorch_model.bin", "preprocessor_config.json"], "whisper"),
    ("yzd-v/DWPose", ["dw-ll_ucoco_384.pth"], "dwpose"),
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
                "--version", "v15"], cwd=W, check=True)
report(lipsync_s=round(time.time() - t, 1), outputs=[p.name for p in OUT.rglob("*.mp4")], musetalk_ref=REF)
