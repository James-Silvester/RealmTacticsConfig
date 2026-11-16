#!/usr/bin/env python3
"""Grittier, side-on takes on the worker (the biped loader), drawn facing right.

    python3 PixelArt/HackticsUnits/worker_side_samples.py     # writes samples/worker_side.gif

Each sample is shown facing right in Team 1 colours and mirrored to face left
in Team 2 colours. Nothing here touches the game files.
"""
import math
import os
import warnings

from PIL import Image, ImageDraw, ImageFont, ImageOps

import generate_units as g
from generate_units import FRAMES, Layer, all_of, any_of, box, curve, ell, poly, rbox, seg
from unit_samples import hazard, part

warnings.filterwarnings("ignore", category=DeprecationWarning)


# --- Grit --------------------------------------------------------------------

def grime(layer, shape, colour="D", on="M", parity=0):
    """Checker dither, used for dirt building up along the bottom of plates."""
    layer.fill(lambda x, y: shape(x, y) and (int(x) + int(y)) % 2 == parity, colour, on=on)


def rivets(layer, points, colour="K", on=None):
    for x, y in points:
        layer.px(x, y, colour, on)


def scratch(layer, x, y, length=3, colour="L", on="MD"):
    for k in range(length):
        layer.px(x + k, y - k, colour, on)


def smoke(frame, x, y, i, drift=-5.0, rise=7.0):
    inside = box(1, 1, 30, 30)
    for k in range(3):
        age = (i / FRAMES + k / 3) % 1.0
        puff = ell(x + drift * age, y - rise * age, 0.9 + age * 1.6, 0.8 + age * 1.3)
        frame.fill(all_of(puff, inside), "c", on=".")


# --- Side-on walk cycle ------------------------------------------------------

def knee_for(hip, ankle, l1, l2):
    """Two bone IK, always picking the knee that bends backwards (to the left)."""
    dx, dy = ankle[0] - hip[0], ankle[1] - hip[1]
    d = max(0.5, min(math.hypot(dx, dy), l1 + l2 - 0.05))
    a = math.acos(max(-1.0, min(1.0, (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d))))
    base = math.atan2(dy, dx)
    k1 = (hip[0] + l1 * math.cos(base + a), hip[1] + l1 * math.sin(base + a))
    k2 = (hip[0] + l1 * math.cos(base - a), hip[1] + l1 * math.sin(base - a))
    return k1 if k1[0] < k2[0] else k2


def foot_offset(phase, stride, lift):
    """Half the cycle planted and sliding back, half swinging forward through the air."""
    phase %= 1.0
    if phase < 0.5:
        return stride * (1 - 4 * phase), 0.0
    u = (phase - 0.5) * 2
    return stride * (-1 + 2 * u), lift * math.sin(math.pi * u)


def leg(frame, hip, phase, near, stride=3.0, lift=2.6, l1=5.0, l2=5.4, plated=True):
    ox, oy = foot_offset(phase, stride, lift)
    ankle = (hip[0] + 1.5 + ox, 26.0 - oy)
    knee = knee_for(hip, ankle, l1, l2)
    fx, fy = round(ankle[0]), round(ankle[1])
    with part(frame) as b:
        b.fill(seg(*hip, *knee, 3.0), "G" if near else "g")
        b.fill(seg(*knee, *ankle, 2.2), "G" if near else "g")
        if near:                                           # exposed piston down the shin
            b.fill(seg(knee[0] + 1.4, knee[1] - 0.4, ankle[0] + 1.0, ankle[1] - 2.2, 1.0), "h")
        b.fill(box(fx - 2, fy + 1, fx + 3, fy + 2), "g")
        if near:
            b.fill(box(fx + 2, fy + 1, fx + 3, fy + 1), "h")
            b.px(fx - 2, fy + 1, "G")
    if near:
        if plated:
            with part(frame) as b:                         # thigh armour takes the team colour
                mx, my = hip[0] + (knee[0] - hip[0]) * 0.62, hip[1] + (knee[1] - hip[1]) * 0.62
                b.fill(seg(hip[0], hip[1], mx, my, 4.4), "M")
                b.fill(seg(hip[0] + 1.2, hip[1] + 1.2, mx + 1.2, my + 1.2, 1.4), "D", on="M")
                b.px(hip[0] - 1.5, hip[1] - 1.5, "L", on="M")
        frame.fill(ell(knee[0], knee[1], 1.3, 1.3), "h")
        frame.px(knee[0] - 0.5, knee[1] - 0.5, "K")
        frame.fill(ell(hip[0], hip[1], 1.2, 1.2), "g")


def stride_bob(i):
    return (1, 0, 0, 0, 1, 0, 0, 0)[i]


def lens(layer, x, y, i):
    """A single hard sensor light rather than a friendly visor."""
    layer.px(x, y, "r")
    layer.px(x + 1, y, "W" if i % 4 < 2 else "p")


# --- Samples -----------------------------------------------------------------

def forklift(i):
    f = Layer()
    p = i / FRAMES
    bob = stride_bob(i)
    leg(f, (15.5, 18 + bob), p + 0.5, near=False)
    carry = 16 + (0, 0, 1, 1, 0, 0, 1, 1)[i]
    with part(f, dy=bob) as b:                             # mast and fork
        b.fill(box(24, 7, 25, 23), "g")
        b.fill(box(24, 7, 24, 23), "G")
        for y in (10, 14, 18, 22):
            b.px(25, y, "h")
        b.fill(box(23, carry, 26, carry + 3), "M")
        hazard(b, 23, carry + 2, 26, carry + 3, on="M")
        b.fill(box(27, carry + 2, 27, carry + 4), "h")
        b.fill(box(27, carry + 4, 29, carry + 4), "h")
    with part(f, dy=bob) as b:
        b.fill(box(7, 4, 8, 8), "g")                       # exhaust stack
        b.px(7, 4, "G")
        b.fill(box(3, 10, 6, 17), "g")                     # power pack
        for y in (11, 13, 15):
            b.fill(box(4, y, 5, y), "G")
        hull = poly([(7, 8), (18, 7), (23, 11), (23, 17), (20, 20), (8, 20), (6, 17), (6, 10)])
        b.fill(hull, "M")
        b.fill(all_of(hull, box(0, 0, 31, 8)), "L")
        b.fill(all_of(hull, box(0, 18, 31, 31)), "D")
        grime(b, all_of(hull, box(0, 15, 31, 17)))
        b.fill(poly([(16, 9), (20, 9.2), (22.6, 11.5), (22.6, 13), (16, 13)]), "K")   # cab glass
        lens(b, 19, 11, i)
        b.fill(box(13, 9, 13, 19), "D", on="M")            # panel seam
        rivets(b, [(8, 10), (11, 10), (8, 17), (11, 17)], on="MD")
        scratch(b, 8, 15, 3)
        scratch(b, 18, 17, 2)
    leg(f, (12, 18 + bob), p, near=True)
    smoke(f, 7.5, 3 + bob, i)
    return f.shadow(15, 11)


def hauler(i):
    f = Layer()
    p = i / FRAMES
    bob = stride_bob(i)
    leg(f, (16.5, 19 + bob), p + 0.5, near=False)
    with part(f, dy=bob) as b:                             # crate lashed to its back
        b.fill(box(5, 4, 16, 12), "G")
        b.fill(box(5, 4, 16, 4), "h")
        b.fill(box(5, 11, 16, 12), "g")
        b.fill(box(15, 5, 16, 12), "g")
        for x in (8, 13):
            b.fill(box(x, 4, x, 12), "K")
        b.fill(box(10, 7, 11, 8), "r")
        b.px(10, 7, "p" if i % 4 < 2 else "r")
        rivets(b, [(6, 6), (6, 10), (14, 6)], "g")
    with part(f, dy=bob) as b:
        hull = poly([(4, 13), (19, 12), (25, 14.5), (26, 18), (22, 21), (7, 21), (4, 18)])
        b.fill(hull, "M")
        b.fill(all_of(hull, box(0, 0, 31, 13)), "L")
        b.fill(all_of(hull, box(0, 19, 31, 31)), "D")
        grime(b, all_of(hull, box(0, 17, 31, 18)))
        b.fill(box(20, 15, 24, 17), "K")                   # low sensor slot
        lens(b, 22, 16, i)
        b.fill(box(10, 14, 10, 20), "D", on="M")
        rivets(b, [(6, 15), (8, 15), (14, 15), (17, 15)], on="M")
        scratch(b, 12, 18, 3)
        hazard(b, 5, 19, 9, 20, on="D")
    with part(f, dy=bob, outline=False) as b:
        b.fill(curve((5, 12), (2, 15), (5, 18), 1.0), "K")  # loose strap
    leg(f, (13, 19 + bob), p, near=True)
    return f.shadow(15, 12)


def jackhammer(i):
    f = Layer()
    p = i / FRAMES
    bob = stride_bob(i)
    pump = (0, 2)[i % 2]
    leg(f, (14.5, 18 + bob), p + 0.5, near=False)
    with part(f, dy=bob) as b:                             # air tank and hose
        b.fill(rbox(3, 8, 6, 18, 1.5), "G")
        b.fill(box(4, 9, 4, 17), "h")
        b.fill(box(3, 12, 6, 12), "g")
        b.fill(box(3, 16, 6, 16), "g")
    with part(f, dy=bob) as b:
        hull = poly([(8, 5), (16, 5), (20, 9), (20, 18), (17, 20), (8, 20), (6, 17), (6, 8)])
        b.fill(hull, "M")
        b.fill(all_of(hull, box(0, 0, 31, 6)), "L")
        b.fill(all_of(hull, box(0, 18, 31, 31)), "D")
        grime(b, all_of(hull, box(0, 15, 31, 17)))
        b.fill(box(15, 8, 19, 10), "K")
        lens(b, 17, 9, i)
        b.fill(box(11, 6, 11, 19), "D", on="M")
        rivets(b, [(8, 8), (8, 12), (8, 16), (13, 8), (13, 16)], on="M")
        scratch(b, 13, 14, 3)
        hazard(b, 14, 17, 19, 18, on="MD")
    with part(f, dy=bob, outline=False) as b:
        b.fill(curve((5, 9), (11, 2), (19, 12), 1.0), "K")  # hose over the shoulder
    with part(f, dy=bob) as b:                             # breaker arm
        b.fill(seg(18, 13, 24, 19, 4.0), "G")
        b.fill(seg(17.4, 14.2, 23.4, 20.2, 1.0), "g")
        b.fill(seg(19.5, 12, 25, 17.5, 1.0), "h")
        b.fill(ell(18, 13, 2.0, 2.0), "g")
    with part(f, dy=bob) as b:
        b.fill(seg(25, 20, 27.2, 22.5 + pump, 1.8), "h")
        b.fill(seg(25, 20, 26, 21.2 + pump * 0.5, 2.6), "g")
    leg(f, (11.5, 18 + bob), p, near=True)
    if pump:                                               # chips flying off the bit
        f.px(29, 25, "W", on=".")
        f.px(25, 27, "h", on=".")
    else:
        f.px(29, 27, "h", on=".")
        f.px(26, 25, "W", on=".")
    return f.shadow(15, 11)


def skeleton(i):
    f = Layer()
    p = i / FRAMES
    bob = stride_bob(i)
    leg(f, (15.5, 18 + bob), p + 0.5, near=False)
    with part(f, dy=bob) as b:                             # bare roll cage
        for a, c in (((8, 6), (18, 6)), ((8, 6), (6, 18)), ((18, 6), (22, 12)), ((22, 12), (20, 19)),
                     ((6, 18), (20, 19)), ((8, 6), (20, 19))):
            b.fill(seg(*a, *c, 1.6), "G")
        b.fill(seg(8, 5.5, 18, 5.5, 0.8), "h")
    with part(f, dy=bob) as b:                             # engine block slung inside it
        b.fill(box(9, 10, 16, 17), "g")
        for y in (11, 13, 15):
            b.fill(box(10, y, 15, y), "G")
        b.fill(box(11, 16, 14, 16), "r" if i % 4 < 2 else "q")
        b.fill(box(17, 12, 18, 16), "g")
        b.px(17, 13, "h")
    with part(f, dy=bob) as b:                             # the only armour it has left
        plate_shape = poly([(12, 3), (21, 4), (24, 10), (15, 9)])
        b.fill(plate_shape, "M")
        b.fill(all_of(plate_shape, box(0, 0, 31, 4)), "L")
        grime(b, all_of(plate_shape, box(0, 7, 31, 31)))
        scratch(b, 16, 8, 3)
        rivets(b, [(14, 5), (20, 6)], on="ML")
    with part(f, dy=bob) as b:                             # sensor on a stalk
        b.fill(seg(21, 13, 25, 11.5, 1.6), "g")
        b.fill(box(24, 8, 28, 12), "G")
        b.fill(box(24, 8, 28, 8), "h")
        b.fill(box(26, 10, 28, 11), "K")
        lens(b, 27, 10, i)
    with part(f, dy=bob) as b:
        grip = (0, 0, 1, 1, 0, 0, 1, 1)[i]
        b.fill(seg(19, 17, 25, 19, 1.8), "g")
        b.fill(seg(25, 19, 28, 18 - grip, 1.0), "h")
        b.fill(seg(25, 19, 28, 21 + grip, 1.0), "h")
    leg(f, (12, 18 + bob), p, near=True, plated=False)
    smoke(f, 8, 5 + bob, i, drift=-4.0, rise=4.0)
    return f.shadow(15, 11)


def crane(i):
    f = Layer()
    p = i / FRAMES
    bob = stride_bob(i)
    swing = 1.6 * math.sin(math.tau * p)
    leg(f, (16.5, 19 + bob), p + 0.5, near=False, l1=4.6, l2=4.8, stride=2.6)
    with part(f, dy=bob) as b:                             # counterweight
        b.fill(box(2, 11, 5, 19), "g")
        b.fill(box(2, 11, 5, 11), "G")
        rivets(b, [(3, 13), (3, 17)], "h")
    with part(f, dy=bob) as b:                             # boom
        b.fill(seg(8, 9, 25, 3.5, 2.4), "G")
        b.fill(seg(8, 9.8, 25, 4.3, 0.9), "g")
        for k in range(4):
            b.px(11 + k * 4, 8 - k * 1.3, "h")
        b.fill(ell(25, 3.8, 1.5, 1.5), "g")
    with part(f, dy=bob, outline=False) as b:              # hook line
        b.fill(seg(25.5, 5, 25.5 + swing, 13, 0.9), "K")
    with part(f, dy=bob) as b:
        hx = round(25 + swing)
        b.fill(box(hx, 13, hx + 1, 14), "h")
        b.fill(box(hx + 1, 15, hx + 1, 16), "h")
        b.fill(box(hx - 1, 16, hx + 1, 16), "h")
    with part(f, dy=bob) as b:
        hull = poly([(6, 9), (19, 9), (23, 12), (23, 19), (20, 21), (7, 21), (5, 18)])
        b.fill(hull, "M")
        b.fill(all_of(hull, box(0, 0, 31, 9)), "L")
        b.fill(all_of(hull, box(0, 19, 31, 31)), "D")
        grime(b, all_of(hull, box(0, 16, 31, 18)))
        b.fill(poly([(16, 11), (20, 11), (22.6, 13), (22.6, 15), (16, 15)]), "K")
        lens(b, 19, 13, i)
        b.fill(box(12, 10, 12, 20), "D", on="M")
        rivets(b, [(7, 12), (10, 12), (7, 17), (10, 17)], on="M")
        scratch(b, 7, 15, 3)
        hazard(b, 17, 18, 22, 19, on="MD")
    leg(f, (12.5, 19 + bob), p, near=True, l1=4.6, l2=4.8, stride=2.6)
    return f.shadow(15, 12)


def scrapper(i):
    f = Layer()
    p = i / FRAMES
    bob = stride_bob(i)
    leg(f, (15.5, 18 + bob), p + 0.5, near=False)
    with part(f, dy=bob) as b:                             # bent aerial
        b.fill(seg(9, 8, 7.5, 3, 0.9), "g")
        b.fill(seg(7.5, 3, 5, 3.5, 0.9), "g")
    with part(f, dy=bob, outline=False) as b:              # cable hanging out of its belly
        sway = 1.5 * math.sin(math.tau * p)
        b.fill(curve((9, 20), (7 + sway, 23), (8 + sway * 1.5, 25), 1.0), "K")
    with part(f, dy=bob) as b:
        hull = poly([(7, 8), (17, 6), (22, 10), (22, 17), (19, 20), (8, 20), (5, 16), (5, 10)])
        b.fill(hull, "M")
        b.fill(all_of(hull, box(0, 0, 31, 8)), "L")
        b.fill(all_of(hull, box(0, 18, 31, 31)), "D")
        b.fill(all_of(hull, box(17, 0, 31, 31)), "G")      # bare steel replacement panel
        b.fill(all_of(hull, box(17, 17, 31, 31)), "g")
        b.fill(box(17, 6, 17, 20), "K", on="MLDGg")
        b.fill(box(12, 9, 16, 12), "L", on="M")            # welded-on patch
        rivets(b, [(12, 9), (16, 9), (12, 12), (16, 12)], on="L")
        b.fill(box(8, 13, 12, 17), "K")                    # panel torn off
        b.px(9, 14, "h")
        b.px(11, 16, "h")
        b.fill(box(9, 15, 10, 15), "r" if i % 4 < 2 else "q")
        grime(b, all_of(hull, box(0, 15, 16, 17)))
        b.fill(box(18, 10, 21, 12), "K")
        lens(b, 19, 11, i)
        scratch(b, 6, 12, 3)
        rivets(b, [(19, 15), (21, 15), (19, 18)], "h", on="Gg")
    grip = (0, 1, 2, 2, 1, 0, 0, 0)[i] * 0.8
    with part(f, dy=bob) as b:                             # oversized salvage claw
        b.fill(seg(18, 12, 25, 8, 3.0), "g")
        b.fill(seg(25, 8, 26, 15, 2.6), "G")
        b.fill(seg(26, 15, 23.5 - grip * 0.3, 20 + grip, 1.6), "h")
        b.fill(seg(26, 15, 29 + grip * 0.2, 19 + grip, 1.6), "h")
        b.fill(ell(25, 8, 1.6, 1.6), "h")
        b.px(24.5, 7.5, "K")
    leg(f, (12, 18 + bob), p, near=True)
    return f.shadow(15, 11)


SAMPLES = [
    ("Forklift", forklift),
    ("Hauler", hauler),
    ("Breaker", jackhammer),
    ("Bare frame", skeleton),
    ("Crane", crane),
    ("Scrapper", scrapper),
]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ground = Image.open(os.path.normpath(os.path.join(
        here, "..", "..", "config", "hacktics", "version1", "entities", "types", "terrain", "ground.png"))).convert("RGBA")
    font = ImageFont.load_default(size=15)
    small = ImageFont.load_default(size=11)
    teams = list(g.TEAM_PREVIEW.items())

    rendered = []
    for name, draw in SAMPLES:
        frames = [draw(i).image() for i in range(FRAMES)]
        g.check(name, frames)
        rendered.append((name, frames))

    scale, cols, pad, label = 6, 3, 10, 24
    tile = g.SIZE * scale
    cell_w, cell_h = tile * 2 + pad, tile + label + 16 + pad
    rows = -(-len(rendered) // cols)
    out = []
    for n in range(FRAMES):
        im = Image.new("RGBA", (cols * cell_w + pad, rows * cell_h + pad), (24, 22, 40, 255))
        pen = ImageDraw.Draw(im)
        for idx, (name, frames) in enumerate(rendered):
            x = pad + (idx % cols) * cell_w
            y = pad + (idx // cols) * cell_h
            pen.text((x, y), f"{idx + 1}  {name}", fill=(235, 235, 245, 255), font=font)
            for k, (team, mapping) in enumerate(teams):
                sprite = g.recolour(frames[n], mapping)
                if k == 1:
                    sprite = ImageOps.mirror(sprite)       # second team faces the other way
                bg = ground.copy()
                bg.alpha_composite(sprite)
                im.paste(bg.resize((tile, tile), Image.NEAREST), (x + k * tile, y + label))
                pen.text((x + k * tile + 2, y + label + tile + 2), f"{team}, facing {'left' if k else 'right'}",
                         fill=(150, 150, 170, 255), font=small)
        out.append(im.convert("RGB"))

    out_dir = os.path.join(here, "samples")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "worker_side.gif")
    out[0].save(path, save_all=True, append_images=out[1:], duration=125, loop=0)
    out[0].save(os.path.join(out_dir, "worker_side.png"))
    print("Wrote", path)


if __name__ == "__main__":
    main()
