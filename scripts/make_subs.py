import json, re, sys
words = json.load(open("transcript.json"))["words"]
plan = json.load(open("edit_plan.json"))
hidden = [(b["start"], b["end"]) for b in plan["broll"]] + [tuple(x) for x in plan["own_inserts"]]

# ASR fixes (merge / replace), applied on lowercase tokens
W = [dict(w) for w in words]
out = []
i = 0
while i < len(W):
    w = W[i]; t = w["word"]
    nxt = W[i+1]["word"] if i+1 < len(W) else ""
    if t == "чан" and nxt == "зензе":
        w = dict(w, word="чжанцзяцзе", end=W[i+1]["end"]); i += 1
    elif t in ("во", "что", "чуть", "ха") and nxt in ("первых", "то", "чуть", "ха"):
        w = dict(w, word=f"{t}-{nxt}", end=W[i+1]["end"]); i += 1
    elif t == "только" and nxt == "эмоций":
        w = dict(w, word="столько")
    elif t == "места" and out and out[-1]["word"] == "много":
        w = dict(w, word="мест")
    else:
        w = dict(w, word={"джунсы": "чунцин", "рилам": "рилсам", "яружан": "аружан", "дешевлем": "дешевле",
                          "выбирайте": "выбираете", "спишет": "пишет", "инстаграм": "инстаграм"}.get(t, t))
    out.append(w); i += 1

FILLERS = {"вот", "ну", "типа", "ээ", "эм", "а"}
KEY = {"мошенников", "китай", "китаю", "чжанцзяцзе", "чунцин", "японию", "корею", "эмоций", "дороже", "дешевле",
       "цены", "комфортно", "комфорт", "шикарные", "круто", "крутой", "классно", "туман", "рилсам", "инстаграм",
       "свобода", "честный", "отзыв", "айдана", "илья", "аружан", "идеальное", "дважды", "лично", "невероятная",
       "доверие", "оправдались", "давил"}
ACCENT = {"мошенников"}
words = [w for w in out if w["word"] not in FILLERS and not any(a <= w["start"] < b for a, b in hidden)]

# chunk: keywords alone; others up to 3 words / 14 chars, break on gaps > 0.35 s
chunks, cur = [], []
for w in words:
    key = w["word"] in KEY
    if cur and (key or cur[-1]["word"] in KEY or len(cur) == 3 or w["start"] - cur[-1]["end"] > 0.35
                or sum(len(x["word"]) for x in cur) + len(w["word"]) > 16):
        chunks.append(cur); cur = []
    cur.append(w)
if cur: chunks.append(cur)

def ts(t):
    t = max(t, 0); return f"{int(t//3600)}:{int(t%3600//60):02d}:{t%60:05.2f}"
def clip_end(s, e):
    for a, b in hidden:
        if s < a < e: e = a
    return e

ev = []
for k, c in enumerate(chunks):
    s = c[0]["start"] - 0.05
    nxt = chunks[k+1][0]["start"] - 0.05 if k+1 < len(chunks) else c[-1]["end"] + 0.6
    e = clip_end(s, min(nxt, c[-1]["end"] + 0.5))
    if e - s < 0.15: continue
    text = " ".join(x["word"] for x in c).upper()
    if c[0]["word"] in ACCENT:
        tag = r"{\an2\pos(960,900)\fscx30\fscy30\frz-6\t(0,110,\fscx135\fscy135\frz4)\t(110,200,\fscx92\fscy92\frz-2)\t(200,280,\fscx100\fscy100\frz0)}"
        ev.append(("Accent", s, e, tag + text))
    elif c[0]["word"] in KEY:
        tag = r"{\an2\pos(960,900)\fscx30\fscy30\t(0,110,\fscx122\fscy122)\t(110,190,\fscx94\fscy94)\t(190,260,\fscx100\fscy100)}"
        ev.append(("Key", s, e, tag + text))
    else:
        tag = r"{\an2\pos(960,905)\fscx70\fscy70\t(0,90,\fscx108\fscy108)\t(90,150,\fscx100\fscy100)}"
        ev.append(("Word", s, e, tag + text))

hdr = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,Montserrat ExtraBold,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,1,0,1,6,2,2,60,60,60,1
Style: Key,Montserrat Black,118,&H0000D6FF,&H0000D6FF,&H00000000,&H8C000000,0,0,0,0,100,100,2,0,1,7,5,2,60,60,60,1
Style: Accent,Montserrat Black,132,&H0000D6FF,&H0000D6FF,&H00000000,&H8C000000,0,0,0,0,100,100,2,0,1,8,6,2,60,60,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
with open(sys.argv[1], "w") as f:
    f.write(hdr)
    for st, s, e, t in ev:
        f.write(f"Dialogue: 0,{ts(s)},{ts(e)},{st},,0,0,0,,{t}\n")
print(len(ev), "events;", sum(1 for x in ev if x[0] != "Word"), "keyword pops")
