#!/usr/bin/env python3
"""Everyday video edits with ffmpeg (+ auto-editor for silence cuts). Local, free, scriptable.

    python3 edit.py probe    IN
    python3 edit.py silence  IN OUT [--margin 0.15] [--threshold 4%]       remove dead air (auto-editor)
    python3 edit.py trim     IN OUT --start 2.5 [--end 14 | --duration 8]   frame-accurate cut
    python3 edit.py join     OUT IN1 IN2 ... [--xfade 0.5] [--size 1920x1080] [--fps 30]
    python3 edit.py reframe  IN OUT --to 9:16|1:1|4:5|16:9 [--mode blur|crop|pad]
    python3 edit.py loudness IN OUT [--lufs -14]                          normalize for social platforms
    python3 edit.py speed    IN OUT --factor 1.25                          picture and sound together
    python3 edit.py overlay  IN OUT --image logo.png [--pos tr|tl|br|bl] [--scale 0.12] [--start 0 --end 5]
    python3 edit.py music    IN OUT --track song.mp3 [--volume 0.25] [--duck]   add a bed, ducked under speech
    python3 edit.py thumb    IN OUT.jpg [--at 1.0]

Every output is H.264 + AAC, yuv420p, +faststart, so it plays everywhere and uploads anywhere.
`join` normalizes size, frame rate, sample rate and adds silent audio to clips without sound,
so clips from different tools (HyperFrames, Manim, explainroo, phone footage) join cleanly.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

VS_HOME = os.environ.get("VS_HOME", os.path.expanduser("~/.video-studio"))
ENC = ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart"]
RATIOS = {"9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350), "16:9": (1920, 1080)}


def ff(*args):
    cmd = ["ffmpeg", "-v", "error", "-y", *args]
    r = subprocess.run(cmd)
    if r.returncode:
        sys.exit(f"ffmpeg failed: {' '.join(cmd)}")


def info(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration:stream=codec_type,width,height,r_frame_rate",
                          "-of", "json", path], capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), {})
    num, den = (v.get("r_frame_rate", "30/1").split("/") + ["1"])[:2]
    return {"duration": float(d["format"]["duration"]), "width": v.get("width"), "height": v.get("height"),
            "fps": round(float(num) / float(den or 1), 3),
            "audio": any(s["codec_type"] == "audio" for s in d["streams"])}


def outdir(p):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)


def cmd_probe(a):
    print(json.dumps(info(a.input), indent=1))


def cmd_silence(a):
    exe = shutil.which("auto-editor") or os.path.join(VS_HOME, "venv-editor", "bin", "auto-editor")
    if not os.path.exists(exe):
        sys.exit("auto-editor not found: run the studio installer")
    outdir(a.output)
    tmp = a.output + ".ae.mp4"
    subprocess.run([exe, a.input, "--edit", f"audio:threshold={a.threshold}", "--margin", f"{a.margin}sec",
                    "--no-open", "-o", tmp], check=True, stdout=subprocess.DEVNULL)
    ff("-i", tmp, *ENC, a.output)  # re-encode for a uniform, upload-safe file
    os.remove(tmp)
    before, after = info(a.input)["duration"], info(a.output)["duration"]
    print(f"{a.output}: {before:.2f}s -> {after:.2f}s ({before - after:.2f}s of silence removed)")


def cmd_trim(a):
    outdir(a.output)
    span = ["-t", f"{a.end - a.start:.3f}"] if a.end is not None else (["-t", str(a.duration)] if a.duration else [])
    ff("-ss", str(a.start), "-i", a.input, *span, *ENC, a.output)
    print(f"{a.output}: {info(a.output)['duration']:.2f}s")


def cmd_join(a):
    w, h = map(int, a.size.split("x"))
    outdir(a.output)
    inputs, chains, durs = [], [], []
    for i, p in enumerate(a.inputs):
        meta = info(p)
        durs.append(meta["duration"])
        inputs += ["-i", p]
        chains.append(f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,"
                      f"setsar=1,fps={a.fps},format=yuv420p,settb=AVTB[v{i}]")
        if meta["audio"]:
            chains.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,asetpts=PTS-STARTPTS[a{i}]")
        else:
            chains.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{meta['duration']:.3f}[a{i}]")
    n = len(a.inputs)
    if a.xfade and n > 1:
        x = a.xfade
        vlast, alast, offset = "v0", "a0", 0.0
        for i in range(1, n):
            offset += durs[i - 1] - x
            chains.append(f"[{vlast}][v{i}]xfade=transition={a.transition}:duration={x}:offset={offset:.3f}[vx{i}]")
            chains.append(f"[{alast}][a{i}]acrossfade=d={x}[ax{i}]")
            vlast, alast = f"vx{i}", f"ax{i}"
        maps = ["-map", f"[{vlast}]", "-map", f"[{alast}]"]
    else:
        chains.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vo][ao]")
        maps = ["-map", "[vo]", "-map", "[ao]"]
    ff(*inputs, "-filter_complex", ";".join(chains), *maps, *ENC, a.output)
    print(f"{a.output}: {info(a.output)['duration']:.2f}s from {n} clips")


def cmd_reframe(a):
    w, h = RATIOS[a.to]
    outdir(a.output)
    if a.mode == "crop":
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
    elif a.mode == "pad":
        vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
    else:  # blur: the whole picture, centred over a blurred, zoomed copy of itself
        vf = (f"split[bg][fg];[bg]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=28:2,"
              f"eq=brightness=-0.08[b];[fg]scale={w}:{h}:force_original_aspect_ratio=decrease[f];"
              f"[b][f]overlay=(W-w)/2:(H-h)/2,setsar=1")
    audio = [] if info(a.input)["audio"] else ["-an"]
    ff("-i", a.input, "-filter_complex" if a.mode == "blur" else "-vf", vf, *ENC, *audio, a.output)
    print(f"{a.output}: {w}x{h} ({a.mode})")


def cmd_loudness(a):
    outdir(a.output)
    ff("-i", a.input, "-af", f"loudnorm=I={a.lufs}:TP=-1.5:LRA=11", "-c:v", "copy",
       "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", a.output)
    print(f"{a.output}: normalized to {a.lufs} LUFS")


def cmd_speed(a):
    outdir(a.output)
    f = a.factor
    atempo = []
    r = f
    while r > 2.0:
        atempo.append("atempo=2.0"); r /= 2.0
    while r < 0.5:
        atempo.append("atempo=0.5"); r /= 0.5
    atempo.append(f"atempo={r:.4f}")
    has_audio = info(a.input)["audio"]
    ff("-i", a.input, "-filter:v", f"setpts=PTS/{f}", *(["-filter:a", ",".join(atempo)] if has_audio else ["-an"]), *ENC, a.output)
    print(f"{a.output}: {info(a.output)['duration']:.2f}s at {f}x")


def cmd_overlay(a):
    outdir(a.output)
    m = 40
    pos = {"tr": f"W-w-{m}:{m}", "tl": f"{m}:{m}", "br": f"W-w-{m}:H-h-{m}", "bl": f"{m}:H-h-{m}"}[a.pos]
    vw = info(a.input)["width"]
    enable = f":enable='between(t,{a.start},{a.end})'" if a.end else ""
    fc = f"[1:v]scale={int(vw * a.scale)}:-1[lg];[0:v][lg]overlay={pos}{enable}"
    ff("-i", a.input, "-i", a.image, "-filter_complex", fc, *ENC, a.output)
    print(f"{a.output}: overlay {a.image} at {a.pos}")


def cmd_music(a):
    outdir(a.output)
    d = info(a.input)["duration"]
    has_audio = info(a.input)["audio"]
    bed = f"[1:a]aloop=loop=-1:size=2e9,atrim=0:{d:.3f},volume={a.volume},afade=t=out:st={max(0, d - 1.5):.3f}:d=1.5[m]"
    if has_audio and a.duck:
        fc = f"{bed};[0:a]asplit[s][sc];[m][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[md];[s][md]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5[ao]"
    elif has_audio:
        fc = f"{bed};[0:a][m]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5[ao]"
    else:
        fc = f"{bed};[m]loudnorm=I=-14:TP=-1.5[ao]"
    ff("-i", a.input, "-i", a.track, "-filter_complex", fc, "-map", "0:v", "-map", "[ao]", "-c:v", "copy",
       "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{d:.3f}", a.output)
    print(f"{a.output}: music bed added{' (ducked)' if a.duck and has_audio else ''}")


def cmd_thumb(a):
    outdir(a.output)
    ff("-ss", str(a.at), "-i", a.input, "-frames:v", "1", "-q:v", "2", a.output)
    print(a.output)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("probe"); p.add_argument("input"); p.set_defaults(fn=cmd_probe)
    p = sp.add_parser("silence"); p.add_argument("input"); p.add_argument("output")
    p.add_argument("--margin", type=float, default=0.15); p.add_argument("--threshold", default="4%"); p.set_defaults(fn=cmd_silence)
    p = sp.add_parser("trim"); p.add_argument("input"); p.add_argument("output"); p.add_argument("--start", type=float, default=0)
    p.add_argument("--end", type=float); p.add_argument("--duration", type=float); p.set_defaults(fn=cmd_trim)
    p = sp.add_parser("join"); p.add_argument("output"); p.add_argument("inputs", nargs="+")
    p.add_argument("--xfade", type=float, default=0); p.add_argument("--transition", default="fade")
    p.add_argument("--size", default="1920x1080"); p.add_argument("--fps", type=int, default=30); p.set_defaults(fn=cmd_join)
    p = sp.add_parser("reframe"); p.add_argument("input"); p.add_argument("output"); p.add_argument("--to", required=True, choices=RATIOS)
    p.add_argument("--mode", default="blur", choices=["blur", "crop", "pad"]); p.set_defaults(fn=cmd_reframe)
    p = sp.add_parser("loudness"); p.add_argument("input"); p.add_argument("output"); p.add_argument("--lufs", type=float, default=-14); p.set_defaults(fn=cmd_loudness)
    p = sp.add_parser("speed"); p.add_argument("input"); p.add_argument("output"); p.add_argument("--factor", type=float, required=True); p.set_defaults(fn=cmd_speed)
    p = sp.add_parser("overlay"); p.add_argument("input"); p.add_argument("output"); p.add_argument("--image", required=True)
    p.add_argument("--pos", default="tr", choices=["tr", "tl", "br", "bl"]); p.add_argument("--scale", type=float, default=0.12)
    p.add_argument("--start", type=float, default=0); p.add_argument("--end", type=float); p.set_defaults(fn=cmd_overlay)
    p = sp.add_parser("music"); p.add_argument("input"); p.add_argument("output"); p.add_argument("--track", required=True)
    p.add_argument("--volume", type=float, default=0.25); p.add_argument("--duck", action="store_true"); p.set_defaults(fn=cmd_music)
    p = sp.add_parser("thumb"); p.add_argument("input"); p.add_argument("output"); p.add_argument("--at", type=float, default=1.0); p.set_defaults(fn=cmd_thumb)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
