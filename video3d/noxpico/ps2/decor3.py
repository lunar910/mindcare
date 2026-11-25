"""Set dressing for version 3 of the workshop: more to look at in every shot.   import decor3; decor3.dress(A)

Everything is placed for the cameras of excerpt3.py (each line says which shot it is for).  Simple geometry + pictures
drawn front-on at real size, in the same hand-made low-poly spirit as the rest of the room:
  - a hanging lamp in the foreground of the wide shot (it is what "lights" the scene),
  - a low cabinet under the window with a radio, books and a cactus; a red toolbox on the floor,
  - a shelf with books, a globe and a box above the door,
  - the corridor behind the door (background of Pico's two shots): calmer wall colour, a picture, a wall lamp, a
    coat rack with a jacket and a cap."""
import math

import bpy
import numpy as np
from mathutils import Vector
from PIL import Image, ImageDraw

import atelier2 as AT

OUT = (26, 18, 22, 255)
SCONCE_Y = 2.46            # the wall lamp of the corridor: at the edge of Pico's medium shot, outside her close-up


# ------------------------------------------------------------------ small builders
def _flat_shade(ob):
    for p in ob.data.polygons:
        p.use_smooth = False


def rod(name, p0, p1, r, mat, verts=8):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=d.length, location=(p0 + p1) / 2)
    ob = bpy.context.active_object
    ob.name = name
    ob.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    ob.data.materials.append(mat)
    return ob


def cone(name, loc, r_bottom, r_top, depth, mat, verts=12, rot=(0, 0, 0), caps=True):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r_bottom, radius2=r_top, depth=depth, location=loc, rotation=rot,
                                    end_fill_type='NGON' if caps else 'NOTHING')
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(mat)
    _flat_shade(ob)
    return ob


def ball(name, loc, r, mat, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=10, ring_count=7, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = scale
    ob.data.materials.append(mat)
    return ob


def box(name, c, size, mat, rot=(0.0, 0.0, 0.0)):
    """A box that keeps its own origin (so that it can be turned on the spot)."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=c, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = size
    ob.data.materials.append(mat)
    return ob


def rbox(name, c, size, mat, rot_z=0.0):
    return box(name, c, size, mat, (0.0, 0.0, rot_z))


# ------------------------------------------------------------------ drawn pieces (PIL image, (width_m, height_m))
def cabinet_front(ppm=300):
    W, H = int(0.74 * ppm), int(0.62 * ppm)
    im = Image.new('RGBA', (W, H), (112, 72, 46, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W - 1, H - 1], outline=OUT, width=2)
    for k in range(2):
        y0, y1 = int(H * (0.06 + 0.46 * k)), int(H * (0.48 + 0.46 * k))
        d.rectangle([int(W * 0.05), y0, int(W * 0.95), y1], fill=(132, 88, 56, 255), outline=(70, 44, 28, 255), width=2)
        d.line([int(W * 0.07), y0 + 4, int(W * 0.93), y0 + 4], fill=(156, 108, 70, 255), width=2)
        for x in (0.3, 0.7):
            cx, cy = int(W * x), (y0 + y1) // 2
            d.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=(196, 176, 120, 255), outline=OUT)
    return im, (0.74, 0.62)


def radio_front(ppm=600):
    W, H = int(0.26 * ppm), int(0.15 * ppm)
    im = Image.new('RGBA', (W, H), (176, 70, 52, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W - 1, H - 1], outline=OUT, width=2)
    d.rectangle([8, 8, int(W * 0.56), H - 9], fill=(60, 50, 48, 255), outline=OUT)                      # speaker grill
    for y in range(13, H - 12, 6):
        d.line([12, y, int(W * 0.56) - 4, y], fill=(96, 84, 80, 255), width=2)
    d.rectangle([int(W * 0.62), 10, W - 10, int(H * 0.45)], fill=(232, 222, 190, 255), outline=OUT)     # dial
    for k in range(6):
        x = int(W * 0.64) + k * int(W * 0.05)
        d.line([x, 13, x, int(H * 0.30)], fill=(90, 70, 60, 255))
    d.line([int(W * 0.78), 12, int(W * 0.78), int(H * 0.42)], fill=(214, 60, 50, 255), width=2)
    for x in (0.68, 0.86):
        cx, cy = int(W * x), int(H * 0.72)
        d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=(232, 222, 190, 255), outline=OUT)
    return im, (0.26, 0.15)


def picture_sea(ppm=420):
    W, H = int(0.30 * ppm), int(0.38 * ppm)
    im = Image.new('RGBA', (W, H), (70, 46, 32, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W - 1, H - 1], outline=OUT, width=2)
    x0, y0, x1, y1 = 9, 9, W - 10, H - 10
    for y in range(y0, y1):
        t = (y - y0) / (y1 - y0)
        col = (int(250 - 60 * t), int(170 + 20 * t), int(110 + 90 * t)) if t < 0.55 else (int(40 + 30 * (t - 0.55)), int(96 + 60 * (1 - t)), int(150 + 40 * (1 - t)))
        d.line([x0, y, x1, y], fill=col + (255,))
    cy = y0 + int((y1 - y0) * 0.50)
    d.ellipse([W // 2 - 16, cy - 20, W // 2 + 16, cy + 12], fill=(255, 236, 170, 255))
    d.rectangle([x0, y0 + int((y1 - y0) * 0.55), x1, y0 + int((y1 - y0) * 0.57)], fill=(250, 220, 170, 255))
    d.polygon([(x0, y1), (x0, y0 + int((y1 - y0) * 0.72)), (x0 + 30, y0 + int((y1 - y0) * 0.66)), (x0 + 52, y1)], fill=(34, 40, 60, 255))
    return im, (0.30, 0.38)


def jacket(ppm=300):
    W, H = int(0.46 * ppm), int(0.70 * ppm)
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    body, dark, light = (44, 96, 112, 255), (30, 68, 82, 255), (66, 128, 144, 255)
    cx = W // 2
    d.polygon([(cx - 24, 16), (cx + 24, 16), (cx + 62, 40), (cx + 58, H - 12), (cx - 58, H - 12), (cx - 62, 40)], fill=body, outline=OUT)
    d.polygon([(cx - 62, 40), (cx - 68, int(H * 0.72)), (cx - 50, int(H * 0.74)), (cx - 44, 70)], fill=dark, outline=OUT)      # sleeves hang
    d.polygon([(cx + 62, 40), (cx + 68, int(H * 0.72)), (cx + 50, int(H * 0.74)), (cx + 44, 70)], fill=dark, outline=OUT)
    d.polygon([(cx - 24, 16), (cx, 44), (cx + 24, 16), (cx + 14, 8), (cx - 14, 8)], fill=light, outline=OUT)                   # collar
    d.line([cx, 44, cx, H - 14], fill=(222, 214, 190, 255), width=3)                                                       # zip
    d.rectangle([cx - 58, H - 30, cx + 58, H - 12], fill=dark, outline=OUT)
    d.rectangle([cx - 44, int(H * 0.55), cx - 14, int(H * 0.57)], fill=dark)
    d.rectangle([cx + 14, int(H * 0.55), cx + 44, int(H * 0.57)], fill=dark)
    d.line([cx, 8, cx, 0], fill=OUT, width=3)                                                                              # hanging loop
    return im, (0.46, 0.70)


def cap(ppm=300):
    W, H = int(0.26 * ppm), int(0.20 * ppm)
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.pieslice([8, 6, W - 22, H + 30], 180, 360, fill=(206, 62, 54, 255), outline=OUT)
    d.polygon([(W - 40, H - 14), (W - 2, H - 8), (W - 4, H - 2), (W - 44, H - 4)], fill=(150, 40, 36, 255), outline=OUT)
    d.rectangle([8, H - 12, W - 30, H - 4], fill=(176, 50, 44, 255), outline=OUT)
    d.ellipse([W // 2 - 20, 4, W // 2 - 10, 14], fill=(240, 232, 210, 255), outline=OUT)
    return im, (0.26, 0.20)


BOOKS = [(196, 62, 54), (58, 110, 176), (226, 178, 60), (70, 150, 96), (140, 84, 150), (222, 214, 190), (40, 60, 90)]


# ------------------------------------------------------------------ the dressing
def dress(A):
    x0, x1 = A['doorway']
    Y = AT.WALL_Y
    wood = AT.mat_col('d_wood', [112, 72, 46])
    wood_d = AT.mat_col('d_wood_dark', [78, 50, 34])
    metal = AT.mat_col('d_metal', [58, 62, 72])
    made = []

    # ---- hanging lamp, foreground top of the wide shot
    lx, ly = -0.16, -0.60
    enamel = AT.mat_col('lamp_enamel', [34, 86, 72])
    glow_in = AT.mat_col('lamp_inside', [255, 214, 150], emit=2.2)
    bulb = AT.mat_col('lamp_bulb', [255, 236, 190], emit=9.0)
    made += [rod('lamp_cord', (lx, ly, AT.CEIL), (lx, ly, 2.63), 0.006, metal, 6),
             cone('lamp_shade', (lx, ly, 2.535), 0.23, 0.045, 0.19, enamel, 14, caps=False),
             cone('lamp_shade_in', (lx, ly, 2.533), 0.215, 0.04, 0.18, glow_in, 14, caps=False),
             ball('lamp_bulb', (lx, ly, 2.47), 0.045, bulb)]
    for o in made:
        o['no_shadow'] = True

    # ---- under the window (wide shot): cabinet, radio, books, cactus
    cz = 0.62
    made.append(box('cabinet', (0.0, Y - 0.15, cz / 2), (0.74, 0.27, cz), wood))
    AT.flat('cabinet_front', cabinet_front(), (0.0, Y - 0.288, cz / 2))
    made.append(box('cabinet_top', (0.0, Y - 0.155, cz + 0.012), (0.78, 0.30, 0.024), wood_d))
    top = cz + 0.024
    made.append(box('radio', (-0.19, Y - 0.14, top + 0.075), (0.26, 0.09, 0.15), AT.mat_col('radio_m', [150, 58, 44])))
    AT.flat('radio_front', radio_front(), (-0.19, Y - 0.187, top + 0.075))
    made.append(rod('radio_antenna', (-0.30, Y - 0.12, top + 0.15), (-0.34, Y - 0.10, top + 0.36), 0.004, AT.mat_col('chrome', [190, 194, 204]), 5))
    for k, (w, d_, col, rz) in enumerate(((0.23, 0.16, BOOKS[1], 0.10), (0.21, 0.15, BOOKS[0], -0.08), (0.19, 0.14, BOOKS[2], 0.22))):
        made.append(rbox(f'book_stack_{k}', (0.21, Y - 0.15, top + 0.018 + 0.036 * k), (w, d_, 0.034), AT.mat_col(f'book_s{k}', list(col)), rz))
    made.append(cone('cactus_pot', (0.02, Y - 0.10, top + 0.035), 0.036, 0.048, 0.07, AT.mat_col('pot', [176, 96, 60]), 10))
    made.append(ball('cactus', (0.02, Y - 0.10, top + 0.115), 0.036, AT.mat_col('cactus_m', [70, 140, 84]), scale=(1, 1, 1.5)))
    # the sneakers go in front of the cabinet
    A['objs']['sneakers'][0].location = (-0.03, Y - 0.42, 0)

    # ---- red toolbox on the floor, right of the bench (wide shot)
    red = AT.mat_col('toolbox_red', [186, 48, 44])
    tb = (0.10, 1.02)
    made += [rbox('toolbox', (tb[0], tb[1], 0.075), (0.36, 0.17, 0.15), red, 0.3),
             rbox('toolbox_lid', (tb[0], tb[1], 0.158), (0.37, 0.18, 0.016), AT.mat_col('toolbox_dark', [130, 34, 32]), 0.3),
             rbox('toolbox_handle', (tb[0], tb[1], 0.178), (0.14, 0.02, 0.026), metal, 0.3)]

    # ---- shelf above the door (wide shot, right)
    sx, sz = (x0 + x1) / 2, AT.DOOR_H + 0.30
    made.append(box('shelf', (sx, Y - 0.10, sz), (x1 - x0 - 0.02, 0.19, 0.028), wood_d))
    for bx in (x0 + 0.10, x1 - 0.10):
        made.append(box(f'shelf_br_{bx:.2f}', (bx, Y - 0.06, sz - 0.07), (0.025, 0.11, 0.12), metal))
    x = x0 + 0.08
    for k, col in enumerate(BOOKS[:6]):
        w, h = 0.036 + 0.008 * (k % 3), 0.19 + 0.02 * ((k * 7) % 3)
        lean = k == 5                                                    # the last book leans against the others
        made.append(box(f'shelf_book_{k}', (x + w / 2 + (0.028 if lean else 0), Y - 0.10, sz + 0.014 + h / 2 - (0.004 if lean else 0)), (w, 0.13, h),
                        AT.mat_col(f'book_{k}', list(col)), (0, math.radians(-14) if lean else 0, 0)))
        x += w + 0.004
    made += [ball('globe', (x + 0.16, Y - 0.10, sz + 0.125), 0.075, AT.mat_col('globe_m', [56, 120, 176])),
             cone('globe_foot', (x + 0.16, Y - 0.10, sz + 0.035), 0.05, 0.012, 0.045, metal, 8),
             box('shelf_box', (x1 - 0.20, Y - 0.10, sz + 0.074), (0.22, 0.15, 0.12), AT.mat_col('carton', [176, 136, 92]))]

    # ---- corridor (background of Pico's medium shot and close-up)
    xr, yb = x1 + 0.5, Y + 1.3
    import tex2
    for mname, pic, width in (('corridor_wall', True, x1 - x0 + 1.0), ('corridor_side', False, 1.3)):     # a calmer wall colour
        node = next(n for n in bpy.data.materials[mname].node_tree.nodes if n.type == 'TEX_IMAGE')
        node.image = AT.img_from_pil(mname + '_v3', tex2.corridor_wall(picture=pic, width=width, height=AT.CEIL, paint=(146, 170, 170))[0])
    AT.flat('corr_picture2', picture_sea(), (1.56, yb - 0.012, 1.56))
    made.append(box('rack_board', (xr - 0.012, 2.80, 1.68), (0.024, 0.62, 0.07), wood_d))
    for hy in (2.58, 2.80, 3.02):
        made.append(box(f'rack_hook_{hy:.2f}', (xr - 0.04, hy, 1.67), (0.05, 0.02, 0.02), metal))
    AT.flat('jacket', jacket(), (xr - 0.06, 2.80, 1.33), normal='-X')
    AT.flat('cap', cap(), (xr - 0.07, 3.04, 1.60), normal='-X')
    sconce = AT.mat_col('sconce_glow', [255, 208, 140], emit=3.0)
    made += [box('sconce_plate', (xr - 0.012, SCONCE_Y, 1.98), (0.024, 0.09, 0.16), metal),
             cone('sconce_shade', (xr - 0.075, SCONCE_Y, 2.00), 0.055, 0.04, 0.12, sconce, 10)]
    for o in made[-2:]:
        o['no_shadow'] = True
    return made


