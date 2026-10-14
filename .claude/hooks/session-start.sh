#!/bin/bash
# Prepares a Claude Code cloud session for making video from code:
# FFmpeg, whisper.cpp (whisper-cli), HyperFrames CLI + agent skills + headless Chrome,
# and the Python packages used by scripts/ (OpenCV, faster-whisper, sherpa-onnx, Pillow, python-pptx).
# Idempotent: every step checks first and skips what is already there.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

log() { echo "[session-start] $*" >&2; }

# 1. FFmpeg / ffprobe
if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  log "installing ffmpeg"
  apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ffmpeg >/dev/null
fi

# 2. whisper.cpp -> whisper-cli in PATH (built from source; no prebuilt Linux binary)
if ! command -v whisper-cli >/dev/null; then
  log "building whisper.cpp"
  src="$HOME/.cache/whisper.cpp"
  [ -d "$src/.git" ] || git clone --depth 1 https://github.com/ggml-org/whisper.cpp "$src"
  cmake -S "$src" -B "$src/build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF >/dev/null
  cmake --build "$src/build" -j"$(nproc)" --target whisper-cli >/dev/null
  install -m755 "$src/build/bin/whisper-cli" /usr/local/bin/whisper-cli
fi

# 3. HyperFrames CLI, agent skills, headless Chrome
if ! command -v hyperframes >/dev/null; then
  log "installing hyperframes"
  npm install -g hyperframes >/dev/null 2>&1
fi
if [ ! -d "$HOME/.claude/skills/hyperframes" ]; then
  log "installing hyperframes skills"
  (cd "$HOME" && hyperframes skills >/dev/null 2>&1) || log "WARN: hyperframes skills failed"
fi
if ! ls "$HOME"/.cache/hyperframes/chrome/chrome-headless-shell/*/chrome-headless-shell-linux64/chrome-headless-shell >/dev/null 2>&1; then
  log "downloading headless Chrome"
  (cd "$HOME" && hyperframes browser ensure >/dev/null 2>&1) || log "WARN: headless Chrome download failed"
fi

# 4. Python packages used by scripts/
missing=()
python3 -c "import cv2" 2>/dev/null || missing+=(opencv-python-headless)
python3 -c "import faster_whisper" 2>/dev/null || missing+=(faster-whisper)
python3 -c "import sherpa_onnx" 2>/dev/null || missing+=(sherpa-onnx)
python3 -c "import PIL" 2>/dev/null || missing+=(pillow)
python3 -c "import pptx" 2>/dev/null || missing+=(python-pptx)
if [ ${#missing[@]} -gt 0 ]; then
  log "pip installing ${missing[*]}"
  pip3 install -q --break-system-packages "${missing[@]}"
fi

# 5. Multilingual whisper.cpp model (Russian-capable). Needs huggingface.co to be
#    allowed in the environment's network settings; skipped with a warning otherwise.
model_dir="$HOME/.cache/whisper-models"
model="$model_dir/ggml-small.bin"
if [ ! -s "$model" ]; then
  mkdir -p "$model_dir"
  if curl -fsSL -o "$model.part" https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin; then
    mv "$model.part" "$model"
  else
    rm -f "$model.part"
    log "WARN: whisper model not downloaded (huggingface.co blocked?) - speech-to-text unavailable"
  fi
fi

log "done"
