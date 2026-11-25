"""vs-qc — automated visual + audio quality gate for a finished video. CPU only.

  vs-qc VIDEO [--preset reel|youtube|square|feed] [--script SCRIPT.txt] [--lang ar|en]
        [--production production.json] [--out-dir DIR] [--no-asr]

Checks (FAIL blocks delivery, WARN is reported):
  format     size/fps/codec/pix_fmt/faststart match the preset; audio is AAC                    FAIL
  black      no black stretch > 0.5 s (except a fade at the very start/end)                      FAIL
  freeze     no frozen picture > 2.5 s (still shots with camera moves never freeze)              WARN
  loudness   integrated -14 LUFS ±1.5, true peak ≤ -1.0 dBTP                                    FAIL
  clipping   no clipped samples                                                                  WARN
  silence    no dead air > 2.0 s inside the film                                                 WARN
  speech     Whisper transcript vs the script: word error rate ≤ 15% (ar, tashkeel-blind) / 10% (en)  FAIL
  text       OCR (Tesseract ara+eng) of each shot's on-screen text vs the plan, similarity ≥ 0.6  WARN
  character  DINOv2 similarity of each character shot to its reference sheet ≥ 0.55             WARN
Writes DIR/qc-report.json and DIR/qc-report.md. Exit 1 if any FAIL.
"""
import argparse, json, os, re, subprocess, sys, tempfile, unicodedata

VS_HOME = os.environ.get("VS_HOME", os.path.expanduser("~/.video-studio"))
PRESETS = {"reel": (1080, 1920), "youtube": (1920, 1080), "square": (1080, 1080), "feed": (1080, 1350)}
DINO = os.path.join(VS_HOME, "models", "onnx", "dinov2-small.onnx")
results = []


def add(check, status, detail, **data):
    results.append({"check": check, "status": status, "detail": detail, **data})
    print(f"  {status:4}  {check:10} {detail}")


def ff(args):
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args], capture_output=True, text=True).stderr


def probe(v):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", v],
                         capture_output=True, text=True).stdout
    return json.loads(out)


# ---------------------------------------------------------------- format
def check_format(v, preset):
    d = probe(v); vs = [s for s in d["streams"] if s["codec_type"] == "video"]; au = [s for s in d["streams"] if s["codec_type"] == "audio"]
    dur = float(d["format"]["duration"])
    if not vs:
        add("format", "FAIL", "no video stream"); return dur, False
    s = vs[0]; w, h = s["width"], s["height"]; fps = eval(s["r_frame_rate"])
    probs = []
    if preset and (w, h) != PRESETS[preset]:
        probs.append(f"size {w}x{h} ≠ {PRESETS[preset][0]}x{PRESETS[preset][1]}")
    if s["codec_name"] != "h264": probs.append(f"codec {s['codec_name']}")
    if s.get("pix_fmt") != "yuv420p": probs.append(f"pix_fmt {s.get('pix_fmt')}")
    if not (23.9 <= fps <= 60.1): probs.append(f"fps {fps:.2f}")
    if not au: probs.append("no audio")
    elif au[0]["codec_name"] != "aac": probs.append(f"audio {au[0]['codec_name']}")
    with open(v, "rb") as f:
        head = f.read(1 << 16)
    if head.find(b"moov") == -1 or (head.find(b"mdat") != -1 and head.find(b"moov") > head.find(b"mdat")):
        probs.append("not faststart")
    add("format", "FAIL" if probs else "PASS", "; ".join(probs) or f"{w}x{h} {fps:.0f}fps h264/aac {dur:.1f}s",
        width=w, height=h, fps=fps, duration=dur)
    return dur, bool(au)


# ---------------------------------------------------------------- picture
def check_black(v, dur):
    log = ff(["-i", v, "-vf", "blackdetect=d=0.5:pix_th=0.10", "-an", "-f", "null", "-"])
    spans = [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", log)]
    bad = [s for s in spans if not (s[0] < 0.05 or s[1] > dur - 0.05)]
    add("black", "FAIL" if bad else "PASS", f"{len(bad)} black stretch(es) inside the film" if bad else "none", spans=bad)


def check_freeze(v):
    log = ff(["-i", v, "-vf", "scale=320:-2,freezedetect=n=0.001:d=2.5", "-an", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", log)]
    add("freeze", "WARN" if starts else "PASS", f"frozen picture at {', '.join(f'{s:.1f}s' for s in starts)}" if starts else "none",
        at=starts)


# ---------------------------------------------------------------- sound
def check_audio(v, dur):
    log = ff(["-i", v, "-vn", "-af", "ebur128=peak=true,astats=metadata=0", "-f", "null", "-"])
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", log); tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", log)
    lufs = float(i[-1]) if i else None; peak = float(tp[-1]) if tp else None
    ok = lufs is not None and abs(lufs + 14) <= 1.5 and (peak is None or peak <= -1.0)
    add("loudness", "PASS" if ok else "FAIL", f"{lufs} LUFS, true peak {peak} dBTP (target -14 / ≤ -1.0)", lufs=lufs, true_peak=peak)
    clips = re.findall(r"Number of samples clipped: (\d+)", log) or re.findall(r"Peak count: (\d+)", log)
    maxlev = re.findall(r"Peak level dB: (-?[\d.inf]+)", log)
    clipped = maxlev and maxlev[-1] not in ("-inf",) and float(maxlev[-1]) >= -0.01
    add("clipping", "WARN" if clipped else "PASS", f"peak sample {maxlev[-1] if maxlev else '?'} dBFS")
    log = ff(["-i", v, "-vn", "-af", "silencedetect=n=-45dB:d=2.0", "-f", "null", "-"])
    sil = [(float(a), float(b)) for a, b in zip(re.findall(r"silence_start: ([\d.]+)", log), re.findall(r"silence_end: ([\d.]+)", log))]
    inner = [s for s in sil if s[0] > 0.3 and s[1] < dur - 0.3]
    add("silence", "WARN" if inner else "PASS", f"dead air at {', '.join(f'{a:.1f}-{b:.1f}s' for a, b in inner)}" if inner else "none")


AR_DIAC = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")


def norm(t, lang):
    t = unicodedata.normalize("NFKC", t)
    if lang == "ar":
        t = AR_DIAC.sub("", t)
        t = re.sub("[إأآٱ]", "ا", t); t = t.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
        t = re.sub(r"[٠-٩]", lambda m: str("٠١٢٣٤٥٦٧٨٩".index(m.group())), t)
    t = t.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def check_speech(v, script, lang):
    import jiwer
    sub = os.path.join(os.environ.get("VS_SKILLS", ""), "auto-subtitles", "scripts", "subtitle.py")
    py = os.path.join(VS_HOME, "venv", "bin", "python")
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run([py, sub, v, "--transcribe-only", "--lang", lang, "--out-dir", td, "--model",
                            os.environ.get("VS_QC_WHISPER", "large-v3-turbo")], capture_output=True, text=True)
        txt = ""
        for f in os.listdir(td):
            if f.endswith(".words.json"):
                txt = " ".join(w["word"] for w in json.load(open(os.path.join(td, f), encoding="utf-8")))
    if not txt:
        add("speech", "FAIL", f"no transcript ({r.stderr.strip()[-200:]})"); return
    ref, hyp = norm(script, lang), norm(txt, lang)
    wer = jiwer.wer(ref, hyp) if ref else 1.0
    lim = 0.15 if lang == "ar" else 0.10
    add("speech", "PASS" if wer <= lim else "FAIL", f"word error rate {wer:.0%} (limit {lim:.0%})", wer=wer, heard=txt.strip()[:2000])


# ---------------------------------------------------------------- planned shots: on-screen text, characters
def frame_at(v, t, path):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", v, "-frames:v", "1", path], check=True)


def check_text(v, shots, lang):
    from difflib import SequenceMatcher
    with tempfile.TemporaryDirectory() as td:
        for s in shots:
            want = s.get("onscreen_text")
            if not want or "t_mid" not in s:
                continue
            p = os.path.join(td, f"{s['id']}.png"); frame_at(v, s["t_mid"], p)
            got = subprocess.run(["tesseract", p, "-", "-l", "ara+eng", "--psm", "6"], capture_output=True, text=True).stdout
            a, b = norm(want, "ar"), norm(got, "ar")
            score = max((SequenceMatcher(None, a, b[i:i + len(a)]).ratio() for i in range(0, max(1, len(b) - len(a) + 1), 3)), default=0)
            add("text", "PASS" if score >= 0.6 else "WARN", f"{s['id']}: '{want[:40]}' similarity {score:.2f}", shot=s["id"], score=score)


def dino_embed(sess, path):
    import numpy as np
    from PIL import Image
    x = np.asarray(Image.open(path).convert("RGB").resize((224, 224), Image.BICUBIC), dtype=np.float32) / 255.0
    x = ((x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]).transpose(2, 0, 1)[None].astype(np.float32)
    out = sess.run(None, {sess.get_inputs()[0].name: x})
    e = out[1].reshape(-1) if len(out) > 1 and out[1].size >= 384 else out[0][0, 0]
    return e / (np.linalg.norm(e) + 1e-9)


def check_characters(v, shots, chars, base):
    if not chars or not os.path.exists(DINO):
        return
    import numpy as np, onnxruntime as ort
    sess = ort.InferenceSession(DINO, providers=["CPUExecutionProvider"])
    refs = {n: [dino_embed(sess, os.path.join(base, r)) for r in c.get("refs", [])] for n, c in chars.items()}
    with tempfile.TemporaryDirectory() as td:
        for s in shots:
            for n in s.get("characters", []):
                if not refs.get(n) or "t_mid" not in s:
                    continue
                p = os.path.join(td, f"{s['id']}.png"); frame_at(v, s["t_mid"], p)
                e = dino_embed(sess, p); sim = max(float(np.dot(e, r)) for r in refs[n])
                add("character", "PASS" if sim >= 0.55 else "WARN", f"{s['id']}: {n} similarity {sim:.2f}", shot=s["id"], sim=sim)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video"); ap.add_argument("--preset", choices=list(PRESETS)); ap.add_argument("--script")
    ap.add_argument("--lang", default="ar"); ap.add_argument("--production"); ap.add_argument("--out-dir")
    ap.add_argument("--no-asr", action="store_true")
    a = ap.parse_args()
    out = a.out_dir or os.path.dirname(os.path.abspath(a.video))
    prod = json.load(open(a.production, encoding="utf-8")) if a.production else {}
    preset = a.preset or prod.get("format")
    lang = prod.get("lang", a.lang)
    print(f"QC {a.video}")
    dur, has_audio = check_format(a.video, preset)
    check_black(a.video, dur); check_freeze(a.video)
    if has_audio:
        check_audio(a.video, dur)
        script = open(a.script, encoding="utf-8").read() if a.script else " ".join(s.get("vo", "") for s in prod.get("shots", []))
        if script.strip() and not a.no_asr:
            check_speech(a.video, script, lang)
    shots = prod.get("_timeline", [])
    base = os.path.dirname(os.path.abspath(a.production)) if a.production else "."
    check_text(a.video, shots, lang); check_characters(a.video, shots, prod.get("characters", {}), base)
    fails = [r for r in results if r["status"] == "FAIL"]; warns = [r for r in results if r["status"] == "WARN"]
    verdict = "FAIL" if fails else "PASS"
    rep = {"video": os.path.abspath(a.video), "verdict": verdict, "fails": len(fails), "warns": len(warns), "checks": results}
    os.makedirs(out, exist_ok=True)
    json.dump(rep, open(os.path.join(out, "qc-report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    with open(os.path.join(out, "qc-report.md"), "w", encoding="utf-8") as f:
        f.write(f"# QC: {os.path.basename(a.video)} — **{verdict}**\n\n| Check | Status | Detail |\n|---|---|---|\n")
        for r in results:
            f.write(f"| {r['check']} | {r['status']} | {r['detail']} |\n")
    print(f"verdict: {verdict}  (FAIL {len(fails)}, WARN {len(warns)})  → {out}/qc-report.md")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
