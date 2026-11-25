# GPU job: expressive Arabic/English speech with Chatterbox Multilingual (Resemble AI, MIT).
# T4: 0.5B model in fp32 (~3 GB) — one copy per GPU, lines processed on both T4s in parallel.
# PARAMS: {"lang":"ar","voice":"ref.wav" (optional reference clip in IN/, own voice or consented only),
#          "lines":[{"id":"vo1","text":"...","exaggeration":0.5,"cfg":0.5}]}
# Emotion: exaggeration 0.25 calm … 0.5 neutral … 0.7-1.0 dramatic (lower cfg to ~0.3 to keep pace).
import subprocess, sys
# chatterbox pins old torch; install it without deps into the image's torch, then its light deps.
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "chatterbox-tts==0.1.7"], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "s3tokenizer", "conformer==0.3.2", "resemble-perth",
                "librosa", "spacy-pkuseg", "pykakasi", "pyloudnorm"], check=True)
import torch, torchaudio
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
LINES = shard(PARAMS["lines"])          # 0.5B model: one copy per T4, lines split across both GPUs
t = time.time(); m = ChatterboxMultilingualTTS.from_pretrained(device="cuda"); report(load_s=round(time.time() - t, 1))
ref = str(IN / PARAMS["voice"]) if PARAMS.get("voice") else None
done = []
for ln in LINES:
    s = time.time()
    wav = m.generate(ln["text"], language_id=PARAMS.get("lang", "ar"), audio_prompt_path=ref,
                     exaggeration=ln.get("exaggeration", 0.5), cfg_weight=ln.get("cfg", 0.5))
    torchaudio.save(str(OUT / f"{ln['id']}.wav"), wav.cpu(), m.sr)
    done.append({"id": ln["id"], "s": round(time.time() - s, 1)}); report(lines=done)
