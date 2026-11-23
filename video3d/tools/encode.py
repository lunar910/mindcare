"""Assemble rendered frames into the final clip: PS2-style grade, reel subtitles, optional vertical 9:16 layout.

    python3 encode.py FRAMES_DIR OUT.mp4 --fps 15 [--subs subs.json] [--vertical] [--audio voice.wav]

FRAMES_DIR holds 0001.png, 0002.png ... (640x480). subs.json = [{"start": 1.0, "end": 3.2, "text": "..."}]."""
import argparse
import json
import os
import subprocess
import tempfile

FONT = '/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf'

ap = argparse.ArgumentParser()
ap.add_argument('frames')
ap.add_argument('out')
ap.add_argument('--fps', type=float, default=15)
ap.add_argument('--subs')
ap.add_argument('--vertical', action='store_true')
ap.add_argument('--audio')
ap.add_argument('--still', action='store_true', help='treat FRAMES as one image and write one graded PNG')
a = ap.parse_args()

W, H = (1080, 810) if a.vertical else (1440, 1080)
fs = 34 if a.vertical else 46
chain = [f'scale={W}:{H}:flags=bilinear', 'eq=contrast=1.1:saturation=0.94:brightness=-0.012',
         'split[base][glow]', '[glow]gblur=sigma=14[glow2]', '[base][glow2]blend=all_mode=screen:all_opacity=0.18',
         'vignette=PI/5.5', 'noise=alls=4:allf=t']
tmp = tempfile.mkdtemp()
if a.subs:
    for i, s in enumerate(json.load(open(a.subs))):
        tf = os.path.join(tmp, f's{i}.txt')
        open(tf, 'w', encoding='utf-8').write(s['text'])
        chain.append(f"drawtext=fontfile={FONT}:textfile={tf}:fontsize={fs}:fontcolor=white:borderw={max(3, fs // 11)}:bordercolor=black:"
                     f"x=(w-text_w)/2:y=h-{int(fs * 2.9)}:enable='between(t,{s['start']},{s['end']})'")
if a.vertical:
    chain.append('pad=1080:1920:0:555:color=0x0b0f17')
# the first filters use labels, so build one filtergraph string
head = f"[0:v]{chain[0]},{chain[1]},{chain[2]};{chain[3]};{chain[4]}"
vf = head + ''.join(',' + c for c in chain[5:]) + '[v]'
cmd = ['ffmpeg', '-y', '-loglevel', 'error']
if a.still:
    cmd += ['-i', a.frames, '-filter_complex', vf, '-map', '[v]', '-frames:v', '1', a.out]
else:
    cmd += ['-framerate', str(a.fps), '-i', os.path.join(a.frames, '%04d.png')]
    if a.audio:
        cmd += ['-i', a.audio]
    cmd += ['-filter_complex', vf, '-map', '[v]']
    if a.audio:
        cmd += ['-map', '1:a', '-c:a', 'aac', '-b:a', '160k', '-shortest']
    cmd += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '17', '-r', str(max(a.fps, 30)), a.out]
subprocess.run(cmd, check=True)
print('wrote', a.out)
