"""Build the final ffmpeg command: main segments + B-roll with xfade transitions, push-in, subtitles."""
import json, sys, subprocess, shlex
main, out = sys.argv[1], sys.argv[2]
preview = "--preview" in sys.argv          # 960x540 fast render of a time range
rng = [float(x) for x in sys.argv[sys.argv.index("--range")+1].split(":")] if "--range" in sys.argv else None
plan = json.load(open("edit_plan.json")); B = plan["broll"]; D = 158.4; d = 0.25
inputs = ["-i", main] + sum((["-i", b["clip"]] for b in B), [])
segs, t = [], 0.0
for i, b in enumerate(B):
    segs.append(("main", t, b["start"] + d/2)); segs.append(("broll", i, b["end"] - b["start"] + d)); t = b["end"] - d/2
segs.append(("main", t, D))
SS = "3840:2160" if not preview else "1920:1080"
fc, labels = [], []
for k, s in enumerate(segs):
    if s[0] == "main":
        a, e = s[1], s[2]; n = round((e - a) * 30)
        src = f"[0:v]trim=start={a}:end={e},setpts=PTS-STARTPTS," + ("fps=30," if "--rawmain" in sys.argv else "")
        z = f"1+0.08*on/{n}"
    else:
        i, L = s[1], s[2]; n = round(L * 30)
        src = f"[{i+1}:v]trim=duration={L},setpts=PTS-STARTPTS,"
        z = f"1+0.06*on/{n}"
    fc.append(f"{src}scale={SS}:flags=lanczos,zoompan=z='{z}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1920x1080:fps=30,setsar=1,format=yuv420p[s{k}]")
    labels.append((f"s{k}", s))
cur, off = "s0", 0.0
for k in range(1, len(segs)):
    prev = segs[k-1]; plen = (prev[2]-prev[1]) if prev[0] == "main" else prev[2]
    off = (off + plen - d) if k > 1 else plen - d
    trans = "zoomin" if segs[k][0] == "broll" else "smoothleft"
    fc.append(f"[{cur}][s{k}]xfade=transition={trans}:duration={d}:offset={off:.4f}[x{k}]"); cur = f"x{k}"
post = "ass=subs.ass:fontsdir=fonts"
if preview: post += ",scale=960:540:flags=lanczos"
fc.append(f"[{cur}]{post}[vout]")
cmd = ["ffmpeg", "-nostdin", "-v", "error", "-stats", "-y"] + inputs + ["-i", "work/audio_final.wav", "-filter_complex", ";".join(fc),
       "-map", "[vout]", "-map", f"{len(B)+1}:a"]
if rng: cmd += ["-ss", str(rng[0]), "-t", str(rng[1] - rng[0])]
if preview:
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k"]
else:
    cmd += ["-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
            "-x264-params", "vbv-maxrate=40000:vbv-bufsize=60000", "-r", "30",
            "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart"]
cmd += ["-shortest", out]
print(" ".join(shlex.quote(c) for c in cmd)[:400], "...")
subprocess.run(cmd, check=True)
