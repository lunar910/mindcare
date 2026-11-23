"""Face shape, skin painting, eyes and expression settings. Owner: the face pass."""
import os as _os

_A = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), 'mh-assets')

# face morph targets (head/..., chin/..., cheek/..., nose/..., eyes/..., eyebrows/..., mouth/..., forehead/..., ears/...)
FACE_DETAILS = {
    'head/head-invertedtriangular': 0.35, 'head/head-oval': 0.2,
    'chin/chin-width-decr': 0.3, 'chin/chin-prominent-incr': 0.25, 'chin/chin-jaw-drop-decr': 0.15,
    'cheek/l-cheek-bones-incr': 0.45, 'cheek/r-cheek-bones-incr': 0.45, 'cheek/l-cheek-volume-decr': 0.4, 'cheek/r-cheek-volume-decr': 0.4,
    'nose/nose-scale-horiz-decr': 0.3, 'nose/nose-point-width-decr': 0.3, 'nose/nose-nostrils-width-decr': 0.25, 'nose/nose-hump-decr': 0.2,
    'nose/nose-scale-vert-decr': 0.08,
    'eyes/l-eye-corner2-up': 0.3, 'eyes/r-eye-corner2-up': 0.3, 'eyes/l-eye-bag-decr': 0.5, 'eyes/r-eye-bag-decr': 0.5,
    'eyebrows/eyebrows-trans-down': 0.3, 'eyebrows/eyebrows-angle-up': 0.2,
    'mouth/mouth-upperlip-volume-decr': 0.2, 'mouth/mouth-scale-horiz-decr': 0.05,
    'forehead/forehead-scale-vert-decr': 0.2,
}
# skin painting (see da.skin_colors); colours sRGB 0..255, distances in metres in the canonical head frame
SKIN = dict(
    base_tex=_os.path.join(_A, 'skins', 'young_caucasian_male', 'young_lightskinned_male_diffuse.png'),
    skin=[226, 176, 146], skin_shadow=[168, 110, 86], skin_deep=[92, 52, 44], blush=[214, 122, 104], cool=[150, 128, 150],
    highlight=[255, 238, 220], lip=[190, 112, 100], lip_upper=[0.9, 0.84, 0.84], mouth_line=[50, 22, 22],
    brow=[30, 24, 25], lash=[20, 15, 15], scalp=[70, 72, 80], seed=21,
    bake=0.8, ambient=0.3, contour=0.85, lights=1.0, zones=1.0, lip_strength=0.85, tex_contrast=1.15, stubble=0.0, grain=0.04,
    rough=0.8, spec=0.08, down=2, face_patch=True, lash_w=1.0, wing=0.0034, crease=0.0093, lid_smoke=0.3,
    # eyebrows: centre line (|cx|, cy) from the nose outwards and full thickness along |cx|; drawn as individual hair strokes
    brows=dict(line=[(0.0092, 0.0102), (0.016, 0.0118), (0.024, 0.0138), (0.032, 0.0155), (0.0405, 0.0166), (0.0475, 0.0152), (0.053, 0.0122), (0.0572, 0.0088)],
               thick=[(0.009, 0.0058), (0.014, 0.0068), (0.024, 0.0064), (0.034, 0.0054), (0.042, 0.0042), (0.05, 0.0028), (0.057, 0.0014)],
               hairs=260, core=0.5, ink=0.95, hair_len=1.0, hair_w=1.25),
)
# eyes: painted texture (see da.eye_texture); iris_deg = angular radius of the iris seen from the eyeball centre
IRIS = [58, 88, 118]
IRIS_IN = [124, 158, 180]
EYE = dict(iris_deg=24.0, pupil=0.36, limbus=[14, 20, 30], sclera=[226, 220, 214], sclera_edge=[150, 122, 118], collarette=[176, 170, 150],
           glow=[150, 190, 215], glow_k=0.35, lid_shade=0.55, lid_dark=0.38, socket_dark=0.5, catch_emit=0.9, rough=0.32, spec=0.3, tex=128, seed=7,
           catch=[(-0.30, 0.36, 0.17, 0.13, 1.0), (0.34, -0.40, 0.07, 0.06, 0.55)])
LASHES = dict(asset='eyelashes01', color=[16, 12, 12], down=4, strength=1.0)      # asset=None: painted lash line only
MOUTH = dict(teeth='teeth_base', tongue='tongue01', teeth_down=8, tongue_down=8)
# resting expression: MakeHuman expression units (0..1) applied as shape keys
EXPR = {'eyebrows-left-down': 0.35, 'eyebrows-right-down': 0.35, 'eyebrows-left-extern-up': 0.25, 'eyebrows-right-extern-up': 0.25}
SMIRK = {'L': 0.4}              # one-sided mouth corner pull (side: amount)
# expression presets for face.set_expression(ch, name, strength): {unit: value}, applied on top of the resting expression.
# 'rest' = how much of the resting expression is kept (default 1).
EXPRESSIONS = {
    'neutral': {},
}
