"""Face pass: skin texture, eyes, expression. Entry point: build(ch)."""
import cfg_body as CB
import cfg_face as CF
import cfg_hair as CH
import da
import look


def build(ch):
    body = ch['body']
    P = dict(CF.SKIN)
    P.update(hairline_az=CH.HAIRLINE_AZ, hairline_y=CH.HAIRLINE_Y, scalp=CH.SCALP_PAINT, glove=CB.PAINT_GLOVES)
    T = da.Texels(ch)
    skin_img, _ = da.paint_skin(ch, P, T)
    body.data.materials.append(da.skin_material(ch['name'] + '_skin', skin_img))
    em = da.eye_material(ch['name'] + '_eye', CF.IRIS, CF.IRIS_IN)
    for e in ch['eyes']:
        e.data.materials.append(em)
    for k, v in CF.EXPR.items():
        body.data.shape_keys.key_blocks[k].value = v
    for side, amount in CF.SMIRK.items():
        look.add_smirk(ch, side, amount)
    ch['texels'] = T
