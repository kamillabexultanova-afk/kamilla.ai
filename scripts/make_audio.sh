#!/bin/bash
# voice cleanup + whooshes at b-roll in/out, then 2-pass loudnorm to -14 LUFS / -1 dBTP
set -e
W=$(python3 -I -c "
import json; p=json.load(open('edit_plan.json'))
ts=[t for b in p['broll'] for t in (b['start']-0.35, b['end']-0.35)]
print(' '.join(str(int(t*1000)) for t in ts))")
inputs="-i input.mp4"; fc="[0:a]aresample=48000,aformat=channel_layouts=stereo,highpass=f=80,afftdn=nf=-28:nr=10,equalizer=f=4000:t=q:w=1.2:g=3.5,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=160:makeup=2[v];"
mix="[v]"; n=1
for ms in $W; do
  inputs="$inputs -i sfx/whoosh_synth.wav"; fc="$fc[$n:a]adelay=${ms}|${ms},volume=-9dB[w$n];"; mix="$mix[w$n]"; n=$((n+1))
done
fc="${fc}${mix}amix=inputs=$n:normalize=0:duration=first[m]"
ffmpeg -nostdin -v error -y $inputs -filter_complex "$fc" -map "[m]" -c:a pcm_s24le work/mix.wav
J=$(ffmpeg -nostdin -hide_banner -i work/mix.wav -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null - 2>&1 | sed -n '/{/,/}/p')
g(){ echo "$J" | python3 -c "import sys,json;print(json.load(sys.stdin)['$1'])"; }
ffmpeg -nostdin -v error -y -i work/mix.wav -af "loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=$(g input_i):measured_TP=$(g input_tp):measured_LRA=$(g input_lra):measured_thresh=$(g input_thresh):offset=$(g target_offset):linear=true,alimiter=limit=0.89:level=false,aresample=48000" -c:a pcm_s24le work/audio_final.wav
ffmpeg -nostdin -hide_banner -i work/audio_final.wav -af ebur128=peak=true -f null - 2>&1 | grep -A12 Summary | grep -E "I:|Peak:"
