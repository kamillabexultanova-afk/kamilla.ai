import sherpa_onnx, numpy as np, json, sys
M = sys.argv[1]
rec = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=f"{M}/encoder.int8.onnx", decoder=f"{M}/decoder.onnx", joiner=f"{M}/joiner.onnx",
    tokens=f"{M}/tokens.txt", model_type="nemo_transducer", num_threads=4, decoding_method="greedy_search")
import wave; _w = wave.open(sys.argv[2]); sr = _w.getframerate(); a = np.frombuffer(_w.readframes(_w.getnframes()), np.int16).astype(np.float32)/32768; assert sr == 16000
# split at quiet points: frame RMS 20ms, cut at quietest frame within 12-20 s windows
fr = 320; rms = np.sqrt(np.convolve(a**2, np.ones(fr)/fr, "same"))[::fr]
cuts = [0]; 
while len(a)/sr - cuts[-1]/50 > 20:
    lo, hi = cuts[-1] + 12*50, cuts[-1] + 20*50
    cuts.append(lo + int(np.argmin(rms[lo:hi])))
cuts.append(len(rms))
words = []
for s, e in zip(cuts[:-1], cuts[1:]):
    st = rec.create_stream(); off = s/50
    st.accept_waveform(sr, a[s*fr:e*fr]); rec.decode_stream(st); r = st.result
    cur = None
    for tok, t in zip(r.tokens, r.timestamps):
        t = round(off + t, 3)
        if tok.startswith("▁") or tok == " " or cur is None:
            if cur: words.append(cur)
            cur = {"word": tok.replace("▁", "").strip(), "start": t, "end": t + 0.08}
        else:
            cur["word"] += tok; cur["end"] = t + 0.08
    if cur: words.append(cur)
    print(f"[{off:6.2f}] {r.text}", flush=True)
words = [w for w in words if w["word"]]
# end of word = just before next word start (bounded)
for w, n in zip(words, words[1:] + [None]):
    w["end"] = round(min(w["end"] + 0.12, n["start"]) if n else w["end"] + 0.15, 3)
json.dump({"model": "GigaAM-v2 RNNT (sherpa-onnx)", "words": words}, open(sys.argv[3], "w"), ensure_ascii=False, indent=1)
print(len(words), "words")
