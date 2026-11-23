import sys, os
from PIL import Image, ImageDraw
out, cols, cell = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
paths = sys.argv[4:]
rows = (len(paths) + cols - 1) // cols
sheet = Image.new('RGB', (cols * cell, rows * (cell + 18)), (24, 24, 28))
dr = ImageDraw.Draw(sheet)
for i, p in enumerate(paths):
    im = Image.open(p).convert('RGB')
    im.thumbnail((cell, cell))
    x, y = (i % cols) * cell, (i // cols) * (cell + 18)
    sheet.paste(im, (x + (cell - im.width) // 2, y + (cell - im.height) // 2))
    dr.text((x + 4, y + cell + 3), os.path.basename(p)[:-4], fill=(230, 230, 230))
sheet.save(out)
print(out)
