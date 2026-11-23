"""Hair settings. Owner: the hair pass.

STYLE picks the cut; STYLES describes every cut as data (read by hairda.build, see the docstring of hairda.py for the
vocabulary). To add a cut: add an entry to STYLES. Angles: phi = azimuth in degrees (0 front, +90 the character's left,
180 back), theta = polar angle from straight up; lengths in metres; `tip` = height of a lock's tip above the eye line."""
import os as _os

STYLE = _os.environ.get('HAIR_STYLE', 'curtain')      # 'curtain' (default) or 'swept_back'

HAIR_LIGHT = (0.86, 0.87, 0.90)     # strand texture colours, sRGB 0..1: highlight streaks,
HAIR_MID = (0.60, 0.61, 0.67)       # body of the hair,
HAIR_DARK = (0.25, 0.27, 0.36)      # cool grey gaps and roots
ROUGH, SPEC, EMIT = 0.72, 0.1, 0.0  # matte material; EMIT > 0 adds a little self-illumination
TEX_SEED = 3
STYLE_SEED = 4

_HALO = dict(dir=(24, -25), angle=40, width=9, gain=0.14)       # painted highlight ring (axis theta/phi, ring angle, width)

STYLES = {
    # ------------------------------------------------------------------ layered cut falling over the forehead
    'curtain': dict(
        # hairline height (metres above the eye line, canonical head frame) as a function of azimuth (0 = front, pi = back)
        hairline_az=[0, 0.45, 0.85, 1.25, 1.5, 1.9, 2.4, 3.15],
        hairline_y=[0.06, 0.058, 0.045, 0.03, 0.012, -0.03, -0.06, -0.066],
        scalp_paint=[108, 110, 124],
        whorl=dict(theta=16, phi=180),
        volume=dict(theta=[0, 50, 80, 110, 150], thick=[0.010, 0.010, 0.007, 0.005, 0.003], edge_ramp=0.03),
        shell=dict(shade=0.86),
        halo=_HALO,
        groups=[
            # fringe: parted a little to his left, the two sides curve away from the part; one strand falls between the eyes.
            # tips over the eyes (|phi| 9..29) stay above the brows so that both pupils stay readable
            dict(name='fringe', layer=3, theta=('hl', 2.0), root_f=0.04, swirl=-0.06, lift=0.007, bump=0.004, t_blend=0.42, clear=0.006,
                 width=0.022, point=0.05, jitter=dict(phi=0.5, tip=0.002, root_f=0.02),
                 locks=[
                     dict(phi=5, tip=0.002, width=0.016, bend=(-0.42, 0.12), point=0.06),
                     dict(phi=-4, tip=0.024, width=0.02, bend=(-0.35, 0.05)),
                     dict(phi=-13, tip=0.034, width=0.024, bend=(-0.3, 0.0), wisps=1),
                     dict(phi=-23, tip=0.03, width=0.026, bend=(-0.3, 0.05)),
                     dict(phi=-33, tip=-0.004, width=0.026, bend=(-0.25, 0.15), wisps=1, point=0.06),
                     dict(phi=-43, tip=-0.036, width=0.028, bend=(-0.12, 0.2), point=0.07),
                     dict(phi=13, tip=0.04, width=0.018, bend=(0.3, -0.05)),
                     dict(phi=21, tip=0.031, width=0.024, bend=(0.32, 0.0), wisps=1),
                     dict(phi=31, tip=-0.012, width=0.026, bend=(0.25, -0.15), point=0.06),
                     dict(phi=41, tip=-0.044, width=0.028, bend=(0.12, -0.2), wisps=1, point=0.07),
                 ]),
            # face-framing side locks, in front of the ears, down to the jaw
            dict(name='temple', layer=3, theta=('hl', 0.0), root_f=0.05, swirl=-0.06, lift=0.007, bump=0.004, t_blend=0.4, clear=0.006,
                 width=0.028, point=0.07, hug=0.3, off=(0.01, 0.008), jitter=dict(phi=0.8, tip=0.003, root_f=0.02),
                 locks=[
                     dict(phi=-52, tip=-0.06, bend=(-0.05, 0.2)),
                     dict(phi=53, tip=-0.068, bend=(0.05, -0.2), wisps=1),
                     dict(phi=-63, tip=-0.084, bend=(0.0, 0.25), wisps=1),
                     dict(phi=65, tip=-0.078, bend=(0.0, -0.25)),
                     dict(phi=-75, tip=-0.064, bend=(0.1, 0.1), flick=0.25),
                     dict(phi=78, tip=-0.07, bend=(-0.1, -0.1), flick=0.25),
                 ]),
            # short inner fringe: closes the hairline between the big locks
            dict(name='fringe_under', layer=1, ring=dict(phi=(-44, 44), n=9), theta=('hl', 4.0), root_f=0.7, lift=0.002, bump=0.0,
                 tip=[(0, 0.044), (44, 0.034)], width=0.026, point=0.03, t_blend=0.3, hug=0.5, off=(0.004, 0.006), shade=0.8,
                 jitter=dict(phi=1.5, tip=0.004)),
            # sides: a top layer that flicks out above the ears, an under layer lying on the ears
            dict(name='side_top', layer=3, mirror=True, ring=dict(phi=(86, 128), n=4), theta=78, root_f=0.05, swirl=-0.06, lift=0.008,
                 length=0.055, flick=0.3, t_blend=0.6, width=0.028, point=0.055, alt=dict(length=(1.0, 0.8)), jitter=dict(root_f=0.02)),
            dict(name='side_under', layer=2, mirror=True, ring=dict(phi=(84, 124), n=4), theta=('hl', -4.0), root_f=0.45, lift=0.003,
                 length=0.04, flick=0.15, hug=0.4, off=(0.006, 0.01), width=0.03, point=0.04, shade=0.88),
            # back: three shingled rows of spikes, short at the nape
            dict(name='back_top', layer=3, ring=dict(phi=(138, 222), n=7), theta=76, root_f=0.05, swirl=-0.06, lift=0.008,
                 length=0.06, flick=0.35, t_blend=0.6, width=0.028, point=0.06, wisps=1,
                 alt=dict(length=(1.0, 0.8, 1.1), wisps=(1, 0)), jitter=dict(root_f=0.02)),
            dict(name='back_mid', layer=2, ring=dict(phi=(128, 232), n=9), theta=102, root_f=0.5, lift=0.004,
                 length=0.055, flick=0.28, hug=0.2, off=(0.008, 0.02), width=0.026, point=0.055, shade=0.9,
                 alt=dict(length=(0.85, 1.0))),
            dict(name='nape', layer=1, ring=dict(phi=(120, 240), n=10), theta=('hl', -14.0), root_f=0.7, lift=0.002, bump=0.0,
                 length=0.038, flick=0.12, hug=0.5, off=(0.005, 0.012), width=0.024, point=0.035, shade=0.8),
            # short tufts around the whorl: volume and a broken outline on top
            dict(name='crown', layer=4, ring=dict(phi=(-180, 180), n=6), theta=[(0, 42), (180, 50)], root_f=0.0, swirl=-0.12, lift=0.009,
                 length=0.035, rise=0.25, flick=0.25, grav=0.75, width=0.026, point=0.04, jitter=dict(phi=8, theta=4, length=0.2, root_f=0.0)),
        ]),
}

HAIRLINE_AZ = STYLES[STYLE]['hairline_az']
HAIRLINE_Y = STYLES[STYLE]['hairline_y']
SCALP_PAINT = STYLES[STYLE]['scalp_paint']          # colour painted on the head skin under the hair
