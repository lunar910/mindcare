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
# skin painting (see da.paint_skin); colours sRGB 0..255, distances in metres in the canonical head frame
SKIN = dict(
    base_tex=_os.path.join(_A, 'skins', 'young_caucasian_male', 'young_lightskinned_male_diffuse.png'),
    skin=[214, 152, 126], skin_shadow=[150, 96, 74], skin_deep=[84, 48, 42], blush=[208, 112, 100], lip=[172, 92, 88],
    brow=[26, 22, 24], scalp=[70, 72, 80], seed=21, bake=0.7, contour=0.85, lip_strength=0.8, tex_contrast=1.3, stubble=0.0, down=2,
    brows=dict(x0=0.008, x1=0.054, y0=0.0088, rise=0.0085, arch=0.001, drop=0.0035, thick=0.0098),
)
IRIS = [50, 82, 110]
IRIS_IN = [118, 152, 172]
# resting expression: MakeHuman expression units (0..1) applied as shape keys
EXPR = {'eyebrows-left-down': 0.35, 'eyebrows-right-down': 0.35, 'eyebrows-left-extern-up': 0.25, 'eyebrows-right-extern-up': 0.25}
SMIRK = {'L': 0.4}              # one-sided mouth corner pull (side: amount)
