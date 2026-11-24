#!/bin/bash
# after run_v5.sh: final MP4 (captions + music + door + steps), a caption-free copy and MediaPipe tracks for the critics
set -e
cd "$(dirname "$0")"
OUT=${1:-out_v5}; TAG=${2:-v5}
NAME=Nox-et-Pico-ep01-extrait-3D-$TAG.mp4
NP_SCRIPT=script5 ../blender-venv/bin/python post2.py video $OUT $NAME
cp $OUT/$NAME ../study/mine_$TAG.mp4
ffmpeg -y -loglevel error -framerate 30 -i $OUT/px/f%05d.png -c:v libx264 -preset slow -crf 14 -pix_fmt yuv420p ../study/mine_${TAG}_nocaptions.mp4
../mpenv/bin/python ../study/extract.py ../study/mine_${TAG}_nocaptions.mp4 ../study/data/mine_$TAG.npz || true
echo FINISH DONE
