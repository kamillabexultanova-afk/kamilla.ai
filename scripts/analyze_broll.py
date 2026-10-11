import cv2, numpy as np, json, sys, glob, os
res = {}
for f in sorted(glob.glob(sys.argv[1] + "/*.mp4")):
    cap = cv2.VideoCapture(f); fps = cap.get(5); n = int(cap.get(7))
    prev = None; rows = []; stack = []
    for i in range(n):
        ok, fr = cap.read()
        if not ok: break
        g = cv2.cvtColor(cv2.resize(fr, (640, 360)), cv2.COLOR_BGR2GRAY).astype(np.float32)
        if i % 3 == 0: stack.append(cv2.Canny(g.astype(np.uint8), 80, 160) > 0)
        if prev is not None:
            (dx, dy), _ = cv2.phaseCorrelate(prev, g)
            rows.append(dict(t=i / fps, lap=cv2.Laplacian(g, cv2.CV_32F).var(), mean=g.mean(),
                             over=(g > 245).mean(), under=(g < 12).mean(), dx=dx, dy=dy))
        prev = g
    dx = np.array([r["dx"] for r in rows]); dy = np.array([r["dy"] for r in rows])
    # shake = high-frequency part of motion (motion minus its smoothed trend)
    k = np.ones(9) / 9
    jit = np.sqrt((dx - np.convolve(dx, k, "same"))**2 + (dy - np.convolve(dy, k, "same"))**2)
    # static-overlay check: edges present in >90% of frames, inside 15% border zones
    E = np.mean(stack, axis=0); h, w = E.shape; m = np.zeros_like(E, bool)
    bh, bw = int(h * .15), int(w * .2); m[:bh] = m[-bh:] = True; m[:, :bw] = m[:, -bw:] = True
    static = float(((E > 0.9) & m).sum())
    sec = []
    for s in range(int(rows[-1]["t"]) + 1):
        rr = [r for r in rows if s <= r["t"] < s + 1]
        if rr: sec.append(dict(sec=s, lap=round(np.mean([r["lap"] for r in rr]), 1), mean=round(np.mean([r["mean"] for r in rr]), 1),
                               over=round(np.mean([r["over"] for r in rr]), 3), jitter=round(float(np.mean(jit[[rows.index(r) for r in rr]])), 2)))
    res[os.path.basename(f)] = dict(fps=fps, frames=n, dur=round(n / fps, 2), static_edge_px_border=static, per_sec=sec)
    print(os.path.basename(f), "dur", round(n/fps,2), "static_border_px", static)
    for s in sec: print("   ", s)
json.dump(res, open(sys.argv[2], "w"), indent=1)
