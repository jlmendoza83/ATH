#!/usr/bin/env bash
# tools/build.sh — Rebuild the explainer video end to end.
#
#   script.json ──tts.py──► narration.wav + timings.js + captions-en.vtt
#               ──music.py─► music.wav
#               ──ffmpeg──► src/audio.m4a  (voice + ducked music, -16 LUFS)
#   src/index.html ──render.cjs──► build/video-master.mp4 ──ffmpeg──► dist/*.mp4 + poster.jpg
#
# Requirements: python3 (kokoro-onnx soundfile numpy imageio-ffmpeg), node + playwright.
set -euo pipefail
cd "$(dirname "$0")/.."

FFMPEG="${FFMPEG:-$(python3 -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')}"
export FFMPEG
export NODE_PATH="${NODE_PATH:-$(npm root -g)}"
mkdir -p build dist

python3 tools/tts.py
DUR=$(python3 -c "import json; print(json.load(open('build/timings.json'))['duration'])")
python3 tools/music.py "$DUR"

echo "[mix] voice + music (bed ~14 dB under the voice, ducked further while speaking)"
"$FFMPEG" -y -loglevel error -i build/narration.wav -i build/music.wav -filter_complex \
  "[0:a]aresample=48000,aformat=channel_layouts=stereo,highpass=f=70,acompressor=threshold=-18dB:ratio=2.5:attack=5:release=150,asplit=2[v1][v2];\
   [1:a]highpass=f=90,volume=0.14[m];\
   [m][v1]sidechaincompress=threshold=0.02:ratio=6:attack=40:release=800[md];\
   [v2][md]amix=inputs=2:duration=first:normalize=0" \
  -c:a pcm_s16le build/mix.wav

# Two-pass, linear loudness normalisation to -16 LUFS (web/podcast standard, no pumping)
MEAS=$("$FFMPEG" -hide_banner -i build/mix.wav -af loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json -f null - 2>&1 | python3 -c '
import sys, json, re
d = json.loads(re.findall(r"\{[^{}]*\}", sys.stdin.read(), re.S)[-1])
keys = [("measured_I", "input_i"), ("measured_TP", "input_tp"), ("measured_LRA", "input_lra"),
        ("measured_thresh", "input_thresh"), ("offset", "target_offset")]
print(":".join(k + "=" + d[v] for k, v in keys))')
"$FFMPEG" -y -loglevel error -i build/mix.wav -af "loudnorm=I=-16:TP=-1.5:LRA=11:$MEAS:linear=true" \
  -ar 48000 -c:a aac -b:a 192k src/audio.m4a

# Video is rendered once into a near-lossless master; audio can be remixed without re-rendering.
if [[ ! -f build/video-master.mp4 || src/index.html -nt build/video-master.mp4 || src/timings.js -nt build/video-master.mp4 ]]; then
  node tools/render.cjs video build/video-master.mp4 30
fi

OUT=dist/gabriel-archangel-how-it-works
echo "[encode] 1080p"
"$FFMPEG" -y -loglevel error -i build/video-master.mp4 -i src/audio.m4a -map 0:v -map 1:a \
  -c:v libx264 -preset slow -crf 21 -tune animation -pix_fmt yuv420p -profile:v high -level 4.1 \
  -c:a copy -movflags +faststart -shortest "$OUT-1080p.mp4"
echo "[encode] 720p"
"$FFMPEG" -y -loglevel error -i build/video-master.mp4 -i src/audio.m4a -map 0:v -map 1:a \
  -vf scale=1280:720:flags=lanczos \
  -c:v libx264 -preset slow -crf 23 -tune animation -pix_fmt yuv420p -profile:v high \
  -c:a aac -b:a 128k -movflags +faststart -shortest "$OUT-720p.mp4"

POSTER_T=$(python3 -c "import json; t=json.load(open('build/timings.json')); print(t['scenes']['intro']['end'] - 0.8)")
"$FFMPEG" -y -loglevel error -ss "$POSTER_T" -i build/video-master.mp4 -frames:v 1 -q:v 2 dist/poster.jpg

ls -lh dist
