#!/bin/bash
# full-quality render of version 4 (statics reused from v3: same set, same cameras), three frame workers
cd "$(dirname "$0")"
PY=../blender-venv/bin/python
OUT=${1:-out_v4b}
mkdir -p $OUT/px
for r in 0:215 216:431 432:647; do
  $PY excerpt4.py frames $OUT --frames $r > $OUT/frames_${r/:/_}.log 2>&1 &
done
wait
echo RENDER DONE
