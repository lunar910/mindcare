"""Contact sheet: python3 -I sheet.py OUT.png COLS CELL_WIDTH img1.png img2.png ...   (labels = file names; nearest-neighbour scaling)"""
import os
import sys

from PIL import Image, ImageDraw

out, cols, cell = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
files = sys.argv[4:]
ims = []
for f in files:
    im = Image.open(f).convert('RGB')
    h = round(im.height * cell / im.width)
    ims.append((os.path.splitext(os.path.basename(f))[0], im.resize((cell, h), Image.NEAREST if cell >= im.width else Image.LANCZOS)))
rows = (len(ims) + cols - 1) // cols
ch = max(i.height for _, i in ims) + 16
sheet = Image.new('RGB', (cols * cell, rows * ch), (22, 22, 26))
d = ImageDraw.Draw(sheet)
for k, (name, im) in enumerate(ims):
    x, y = (k % cols) * cell, (k // cols) * ch
    sheet.paste(im, (x, y))
    d.text((x + 4, y + ch - 14), name, fill=(235, 235, 235))
sheet.save(out)
print(out, sheet.size)
