import json, sys
from faster_whisper import WhisperModel
m = WhisperModel("large-v3", device="cpu", compute_type="int8", cpu_threads=4)
segs, info = m.transcribe(sys.argv[1], language="ru", word_timestamps=True, beam_size=5, vad_filter=False)
out = {"language": info.language, "duration": info.duration, "segments": []}
for s in segs:
    out["segments"].append({"start": s.start, "end": s.end, "text": s.text,
        "words": [{"word": w.word.strip(), "start": round(w.start,3), "end": round(w.end,3), "prob": round(w.probability,3)} for w in s.words]})
    print(f"[{s.start:6.2f}-{s.end:6.2f}] {s.text}", flush=True)
json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
