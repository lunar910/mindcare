#!/bin/bash
# full-quality render of version 3: statics, then three frame workers
cd "$(dirname "$0")"
PY=../blender-venv/bin/python
$PY excerpt3.py statics out_v3 --ao 64 > out_v3/statics.log 2>&1 || { echo STATICS FAILED; exit 1; }
for r in 0:215 216:431 432:647; do
  $PY excerpt3.py frames out_v3 --frames $r > out_v3/frames_${r/:/_}.log 2>&1 &
done
wait
echo RENDER DONE
