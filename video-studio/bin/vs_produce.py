"""vs-produce — turn a production.json into a finished, checked MP4. Claude writes the plan; this runs it.

  vs-produce PROJECT_DIR [--stage all|gen|voice|shots|edit|qc] [--gpu auto|kaggle|off] [--force]

PROJECT_DIR/production.json (see video-producer/reference/production-schema.md):
  title, lang (ar|en), format (reel|youtube|square|feed), fps, template,
  voice {engine: piper|chatterbox|edge|none, voice, length_scale, ref},
  music {track, volume}, grade {look, grain, vignette, letterbox}, subtitles {burn, style},
  characters {name: {refs: [...], prompt: "..."}},
  shots [{id, engine: still|clip|ai-image|ai-video, source, prompt, camera {move, parallax, amount},
          vo, emotion, dur, pad, transition, transition_dur, onscreen_text, characters}]

Stages (each resumable; outputs in PROJECT_DIR/build, deliverables in PROJECT_DIR/out):
  gen    ai-image / ai-video shots → open models on Kaggle's free GPU (vs-gpu); if no GPU is available,
         ai-video falls back to its keyframe + parallax camera move, and the route is recorded
  voice  narration per shot (Piper CPU · Chatterbox GPU · edge-tts online), durations measured
  shots  each shot conformed to size/fps/duration (stills get camera moves, clips are fit/held)
  edit   transitions, narration placement, music ducking, grade, loudness −14 LUFS, subtitles, cover
  qc     vs-qc gate (exit 1 on FAIL)
"""
import argparse, json, math, os, re, shutil, subprocess, sys, time

VS_HOME = os.environ.get("VS_HOME", os.path.expanduser("~/.video-studio"))
VS_SKILLS = os.environ.get("VS_SKILLS", "")
VS_REPO = os.environ.get("VS_REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIN = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(VS_HOME, "venv", "bin", "python")
SIZES = {"reel": (1080, 1920), "youtube": (1920, 1080), "square": (1080, 1080), "feed": (1080, 1350)}
XFADES = {"cut", "fade", "fadeblack", "fadewhite", "dissolve", "wipeleft", "wiperight", "wipeup", "wipedown",
          "slideleft", "slideright", "slideup", "slidedown", "smoothleft", "smoothright", "circleopen", "circleclose",
          "radial", "zoomin", "hblur", "pixelize", "distance", "squeezeh", "squeezev", "coverleft", "coverright",
          "revealleft", "revealright", "diagtl", "diagbr"}


def log(*a):
    print("[vs-produce]", *a, file=sys.stderr, flush=True)


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode:
        raise SystemExit(f"command failed: {' '.join(map(str, cmd))[:300]}\n{r.stderr[-1500:]}")
    return r.stdout


def dur_of(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).strip())


def has_audio(path):
    return bool(run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", path]).strip())


class Project:
    def __init__(self, d):
        self.d = os.path.abspath(d)
        self.pf = os.path.join(self.d, "production.json")
        self.p = json.load(open(self.pf, encoding="utf-8"))
        self.b = os.path.join(self.d, "build"); self.o = os.path.join(self.d, "out")
        for x in ("", "vo", "shots", "gen", "edit"):
            os.makedirs(os.path.join(self.b, x), exist_ok=True)
        os.makedirs(self.o, exist_ok=True)
        self.W, self.H = SIZES[self.p.get("format", "youtube")]
        self.fps = int(self.p.get("fps", 30))
        self.route_f = os.path.join(self.b, "route.json")
        self.route = json.load(open(self.route_f)) if os.path.exists(self.route_f) else {}

    def path(self, rel):
        return rel if os.path.isabs(rel) else os.path.join(self.d, rel)

    def save(self):
        json.dump(self.p, open(self.pf, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        json.dump(self.route, open(self.route_f, "w"), ensure_ascii=False, indent=2)

    def note(self, sid, **kw):
        self.route.setdefault(sid, {}).update(kw)


# ---------------------------------------------------------------- gen: AI images/video on Kaggle
def gpu_ready(mode):
    if mode == "off":
        return False, "GPU disabled (--gpu off)"
    if not os.environ.get("KAGGLE_USERNAME"):
        return False, "KAGGLE_USERNAME not set"
    stf = os.path.join(VS_HOME, "gpu-status.json")
    if mode == "auto" and os.path.exists(stf):
        st = json.load(open(stf))
        if not st.get("granted") and time.time() - st.get("t", 0) < 6 * 3600:
            return False, ("Kaggle granted no GPU on the last try (phone verification?); "
                           "`vs-gpu run $VS_REPO/gpu-jobs/probe.py /tmp/p` re-checks, or use --gpu kaggle")
    r = subprocess.run([os.path.join(BIN, "vs-gpu"), "quota"], capture_output=True, text=True)
    if r.returncode:
        return False, f"Kaggle unreachable: {r.stderr.strip()[-200:]}"
    q = json.loads(r.stdout)
    if q["gpu_left_h"] < 0.3:
        return False, f"Kaggle GPU quota used up until {q['refresh']}"
    return True, f"Kaggle GPU {q['gpu_left_h']} h left this week"


def gpu_job(pr, job, items, name, inputs=(), timeout=5400, accel=None):
    out = os.path.join(pr.b, "gen", name)
    params = os.path.join(pr.b, "gen", f"{name}.params.json")
    json.dump(items, open(params, "w", encoding="utf-8"), ensure_ascii=False)
    cmd = [os.path.join(BIN, "vs-gpu"), "run", os.path.join(VS_REPO, "gpu-jobs", job), out, "--name", f"{name}",
           "--params", "@" + params, "--timeout", str(timeout),
           "--accelerator", accel or pr.p.get("gpu", {}).get("accelerator", "NvidiaTeslaT4")]
    for i in inputs:
        cmd += ["--input", i]
    log("GPU job", name, f"({len(inputs)} inputs)")
    r = subprocess.run(cmd, capture_output=True, text=True)
    sys.stderr.write(r.stderr[-2000:])
    return out if r.returncode == 0 else None


def stage_gen(pr, mode):
    shots = pr.p["shots"]
    need_img = [s for s in shots if s.get("engine") in ("ai-image", "ai-video") and not s.get("source")
                and not s.get("keyframe")]
    need_vid = [s for s in shots if s.get("engine") == "ai-video" and not s.get("source")]
    if not need_img and not need_vid:
        log("gen: nothing to generate"); return
    ok, why = gpu_ready(mode); log("gen:", why)
    W, H = pr.W, pr.H
    chars = pr.p.get("characters", {})

    def full_prompt(s):
        extra = " ".join(chars[c].get("prompt", "") for c in s.get("characters", []) if c in chars)
        style = pr.p.get("style", "")
        return " ".join(x for x in (s["prompt"], extra, style) if x)
    if need_img and ok:
        iw, ih = (1280, 720) if W >= H else (720, 1280)
        if W == H:
            iw = ih = 1024
        items = {"items": [{"id": s["id"], "prompt": full_prompt(s), "width": iw, "height": ih,
                            "seed": s.get("seed", abs(hash(s["id"])) % 10**6)} for s in need_img], "steps": 8}
        out = gpu_job(pr, "image_zimage.py", items, "images")
        for s in need_img:
            f = os.path.join(out or "", f"{s['id']}.png")
            if out and os.path.exists(f):
                dst = os.path.join(pr.d, "assets", f"{s['id']}.png"); os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy(f, dst)
                key = "keyframe" if s["engine"] == "ai-video" else "source"
                s[key] = os.path.relpath(dst, pr.d)
                if s["engine"] == "ai-image":
                    s["engine"] = "still"
                pr.note(s["id"], image="z-image-turbo@kaggle")
    if need_vid and ok:
        vw, vh = (1280, 704) if W >= H else (704, 1280)
        items, inputs = [], []
        for s in need_vid:
            n = max(1, round((s.get("dur", 5) + 0.5) * 24 / 4)) * 4 + 1
            it = {"id": s["id"], "prompt": full_prompt(s), "frames": min(n, 121), "width": vw, "height": vh,
                  "seed": s.get("seed", abs(hash(s["id"])) % 10**6)}
            if s.get("keyframe"):
                inputs.append(pr.path(s["keyframe"])); it["image"] = os.path.basename(s["keyframe"])
            items.append(it)
        out = gpu_job(pr, "video_wan22.py", {"items": items, "steps": pr.p.get("gpu", {}).get("video_steps", 30), "fps": 24},
                      "clips", inputs=inputs, timeout=10800)
        for s in need_vid:
            f = os.path.join(out or "", f"{s['id']}.mp4")
            if out and os.path.exists(f):
                dst = os.path.join(pr.d, "assets", f"{s['id']}.mp4"); shutil.copy(f, dst)
                s["source"] = os.path.relpath(dst, pr.d); pr.note(s["id"], video="wan2.2-ti2v-5b@kaggle")
    # fallbacks — never stop the film for a missing GPU
    for s in shots:
        if s.get("engine") == "ai-video" and not s.get("source"):
            if s.get("keyframe"):
                s["engine"] = "still"; s["source"] = s["keyframe"]
                s.setdefault("camera", {}).setdefault("parallax", True)
                s["camera"].setdefault("move", "dolly-in")
                pr.note(s["id"], fallback=f"ai-video → keyframe + parallax ({why})")
            else:
                raise SystemExit(f"shot {s['id']}: no GPU ({why}) and no keyframe — give it a source (image, "
                                 "HyperFrames/Manim/p5 render) or a keyframe")
        if s.get("engine") == "ai-image" and not s.get("source"):
            raise SystemExit(f"shot {s['id']}: no GPU ({why}) — give it a source image or a code-drawn render")
    pr.save()


# ---------------------------------------------------------------- voice
def stage_voice(pr, mode, force):
    v = pr.p.get("voice", {}); eng = v.get("engine", "piper"); lang = pr.p.get("lang", "ar")
    lines = [(s["id"], s["vo"]) for s in pr.p["shots"] if s.get("vo")]
    todo = [(i, t) for i, t in lines if force or not os.path.exists(os.path.join(pr.b, "vo", f"{i}.wav"))]
    if not todo or eng == "none":
        log("voice: nothing to do"); return
    if eng == "chatterbox":
        ok, why = gpu_ready(mode)
        if ok:
            em = {s["id"]: s.get("emotion", 0.5) for s in pr.p["shots"]}
            items = {"lang": lang, "lines": [{"id": i, "text": t, "exaggeration": em.get(i, 0.5),
                                              "cfg": 0.3 if em.get(i, 0.5) > 0.65 else 0.5} for i, t in todo]}
            inputs = []
            if v.get("ref"):
                inputs.append(pr.path(v["ref"])); items["voice"] = os.path.basename(v["ref"])
            out = gpu_job(pr, "tts_chatterbox.py", items, "voice", inputs=inputs, timeout=3600)
            if out:
                for i, _ in todo:
                    f = os.path.join(out, f"{i}.wav")
                    if os.path.exists(f):
                        run(["ffmpeg", "-v", "error", "-y", "-i", f, "-ar", "48000", "-ac", "1", os.path.join(pr.b, "vo", f"{i}.wav")])
                        pr.note(i, voice="chatterbox@kaggle")
                todo = [(i, t) for i, t in todo if not os.path.exists(os.path.join(pr.b, "vo", f"{i}.wav"))]
        if todo:
            log(f"voice: Chatterbox unavailable ({why if not ok else 'job failed'}) → Piper")
            eng = "piper"
    if eng == "edge":
        vname = v.get("voice") or ("ar-SA-HamedNeural" if lang == "ar" else "en-US-AndrewNeural")
        for i, t in todo:
            mp3 = os.path.join(pr.b, "vo", f"{i}.mp3")
            run([PY, "-m", "edge_tts", "--voice", vname, "--text", t, "--write-media", mp3])
            run(["ffmpeg", "-v", "error", "-y", "-i", mp3, "-ar", "48000", "-ac", "1", os.path.join(pr.b, "vo", f"{i}.wav")])
            pr.note(i, voice=f"edge-tts:{vname} (online)")
    elif eng == "piper" and todo:
        vname = v.get("voice") or ("ar_JO-kareem-medium" if lang == "ar" else "en_US-lessac-medium")
        model = os.path.join(VS_HOME, "models", "piper", vname + ".onnx")
        for i, t in todo:
            raw = os.path.join(pr.b, "vo", f"{i}.raw.wav")
            subprocess.run([PY, "-m", "piper", "-m", model, "-f", raw, "--length-scale", str(v.get("length_scale", 1.0)),
                            "--sentence-silence", "0.25"], input=t.encode("utf-8"), check=True, capture_output=True)
            # trim edges, light de-ess/EQ polish, 48 kHz mono
            run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-af",
                 "silenceremove=start_periods=1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                 "highpass=f=70,equalizer=f=3500:t=q:w=1.2:g=2,acompressor=threshold=-20dB:ratio=2.5:attack=5:release=80",
                 "-ar", "48000", "-ac", "1", os.path.join(pr.b, "vo", f"{i}.wav")])
            os.remove(raw); pr.note(i, voice=f"piper:{vname}")
    pr.save()


# ---------------------------------------------------------------- shots
def shot_plan(pr):
    """Duration of each shot = max(planned, narration + pad); transitions overlap neighbours."""
    plan, t = [], 0.0
    shots = pr.p["shots"]
    for k, s in enumerate(shots):
        vo = os.path.join(pr.b, "vo", f"{s['id']}.wav")
        vlen = dur_of(vo) if os.path.exists(vo) else 0.0
        lead = s.get("vo_lead", 0.25)
        d = max(float(s.get("dur", 3)), vlen + lead + s.get("pad", 0.45))
        tr = s.get("transition", "fade") if k < len(shots) - 1 else "cut"
        td = 0.0 if tr == "cut" else float(s.get("transition_dur", 0.5))
        d += td  # the overlap is eaten by the next shot, so add it here
        plan.append({"id": s["id"], "dur": round(d, 3), "start": round(t, 3), "vo_len": vlen, "lead": lead,
                     "transition": tr, "tdur": td})
        t += d - td
    return plan, t


def stage_shots(pr, force):
    plan, total = shot_plan(pr)
    W, H, fps = pr.W, pr.H, pr.fps
    for s, pl in zip(pr.p["shots"], plan):
        out = os.path.join(pr.b, "shots", f"{s['id']}.mp4")
        sig = json.dumps([s.get("source"), s.get("camera"), pl["dur"], W, H, fps], sort_keys=True)
        sigf = out + ".sig"
        if not force and os.path.exists(out) and os.path.exists(sigf) and open(sigf).read() == sig:
            continue
        src = pr.path(s["source"]) if s.get("source") else None
        if not src or not os.path.exists(src):
            raise SystemExit(f"shot {s['id']}: source missing ({s.get('source')}); run the gen stage or render it")
        eng = s.get("engine", "still")
        if eng == "still" or src.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            cam = s.get("camera", {}); move = cam.get("move", "push-in")
            cmd = [os.path.join(BIN, "vs-camera"), "parallax" if cam.get("parallax") else "move", src, out,
                   "--move", move, "--dur", str(pl["dur"]), "--size", f"{W}x{H}", "--fps", str(fps),
                   "--amount", str(cam.get("amount", 0.10))]
            if cam.get("strength"):
                cmd += ["--strength", str(cam["strength"])]
            run(cmd)
        else:
            cd = dur_of(src); speed = 1.0
            if cd < pl["dur"]:
                speed = max(0.8, cd / pl["dur"])  # gentle slow-motion first, then hold the last frame
            vf = (f"setpts=PTS/{speed},fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                  f"tpad=stop_mode=clone:stop_duration={pl['dur']},setsar=1,format=yuv420p")
            run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", vf, "-t", str(pl["dur"]), "-an",
                 "-c:v", "libx264", "-crf", "17", "-preset", "medium", out])
        open(sigf, "w").write(sig)
        log(f"shot {s['id']}: {pl['dur']:.2f}s ({eng})")
    json.dump({"plan": plan, "total": total}, open(os.path.join(pr.b, "plan.json"), "w"), indent=2)


# ---------------------------------------------------------------- edit
def srt_time(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def make_srt(pr, plan, path, max_chars):
    cues = []
    for s, pl in zip(pr.p["shots"], plan):
        text = s.get("subtitle", s.get("vo", "")).strip()
        if not pr.p.get("subtitles", {}).get("keep_tashkeel"):
            text = re.sub(r"[\u0610-\u061A\u064B-\u065F\u0670]", "", text)
        if not text or not pl["vo_len"]:
            continue
        words = text.split(); chunks, cur = [], ""
        for w in words:
            if cur and len(cur) + 1 + len(w) > max_chars:
                chunks.append(cur); cur = w
            else:
                cur = f"{cur} {w}".strip()
        if cur:
            chunks.append(cur)
        total = sum(len(c) for c in chunks); t = pl["start"] + pl["lead"]
        for c in chunks:
            d = pl["vo_len"] * len(c) / total
            cues.append((t, t + d, c)); t += d
    with open(path, "w", encoding="utf-8") as f:
        for n, (a, b, c) in enumerate(cues, 1):
            f.write(f"{n}\n{srt_time(a)} --> {srt_time(b)}\n{c}\n\n")
    return len(cues)


def stage_edit(pr):
    planj = json.load(open(os.path.join(pr.b, "plan.json"))); plan, total = planj["plan"], planj["total"]
    E = os.path.join(pr.b, "edit")
    # 1) picture: xfade chain
    ins, fc, last, off = [], [], "0:v", 0.0
    for k, pl in enumerate(plan):
        ins += ["-i", os.path.join(pr.b, "shots", f"{pl['id']}.mp4")]
    for k in range(1, len(plan)):
        prev = plan[k - 1]; off += prev["dur"] - prev["tdur"]
        tr = prev["transition"]; tr = tr if tr in XFADES else "fade"
        lab = f"v{k}"
        if tr == "cut" or prev["tdur"] == 0:
            fc.append(f"[{last}][{k}:v]concat=n=2:v=1:a=0[{lab}]")
        else:
            fc.append(f"[{last}][{k}:v]xfade=transition={tr}:duration={prev['tdur']}:offset={off:.3f}[{lab}]")
        last = lab
    g = pr.p.get("grade", {})
    look = []
    if g:
        from importlib import util  # reuse the looks table from vs_camera
        spec = util.spec_from_file_location("vc", os.path.join(BIN, "vs_camera.py"))
        vc = util.module_from_spec(spec)
        try:
            spec.loader.exec_module(vc); look = [vc.LOOKS.get(g.get("look", "neutral"), "")]
        except Exception:
            look = []
        if g.get("vignette"): look.append("vignette=PI/5")
        if g.get("grain"): look.append(f"noise=alls={int(g['grain'])}:allf=t")
    post = ",".join(x for x in look if x)
    fc.append(f"[{last}]{post + ',' if post else ''}format=yuv420p[vout]")
    video = os.path.join(E, "picture.mp4")
    run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[vout]",
         "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-r", str(pr.fps), video])
    # 2) sound: narration at each shot's start + lead, original clip audio (if asked), music ducked under voice
    aud_in, parts, n = [], [], 0
    for pl in plan:
        f = os.path.join(pr.b, "vo", f"{pl['id']}.wav")
        if os.path.exists(f):
            aud_in += ["-i", f]; ms = int((pl["start"] + pl["lead"]) * 1000)
            parts.append(f"[{n}:a]aresample=48000,adelay={ms}:all=1[a{n}]"); n += 1
    total_ms = int(total * 1000)
    if n:
        fc = parts + ["".join(f"[a{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0,apad=whole_dur={total:.3f}[voice]"]
    else:
        fc = [f"anullsrc=r=48000:cl=mono,atrim=0:{total:.3f}[voice]"]
    m = pr.p.get("music", {})
    if m.get("track"):
        aud_in += ["-stream_loop", "-1", "-i", pr.path(m["track"])]
        fc += [f"[{n}:a]aresample=48000,volume={m.get('volume', 0.2)},atrim=0:{total:.3f},afade=t=out:st={max(0, total - 2):.3f}:d=2[mus]",
               "[voice]asplit=2[v1][v2]", "[mus][v2]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[duck]",
               "[v1][duck]amix=inputs=2:normalize=0[mix]"]
        outlab = "mix"
    else:
        outlab = "voice"
    mixwav = os.path.join(E, "mix.wav")
    run(["ffmpeg", "-v", "error", "-y", *aud_in, "-filter_complex", ";".join(fc), "-map", f"[{outlab}]",
         "-t", f"{total:.3f}", "-ac", "2", "-ar", "48000", mixwav])
    # loudness: two-pass loudnorm to -14 LUFS / -1.5 dBTP
    meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", mixwav, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                           "-f", "null", "-"], capture_output=True, text=True).stderr
    js = json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
          f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true")
    if float(js["input_i"]) < -60:   # silent film (no narration, no music)
        ln = "anull"
    master = os.path.join(E, "master.m4a")
    run(["ffmpeg", "-v", "error", "-y", "-i", mixwav, "-af", ln + ",aresample=48000", "-c:a", "aac", "-b:a", "192k", master])
    # 3) mux, subtitles, cover
    title = re.sub(r"[^\w\-]+", "-", pr.p.get("slug") or pr.p.get("title", "video")).strip("-")[:60] or "video"
    muxed = os.path.join(E, "muxed.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", master, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
         "-c:a", "copy", "-shortest", "-movflags", "+faststart", muxed])
    final = os.path.join(pr.o, f"{title}.mp4"); srt = os.path.join(pr.o, f"{title}.srt")
    sub = pr.p.get("subtitles", {"burn": True, "style": "reel" if pr.H > pr.W else "clean"})
    ncues = make_srt(pr, plan, srt, 28 if pr.H > pr.W else 42)
    if sub.get("burn") and ncues:
        run([PY, os.path.join(VS_SKILLS, "auto-subtitles", "scripts", "subtitle.py"), muxed, "--srt", srt,
             "--style", sub.get("style", "clean"), "--out-dir", E, "--burn", final])
        # subtitle.py re-encodes; restore faststart and exact audio
        tmp = final + ".tmp.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-i", final, "-i", master, "-map", "0:v", "-map", "1:a", "-c", "copy",
             "-movflags", "+faststart", tmp]); os.replace(tmp, final)
    else:
        shutil.copy(muxed, final)
    best = max(plan, key=lambda p: p["dur"])
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{best['start'] + best['dur'] / 2:.2f}", "-i", video, "-frames:v", "1",
         "-q:v", "2", os.path.join(pr.o, f"{title}.cover.jpg")])
    # timeline for QC (mid-time of each shot)
    pr.p["_timeline"] = [{"id": pl["id"], "t_mid": round(pl["start"] + pl["dur"] / 2, 2),
                          "onscreen_text": s.get("onscreen_text", ""), "characters": s.get("characters", [])}
                         for s, pl in zip(pr.p["shots"], plan)]
    pr.p["_deliverable"] = os.path.relpath(final, pr.d)
    pr.save()
    log(f"edit: {final} ({total:.1f}s, {len(plan)} shots, {ncues} subtitle cues)")
    return final


def stage_qc(pr):
    final = pr.path(pr.p["_deliverable"])
    script = " ".join(s.get("vo", "") for s in pr.p["shots"])
    cmd = [os.path.join(BIN, "vs-qc"), final, "--preset", pr.p.get("format", "youtube"), "--production", pr.pf,
           "--lang", pr.p.get("lang", "ar"), "--out-dir", pr.o]
    if not script.strip():
        cmd.append("--no-asr")
    r = subprocess.run(cmd); subprocess.run([os.path.join(BIN, "vs-verify"), final, os.path.splitext(final)[0] + ".sheet.jpg"],
                                            capture_output=True)
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("--stage", default="all", choices=["all", "gen", "voice", "shots", "edit", "qc"])
    ap.add_argument("--gpu", default="auto", choices=["auto", "kaggle", "off"]); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    pr = Project(a.project); t0 = time.time()
    st = a.stage
    if st in ("all", "gen"): stage_gen(pr, a.gpu)
    if st in ("all", "voice"): stage_voice(pr, a.gpu, a.force)
    if st in ("all", "shots"): stage_shots(pr, a.force)
    if st in ("all", "edit"): stage_edit(pr)
    ok = True
    if st in ("all", "qc"): ok = stage_qc(pr)
    log(f"done in {time.time() - t0:.0f}s → {pr.p.get('_deliverable')}  QC {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
