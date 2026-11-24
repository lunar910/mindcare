#!/bin/bash
# full render of version 5: the shot plates first (one clean high-sample background per locked-off shot, reused by every
# frame), then the 738 frames in two workers (each frame = a low-sample render of the moving part, merged into its plate)
cd "$(dirname "$0")"
PY=../blender-venv/bin/python
OUT=${1:-out_v5}
mkdir -p $OUT/px $OUT/plates
$PY excerpt5.py stills $OUT --plates --times 1.2,3.0,4.40,6.4,9.13,11.0,13.7,14.6,16.6,20.0,23.2 > $OUT/plates.log 2>&1
for r in 0:368 369:737; do
  $PY excerpt5.py frames $OUT --plates --frames $r > $OUT/frames_${r/:/_}.log 2>&1 &
done
wait
echo RENDER DONE
