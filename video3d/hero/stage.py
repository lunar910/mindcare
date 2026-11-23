"""Staging of the living-room shots: light levels of the room, and the camera and character lights of each named shot.
Owner: the room / lighting pass.

    R = room_bl.build_room()
    stage.room_lighting(R)                                  # final light levels of the room
    pos, target, fov, eyes_to_camera = stage.shot(ch, 'room_close')
    lights = stage.shot_lights(ch, 'room_close')            # warm key + cool rim for that shot; delete them before the next shot
"""
import bpy
from mathutils import Vector as V

import herolib

WARM = (1.0, 0.8, 0.62)         # lamp light on the character
COOL = (0.5, 0.62, 1.0)         # night light from the window, used as a rim
SHOTS = ('room_close', 'room_portrait', 'room_medium', 'room_wide', 'room_side', 'room_top', 'room_low')


def room_lighting(R):
    """Final look of the living room: warm lamp light inside, blue night outside."""
    sc = bpy.context.scene
    sc.world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.3, 0.22, 0.17, 1)
    sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.55
    R['L']['ceiling'].data.energy = 18
    R['L']['ceiling'].data.color = (1.0, 0.72, 0.45)
    R['L']['tv'].data.energy = 5
    R['L']['moon'].data.energy = 700
    R['L']['lamp'].data.energy = 70


def _shots(ch):
    e = herolib.eyes_mid(ch)
    hips = herolib.bone_world(ch, 'spine05')
    # name: (camera position, camera target, vertical fov in degrees, eyes look at the camera, key light (position, target, watts, size))
    return {
        'room_close': (e + V((-0.3, -0.66, -0.015)), e + V((0.005, 0.03, -0.022)), 20, True, (e + V((-0.8, -0.5, 0.3)), e, 12, 0.8)),
        'room_portrait': (e + V((-0.42, -0.86, 0.03)), e + V((0.0, 0.03, -0.035)), 22, True, (e + V((-0.8, -0.55, 0.35)), e, 12, 0.8)),
        'room_medium': (V((-0.45, -0.75, 1.1)), V((0.03, 1.15, 0.9)), 38, True, (V((-1.0, -0.3, 1.6)), V((0, 1.1, 1.0)), 55, 1.0)),
        'room_wide': (V((0.0, -2.05, 1.06)), V((0.0, 1.0, 0.9)), 38, True, (V((-1.0, -0.6, 2.0)), V((0, 1.1, 0.9)), 110, 1.2)),
        'room_side': (hips + V((-2.4, -0.25, 0.35)), hips + V((0, -0.15, 0.2)), 34, False, (hips + V((-1.5, -1.5, 1.5)), hips, 160, 1.2)),
        'room_top': (hips + V((0.0, -0.5, 2.3)), hips + V((0, -0.2, 0.0)), 40, False, (hips + V((-1.0, -1.0, 2.0)), hips, 160, 1.2)),
        'room_low': (V((0.5, -1.6, 0.35)), hips + V((0, -0.2, 0.05)), 40, False, (V((-1.0, -0.6, 1.6)), hips, 110, 1.2)),
    }


def shot(ch, name):
    """Camera of a named shot: (position, target, vertical fov in degrees, eyes_to_camera)."""
    s = _shots(ch)
    if name not in s:
        raise SystemExit('unknown view ' + name)
    return s[name][:4]


def shot_lights(ch, name):
    """Create the character lights of a shot (warm key from the lamp side, cool rim from the window). Returns the light objects."""
    key = _shots(ch)[name][4]
    e = herolib.eyes_mid(ch)
    return [herolib.area('key', key[0], key[1], key[2], WARM, key[3]),
            herolib.area('rim', e + V((0.9, 0.9, 0.5)), e, 30, COOL, 0.5)]
