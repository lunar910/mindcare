"""Contact strip of rendered frames.   python strip.py OUT_DIR f0 f1 step cols out.png [w]"""
import sys
from PIL import Image
d, f0, f1, step, cols, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
w = int(sys.argv[7]) if len(sys.argv) > 7 else 135
fs = list(range(f0, f1 + 1, step))
ims = [Image.open(f'{d}/px/f{f:05d}.png').convert('RGB') for f in fs]
h = int(w * ims[0].size[1] / ims[0].size[0])
rows = (len(ims) + cols - 1) // cols
sheet = Image.new('RGB', (cols * (w + 2), rows * (h + 2)), 'white')
for i, im in enumerate(ims):
    sheet.paste(im.resize((w, h), Image.LANCZOS), ((i % cols) * (w + 2), (i // cols) * (h + 2)))
sheet.save(out); print(out, sheet.size, len(ims), 'frames')
