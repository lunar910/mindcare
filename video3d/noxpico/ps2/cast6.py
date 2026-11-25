"""Version 6 characters: the version 5 look (Meshy's PBR materials, living skin, hands) with the faces rebuilt from
separate parts (face6.py): real eyeballs and lids, teeth, tongue, a jaw that turns, Nox's glasses as real glasses.

    a = cast6.actor('nox', clips)        a.express(values) drives the whole face; a.face6['objects'] = the parts"""
import cast2
import cast5

CAST = cast5.CAST


def actor(who, clips, hands=True):
    cast2.MATTE = False
    cast2.FACE = 'face6'
    c = CAST[who]
    a = cast2.Actor(c['name'], c['rig'], [c['clips_from'] + ':' + k for k in clips], scale=1.0, glasses=False)
    cast5.realism(a, body_normal=0.85)
    cast5.living_skin(a, hair_dark=(who == 'nox'))
    if a.face6 is not None:
        import face6
        face6.match_skin(a.face6)
    if hands:
        try:
            import hands5
            hands5.add_hands(a.arm, a.mesh)
            a.hands5 = True
        except Exception as e:
            print('hands5 not used:', repr(e)[:200])
            a.hands5 = False
    return a
