"""Images for Nox's workstation (set5.workstation): screens, displays, PCB, notebook, labels.  PIL only, written to
ps2/lab/set5/tex/ws_*.png (generated once, `make_all(force=True)` regenerates).  French/English text only, no logos."""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(os.path.dirname(HERE), 'lab', 'set5', 'tex')
FD = '/usr/share/fonts/truetype/dejavu/'
VERSION = 3


def font(size, kind='mono'):
    f = {'mono': 'DejaVuSansMono.ttf', 'monob': 'DejaVuSansMono-Bold.ttf', 'sans': 'DejaVuSans.ttf',
         'sansb': 'DejaVuSans-Bold.ttf', 'obl': 'DejaVuSansMono-Oblique.ttf', 'serif': 'DejaVuSerif.ttf'}[kind]
    try:
        return ImageFont.truetype(FD + f, size)
    except Exception:
        return ImageFont.load_default()


def path(name):
    return os.path.join(TEX, f'ws{VERSION}_{name}.png')


# ------------------------------------------------------------------ seven segment digits
SEG = {'0': 'abcdef', '1': 'bc', '2': 'abged', '3': 'abgcd', '4': 'fgbc', '5': 'afgcd', '6': 'afgedc', '7': 'abc',
       '8': 'abcdefg', '9': 'abcdfg', '-': 'g', ' ': ''}


def seven(d, x, y, w, h, ch, on, off, t=None, slant=0.12):
    """Draw one 7-segment digit with its top-left at (x, y)."""
    t = t or max(2, int(w * 0.18))
    def sk(px, py):                                  # italic slant like real LED displays
        return (px + (y + h - py) * slant, py)
    hh = h / 2
    segs = {
        'a': [(x + t * 0.6, y), (x + w - t * 0.6, y), (x + w - t * 1.1, y + t), (x + t * 1.1, y + t)],
        'd': [(x + t * 1.1, y + h - t), (x + w - t * 1.1, y + h - t), (x + w - t * 0.6, y + h), (x + t * 0.6, y + h)],
        'g': [(x + t * 0.7, y + hh), (x + t * 1.2, y + hh - t / 2), (x + w - t * 1.2, y + hh - t / 2), (x + w - t * 0.7, y + hh),
              (x + w - t * 1.2, y + hh + t / 2), (x + t * 1.2, y + hh + t / 2)],
        'f': [(x, y + t * 0.6), (x + t, y + t * 1.1), (x + t, y + hh - t * 0.6), (x, y + hh - t * 0.15)],
        'e': [(x, y + hh + t * 0.15), (x + t, y + hh + t * 0.6), (x + t, y + h - t * 1.1), (x, y + h - t * 0.6)],
        'b': [(x + w - t, y + t * 1.1), (x + w, y + t * 0.6), (x + w, y + hh - t * 0.15), (x + w - t, y + hh - t * 0.6)],
        'c': [(x + w - t, y + hh + t * 0.6), (x + w, y + hh + t * 0.15), (x + w, y + h - t * 0.6), (x + w - t, y + h - t * 1.1)],
    }
    lit = SEG.get(ch, '')
    for k, poly in segs.items():
        d.polygon([sk(*p) for p in poly], fill=on if k in lit else off)


def seven_text(d, x, y, w, h, text, on, off, gap=None, dot_r=None):
    gap = gap if gap is not None else w * 0.35
    cx = x
    for i, ch in enumerate(text):
        if ch == '.':
            r = dot_r or w * 0.11
            d.ellipse([cx - gap * 0.75 - r, y + h - 2 * r, cx - gap * 0.75 + r, y + h], fill=on)
            continue
        seven(d, cx, y, w, h, ch, on, off)
        cx += w + gap
    return cx


def _screen(a, b, k):
    import numpy as np
    A = np.asarray(a).astype(float) / 255
    B = np.asarray(b).astype(float) / 255 * k
    C = 1 - (1 - A) * (1 - B)
    return Image.fromarray((C * 255).clip(0, 255).astype('uint8'))


# ------------------------------------------------------------------ monitor: code + schematic
CODE = [
    [('cm', '// bip_motor.c  -  carte moteur Bip v3 (rev B)')],
    [('cm', '// PID vitesse, 2 moteurs, PWM 20 kHz')],
    [],
    [('pp', '#include "bip_motor.h"')],
    [('pp', '#include "pid.h"')],
    [],
    [('kw', 'static'), ('ty', ' pid_t'), ('', ' pid_left, pid_right;')],
    [('kw', 'static volatile'), ('ty', ' uint16_t'), ('', ' ticks_l = '), ('nu', '0'), ('', ';')],
    [],
    [('ty', 'void'), ('fn', ' motor_init'), ('', '('), ('ty', 'void'), ('', ') {')],
    [('', '    pwm_setup(PWM_FREQ_HZ, '), ('nu', '20000'), ('', ');')],
    [('', '    pid_init(&pid_left,  '), ('nu', '0.82f'), ('', ', '), ('nu', '0.05f'), ('', ', '), ('nu', '0.01f'), ('', ');')],
    [('', '    pid_init(&pid_right, '), ('nu', '0.82f'), ('', ', '), ('nu', '0.05f'), ('', ', '), ('nu', '0.01f'), ('', ');')],
    [('', '    enc_attach(ENC_L, &ticks_l);')],
    [('', '}')],
    [],
    [('ty', 'void'), ('fn', ' motor_update'), ('', '('), ('ty', 'float'), ('', ' dt) {')],
    [('kw', '    float'), ('', ' rpm = ticks_to_rpm(ticks_l, dt);')],
    [('', '    ticks_l = '), ('nu', '0'), ('', ';')],
    [('kw', '    float'), ('', ' u = pid_step(&pid_left, target, rpm, dt);')],
    [('kw', '    if'), ('', ' (u > '), ('nu', '1.0f'), ('', ') u = '), ('nu', '1.0f'), ('', ';  '), ('cm', '// saturation')],
    [('kw', '    if'), ('', ' (fabsf(rpm) > RPM_MAX) {')],
    [('', '        motor_brake();')],
    [('', '        log_warn('), ('st', '"surchauffe moteur G"'), ('', ');')],
    [('kw', '        return'), ('', ';')],
    [('', '    }')],
    [('', '    pwm_write(CH_LEFT, (uint16_t)(u * PWM_TOP));')],
    [('', '}')],
    [],
    [('cm', '// TODO: tester avec la batterie 2S (7.4 V)')],
    [('cm', '// TODO: Pico dit que le moteur G')],
    [('cm', '//       "fait un bruit bizarre" ?!')],
]


def _code_lines():
    return CODE


def _resistor(d, x0, y0, x1, y1, col, w=3):
    """Zigzag resistor between two points (horizontal or vertical)."""
    n = 6
    pts = [(x0, y0)]
    L = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    px, py = -uy, ux
    a, b = 0.2, 0.8
    pts.append((x0 + ux * L * a, y0 + uy * L * a))
    for i in range(n):
        t = a + (b - a) * (i + 0.5) / n
        s = 9 if i % 2 == 0 else -9
        pts.append((x0 + ux * L * t + px * s, y0 + uy * L * t + py * s))
    pts.append((x0 + ux * L * b, y0 + uy * L * b))
    pts.append((x1, y1))
    d.line(pts, fill=col, width=w, joint='curve')


def schematic(d, X, Y, W, H, bg, wire, sym, txt, red):
    d.rectangle([X, Y, X + W, Y + H], fill=bg)
    # grid dots
    for gx in range(X + 10, X + W, 20):
        for gy in range(Y + 10, Y + H, 20):
            d.point((gx, gy), fill=(212, 208, 196))
    f = font(15, 'mono')
    fb = font(17, 'monob')
    # MCU block
    mx, my, mw, mh = X + 230, Y + 150, 150, 250
    d.rectangle([mx, my, mx + mw, my + mh], outline=sym, width=3, fill=(250, 246, 226))
    d.text((mx, my - 26), 'U1  MCU', fill=txt, font=fb)
    pins_l = ['VCC', 'GND', 'XTAL1', 'XTAL2', 'RESET', 'ADC0']
    pins_r = ['PWM1', 'PWM2', 'DIR1', 'DIR2', 'ENC_A', 'ENC_B']
    for i, (pl, pr) in enumerate(zip(pins_l, pins_r)):
        yy = my + 30 + i * 38
        d.line([mx - 40, yy, mx, yy], fill=sym, width=3)
        d.text((mx + 6, yy - 9), pl, fill=txt, font=f)
        d.line([mx + mw, yy, mx + mw + 40, yy], fill=sym, width=3)
        d.text((mx + mw - 6 - 9 * len(pr), yy - 9), pr, fill=txt, font=f)
    # H bridge block
    hx, hy = X + 480, Y + 170
    d.rectangle([hx, hy, hx + 130, hy + 200], outline=sym, width=3, fill=(250, 246, 226))
    d.text((hx + 40, hy + 80), 'U2', fill=txt, font=fb)
    d.text((hx + 18, hy + 104), 'PONT H', fill=txt, font=f)
    for i in range(4):
        yy = my + 30 + i * 38
        d.line([mx + mw + 40, yy, hx, hy + 20 + i * 40], fill=wire, width=3)
    # motor
    cx, cy = hx + 200, hy + 100
    d.line([hx + 130, hy + 60, cx, hy + 60, cx, cy - 40], fill=wire, width=3)
    d.line([hx + 130, hy + 140, cx, hy + 140, cx, cy + 40], fill=wire, width=3)
    d.ellipse([cx - 40, cy - 40, cx + 40, cy + 40], outline=sym, width=3, fill=(250, 246, 226))
    d.text((cx - 11, cy - 12), 'M', fill=txt, font=font(22, 'sansb'))
    d.text((cx + 48, cy - 10), 'M1', fill=txt, font=fb)
    # crystal + caps on the left
    xx = X + 120
    d.line([mx - 40, my + 106, xx, my + 106], fill=wire, width=3)
    d.line([mx - 40, my + 144, xx, my + 144], fill=wire, width=3)
    d.rectangle([xx - 10, my + 112, xx + 10, my + 138], outline=sym, width=3)
    d.text((xx - 70, my + 116), 'Y1', fill=txt, font=fb)
    for yy in (my + 106, my + 144):
        d.line([xx, yy, xx - 60, yy], fill=wire, width=3)
        d.line([xx - 60, yy, xx - 60, yy + 40], fill=wire, width=3)
    for i, (ccx, lab) in enumerate(((xx - 60, 'C1'), (xx - 60, 'C2'))):
        pass
    # decoupling cap + resistor network at the top
    vy = Y + 70
    d.line([X + 60, vy, X + W - 80, vy], fill=red, width=3)
    d.text((X + 60, vy - 26), '+5V', fill=red, font=fb)
    d.line([mx - 40, my + 30, mx - 80, my + 30, mx - 80, vy], fill=red, width=3)
    for k, (rx, lab, val) in enumerate(((X + 420, 'R1', '10k'), (X + 455, 'R2', '10k'))):
        _resistor(d, rx, vy, rx, my + 10, sym)
        d.text((rx + 12, vy + 20), lab, fill=txt, font=fb)
        d.text((rx + 12, vy + 40), val, fill=txt, font=f)
        d.line([rx, my + 10, rx, my + 30 + (4 + k) * 38, mx + mw + 40, my + 30 + (4 + k) * 38], fill=wire, width=3)
        d.ellipse([rx - 5, vy - 5, rx + 5, vy + 5], fill=wire)
    # capacitor symbol
    ccx = X + 150
    d.line([ccx, vy, ccx, vy + 50], fill=wire, width=3)
    d.line([ccx - 22, vy + 50, ccx + 22, vy + 50], fill=sym, width=4)
    d.line([ccx - 22, vy + 62, ccx + 22, vy + 62], fill=sym, width=4)
    d.line([ccx, vy + 62, ccx, vy + 100], fill=wire, width=3)
    d.text((ccx + 28, vy + 44), 'C3 100n', fill=txt, font=f)
    for gx in (ccx, X + 120 - 60):
        gy = vy + 100 if gx == ccx else my + 190
        d.line([gx - 18, gy, gx + 18, gy], fill=sym, width=3)
        d.line([gx - 11, gy + 7, gx + 11, gy + 7], fill=sym, width=3)
        d.line([gx - 4, gy + 14, gx + 4, gy + 14], fill=sym, width=3)
    # LED + resistor
    lx, ly = X + 120, Y + H - 170
    d.line([mx - 40, my + 220, lx + 60, my + 220, lx + 60, ly], fill=wire, width=3)
    _resistor(d, lx + 60, ly, lx + 60, ly + 70, sym)
    d.polygon([(lx + 45, ly + 80), (lx + 75, ly + 80), (lx + 60, ly + 105)], outline=sym, width=3)
    d.line([lx + 45, ly + 107, lx + 75, ly + 107], fill=sym, width=3)
    d.text((lx + 80, ly + 25), 'R5 330', fill=txt, font=f)
    d.text((lx + 80, ly + 85), 'D1', fill=txt, font=fb)
    # title block
    tx, ty = X + W - 300, Y + H - 110
    d.rectangle([tx, ty, X + W - 20, Y + H - 20], outline=sym, width=2)
    d.line([tx, ty + 34, X + W - 20, ty + 34], fill=sym, width=2)
    d.text((tx + 10, ty + 7), 'BIP v3 - carte moteur', fill=txt, font=fb)
    d.text((tx + 10, ty + 44), 'Rev B   feuille 2/4', fill=txt, font=f)
    d.text((tx + 10, ty + 64), 'Nox  -  11/2026', fill=txt, font=f)


def monitor(force=False):
    p = path('monitor')
    if os.path.exists(p) and not force:
        return p
    W, H = 1600, 900
    im = Image.new('RGB', (W, H), (30, 31, 36))
    d = ImageDraw.Draw(im)
    # title bar + tabs
    d.rectangle([0, 0, W, 34], fill=(22, 23, 27))
    for i, (t, on) in enumerate((('bip_motor.c', True), ('pid.h', False), ('carte_moteur.sch', False))):
        x = 200 + i * 210
        d.rectangle([x, 4, x + 200, 34], fill=(30, 31, 36) if on else (38, 40, 46))
        d.text((x + 14, 10), t, fill=(220, 220, 220) if on else (140, 142, 150), font=font(15, 'mono'))
    # file tree
    d.rectangle([0, 34, 190, H], fill=(25, 26, 30))
    tree = ['BIP_V3', ' firmware', '  bip_motor.c', '  bip_motor.h', '  pid.c', '  pid.h', '  main.c', ' hardware',
            '  carte_moteur.sch', '  carte_moteur.pcb', '  bom.csv', ' notes.md']
    for i, t in enumerate(tree):
        col = (230, 230, 230) if 'motor.c' in t else (150, 154, 162)
        if 'motor.c' in t:
            d.rectangle([0, 50 + i * 24 - 3, 190, 50 + i * 24 + 19], fill=(44, 50, 64))
        d.text((10, 50 + i * 24), t, fill=col, font=font(14, 'mono'))
    # code
    colors = {'': (190, 196, 204), 'cm': (110, 118, 130), 'pp': (200, 120, 210), 'kw': (200, 120, 210),
              'ty': (230, 192, 120), 'fn': (100, 170, 240), 'nu': (215, 150, 100), 'st': (150, 200, 120)}
    f = font(16, 'mono')
    cw = 9.63
    x0, y0, lh = 248, 48, 22
    for i, line in enumerate(_code_lines()):
        y = y0 + i * lh
        d.text((200, y), f'{i + 1:3d}', fill=(80, 84, 94), font=font(15, 'mono'))
        if i == 19:
            d.rectangle([240, y - 2, 860, y + lh - 3], fill=(40, 42, 50))
        x = x0
        for kind, s in line:
            d.text((x, y), s, fill=colors[kind], font=f)
            x += cw * len(s)
    # cursor
    d.rectangle([x0 + 30 * cw, y0 + 19 * lh, x0 + 30 * cw + 2, y0 + 19 * lh + 19], fill=(230, 230, 230))
    # serial monitor at the bottom of the code pane
    d.rectangle([190, H - 150, 870, H], fill=(20, 21, 24))
    d.line([190, H - 150, 870, H - 150], fill=(60, 62, 70), width=2)
    d.text((200, H - 142), 'MONITEUR SERIE  /dev/ttyUSB0  115200', fill=(150, 154, 162), font=font(14, 'mono'))
    for i, t in enumerate(['rpm_g=3412 rpm_d=3398 u=0.62', 'rpm_g=3420 rpm_d=3401 u=0.62', 'rpm_g=3388 rpm_d=3405 u=0.63',
                           'rpm_g=3610 rpm_d=3402 u=0.71  !', 'WARN surchauffe moteur G']):
        col = (120, 220, 140) if i < 3 else ((230, 200, 90) if i == 3 else (240, 110, 90))
        d.text((200, H - 116 + i * 22), t, fill=col, font=font(15, 'mono'))
    # schematic pane
    schematic(d, 870, 34, W - 870, H - 58, (244, 240, 222), (40, 120, 90), (150, 40, 40), (40, 40, 90), (180, 40, 40))
    # status bar
    d.rectangle([0, H - 24, W, H], fill=(36, 84, 150))
    d.text((10, H - 21), 'main*   Ln 25, Col 23   UTF-8   C   Bip v3', fill=(230, 236, 246), font=font(14, 'mono'))
    im.save(p)
    return p


# ------------------------------------------------------------------ oscilloscope screen
def scope(force=False):
    p = path('scope')
    if os.path.exists(p) and not force:
        return p
    W, H = 800, 480
    im = Image.new('RGB', (W, H), (6, 9, 10))
    d = ImageDraw.Draw(im)
    gx0, gy0, gw, gh = 40, 40, 720, 400
    d.rectangle([0, 0, W, 34], fill=(16, 22, 26))
    d.text((10, 8), 'CH1  500mV   DC', fill=(90, 255, 140), font=font(16, 'monob'))
    d.text((300, 8), 'H 20.0us', fill=(220, 220, 220), font=font(16, 'mono'))
    d.text((520, 8), 'T  CH1  1.20V', fill=(240, 200, 80), font=font(16, 'mono'))
    for i in range(11):
        x = gx0 + i * gw / 10
        for y in range(gy0, gy0 + gh, 4):
            d.point((x, y), fill=(70, 80, 84) if i != 5 else (110, 120, 124))
    for j in range(9):
        y = gy0 + j * gh / 8
        for x in range(gx0, gx0 + gw, 4):
            d.point((x, y), fill=(70, 80, 84) if j != 4 else (110, 120, 124))
    for i in range(51):
        x = gx0 + i * gw / 50
        d.line([x, gy0 + gh / 2 - 4, x, gy0 + gh / 2 + 4], fill=(110, 120, 124))
    d.rectangle([gx0, gy0, gx0 + gw, gy0 + gh], outline=(110, 120, 124))
    # PWM-ish trace with ringing (what a motor driver looks like)
    tr = Image.new('RGB', (W, H), (0, 0, 0))
    td = ImageDraw.Draw(tr)
    pts = []
    for k in range(gw + 1):
        t = k / gw * 2.5
        ph = t % 1.0
        v = 1.0 if ph < 0.62 else -1.0
        e = (ph if ph < 0.62 else ph - 0.62)
        v += 0.28 * math.exp(-e * 40) * math.cos(e * 260) * (1 if ph < 0.62 else -1)
        v += 0.02 * math.sin(k * 1.7)
        pts.append((gx0 + k, gy0 + gh / 2 - v * 110 - 20))
    td.line(pts, fill=(60, 255, 120), width=3)
    im = _screen(im, tr.filter(ImageFilter.GaussianBlur(5)), 1.2)
    im = _screen(im, tr, 1.0)
    d = ImageDraw.Draw(im)
    d.text((gx0 + 6, gy0 + gh / 2 - 150), '1', fill=(90, 255, 140), font=font(16, 'monob'))
    d.rectangle([0, H - 36, W, H], fill=(16, 22, 26))
    d.text((10, H - 28), 'Freq 20.01 kHz   Vpp 2.86 V   Duty 62.0 %', fill=(90, 255, 140), font=font(16, 'mono'))
    im.save(p)
    return p


# ------------------------------------------------------------------ small displays
def station(force=False):
    p = path('station')
    if os.path.exists(p) and not force:
        return p
    im = Image.new('RGB', (320, 140), (14, 4, 3))
    d = ImageDraw.Draw(im)
    on, off = (255, 70, 24), (26, 7, 5)
    seven_text(d, 26, 20, 56, 100, '350', on, off, gap=16)
    d.text((248, 22), '°C', fill=on, font=font(30, 'sansb'))
    d.ellipse([256, 104, 268, 116], fill=(255, 140, 40))
    im = _screen(im, im.filter(ImageFilter.GaussianBlur(4)), 0.7)
    im.save(p)
    return p


def psu(force=False):
    p = path('psu')
    if os.path.exists(p) and not force:
        return p
    im = Image.new('RGB', (360, 120), (8, 6, 6))
    d = ImageDraw.Draw(im)
    seven_text(d, 18, 16, 50, 88, '12.00', (255, 60, 40), (20, 7, 6), gap=14)
    im = _screen(im, im.filter(ImageFilter.GaussianBlur(4)), 0.7)
    im.save(p)
    p2 = path('psu_a')
    im = Image.new('RGB', (360, 120), (6, 8, 6))
    d = ImageDraw.Draw(im)
    seven_text(d, 18, 16, 50, 88, '0.352', (70, 255, 110), (8, 20, 10), gap=14)
    im = _screen(im, im.filter(ImageFilter.GaussianBlur(4)), 0.7)
    im.save(p2)
    return p


def meter(force=False):
    """Multimeter front face (grey, dial markings) with the LCD at the top."""
    p = path('meter')
    if os.path.exists(p) and not force:
        return p
    W, H = 360, 720
    im = Image.new('RGB', (W, H), (58, 60, 62))
    d = ImageDraw.Draw(im)
    # LCD
    d.rounded_rectangle([30, 40, W - 30, 220], 14, fill=(30, 32, 30))
    d.rectangle([44, 54, W - 44, 206], fill=(150, 166, 140))
    seven_text(d, 70, 80, 46, 96, '4.98', (24, 26, 24), (144, 160, 134), gap=12)
    d.text((W - 110, 170), 'V DC', fill=(24, 26, 24), font=font(22, 'sansb'))
    d.text((60, 60), 'AUTO', fill=(24, 26, 24), font=font(14, 'sansb'))
    # dial ring markings
    cx, cy, r = W // 2, 410, 118
    labels = ['OFF', 'V~', 'V=', 'mV', 'Ω', '))', 'A', 'mA', 'Hz', '°C']
    for i, t in enumerate(labels):
        a = math.radians(-150 + i * 300 / (len(labels) - 1))
        x, y = cx + math.sin(a) * (r + 26), cy - math.cos(a) * (r + 26)
        d.text((x - 12, y - 9), t, fill=(230, 230, 226) if t != 'OFF' else (240, 200, 60), font=font(17, 'sansb'))
        d.line([cx + math.sin(a) * r, cy - math.cos(a) * r, cx + math.sin(a) * (r + 10), cy - math.cos(a) * (r + 10)],
               fill=(230, 230, 226), width=3)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(90, 92, 94), width=3)
    # buttons row
    for i, t in enumerate(('HOLD', 'RANGE', 'REL')):
        x = 40 + i * 100
        d.rounded_rectangle([x, 246, x + 80, 274], 6, fill=(96, 98, 100))
        d.text((x + 14, 252), t, fill=(240, 240, 236), font=font(14, 'sansb'))
    # sockets labels
    for i, t in enumerate(('10A', 'mA', 'COM', 'VΩ')):
        x = 50 + i * 80
        d.text((x, 650), t, fill=(240, 240, 236) if t != 'VΩ' else (240, 90, 80), font=font(16, 'sansb'))
    im.save(p)
    return p


# ------------------------------------------------------------------ PCB
# component layout in board coordinates (u, v in 0..1, board 100 x 70 mm), shared with workstation.py
PCB_PARTS = {
    'U1': (0.40, 0.55, 'dip16'), 'U2': (0.72, 0.62, 'soic8'), 'Q1': (0.15, 0.25, 'to220'),
    'C1': (0.13, 0.62, 'elec8'), 'C2': (0.24, 0.80, 'elec6'), 'C3': (0.60, 0.28, 'elec6'),
    'R1': (0.38, 0.20, 'res'), 'R2': (0.48, 0.20, 'res'), 'R3': (0.62, 0.85, 'res'), 'D1': (0.86, 0.85, 'led'),
    'J1': (0.92, 0.38, 'term2'), 'J2': (0.50, 0.92, 'hdr8'), 'Y1': (0.25, 0.48, 'xtal'), 'C4': (0.80, 0.30, 'cer'),
    'C5': (0.30, 0.30, 'cer'),
}


def pcb(force=False):
    p = path('pcb')
    if os.path.exists(p) and not force:
        return p
    W, H = 1000, 700
    rnd = random.Random(7)
    im = Image.new('RGB', (W, H), (20, 84, 46))
    d = ImageDraw.Draw(im)
    trace, pad, silk = (34, 118, 64), (204, 204, 196), (232, 232, 222)
    def P(u, v):
        return (u * W, (1 - v) * H)
    # ground pour hatching edge + traces
    for k in range(40):
        a = P(rnd.uniform(0.05, 0.95), rnd.uniform(0.05, 0.95))
        b = (a[0] + rnd.choice((-1, 1)) * rnd.uniform(60, 260), a[1])
        c = (b[0] + rnd.choice((-1, 1)) * 40, b[1] + rnd.choice((-1, 1)) * 40)
        e = (c[0], c[1] + rnd.choice((-1, 1)) * rnd.uniform(40, 200))
        d.line([a, b, c, e], fill=trace, width=rnd.choice((6, 8, 8, 14)), joint='curve')
        for q in (a, e):
            d.ellipse([q[0] - 7, q[1] - 7, q[0] + 7, q[1] + 7], fill=pad)
            d.ellipse([q[0] - 3, q[1] - 3, q[0] + 3, q[1] + 3], fill=(30, 30, 30))
    d.line([P(0.02, 0.97), P(0.98, 0.97), P(0.98, 0.03), P(0.02, 0.03), P(0.02, 0.97)], fill=trace, width=16)
    f = font(22, 'sansb')
    for name, (u, v, kind) in PCB_PARTS.items():
        x, y = P(u, v)
        size = {'dip16': (220, 80), 'soic8': (60, 56), 'to220': (110, 50), 'elec8': (90, 90), 'elec6': (66, 66),
                'res': (80, 22), 'led': (34, 34), 'term2': (60, 90), 'hdr8': (210, 30), 'xtal': (120, 46), 'cer': (40, 22)}[kind]
        sw, sh = size
        if kind.startswith('elec') or kind == 'led':
            d.ellipse([x - sw / 2 - 6, y - sh / 2 - 6, x + sw / 2 + 6, y + sh / 2 + 6], outline=silk, width=3)
        else:
            d.rectangle([x - sw / 2 - 6, y - sh / 2 - 6, x + sw / 2 + 6, y + sh / 2 + 6], outline=silk, width=3)
        if kind == 'dip16':
            for i in range(8):
                for s in (-1, 1):
                    px, py = x - 100 + i * 28.6, y + s * 52
                    d.ellipse([px - 9, py - 9, px + 9, py + 9], fill=pad)
            d.ellipse([x - sw / 2 - 2, y - 8, x - sw / 2 + 14, y + 8], fill=silk)
        if kind == 'hdr8':
            for i in range(8):
                px = x - 89 + i * 25.4
                d.rectangle([px - 9, y - 9, px + 9, y + 9], fill=pad)
        if kind in ('res', 'cer', 'led', 'elec6', 'elec8', 'xtal', 'term2', 'to220'):
            for s in (-1, 1):
                if kind == 'term2':
                    px, py = x, y + s * 25
                elif kind == 'to220':
                    px, py = x + s * 36, y + 40
                else:
                    px, py = x + s * (sw / 2 + 18 if kind == 'res' else sw / 4), y
                d.ellipse([px - 9, py - 9, px + 9, py + 9], fill=pad)
            if kind == 'to220':
                d.ellipse([x - 9, y + 31, x + 9, y + 49], fill=pad)
        d.text((x - sw / 2 - 4, y - sh / 2 - 34), name, fill=silk, font=f)
    d.text(P(0.62, 0.12), 'BIP-MOT v3  rev B', fill=silk, font=font(26, 'sansb'))
    d.text(P(0.06, 0.12), 'NOX 2026', fill=silk, font=font(20, 'sans'))
    for u, v in ((0.04, 0.06), (0.96, 0.06), (0.04, 0.94), (0.96, 0.94)):
        x, y = P(u, v)
        d.ellipse([x - 18, y - 18, x + 18, y + 18], fill=pad)
        d.ellipse([x - 11, y - 11, x + 11, y + 11], fill=(16, 16, 16))
    im = im.filter(ImageFilter.GaussianBlur(0.6))
    im.save(p)
    return p


# ------------------------------------------------------------------ notebook spread
def _hand(d, xy, text, col, size=24, rnd=None):
    """Fake handwriting: oblique font, each character jittered a little."""
    rnd = rnd or random.Random(1)
    f = font(size, 'obl')
    x, y = xy
    for ch in text:
        d.text((x + rnd.uniform(-0.8, 0.8), y + rnd.uniform(-1.5, 1.5)), ch, fill=col, font=f)
        x += size * 0.58 + rnd.uniform(-1, 1)


def _wobble(d, pts, col, w=3, rnd=None, amp=1.2):
    rnd = rnd or random.Random(2)
    out = []
    for (a, b) in zip(pts[:-1], pts[1:]):
        n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 12))
        for i in range(n):
            t = i / n
            out.append((a[0] + (b[0] - a[0]) * t + rnd.uniform(-amp, amp), a[1] + (b[1] - a[1]) * t + rnd.uniform(-amp, amp)))
    out.append(pts[-1])
    d.line(out, fill=col, width=w, joint='curve')


def notebook(force=False):
    p = path('notebook')
    if os.path.exists(p) and not force:
        return p
    W, H = 1200, 850
    im = Image.new('RGB', (W, H), (236, 232, 220))
    d = ImageDraw.Draw(im)
    for x in range(0, W, 24):
        d.line([x, 0, x, H], fill=(206, 214, 222), width=1)
    for y in range(0, H, 24):
        d.line([0, y, W, y], fill=(206, 214, 222), width=1)
    d.rectangle([594, 0, 606, H], fill=(214, 208, 196))
    ink, pencil, red = (30, 50, 130), (90, 90, 96), (170, 40, 40)
    rnd = random.Random(5)
    _hand(d, (50, 40), 'Bip v3 - moteur G', ink, 30, rnd)
    _wobble(d, [(48, 82), (400, 80)], ink, 2, rnd)
    # hand-drawn H bridge
    bx, by = 120, 160
    for (x0, y0, x1, y1) in ((bx, by, bx + 300, by), (bx, by + 330, bx + 300, by + 330), (bx, by, bx, by + 330),
                             (bx + 300, by, bx + 300, by + 330)):
        _wobble(d, [(x0, y0), (x1, y1)], ink, 3, rnd)
    for (qx, qy, lab) in ((bx, by + 90, 'Q1'), (bx + 300, by + 90, 'Q2'), (bx, by + 240, 'Q3'), (bx + 300, by + 240, 'Q4')):
        d.ellipse([qx - 26, qy - 26, qx + 26, qy + 26], outline=ink, width=3)
        _wobble(d, [(qx - 10, qy - 16), (qx - 10, qy + 16)], ink, 3, rnd)
        _hand(d, (qx + 32 if qx > bx else qx - 70, qy - 14), lab, ink, 24, rnd)
    d.ellipse([bx + 110, by + 125, bx + 190, by + 205], outline=ink, width=3)
    _hand(d, (bx + 136, by + 148), 'M', ink, 30, rnd)
    _wobble(d, [(bx, by + 165), (bx + 110, by + 165)], ink, 3, rnd)
    _wobble(d, [(bx + 190, by + 165), (bx + 300, by + 165)], ink, 3, rnd)
    _hand(d, (bx + 80, by - 40), '+7,4 V', red, 24, rnd)
    _hand(d, (bx + 110, by + 345), 'GND', ink, 24, rnd)
    _hand(d, (60, 600), 'R = (5 - 2,1) / 0,02', ink, 24, rnd)
    _hand(d, (60, 640), '  = 145 -> 150 ohm', ink, 24, rnd)
    _hand(d, (60, 700), 'PWM 20 kHz (pas de sifflement)', pencil, 22, rnd)
    _wobble(d, [(55, 735), (520, 732)], red, 2, rnd)
    # right page: block diagram
    blocks = [('Batterie 2S', 680, 60), ('Regul. 5V', 680, 200), ('MCU', 930, 200), ('Pont H', 930, 360), ('Moteurs', 930, 500)]
    for t, x, y in blocks:
        _wobble(d, [(x, y), (x + 200, y), (x + 200, y + 80), (x, y + 80), (x, y)], ink, 3, rnd)
        _hand(d, (x + 16, y + 26), t, ink, 24, rnd)
    for (a, b) in (((780, 140), (780, 200)), ((880, 240), (930, 240)), ((1030, 280), (1030, 360)), ((1030, 440), (1030, 500))):
        _wobble(d, [a, b], ink, 3, rnd)
        d.polygon([(b[0] - 8, b[1] - 12), (b[0] + 8, b[1] - 12), b] if a[0] == b[0] else
                  [(b[0] - 12, b[1] - 8), (b[0] - 12, b[1] + 8), b], fill=ink)
    _hand(d, (660, 640), 'tester encodeur ?', red, 26, rnd)
    _wobble(d, [(650, 700), (1100, 696)], ink, 2, rnd)
    _hand(d, (660, 720), 'Pico : "ça fait bzzz"', pencil, 24, rnd)
    # coffee ring on the right page
    for k in range(3):
        r = 70 + k * 2
        d.arc([1000 - r, 700 - r, 1000 + r, 700 + r], 200 + k * 30, 470 + k * 30, fill=(170, 130, 90), width=3 - k)
    im = im.filter(ImageFilter.GaussianBlur(0.5))
    im.save(p)
    return p


# ------------------------------------------------------------------ drawer labels atlas (4 x 6)
LABELS = ['R 10k', 'R 1k', 'R 330', 'R 4k7', 'C 100n', 'C 10u', 'LED R', 'LED V', 'BC547', 'IRF540', '1N4148',
          'DIP 16', 'quartz', 'header', 'vis M3', 'écrous', 'JST', 'fusibles', 'divers', 'moteurs', 'servo', 'capteurs',
          'Bip', 'HS']


def labels(force=False):
    p = path('labels')
    if os.path.exists(p) and not force:
        return p
    cw, ch = 160, 56
    im = Image.new('RGB', (cw * 4, ch * 6), (238, 236, 228))
    d = ImageDraw.Draw(im)
    rnd = random.Random(3)
    for i, t in enumerate(LABELS):
        x, y = (i % 4) * cw, (i // 4) * ch
        d.rectangle([x, y, x + cw - 1, y + ch - 1], outline=(200, 198, 190), width=2)
        _hand(d, (x + 14, y + 12), t, (30, 30, 34), 26, rnd)
    im.save(p)
    return p


def panel_station(force=False):
    """Soldering-station front panel print."""
    p = path('stpanel')
    if os.path.exists(p) and not force:
        return p
    W, H = 600, 400
    im = Image.new('RGB', (W, H), (30, 31, 33))
    d = ImageDraw.Draw(im)
    d.text((26, 18), 'STATION DE SOUDAGE  60 W', fill=(220, 220, 214), font=font(26, 'sansb'))
    d.text((26, 300), 'POWER', fill=(200, 200, 196), font=font(20, 'sans'))
    d.text((420, 300), 'FER', fill=(200, 200, 196), font=font(20, 'sans'))
    d.text((300, 72), 'TEMP °C', fill=(200, 200, 196), font=font(18, 'sans'))
    d.rectangle([0, H - 12, W, H], fill=(200, 60, 40))
    im.save(p)
    return p


def make_all(force=False):
    os.makedirs(TEX, exist_ok=True)
    return {k: f(force) for k, f in (('monitor', monitor), ('scope', scope), ('station', station), ('psu', psu),
                                      ('meter', meter), ('pcb', pcb), ('notebook', notebook), ('labels', labels),
                                      ('stpanel', panel_station))}


if __name__ == '__main__':
    print(make_all(True))
