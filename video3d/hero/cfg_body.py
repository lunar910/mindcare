"""Body shape and outfit settings. Owner: the body / outfit pass."""
# MakeHuman macro sliders, all 0..1 (age 0.5 = 25 years, 0.1875 = child; height 0.5 = average)
MACRO = dict(gender=1.0, age=0.45, muscle=0.62, weight=0.4, height=0.68, proportions=0.8,
             races={'caucasian': 0.75, 'african': 0.15, 'asian': 0.10})
# extra body morph targets (torso/..., armslegs/..., hip/..., neck/..., stomach/...), weights 0..1
BODY_DETAILS = {}
# outfit: MakeHuman assets fitted on the body (see mhassets.find), colours are sRGB 0..255
SUIT = dict(asset='male_casualsuit05', shoes='shoes05', jacket=[108, 18, 24], jeans=[34, 36, 44], shirt=[20, 20, 24])
PAINT_GLOVES = [26, 24, 26]     # fingerless gloves painted on the hand skin (None = bare hands)
TEXDOWN = 4                     # texture downsample factor for clothes (2048 / 4 = 512 px, nearest filtering: PS2 look)
CHAIN = True                    # thin silver chain around the neck
