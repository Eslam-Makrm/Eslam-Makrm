# GPU job: lip-sync a face video or still to speech with MuseTalk 1.5 (Tencent Lyra Lab, MIT).
# PARAMS: {"items":[{"id":"shot03","video":"face.mp4" or "face.png","audio":"vo3.wav"}]}  (files in IN/)
# Consent rule: only faces the person owns, AI-generated people, or people who agreed in writing.
import subprocess, sys
SRC = "https://github.com/TMElyralab/MuseTalk.git"; SRC_REF = "main"   # pin to a commit after the first GPU test
subprocess.run(["git", "clone", "-q", "--depth", "1", "-b", SRC_REF, SRC, "/kaggle/temp/MuseTalk"], check=True)
W = "/kaggle/temp/MuseTalk"
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", f"{W}/requirements.txt"], check=False)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "huggingface_hub", "mmengine", "openmim"], check=True)
subprocess.run(["bash", "-lc", f"cd {W} && bash download_weights.sh"], check=True)
import yaml
cfg = {it["id"]: {"video_path": str(IN / it["video"]), "audio_path": str(IN / it["audio"])} for it in PARAMS["items"]}
open(f"{W}/vs_task.yaml", "w").write(yaml.safe_dump(cfg))
t = time.time()
subprocess.run([sys.executable, "-m", "scripts.inference", "--inference_config", "vs_task.yaml", "--result_dir", str(OUT),
                "--unet_model_path", "models/musetalkV15/unet.pth", "--unet_config", "models/musetalkV15/musetalk.json",
                "--version", "v15"], cwd=W, check=True)
report(lipsync_s=round(time.time() - t, 1), outputs=[p.name for p in OUT.rglob("*.mp4")])
