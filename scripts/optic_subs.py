"""Burn "optical" karaoke subtitles into a 16:9 video.

usage: optic_subs.py IN.mp4 transcript.json OUT.mp4            # full render
       optic_subs.py IN.mp4 transcript.json OUTDIR --frames 6.9 12.4 ...   # preview PNGs
"""
import json, subprocess, sys, math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1920, 1080, 30
FONT = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
WHITE, YELLOW = (255, 255, 255), (255, 214, 0)          # #FFD600
SUB_Y, CENTER_Y = 905, 540                              # baseline-ish centres
IN_T, OUT_T = 0.35, 0.30

# ---------- text: fixes for ASR errors + places ----------
FIX = {"рилам": "рилсам", "спишет": "пишет", "выбирайте": "выбираете", "дешевлем": "дешевле",
       "места": "мест", "илья": "ильяс", "яружан": "аружан", "джунсы": "чунцин"}
PLACES = {"китаю": "китаю", "китай": "китай", "чунцин": "чунцин", "японию": "японию", "корею": "корею",
          "астане": "астане", "японии": "японии", "чжанцзяцзе": "чжанцзяцзе"}
TITLES = [(6.75, "ЧУНЦИН")]                             # place cards, 2 s each
HYPHEN = {("ха", "ха"), ("во", "первых"), ("чуть", "чуть"), ("что", "то")}


def load_words(path):
    w = [dict(x) for x in json.load(open(path))["words"]]
    out = []
    i = 0
    while i < len(w):
        x = w[i]; nxt = w[i + 1] if i + 1 < len(w) else None
        if nxt and x["word"] == "чан" and nxt["word"] == "зензе":
            out.append({"word": "чжанцзяцзе", "start": x["start"], "end": nxt["end"]}); i += 2; continue
        if nxt and (x["word"], nxt["word"]) in HYPHEN:
            out.append({"word": x["word"] + "-" + nxt["word"], "start": x["start"], "end": nxt["end"]}); i += 2; continue
        x["word"] = FIX.get(x["word"], x["word"])
        if x["word"] == "только" and 126 < x["start"] < 128:   # "сразу (с)только эмоций"
            x["word"] = "столько"
        out.append(x); i += 1
    for x in out:
        x["place"] = x["word"] in PLACES
        x["text"] = x["word"].upper()
    return out


def group(words):
    phrases, cur = [], []
    for i, x in enumerate(words):
        gap = x["start"] - words[i - 1]["end"] if i else 0
        chars = sum(len(y["text"]) + 1 for y in cur) + len(x["text"])
        if cur and (len(cur) >= 4 or chars > 20 or gap > 0.35 or x["place"] or cur[-1]["place"]):
            phrases.append(cur); cur = []
        cur.append(x)
    if cur: phrases.append(cur)
    res = []
    for k, p in enumerate(phrases):
        s = max(0, p[0]["start"] - 0.06)
        e = p[-1]["end"]
        res.append({"words": p, "start": s, "end": e, "center": p[0]["place"]})
    for a, b in zip(res, res[1:]):                      # no pauses between phrases
        a["end"] = b["start"] if b["start"] - a["end"] < 1.2 else a["end"] + 0.4
    res[-1]["end"] += 0.6
    return res


# ---------- sprites ----------
_fonts = {}
def font(sz):
    if sz not in _fonts: _fonts[sz] = ImageFont.truetype(FONT, sz)
    return _fonts[sz]


def sprite(text, size, color):
    f = font(size); sw = max(6, size // 11)
    l, t, r, b = f.getbbox(text, stroke_width=sw)
    pad = 30
    im = Image.new("RGBA", (r - l + 2 * pad, int(size * 1.25) + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    org = (pad - l, pad + int(size * 0.05))
    d.text(org, text, font=f, fill=color + (255,), stroke_width=sw, stroke_fill=(0, 0, 0, 255))
    a = np.array(im)
    sh = cv2.GaussianBlur(a[:, :, 3].astype(np.float32), (0, 0), size / 10)
    sh = np.roll(sh, int(size * 0.07), axis=0) * 0.75
    out = np.zeros_like(a, dtype=np.float32)
    fa = a[:, :, 3:4] / 255.0
    out[:, :, :3] = a[:, :, :3] * fa
    out[:, :, 3] = np.maximum(a[:, :, 3], sh)
    return out  # premultiplied RGBA float, 0..255


def build(ph):
    big = ph["center"]
    items = []
    for x in ph["words"]:
        if big:
            items.append(sprite(x["text"], 150, YELLOW))
        elif x["place"]:
            items.append(sprite(x["text"], 112, YELLOW))
        else:
            items.append(sprite(x["text"], 86, WHITE))
    ph["sprites"] = items


def ease_out(p): return 1 - (1 - p) ** 3
def clamp(v): return max(0.0, min(1.0, v))


def word_scale(t, x):
    if t < x["start"] or t > x["end"] + 0.12: return 1.0
    if t <= x["end"]:
        k = (t - x["start"]) / 0.1
        return 1 + 0.16 * k if k < 1 else 1.09 + 0.07 * math.exp(-(k - 1) * 1.5)
    return 1 + 0.09 * (1 - (t - x["end"]) / 0.12)


def phrase_layer(ph, t):
    sp = ph["sprites"]; gap = -26
    widths = [s.shape[1] for s in sp]; hh = max(s.shape[0] for s in sp)
    total = sum(widths) + gap * (len(sp) - 1)
    cw, ch = total + 120, int(hh * 1.4)
    canvas = np.zeros((ch, cw, 4), np.float32)
    x0 = 60
    for s, x in zip(sp, ph["words"]):
        sc = word_scale(t, x)
        cx, cy = x0 + s.shape[1] / 2, ch / 2
        if abs(sc - 1) > 1e-3:
            s = cv2.resize(s, None, fx=sc, fy=sc, interpolation=cv2.INTER_LINEAR)
        paste(canvas, s, int(cx - s.shape[1] / 2), int(cy - s.shape[0] / 2))
        x0 += widths[x["_i"]] + gap
    return canvas


def paste(dst, src, x, y):
    h, w = src.shape[:2]
    x1, y1 = max(x, 0), max(y, 0); x2, y2 = min(x + w, dst.shape[1]), min(y + h, dst.shape[0])
    if x2 <= x1 or y2 <= y1: return
    s = src[y1 - y:y2 - y, x1 - x:x2 - x]; d = dst[y1:y2, x1:x2]
    a = s[:, :, 3:4] / 255.0
    d[:, :, :3] = s[:, :, :3] + d[:, :, :3] * (1 - a)
    d[:, :, 3:4] = s[:, :, 3:4] + d[:, :, 3:4] * (1 - a)


def optic(layer, t, start, end, cy, frame):
    """Float-in from blur/below/bigger, float-out up into blur."""
    if t < start or t > end + OUT_T: return
    p = ease_out(clamp((t - start) / IN_T))
    q = clamp((t - end) / OUT_T); q = q * q * (3 - 2 * q)
    scale = 1 + 0.12 * (1 - p) - 0.04 * q
    dy = 42 * (1 - p) - 48 * q
    blur = 13 * (1 - p) + 12 * q
    alpha = min(1.0, p * 1.6) * (1 - q)
    if alpha <= 0.01: return
    L = layer
    if abs(scale - 1) > 1e-3:
        L = cv2.resize(L, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    if blur > 0.4:
        L = cv2.GaussianBlur(L, (0, 0), blur)
    L = L * alpha
    paste(frame, L, int(W / 2 - L.shape[1] / 2), int(cy + dy - L.shape[0] / 2))


def zoom_env(t, spans):
    z = 0.0
    for s, e in spans:
        if s - 0.4 < t < e + 0.5:
            a = clamp((t - s + 0.1) / 0.5); b = clamp((e + 0.5 - t) / 0.5)
            z = max(z, (a * a * (3 - 2 * a)) * (b * b * (3 - 2 * b)))
    return 1 + 0.07 * z


def vignette():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / math.sqrt(2)
    return (1 - 0.42 * np.clip((r - 0.45) / 0.55, 0, 1) ** 1.6)[:, :, None]


def main():
    src, trj, out = sys.argv[1:4]
    words = load_words(trj)
    phrases = group(words)
    for ph in phrases:
        for i, x in enumerate(ph["words"]): x["_i"] = i
        build(ph)
    titles = []
    for t0, txt in TITLES:
        s = sprite(txt, 175, YELLOW)
        titles.append({"start": t0, "end": t0 + 2.0 - OUT_T, "layer": s})
    zspans = [(p["start"], p["end"]) for p in phrases if p["center"]] + [(x["start"], x["end"]) for x in titles]
    vig = vignette()
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                         "-of", "default=nw=1:nk=1", src]))
    json.dump([{"t": [round(p["start"], 2), round(p["end"], 2)], "text": " ".join(x["text"] for x in p["words"])}
               for p in phrases], open(out.rsplit(".", 1)[0] + "_phrases.json" if out.endswith(".mp4") else out + "/phrases.json", "w"),
              ensure_ascii=False, indent=0)

    def render(frame_u8, t):
        z = zoom_env(t, zspans)
        f = frame_u8
        if z > 1.0005:
            cw, ch = W / z, H / z
            M = np.float32([[z, 0, -(W - cw) / 2 * z], [0, z, -(H - ch) / 2 * z]])
            f = cv2.warpAffine(f, M, (W, H), flags=cv2.INTER_LINEAR)
        fr = f.astype(np.float32) * vig
        ov = np.zeros((H, W, 4), np.float32)
        for ph in phrases:
            if ph["start"] <= t <= ph["end"] + OUT_T:
                optic(phrase_layer(ph, t), t, ph["start"], ph["end"], CENTER_Y if ph["center"] else SUB_Y, ov)
        for ti in titles:
            optic(ti["layer"], t, ti["start"], ti["end"], CENTER_Y, ov)
        a = ov[:, :, 3:4] / 255.0
        fr = ov[:, :, :3] + fr * (1 - a)
        return np.clip(fr, 0, 255).astype(np.uint8)

    dec_vf = f"fps={FPS},scale={W}:{H}:flags=lanczos,unsharp=5:5:0.6,setsar=1"
    if "--frames" in sys.argv:
        ts = [float(v) for v in sys.argv[sys.argv.index("--frames") + 1:]]
        for t in ts:
            raw = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", str(t), "-i", src, "-frames:v", "1",
                                           "-vf", f"scale={W}:{H}:flags=lanczos,unsharp=5:5:0.6", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
            fr = np.frombuffer(raw, np.uint8).reshape(H, W, 3)
            Image.fromarray(render(fr, t)).save(f"{out}/frame_{t:06.2f}.png")
        return

    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-vf", dec_vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-i", src, "-map", "0:v", "-map", "1:a", "-c:v", "libx264",
                            "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "copy",
                            "-movflags", "+faststart", "-shortest", out], stdin=subprocess.PIPE)
    n, fsz = 0, W * H * 3
    while True:
        raw = dec.stdout.read(fsz)
        if len(raw) < fsz: break
        enc.stdin.write(render(np.frombuffer(raw, np.uint8).reshape(H, W, 3), n / FPS).tobytes())
        n += 1
        if n % 300 == 0: print(f"{n / FPS:.0f}/{dur:.0f}s", flush=True)
    enc.stdin.close(); enc.wait(); dec.wait()
    print("frames", n)


if __name__ == "__main__":
    main()
