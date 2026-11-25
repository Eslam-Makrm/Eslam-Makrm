"""vs-camera — cinematic camera moves and looks, CPU only.

  vs-camera move   IMG OUT.mp4 --move push-in [--dur 5 --size 1920x1080 --fps 30 --amount 0.12 --ease inout]
  vs-camera parallax IMG OUT.mp4 --move dolly-in [--dur 5 --strength 0.04 ...]   2.5D from a depth map
  vs-camera depth  IMG OUT.png                                                   save the depth map
  vs-camera grade  IN.mp4 OUT.mp4 --look teal-orange [--grain 6 --vignette --letterbox 2.39 --lut F.cube]

Moves (move and parallax): push-in, pull-out, pan-left, pan-right, tilt-up, tilt-down, truck-left,
truck-right, crane-up, crane-down, orbit-left, orbit-right, dolly-in, dolly-zoom, handheld, static.
Looks: teal-orange, warm, cool, noir, bleach, vintage, vivid, neutral.
Depth: Depth-Anything-V2-Small (Apache-2.0, ONNX, ~1 s per image on 4 cores).
"""
import argparse, math, os, subprocess, sys
import numpy as np
from PIL import Image

VS_HOME = os.environ.get("VS_HOME", os.path.expanduser("~/.video-studio"))
DEPTH_ONNX = os.path.join(VS_HOME, "models", "onnx", "depth-anything-v2-small.onnx")
MOVES = ["push-in", "pull-out", "pan-left", "pan-right", "tilt-up", "tilt-down", "truck-left", "truck-right",
         "crane-up", "crane-down", "orbit-left", "orbit-right", "dolly-in", "dolly-zoom", "handheld", "static"]


def ease(t, kind):
    if kind == "linear":
        return t
    if kind == "in":
        return t * t
    if kind == "out":
        return 1 - (1 - t) ** 2
    return 0.5 - 0.5 * math.cos(math.pi * t)  # inout (default): starts and lands softly


def size(s):
    w, h = s.lower().split("x"); return int(w), int(h)


def cover(img, W, H, over):
    """Resize the still so it covers W*over x H*over (room for the move), centre-cropped."""
    iw, ih = img.size; s = max(W * over / iw, H * over / ih)
    img = img.resize((max(1, round(iw * s)), max(1, round(ih * s))), Image.LANCZOS)
    iw, ih = img.size; l, t = (iw - round(W * over)) // 2, (ih - round(H * over)) // 2
    return np.asarray(img.crop((l, t, l + round(W * over), t + round(H * over))).convert("RGB"))


def writer(out, W, H, fps):
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    return subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                             "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], stdin=subprocess.PIPE)


def path(move, p, amt):
    """Camera state at progress p: (zoom, dx, dy, rot) — dx/dy as a fraction of the frame."""
    z, dx, dy, r = 1.0, 0.0, 0.0, 0.0
    if move in ("push-in", "dolly-in"): z = 1 + amt * p
    elif move == "pull-out": z = 1 + amt * (1 - p)
    elif move == "pan-left": dx = amt * (0.5 - p)
    elif move == "pan-right": dx = amt * (p - 0.5)
    elif move in ("tilt-up", "crane-up"): dy = amt * (0.5 - p)
    elif move in ("tilt-down", "crane-down"): dy = amt * (p - 0.5)
    elif move == "truck-left": dx = amt * (0.5 - p) * 0.8; z = 1 + amt * 0.25
    elif move == "truck-right": dx = amt * (p - 0.5) * 0.8; z = 1 + amt * 0.25
    elif move in ("orbit-left", "orbit-right"):
        sgn = -1 if move == "orbit-left" else 1
        dx = sgn * amt * (p - 0.5); r = sgn * 1.2 * (p - 0.5); z = 1 + amt * 0.3
    elif move == "dolly-zoom": z = 1 + amt * p
    elif move == "handheld":
        z = 1 + amt * 0.2
        dx = 0.004 * math.sin(p * 11.0) + 0.002 * math.sin(p * 27.0)
        dy = 0.003 * math.sin(p * 9.0 + 1.0) + 0.002 * math.sin(p * 23.0)
        r = 0.25 * math.sin(p * 7.0)
    return z, dx, dy, r


def render_move(a, parallax=False):
    import cv2
    W, H = size(a.size); fps = a.fps; n = max(2, round(a.dur * fps))
    # margin only where the camera travels sideways; zoom-ins never reveal borders
    lateral = a.move not in ("push-in", "dolly-in", "pull-out", "dolly-zoom", "static")
    over = 1.0 + (a.amount if lateral else 0) + (a.strength * 2 if parallax else 0) + 0.01
    src = cover(Image.open(a.image), W, H, over)
    sh, sw = src.shape[:2]
    depth = None
    if parallax:
        d = depth_map(Image.fromarray(src))
        depth = cv2.resize(d, (sw, sh), interpolation=cv2.INTER_CUBIC)
        depth = cv2.GaussianBlur(depth, (0, 0), sigmaX=max(1.0, sw / 400))  # soften edges: fewer tears
    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    proc = writer(a.out, W, H, fps)
    for i in range(n):
        p = ease(i / (n - 1), a.ease)
        z, dx, dy, r = path(a.move, p, a.amount)
        # output pixel -> source coordinates (zoom about centre, rotate, offset)
        cx, cy = sw / 2, sh / 2
        x = (gx - W / 2) / z; y = (gy - H / 2) / z
        if r:
            th = math.radians(r); c, s_ = math.cos(th), math.sin(th)
            x, y = c * x - s_ * y, s_ * x + c * y
        mx = (x + cx + dx * W).astype(np.float32); my = (y + cy + dy * H).astype(np.float32)
        if depth is not None:
            dd = cv2.remap(depth, mx, my, cv2.INTER_LINEAR)  # near = 1, far = 0
            k = a.strength * W
            if a.move in ("dolly-in", "push-in", "pull-out", "dolly-zoom"):
                g = (p - 0.5) * (1 if a.move != "pull-out" else -1)
                if a.move == "dolly-zoom": g = -g  # background swells while subject holds
                mx = mx - (gx - W / 2) / W * dd * k * g * 2
                my = my - (gy - H / 2) / H * dd * k * g * 2
            else:
                ox, oy = {"pan-left": (1, 0), "pan-right": (-1, 0), "truck-left": (1, 0), "truck-right": (-1, 0),
                          "orbit-left": (1, 0), "orbit-right": (-1, 0), "tilt-up": (0, 1), "tilt-down": (0, -1),
                          "crane-up": (0, 1), "crane-down": (0, -1)}.get(a.move, (1, 0))
                mx = mx + ox * dd * k * (p - 0.5); my = my + oy * dd * k * (p - 0.5)
        frame = cv2.remap(src, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    if proc.wait():
        sys.exit("ffmpeg failed")
    print(a.out)


def depth_map(img):
    """Relative inverse depth in [0,1] (1 = near)."""
    import onnxruntime as ort
    if not os.path.exists(DEPTH_ONNX):
        sys.exit(f"depth model missing: {DEPTH_ONNX} (run install.sh)")
    sess = ort.InferenceSession(DEPTH_ONNX, providers=["CPUExecutionProvider"])
    w, h = img.size; s = 518 / max(w, h)
    nw, nh = max(14, round(w * s / 14) * 14), max(14, round(h * s / 14) * 14)
    x = np.asarray(img.convert("RGB").resize((nw, nh), Image.BICUBIC), dtype=np.float32) / 255.0
    x = (x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
    x = x.transpose(2, 0, 1)[None].astype(np.float32)
    d = sess.run(None, {sess.get_inputs()[0].name: x})[0].squeeze()
    d = (d - d.min()) / max(1e-6, d.max() - d.min())
    return d.astype(np.float32)


LOOKS = {
    "neutral": "",
    "teal-orange": "colorbalance=rs=-0.05:gs=-0.02:bs=0.08:rh=0.08:gh=0.02:bh=-0.06,eq=contrast=1.08:saturation=1.1",
    "warm": "colorbalance=rm=0.06:gm=0.02:bm=-0.05,eq=saturation=1.05",
    "cool": "colorbalance=rm=-0.05:bm=0.06,eq=saturation=0.95",
    "noir": "hue=s=0,eq=contrast=1.25:brightness=-0.02",
    "bleach": "eq=contrast=1.2:saturation=0.55",
    "vintage": "curves=preset=vintage,eq=saturation=0.85",
    "vivid": "eq=contrast=1.06:saturation=1.3",
}


def grade(a):
    f = [LOOKS[a.look]] if LOOKS.get(a.look) else []
    if a.lut:
        f.append(f"lut3d=file='{a.lut}'")
    if a.vignette:
        f.append("vignette=PI/5")
    if a.grain:
        f.append(f"noise=alls={a.grain}:allf=t")
    if a.letterbox:
        f.append(f"drawbox=x=0:y=0:w=iw:h=(ih-iw/{a.letterbox})/2:color=black:t=fill,"
                 f"drawbox=x=0:y=ih-(ih-iw/{a.letterbox})/2:w=iw:h=(ih-iw/{a.letterbox})/2:color=black:t=fill")
    vf = ",".join(x for x in f if x) or "null"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.input, "-vf", vf, "-c:v", "libx264", "-crf", "17",
                    "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", a.out], check=True)
    print(a.out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    for c in ("move", "parallax"):
        p = sp.add_parser(c); p.add_argument("image"); p.add_argument("out")
        p.add_argument("--move", default="push-in", choices=MOVES); p.add_argument("--dur", type=float, default=5)
        p.add_argument("--size", default="1920x1080"); p.add_argument("--fps", type=int, default=30)
        p.add_argument("--amount", type=float, default=0.10, help="zoom/travel as a fraction of the frame")
        p.add_argument("--strength", type=float, default=0.04, help="parallax depth separation")
        p.add_argument("--ease", default="inout", choices=["inout", "in", "out", "linear"])
    p = sp.add_parser("depth"); p.add_argument("image"); p.add_argument("out")
    p = sp.add_parser("grade"); p.add_argument("input"); p.add_argument("out")
    p.add_argument("--look", default="neutral", choices=list(LOOKS)); p.add_argument("--lut")
    p.add_argument("--grain", type=int, default=0); p.add_argument("--vignette", action="store_true")
    p.add_argument("--letterbox", type=float, help="e.g. 2.39")
    a = ap.parse_args()
    if a.cmd == "move":
        render_move(a)
    elif a.cmd == "parallax":
        render_move(a, parallax=True)
    elif a.cmd == "depth":
        d = depth_map(Image.open(a.image)); Image.fromarray((d * 255).astype(np.uint8)).save(a.out); print(a.out)
    elif a.cmd == "grade":
        grade(a)


if __name__ == "__main__":
    main()
