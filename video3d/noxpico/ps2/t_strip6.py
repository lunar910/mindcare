"""Face strips from rendered frames.  python t_strip6.py DIR F0 F1 STEP X0,Y0,X1,Y1 OUT.jpg [cols] [size]"""
import sys, os
from PIL import Image, ImageDraw
d, f0, f1, st = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
box = tuple(int(x) for x in sys.argv[5].split(','))
out = sys.argv[6]
cols = int(sys.argv[7]) if len(sys.argv) > 7 else 10
size = int(sys.argv[8]) if len(sys.argv) > 8 else 220
ims = []
for f in range(f0, f1 + 1, st):
    p = f'{d}/px/f{f:05d}.png'
    if not os.path.exists(p):
        continue
    im = Image.open(p).convert('RGB').crop(box)
    im = im.resize((size, int(size * im.height / im.width)), Image.LANCZOS)
    ImageDraw.Draw(im).text((4, 2), '%.2f' % (f / 30), fill=(255, 255, 0))
    ims.append(im)
if not ims:
    sys.exit('no frames')
h = ims[0].height
rows = (len(ims) + cols - 1) // cols
s = Image.new('RGB', (cols * size, rows * h))
for i, im in enumerate(ims):
    s.paste(im, ((i % cols) * size, (i // cols) * h))
s.save(out, quality=90)
print(out, len(ims), 'frames')
