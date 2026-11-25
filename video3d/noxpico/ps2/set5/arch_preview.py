"""Preview of set5.arch from inside the room at night (eye height 1.5 m, 24-28 mm).

    ../blender-venv/bin/python set5/arch_preview.py [views] [scale] [samples] [--prod] [--city] [--tag=x]

    views   comma list of: win, door, left, front, dooropen (door at 95 deg), up, corridor, bench
            (default win,door,left,front,dooropen)
    scale   1.0 = 512 x 288 landscape
    --prod  add the assembler's night lights (excerpt5.room_lights: 3 cool window areas + soft ambient)
    --city  also build set5.city behind the glazing
Images go to lab/set5/arch_<view>[_tag].png.
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

import look5  # noqa: E402
from set5 import arch  # noqa: E402

OUT = os.path.join(ROOT, 'lab', 'set5')

VIEWS = {
    # name: (camera, target, lens, door angle deg)
    'win':      ((1.4, -2.6, 1.5), (-1.7, 4.0, 1.70), 24, 0),
    'door':     ((-1.2, -1.0, 1.5), (4.0, 1.2, 1.30), 26, 0),
    'left':     ((2.4, 1.0, 1.5), (-5.0, -0.4, 1.55), 24, 0),
    'front':    ((-0.8, 3.0, 1.5), (0.7, -4.0, 1.40), 24, 0),
    'dooropen': ((1.4, -0.6, 1.5), (4.6, 1.25, 1.30), 24, 95),
    'up':       ((0.2, 1.4, 1.5), (-1.6, 2.6, 3.3), 24, 0),
    'corridor': ((3.2, 0.9, 1.5), (6.5, 1.6, 1.35), 28, 95),
    'bench':    ((-2.4, 1.6, 1.5), (-3.3, 4.0, 1.30), 26, 0),
}


def room_lights():
    """Copy of excerpt5.room_lights (the assembler's night fill), to judge the shell in production light."""
    for i, x in enumerate((-3.9, -1.5, 0.9)):
        look5.area(f'win{i}', (x, 3.85, 1.95), (x, 0.0, 1.2), 180.0, (0.42, 0.56, 1.0), 2.2, 2.2)
    look5.area('amb', (0.0, -1.0, 3.3), (0.0, -1.0, 0.0), 60.0, (0.55, 0.62, 0.85), 6.0, 5.0)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = [a for a in sys.argv[1:] if a.startswith('--')]
    views = (args[0] if args else 'win,door,left,front,dooropen').split(',')
    scale = float(args[1]) if len(args) > 1 else 1.0
    samples = int(args[2]) if len(args) > 2 else 24
    tag = next((f.split('=', 1)[1] for f in flags if f.startswith('--tag=')), '')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    look5.setup(512, 288, samples)
    look5.world((0.010, 0.014, 0.030), 1.0)
    t = time.time()
    A = arch.build()
    if '--city' in flags:
        from set5 import city
        city.build()
    if '--prod' in flags:
        room_lights()
    print(f'build {time.time() - t:.1f} s', flush=True)
    dg = bpy.context.evaluated_depsgraph_get()
    tris = 0
    for o in A['prop'].col.all_objects:
        if o.type in ('MESH', 'CURVE'):
            me = o.evaluated_get(dg).to_mesh()
            me.calc_loop_triangles()
            tris += len(me.loop_triangles)
            o.evaluated_get(dg).to_mesh_clear()
    print('arch objects', len(A['prop'].col.all_objects), 'triangles', tris, flush=True)
    cam = look5.camera('cam', 24)
    sc = bpy.context.scene
    hinge = A['door_hinge']
    for v in views:
        pos, tgt, lens, door = VIEWS[v]
        hinge.rotation_euler.z = -math.radians(door)
        look5.aim(cam, pos, tgt, lens)
        sc.render.resolution_x, sc.render.resolution_y = int(512 * scale), int(288 * scale)
        sc.render.filepath = os.path.join(OUT, f'arch_{v}{"_" + tag if tag else ""}.png')
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f'{v}: {time.time() - t:.1f} s -> {sc.render.filepath}', flush=True)


if __name__ == '__main__':
    main()
