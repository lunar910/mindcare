"""Hair settings. Owner: the hair pass."""
HAIR_LIGHT = (0.93, 0.93, 0.94)     # strand texture colours, sRGB 0..1
HAIR_DARK = (0.34, 0.35, 0.42)
CAP_COLOR = [112, 114, 126]         # scalp cap under the cards, sRGB 0..255
SCALP_PAINT = [70, 72, 80]          # colour painted on the head skin under the hair
STYLE_SEED = 4
TEX_DOWN = 8                        # strand texture downsample (128x512 / 8 = 16x64 px, nearest filtering: PS2 look)
# hairline height (metres above the eye line, canonical head frame) as a function of azimuth (0 = front, pi = back)
HAIRLINE_AZ = [0, 0.45, 0.85, 1.25, 1.5, 1.9, 2.4, 3.15]
HAIRLINE_Y = [0.06, 0.058, 0.045, 0.03, 0.012, -0.03, -0.06, -0.066]
