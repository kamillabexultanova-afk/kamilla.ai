#!/bin/bash
# id src start dur desc quality
set -e
mkdir -p clips
while read id src ss dur; do
  [ -z "$id" ] && continue
  ffmpeg -nostdin -v error -y -ss $ss -t $dur -i broll/$src.mp4 -an \
    -vf "hqdn3d=1.5:1.5:4:4,scale=1920:1080:flags=lanczos,unsharp=5:5:0.5:5:5:0.0,eq=contrast=1.08:saturation=1.10,colortemperature=temperature=6200,fps=30" \
    -c:v libx264 -preset slow -crf 10 -pix_fmt yuv420p clips/$id.mp4
  echo "$id ok"
done <<LIST
c01 broll_01 0.5 5.5
c02 broll_02 0.0 4.5
c03 broll_03 0.0 5.0
c04 broll_04 0.0 2.0
c05 broll_05 0.0 5.5
c06 broll_06 0.0 3.5
LIST
