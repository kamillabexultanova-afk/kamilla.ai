#!/bin/bash
# 19fps -> 30fps motion interpolation + denoise + grade, 4 parallel chunks
B=(0 40 80 120 158.4)
for i in 0 1 2 3; do
  ffmpeg -nostdin -v error -y -i input.mp4 -an -vf "trim=start=${B[$i]}:end=${B[$((i+1))]},setpts=PTS-STARTPTS,minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,hqdn3d=2:1.5:4:3,eq=contrast=1.08:saturation=1.10,unsharp=5:5:0.4:5:5:0" \
    -c:v libx264 -preset fast -crf 8 -pix_fmt yuv420p work/main_$i.mp4 &
done
wait
printf "file 'main_%d.mp4'\n" 0 1 2 3 > work/list.txt
ffmpeg -nostdin -v error -y -f concat -safe 0 -i work/list.txt -c copy work/main30.mp4
echo done
