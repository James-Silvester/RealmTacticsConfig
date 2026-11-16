#!/usr/bin/env python3
"""Candidate designs for every Hacktics unit except the worker, six per unit.

    python3 PixelArt/HackticsUnits/unit_samples.py              # writes samples/<unit>.gif and samples/all_units.gif
    python3 PixelArt/HackticsUnits/unit_samples.py virus worm   # only some units

Nothing here touches the game files. Chosen designs get moved into
generate_units.py, after which this file can be deleted.
"""
import math
import os
import sys
import warnings

from PIL import Image, ImageDraw, ImageFont

import generate_units as g
from generate_units import (FRAMES, TAU, Layer, all_of, any_of, box, curve, ell, minus, moved, plate, poly, rbox,
                            scanner, seg, wave)

warnings.filterwarnings("ignore", category=DeprecationWarning)


# --- Shared parts ------------------------------------------------------------

class part:
    """`with part(frame) as layer:` draws on a fresh layer, then outlines it and stacks it on the frame."""

    def __init__(self, frame, dx=0, dy=0, outline=True):
        self.frame, self.dx, self.dy, self.outlined = frame, dx, dy, outline

    def __enter__(self):
        self.layer = Layer()
        return self.layer

    def __exit__(self, *exc):
        if self.outlined:
            self.layer.outline()
        self.frame.over(self.layer, self.dx, self.dy)


def octagon(x0, y0, x1, y1, c=3):
    """Chamfered box in inclusive pixel coordinates."""
    x1 += 1
    y1 += 1
    return poly([(x0 + c, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1 - c), (x1 - c, y1), (x0 + c, y1), (x0, y1 - c),
                 (x0, y0 + c)])


def step_bob(i):
    return 1 if i % 4 in (1, 2) else 0


def hover_bob(i):
    return round(1.2 * wave(i / FRAMES))


def visor(layer, x0, y0, x1, y1, i):
    layer.fill(box(x0, y0, x1, y1), "K")
    scanner(layer, x0 + 1, x1 - 1, (y0 + y1) // 2, i)


def antenna(layer, x, top, bottom, i):
    layer.fill(box(x, top, x, bottom), "D")
    layer.px(x, top, "W" if i % 4 < 2 else "r")


def biped_legs(frame, i, hip_y=17, hip=4, knee=8.5, foot=6, bob=0, knee_y=21.5):
    legs, joints = Layer(), Layer()
    for s, phase in ((-1, 0), (1, 4)):
        lift = (0, 1, 2, 1, 0, 0, 0, 0)[(i + phase) % FRAMES]
        h = (16 + s * hip, hip_y + bob)
        k = (16 + s * knee, knee_y - lift)
        ft = (16 + s * foot, 26.5 - lift)
        legs.fill(seg(*h, *k, 2.8), "M")
        legs.fill(seg(*k, *ft, 2.0), "D")
        legs.fill(box(round(ft[0]) - 2, 27 - lift, round(ft[0]) + 1, 28 - lift), "D")
        joints.fill(ell(*k, 1.4, 1.4), "L")
    legs.outline()
    frame.over(legs)
    frame.over(joints)


def spider_legs(frame, i, hip_y=17, bob=0, reach=12.0):
    legs, joints = Layer(), Layer()
    layout = ((7.5, hip_y, reach, hip_y - 3.5, reach + 0.6), (5.0, hip_y + 3, 8.6, min(hip_y + 5, 24), 7.6))
    order = {(-1, 0): 0, (1, 1): 1, (1, 0): 2, (-1, 1): 3}
    for s in (-1, 1):
        for pair, (hip_dx, hy, knee_dx, knee_y, foot_dx) in enumerate(layout):
            step = (i - 2 * order[(s, pair)]) % FRAMES
            lift = (2, 1)[step] if step < 2 else 0
            knee = (16 + s * knee_dx, knee_y - lift * 0.5)
            foot = (16 + s * foot_dx, 27.6 - lift)
            legs.fill(seg(16 + s * hip_dx, hy + bob, *knee, 2.4), "M")
            legs.fill(seg(*knee, *foot, 1.7), "D")
            legs.fill(box(round(foot[0] - 1), 28 - lift, round(foot[0]), 28 - lift), "D")
            joints.fill(ell(*knee, 1.3, 1.3), "L")
    legs.outline()
    frame.over(legs)
    frame.over(joints)


def outriggers(frame, hip_y=13, reach=12.5):
    legs, joints = Layer(), Layer()
    for s in (-1, 1):
        knee = (16 + s * (reach - 1), hip_y + 5)
        foot = (16 + s * reach, 27.5)
        legs.fill(seg(16 + s * 7, hip_y, *knee, 2.4), "M")
        legs.fill(seg(*knee, *foot, 1.7), "D")
        legs.fill(box(round(foot[0]) - 1, 28, round(foot[0]), 28), "D")
        joints.fill(ell(*knee, 1.3, 1.3), "L")
    legs.outline()
    frame.over(legs)
    frame.over(joints)


def treads(frame, i, x0=4, x1=27, y0=22):
    t = Layer()
    t.fill(rbox(x0, y0, x1, 28, 3), "D")
    t.fill(rbox(x0 + 2, y0 + 2, x1 - 2, 26, 1.5), "K")
    for x in range(x0 + 4, x1 - 3, 6):
        t.fill(box(x, y0 + 2, x + 1, 26), "L")
    for x in range(x0 + 1, x1):
        if (x - i) % 3 == 0:
            t.px(x, y0, "L", on="D")
        if (x + i) % 3 == 0:
            t.px(x, 28, "M", on="D")
    t.outline()
    frame.over(t)


def wheels(frame, i, xs, y=25.5, r=3.0):
    w = Layer()
    a = TAU * i / FRAMES
    for x in xs:
        w.fill(ell(x, y, r, r), "D")
        w.fill(ell(x, y, r - 1.8, r - 1.8), "L")
        w.px(x + math.cos(a) * (r - 1.0) - 0.5, y + math.sin(a) * (r - 1.0) - 0.5, "M", on="D")
    w.outline()
    frame.over(w)


def wash(frame, i, xs, y):
    """Thruster glow under hovering units."""
    for x in xs:
        frame.fill(box(x, y, x + 1, y + i % 2), "p" if i % 2 else "r", on=".")


def flame(layer, cx, base, h, i, ph=0.0):
    t = i / FRAMES
    hh = h + 1.2 * wave(t, ph) + 0.6 * wave(2 * t, ph * 3)
    lean = 1.2 * wave(t, ph + 0.3)
    w = max(1.6, h * 0.4)

    def tongue(wd, ht, ln):
        return any_of(poly([(cx - wd, base + 1), (cx - wd * 0.8, base - ht * 0.4), (cx + ln, base - ht),
                            (cx + wd * 0.8, base - ht * 0.4), (cx + wd, base + 1)]),
                      ell(cx, base - ht * 0.25, wd, ht * 0.3))
    layer.fill(tongue(w, hh, lean), "M")
    layer.fill(tongue(w * 0.5, hh * 0.6, lean * 0.5), "L", on="M")
    layer.fill(tongue(w * 0.22, hh * 0.3, 0), "W", on="L")


def hazard(layer, x0, y0, x1, y1, i=0, on=None):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            layer.px(x, y, "K" if ((x + y + i) // 2) % 2 else "L", on)


def cog(cx, cy, r_in, r_out, teeth, spin):
    def inside(x, y):
        dx, dy = x - cx, y - cy
        r = math.hypot(dx, dy)
        if r <= r_in:
            return True
        if r > r_out:
            return False
        return 0.22 < ((math.atan2(dy, dx) - spin) / (TAU / teeth)) % 1.0 < 0.78
    return inside


# --- Virus -------------------------------------------------------------------

def virus_mine_walker(i):
    f = Layer()
    t = i / FRAMES
    bob = step_bob(i)
    biped_legs(f, i, hip_y=19, bob=bob)
    with part(f, dy=bob) as b:
        for k in range(8):
            a = TAU * (k / 8 + t / 8)
            ln = 8.6 + 0.8 * wave(t, k / 2)
            b.fill(seg(16, 13, 16 + math.cos(a) * ln, 13 + math.sin(a) * ln, 1.8), "D")
    with part(f, dy=bob) as b:
        plate(b, ell(16, 13, 6.6, 6.6), top=8, bottom=17)
        visor(b, 11, 12, 20, 14, i)
    return f.shadow(16, 10)


def virus_hover_mine(i):
    f = Layer()
    t = i / FRAMES
    dy = hover_bob(i)
    with part(f, dy=dy) as b:
        for k in range(8):
            a = TAU * (k / 8 + t / 8)
            ln = 9.4 + 0.8 * wave(t, k / 2)
            tx, ty = 16 + math.cos(a) * ln, 15 + math.sin(a) * ln
            b.fill(seg(16, 15, tx, ty, 1.8), "D")
            b.fill(ell(tx, ty, 1.3, 1.3), "L")
    with part(f, dy=dy) as b:
        plate(b, ell(16, 15, 7.2, 7.2), top=10, bottom=19)
        visor(b, 10, 14, 21, 16, i)
        b.fill(box(15, 10, 16, 11), "W" if i % 4 < 2 else "r")
    return f.shadow(16, 8)


def virus_phage(i):
    f = Layer()
    bob = step_bob(i)
    spider_legs(f, i, hip_y=20, bob=bob)
    with part(f, dy=bob) as b:
        b.fill(box(15, 13, 17, 21), "D")                  # tail sheath
        for y in (14, 16, 18, 20):
            b.fill(box(14, y, 18, y), "L")
        b.fill(box(10, 21, 21, 22), "M")
    with part(f, dy=bob) as b:
        b.fill(poly([(16, 2), (22, 5), (22, 11), (16, 14), (10, 11), (10, 5)]), "M")
        b.fill(poly([(16, 2), (22, 5), (16, 8), (10, 5)]), "L")
        b.fill(poly([(16, 8), (22, 5), (22, 11), (16, 14)]), "D")
        b.fill(box(12, 9, 14, 10), "K")
        b.px(12 + i % 3, 9, "W" if i % 2 else "r")
        b.px(13, 10, "r")
    return f.shadow(16, 12)


def virus_saw(i):
    f = Layer()
    t = i / FRAMES
    dy = hover_bob(i)
    for s in (-1, 1):
        with part(f, dy=dy) as b:
            b.fill(cog(16 + s * 9, 17, 3.3, 5.2, 6, s * t * TAU / 3), "L")
            b.fill(ell(16 + s * 9, 17, 1.4, 1.4), "D")
    with part(f, dy=dy) as b:
        antenna(b, 16, 4, 7, i)
        plate(b, octagon(10, 8, 21, 20, 3), top=9, bottom=19)
        visor(b, 11, 12, 20, 14, i)
        for x in (12, 14, 17, 19):
            b.px(x, 17, "K", on="M")
    wash(f, i, (12, 19), 22 + dy)
    return f.shadow(16, 9)


def virus_crab(i):
    f = Layer()
    bob = step_bob(i)
    spider_legs(f, i, hip_y=19, bob=bob)
    snap = (0, 0, 1, 2, 2, 1, 0, 0)[i]
    with part(f, dy=bob) as b:
        for s in (-1, 1):
            b.fill(seg(16 + s * 6, 13, 16 + s * 10, 8, 2.2), "M")
            b.fill(seg(16 + s * 10, 8, 16 + s * (7 + snap), 4, 1.6), "L")
            b.fill(seg(16 + s * 10, 8, 16 + s * (12.4 - snap * 0.5), 4.5, 1.6), "L")
    with part(f, dy=bob) as b:
        plate(b, octagon(8, 12, 23, 21, 3), top=13, bottom=20)
        visor(b, 10, 15, 21, 17, i)
    return f.shadow(16, 12)


def virus_glitch(i):
    f = Layer()
    dy = hover_bob(i)
    shift = (0, 1, 2, 1, 0, -1, -2, -1)[i]
    with part(f, dy=dy) as b:
        b.fill(box(9, 16, 22, 24), "M")
        b.fill(box(9, 22, 22, 24), "D")
        b.fill(box(21, 16, 22, 24), "D", on="M")
        for x in (11, 13, 15):
            b.fill(box(x, 18, x, 20), "K", on="M")
    with part(f, dx=shift, dy=dy) as b:
        b.fill(box(9, 7, 22, 14), "M")
        b.fill(box(9, 7, 22, 8), "L")
        visor(b, 11, 10, 20, 12, i)
    for k in range(4):                                    # torn off scanlines
        y = 8 + k * 5
        x = (3 if k % 2 else 25) + (i + k) % 3
        f.fill(box(x, y, x + 2, y), "r" if (i + k) % 2 else "p", on=".")
    return f.shadow(16, 8)


# --- Worm --------------------------------------------------------------------

def worm_centipede(i):
    f = Layer()
    t = i / FRAMES
    for k in range(5):
        x = 4 + k * 4
        y = round(21 - 2.5 * (0.5 + 0.5 * wave(t, -k * 0.17)))
        with part(f) as b:
            b.fill(box(x + 1, y + 3, x + 1, 28 - (i + k) % 2), "D")
        with part(f) as b:
            plate(b, rbox(x, y - 3, x + 4, y + 3, 2), top=y - 2, bottom=y + 3)
    hy = round(18 - 2 * (0.5 + 0.5 * wave(t, -0.85)))
    with part(f) as b:
        b.fill(seg(22, hy - 4, 20, hy - 8, 1.0), "D")
        b.px(20, hy - 8, "r")
        plate(b, octagon(20, hy - 4, 28, hy + 4, 3), top=hy - 3, bottom=hy + 3)
        visor(b, 22, hy - 1, 27, hy + 1, i)
        b.fill(box(25, hy + 5, 26, hy + 6), "L")
    return f.shadow(16, 12)


def worm_tunneller(i):
    f = Layer()
    t = i / FRAMES
    for k in range(7):
        u = ((k + 2 * t) % 7) / 7
        a = math.pi * (1 - u)
        x, y = 16 + 10 * math.cos(a), 27 - 16 * math.sin(a)
        with part(f) as b:
            base = "M" if k % 2 == 0 else "L"
            b.fill(ell(x, y, 3.2, 3.2), base)
            b.fill(minus(ell(x, y, 3.2, 3.2), ell(x - 0.5, y - 1.2, 3.2, 3.2)), "D" if base == "M" else "M", on=base)
            if k % 2 == 0:
                b.px(x - 0.5, y - 0.5, "r")
    for cx in (6, 26):                                    # the holes it bores between
        with part(f) as b:
            b.fill(ell(cx, 28, 4.6, 1.9), "D")
            b.fill(ell(cx, 27.6, 3.2, 0.9), "K")
    return f.shadow(16, 12)


def worm_cobra(i):
    f = Layer()
    t = i / FRAMES
    sway = round(1.6 * wave(t))
    with part(f) as b:
        b.fill(ell(16, 25.6, 10.5, 3.2), "M")
        b.fill(all_of(ell(16, 25.6, 10.5, 3.2), box(0, 27, 31, 31)), "D")
        for x in range(7, 26, 3):
            b.px(x + (i // 2) % 3, 25, "L", on="M")
    with part(f) as b:
        b.fill(ell(16, 22, 7.5, 2.6), "M")
        b.fill(all_of(ell(16, 22, 7.5, 2.6), box(0, 23, 31, 31)), "D")
    with part(f) as b:
        neck = curve((15, 21), (11 + sway * 0.4, 14), (16 + sway, 8), 3.6)
        b.fill(neck, "M")
        b.fill(curve((16, 21), (12 + sway * 0.4, 14), (17 + sway, 8), 1.2), "L", on="M")
    hx = 16 + sway
    with part(f) as b:
        plate(b, poly([(hx - 4, 3), (hx + 4, 3), (hx + 8, 6.5), (hx + 4, 10), (hx - 4, 10)]), top=4, bottom=9)
        b.fill(box(hx - 2, 6, hx + 4, 7), "K")
        scanner(b, hx - 2, hx + 4, 6, i)
    return f.shadow(16, 12)


def worm_train(i):
    f = Layer()
    wheels(f, i, (6, 14, 21, 26), y=26.5, r=2.0)
    for k, x in enumerate((3, 11)):
        with part(f, dy=(i + k) % 2) as b:
            b.fill(box(x, 18, x + 7, 23), "M")
            b.fill(box(x, 22, x + 7, 23), "D")
            b.fill(box(x + 1, 14, x + 6, 17), "r")           # payload
            b.fill(box(x + 1, 14, x + 6, 14), "p")
            b.px(x + 2 + (i + k * 3) % 4, 16, "W")
    with part(f, outline=False) as b:
        b.fill(box(10, 21, 11, 21), "K")
        b.fill(box(18, 21, 19, 21), "K")
    with part(f, dy=(i + 1) % 2) as b:
        b.fill(box(20, 8, 21, 11), "D")
        plate(b, poly([(19, 12), (25, 12), (29, 17), (29, 24), (19, 24)]), top=13, bottom=22)
        visor(b, 21, 15, 27, 17, i)
    for k in range(2):
        age = (i / FRAMES + k / 2) % 1.0
        f.px(20 - round(age * 4), 6 - round(age * 3), "L" if age < 0.5 else "p", on=".")
    return f.shadow(16, 13)


def worm_inch(i):
    f = Layer()
    t = i / FRAMES
    arch = 0.5 + 0.5 * wave(t)
    pts = []
    for k in range(6):
        x = 14 + (k - 2.5) / 2.5 * (9.5 - 3.0 * arch)
        y = 25.5 - arch * 9 * math.sin(math.pi * k / 5)
        pts.append((x, y))
    for k, (a, c) in enumerate(zip(pts, pts[1:])):
        with part(f) as b:
            base = "M" if k % 2 == 0 else "L"
            b.fill(seg(*a, *c, 5.0), base)
            b.fill(seg(a[0], a[1] + 1.8, c[0], c[1] + 1.8, 1.4), "D" if base == "M" else "M", on=base)
    hx, hy = round(pts[-1][0]) + 1, round(pts[-1][1]) - 1
    with part(f) as b:
        plate(b, octagon(hx - 3, hy - 4, hx + 4, hy + 3, 2), top=hy - 3, bottom=hy + 2)
        b.fill(box(hx - 1, hy - 1, hx + 3, hy), "K")
        scanner(b, hx - 1, hx + 3, hy - 1, i)
    return f.shadow(16, 12)


def worm_borer(i):
    f = Layer()
    treads(f, i, 3, 22, 23)
    jit = i % 2
    with part(f, dy=-jit) as b:
        cone = poly([(21, 8.5), (29.4, 16), (21, 23.5)])
        b.fill(cone, "L")
        for y in range(8, 24):
            for x in range(21, 30):
                if (x + y + i) % 4 < 2:
                    b.px(x, y, "D", on="L")
    with part(f, dy=-jit) as b:
        plate(b, rbox(3, 10, 21, 22, 2), top=11, bottom=21)
        for x in (15, 19):
            b.fill(box(x, 10, x, 22), "D", on="ML")
        visor(b, 5, 14, 13, 16, i)
        b.fill(box(5, 18, 9, 18), "K", on="M")
    return f.shadow(16, 13)


# --- Firewall ----------------------------------------------------------------

def bricks(layer, x0, y0, x1, y1, on="M"):
    for row, y in enumerate(range(y0 + 3, y1 + 1, 4)):
        layer.fill(box(x0, y, x1, y), "D", on=on)
    for row, y in enumerate(range(y0, y1 + 1, 4)):
        for x in range(x0 + (3 if row % 2 else 7), x1, 8):
            layer.fill(box(x, y, x, y + 2), "D", on=on)


def firewall_shield_walker(i):
    f = Layer()
    bob = step_bob(i)
    biped_legs(f, i, hip_y=20, bob=bob, knee_y=23)
    with part(f, dy=bob) as b:
        flame(b, 9, 8, 4, i, 0.0)
        flame(b, 23, 8, 4, i, 0.5)
    with part(f, dy=bob) as b:
        shield = poly([(5, 8), (27, 8), (27, 17), (16, 25), (5, 17)])
        plate(b, shield, top=9, right=25)
        bricks(b, 5, 10, 26, 24)
        visor(b, 10, 12, 21, 14, i)
    return f.shadow(16, 11)


def firewall_bunker(i):
    f = Layer()
    with part(f) as b:
        flame(b, 10, 12, 6, i, 0.0)
        flame(b, 21, 12, 6, i, 0.5)
    with part(f) as b:
        for x0, x1 in ((4, 8), (12, 19), (23, 27)):       # battlements
            b.fill(box(x0, 10, x1, 13), "M")
            b.fill(box(x0, 10, x1, 10), "L")
        b.fill(box(4, 13, 27, 28), "M")
        b.fill(box(4, 27, 27, 28), "D")
        bricks(b, 4, 13, 27, 26)
        visor(b, 9, 17, 22, 19, i)
    return f.shadow(16, 13)


def firewall_gate(i):
    f = Layer()
    with part(f, outline=False) as b:                      # the barrier itself
        for y in range(9, 27):
            for x in range(10, 22):
                n = (x * 3 + y * 5 + i * 3) % 7
                b.px(x, y, "p" if n < 2 else "r" if n < 5 else "q")
        sweep = 9 + (i * 2) % 18
        b.fill(box(10, sweep, 21, sweep), "W")
    for x0 in (4, 22):
        with part(f) as b:
            plate(b, box(x0, 6, x0 + 5, 28), top=7, bottom=27, right=x0 + 5)
            for y in (10, 15, 20, 25):
                b.fill(box(x0 + 1, y, x0 + 4, y), "K", on="M")
            b.fill(box(x0 + 2, 3, x0 + 3, 5), "W" if (i + x0) % 4 < 2 else "r")
    return f.shadow(16, 13)


def firewall_riot(i):
    f = Layer()
    for x0 in (5, 21):                                    # tracks seen head on
        with part(f) as b:
            b.fill(box(x0, 21, x0 + 5, 28), "D")
            for y in range(21, 29):
                if (y + i) % 3 == 0:
                    b.fill(box(x0, y, x0 + 5, y), "K")
    with part(f, dy=-(i % 2)) as b:
        plate(b, octagon(4, 5, 27, 22, 4), top=6, right=26)
        hazard(b, 5, 19, 26, 21, on="MD")
        visor(b, 9, 9, 22, 11, i)
        for x in (8, 23):
            b.fill(box(x, 14, x, 16), "K", on="M")
        b.fill(box(13, 14, 18, 16), "L", on="M")
    return f.shadow(16, 12)


def firewall_dome(i):
    f = Layer()
    with part(f) as b:
        flame(b, 16, 11, 6, i, 0.2)
    with part(f) as b:
        dome = all_of(ell(16, 25, 12, 14), box(0, 0, 31, 24))
        plate(b, dome, top=13)
        b.fill(minus(dome, ell(14.5, 23.5, 12, 14)), "D", on="M")
        b.fill(box(3, 25, 28, 28), "D")
        b.fill(box(3, 25, 28, 25), "M")
        visor(b, 9, 18, 22, 20, i)
        for x in (6, 11, 16, 21, 26):
            b.px(x - 1, 23, "L", on="MD")
    return f.shadow(16, 13)


def firewall_shutter(i):
    f = Layer()
    gap = (0, 0, 2, 5, 5, 5, 2, 0)[i]
    with part(f) as b:
        plate(b, octagon(4, 3, 27, 28, 3), top=4, right=26)
        b.fill(box(7, 7, 24, 27), "K")
        for y in range(8, 27, 2):
            b.fill(box(8, y, 23, y), "r" if (y + i) % 4 < 2 else "q", on="K")
        bottom = 27 - gap
        for y in range(7, bottom + 1):
            b.fill(box(7, y, 24, y), "L" if (y - gap) % 3 else "M")
        hazard(b, 7, bottom - 2, 24, bottom, on="LM")
        if gap:
            b.fill(box(7, bottom + 1, 24, bottom + 1), "W")
        visor(b, 11, 4, 20, 5, i)
    return f.shadow(16, 13)


# --- Brute -------------------------------------------------------------------

def readout(layer, x, y, i):
    """Password read-out: four digits, one lit at a time."""
    layer.fill(box(x, y, x + 12, y + 3), "K")
    for d in range(4):
        layer.fill(box(x + 1 + d * 3, y + 1, x + 2 + d * 3, y + 2), "W" if (i // 2) % 4 == d else "r")


def brute_fists(i):
    f = Layer()
    t = i / FRAMES
    bob = step_bob(i)
    biped_legs(f, i, hip_y=20, hip=4, knee=7, foot=5.5, bob=bob, knee_y=23.5)
    left, right = round(2.2 * wave(t)), round(2.2 * wave(t, 0.5))
    with part(f, dy=bob) as b:
        b.fill(seg(8.5, 9, 5.5, 16 + left, 3.4), "M")
        b.fill(seg(23.5, 9, 26.5, 16 + right, 3.4), "M")
    with part(f, dy=bob) as b:
        plate(b, octagon(8, 4, 23, 20, 4), top=5, bottom=19, right=22)
        visor(b, 11, 7, 20, 8, i)
        readout(b, 10, 12, i)
    for x0, off in ((2, left), (23, right)):
        with part(f, dy=bob) as b:
            b.fill(rbox(x0, 16 + off, x0 + 6, 22 + off, 1.5), "L")
            b.fill(box(x0, 21 + off, x0 + 6, 22 + off), "M", on="L")
            for x in (x0 + 2, x0 + 4):
                b.fill(box(x, 17 + off, x, 19 + off), "D", on="L")
    return f.shadow(16, 12)


def brute_ram(i):
    f = Layer()
    treads(f, i, 4, 25, 22)
    dx = (0, -1, -2, -2, 2, 3, 2, 1)[i]
    with part(f) as b:
        for x in (8, 19):
            b.fill(box(x, 5, x + 1, 22), "D")
            b.fill(box(x, 5, x, 22), "M")
        b.fill(box(7, 4, 21, 5), "M")
        plate(b, box(9, 17, 18, 21), top=17)
        visor(b, 10, 18, 17, 20, i)
    with part(f, outline=False) as b:
        for x in (10, 17):                                # chains
            for y in range(6, 10, 2):
                b.px(x + (dx > 1), y, "K")
    with part(f, dx=dx) as b:
        b.fill(rbox(5, 10, 22, 15, 2), "M")
        b.fill(box(5, 10, 22, 11), "L", on="M")
        b.fill(box(5, 14, 22, 15), "D", on="M")
        b.fill(box(22, 8, 26, 17), "L")
        b.fill(box(25, 8, 26, 17), "D")
        b.fill(box(22, 16, 26, 17), "D")
    if i == 5:
        f.stamp(["W W", " p ", "W W"], 27, 3, on=".")
    return f.shadow(16, 13)


def brute_ball(i):
    f = Layer()
    t = i / FRAMES
    treads(f, i, 4, 22, 22)
    a = 0.42 * wave(t)
    bx, by = 21 + 13 * math.sin(a), 5 + 13 * math.cos(a)
    with part(f) as b:
        b.fill(seg(8, 21, 10, 5, 2.2), "D")
        b.fill(seg(10, 5, 21, 4, 2.2), "D")
        b.fill(seg(9, 13, 15, 4.5, 1.2), "L")
    with part(f, outline=False) as b:
        b.fill(seg(21, 5, bx, by, 1.0), "K")
    with part(f) as b:
        b.fill(ell(bx, by, 3.6, 3.6), "D")
        b.fill(ell(bx - 1.2, by - 1.4, 1.3, 1.0), "L", on="D")
    with part(f) as b:
        plate(b, rbox(4, 14, 15, 21, 2), top=15, bottom=21)
        visor(b, 6, 16, 13, 18, i)
    return f.shadow(15, 12)


def brute_hammer(i):
    f = Layer()
    bob = step_bob(i)
    biped_legs(f, i, hip_y=20, hip=4, knee=7.5, foot=5.5, bob=bob, knee_y=23.5)
    deg = (-25, -38, -45, -45, 40, 84, 84, 20)[i]
    a = math.radians(deg)
    sx, sy = 21, 14
    tx, ty = sx + 6 * math.sin(a), sy - 6 * math.cos(a)
    with part(f, dy=bob) as b:
        plate(b, octagon(8, 8, 23, 20, 3), top=9, bottom=19, right=22)
        visor(b, 10, 11, 21, 12, i)
        readout(b, 9, 14, i)
    with part(f) as b:
        b.fill(seg(sx, sy + bob, tx, ty, 1.8), "D")
    with part(f) as b:
        nx, ny = math.cos(a), math.sin(a)
        b.fill(seg(tx - nx * 2.6, ty - ny * 2.6, tx + nx * 2.6, ty + ny * 2.6, 4.6), "L")
        b.fill(seg(tx + nx * 1.5, ty + ny * 1.5, tx + nx * 2.6, ty + ny * 2.6, 4.6), "M", on="L")
    if i in (5, 6):
        f.stamp(["p W", "   ", "W p"][:: 1 if i == 5 else -1], 27, 18, on=".")
    return f.shadow(16, 12)


def brute_pistons(i):
    f = Layer()
    treads(f, i, 7, 24, 22)
    ext_l = (0, 1, 3, 2, 0, 0, 0, 0)[i]
    ext_r = (0, 0, 0, 0, 0, 1, 3, 2)[i]
    with part(f) as b:
        b.fill(box(8 - ext_l, 13, 10, 15), "D")
        for x in range(9 - ext_l, 10, 2):
            b.px(x, 13, "L")
        b.fill(box(21, 13, 23 + ext_r, 15), "D")
        for x in range(22, 23 + ext_r, 2):
            b.px(x, 13, "L")
    for x0 in (5 - ext_l, 23 + ext_r):
        with part(f) as b:
            b.fill(box(x0, 10, x0 + 3, 18), "L")
            b.fill(box(x0, 17, x0 + 3, 18), "M")
    with part(f, dy=-(i % 2)) as b:
        plate(b, octagon(9, 7, 22, 21, 3), top=8, bottom=20)
        visor(b, 11, 10, 20, 11, i)
        readout(b, 9, 14, i)
    return f.shadow(16, 12)


def brute_tumbler(i):
    f = Layer()
    t = i / FRAMES
    bob = step_bob(i)
    biped_legs(f, i, hip_y=21, hip=5, knee=8, foot=6, bob=bob, knee_y=24)
    with part(f, dy=bob) as b:
        plate(b, octagon(5, 3, 26, 22, 5), top=4, bottom=21, right=25)
        b.fill(box(11, 4, 20, 4), "K")
        scanner(b, 11, 20, 4, i)
        b.fill(ell(16, 13, 7.2, 7.2), "K")
        b.fill(ell(16, 13, 6.2, 6.2), "L")
        for k in range(12):                               # combination dial
            a = TAU * (k / 12 + t / 4)
            b.px(16 + math.cos(a) * 5.0 - 0.5, 13 + math.sin(a) * 5.0 - 0.5, "K" if k % 3 == 0 else "D", on="L")
        b.fill(ell(16, 13, 2.6, 2.6), "D")
        a = TAU * t / 4 * 3
        b.fill(seg(16, 13, 16 + math.cos(a) * 2.2, 13 + math.sin(a) * 2.2, 1.0), "W")
        b.fill(box(15, 6, 16, 7), "r")
    return f.shadow(16, 12)


# --- DDOS --------------------------------------------------------------------

def ddos_mortar(i):
    f = Layer()
    bob = step_bob(i)
    biped_legs(f, i, hip_y=20, bob=bob, knee_y=23)
    rec = (0, 0, 0, 2, 1, 0, 0, 0)[i] * 0.7
    with part(f, dy=bob) as b:
        b.fill(seg(13, 14, 22.5 - rec, 5.5 + rec, 5.2), "M")
        b.fill(seg(14.5, 15.5, 24 - rec, 7 + rec, 1.4), "D", on="M")
        b.fill(seg(21 - rec, 7 + rec, 22.5 - rec, 5.5 + rec, 5.2), "D", on="MD")
    with part(f, dy=bob) as b:
        plate(b, octagon(8, 13, 21, 21, 3), top=14, bottom=20)
        visor(b, 10, 16, 19, 17, i)
    if i == 3:
        f.stamp([" W ", "WpW", " W "], 24, 2, on=".")
    elif i in (4, 5):
        d = i - 3
        f.fill(box(25 + d, 4 - d, 26 + d, 5 - d), "r", on=".")
    return f.shadow(16, 11)


def ddos_rack(i):
    f = Layer()
    treads(f, i, 4, 27, 22)
    with part(f) as b:
        plate(b, rbox(4, 14, 14, 21, 2), top=15, bottom=21)
        visor(b, 6, 16, 12, 18, i)
        b.fill(seg(16, 20, 18, 14, 2.0), "D")
    with part(f, dy=-(1 if i % 2 == 0 and i < 6 else 0)) as b:
        launcher = poly([(9, 9), (25, 4), (27.5, 11), (11.5, 16)])
        b.fill(launcher, "M")
        b.fill(seg(10, 9.5, 25, 4.8, 1.2), "L", on="M")
        b.fill(seg(12, 15, 27, 10.4, 1.4), "D", on="M")
        b.fill(seg(11, 12.3, 26, 7.6, 1.0), "D", on="M")
        for k in range(3):
            b.fill(box(25, 5 + k * 2, 26, 5 + k * 2), "K" if (i // 2) % 4 != k else "W", on="MLD")
    k = (i // 2) % 4
    if k < 3:                                             # packets leaving one tube at a time
        d = i % 2
        x, y = 27 + d, 3 + k * 2 - d
        f.fill(box(x, y, x + 1, y + 1), "r" if d == 0 else "p", on=".")
    return f.shadow(16, 13)


def ddos_hydra(i):
    f = Layer()
    bob = step_bob(i)
    spider_legs(f, i, hip_y=20, bob=bob)
    firing = (i // 2) % 4
    with part(f, dy=bob) as b:
        for k, s in enumerate((-1, 0, 1)):
            rec = 1.5 if firing == k and i % 2 == 0 else 0
            x0, x1 = 16 + s * 4, 16 + s * 9
            y1 = (5 if s == 0 else 7) + rec
            b.fill(seg(x0, 14, x1, y1, 3.0), "D")
            b.fill(seg(x0 - 0.6, 14, x1 - 0.6, y1, 1.0), "M", on="D")
            b.fill(ell(x1, y1, 1.9, 1.9), "L")
            b.px(x1 - 0.5, y1 - 0.5, "K")
    with part(f, dy=bob) as b:
        plate(b, octagon(8, 13, 23, 22, 3), top=14, bottom=21)
        visor(b, 10, 16, 21, 18, i)
    if firing < 3 and i % 2 == 1:
        s = (-1, 0, 1)[firing]
        x, y = 16 + s * 11, (2 if s == 0 else 4)
        f.fill(box(x - 1, y, x, y + 1), "r", on=".")
        f.px(x - 1, y, "p", on="r")
    return f.shadow(16, 12)


def ddos_dish(i):
    f = Layer()
    outriggers(f, hip_y=17)
    with part(f) as b:
        b.fill(box(15, 14, 17, 20), "D")
        b.fill(seg(13, 12, 21, 5, 1.0), "D")
        b.fill(ell(21, 5, 1.3, 1.3), "r" if i % 2 else "W")
    with part(f) as b:
        dish = minus(ell(13, 12, 8.5, 8.5), ell(17.5, 7.5, 8.5, 8.5))
        b.fill(dish, "L")
        b.fill(minus(dish, moved(dish, 1.3, -1.3)), "M", on="L")
    with part(f) as b:
        plate(b, octagon(9, 18, 22, 24, 2), top=19, bottom=24)
        visor(b, 11, 20, 20, 22, i)
    r = 3.5 + (i % 4) * 2.2
    for k in range(-3, 4):                                # signal rings
        a = math.radians(-45 + k * 13)
        x, y = 21 + math.cos(a) * r, 5 + math.sin(a) * r
        if x < 30.9 and y >= 1.0:
            f.px(x, y, "p" if i % 4 < 2 else "q", on=".")
    return f.shadow(16, 12)


def ddos_swarm(i):
    f = Layer()
    t = i / FRAMES
    dy = hover_bob(i)
    minis = []
    for k in range(4):
        a = TAU * (t + k / 4)
        minis.append((math.sin(a) > 0, round(16 + 11 * math.cos(a)), round(18 + 5 * math.sin(a))))

    def draw(front):
        for is_front, x, y in minis:
            if is_front == front:
                with part(f) as b:
                    b.fill(box(x - 1, y, x + 1, y + 1), "r")
                    b.px(x, y, "W" if i % 2 else "p")

    draw(False)
    with part(f, dy=dy) as b:
        plate(b, octagon(7, 5, 24, 16, 4), top=6, bottom=15)
        visor(b, 10, 8, 21, 9, i)
        for x in (9, 14, 19):                             # launch bays
            b.fill(box(x, 12, x + 3, 14), "K")
            b.px(x + 1 + i % 2, 13, "r")
    wash(f, i, (9, 21), 18 + dy)
    draw(True)
    return f.shadow(16, 9)


def ddos_rail(i):
    f = Layer()
    wheels(f, i, (8, 19), y=25.5, r=3.0)
    rec = 1 if i == 6 else 0
    with part(f, dx=-rec) as b:
        b.fill(seg(6, 21, 22, 21, 2.0), "D")
        b.fill(seg(12, 21, 12, 16, 2.0), "D")
        b.fill(box(8, 9, 28, 10), "L")
        b.fill(box(8, 14, 28, 15), "L")
        b.fill(box(8, 15, 28, 15), "M")
        b.fill(box(8, 11, 28, 13), "K")
        charge = min(i, 5) * 4
        b.fill(box(9, 12, 9 + charge, 12), "r", on="K")
        b.fill(box(max(9, 7 + charge), 12, 9 + charge, 12), "W", on="r")
        for x in (14, 20, 26):
            b.fill(box(x, 9, x, 15), "D", on="LMK")
    with part(f, dx=-rec) as b:
        plate(b, octagon(3, 7, 11, 18, 2), top=8, bottom=17)
        visor(b, 4, 10, 9, 11, i)
    if i in (6, 7):
        f.stamp(["W", "p", "W"] if i == 6 else ["p", " ", "p"], 30, 11, on=".")
    return f.shadow(15, 12)


# --- Botnet ------------------------------------------------------------------

def mini_bot(f, cx, cy, i, lit, big=False):
    w = 5 if big else 4
    h = 6 if big else 5
    with part(f) as b:
        b.fill(box(cx, cy - 3, cx, cy - 1), "D")
        b.fill(box(cx - 1, cy - 4, cx + 1, cy - 3), "W" if lit else "r")
        plate(b, octagon(cx - w, cy, cx + w, cy + h, 2), top=cy, bottom=cy + h)
        b.fill(box(cx - w + 2, cy + 2, cx + w - 2, cy + 3), "K")
        b.fill(box(cx - 2, cy + 2, cx - 1, cy + 3), "W" if lit else "r", on="K")
        b.fill(box(cx + 1, cy + 2, cx + 2, cy + 3), "W" if lit else "r", on="K")


def botnet_trio(i):
    f = Layer()
    t = i / FRAMES
    talk = (i // 2) % 4
    spots = ((7, 8 + (wave(t, 0.1) > 0)), (24, 8 + (wave(t, 0.6) > 0)), (16, 17 + (wave(t, 0.35) > 0)))
    for a, c in ((0, 2), (1, 2), (0, 1)):                 # link beams
        (x0, y0), (x1, y1) = spots[a], spots[c]
        for n in range(1, 6):
            if (n + i) % 3 == 0:
                f.px(x0 + (x1 - x0) * n / 6, y0 + 3 + (y1 - y0) * n / 6, "p", on=".")
    mini_bot(f, *spots[0], i, talk == 0)
    mini_bot(f, *spots[1], i, talk == 2)
    mini_bot(f, *spots[2], i, talk == 1, big=True)
    wash(f, i, (15,), spots[2][1] + 8)
    return f.shadow(16, 10)


def botnet_antenna(i):
    f = Layer()
    bob = step_bob(i)
    biped_legs(f, i, hip_y=21, bob=bob, knee_y=24)
    with part(f, dy=bob) as b:
        b.fill(box(16, 3, 16, 14), "D")
        for y, w in ((4, 5), (7, 4), (10, 3)):
            b.fill(box(16 - w, y, 16 + w, y), "L")
        b.px(16, 3, "W" if i % 4 < 2 else "r")
    with part(f, dy=bob) as b:
        plate(b, octagon(9, 14, 22, 22, 3), top=15, bottom=21)
        visor(b, 11, 17, 20, 18, i)
    r = 4 + (i % 4) * 2
    for s in (-1, 1):                                     # broadcast rings
        for k in (-1, 0, 1):
            a = math.radians(k * 22)
            x = 16 + s * math.cos(a) * (r + 3)
            if 1 <= x <= 30:
                f.px(x, 7 + math.sin(a) * (r + 3), "p" if i % 4 < 2 else "q", on=".")
    return f.shadow(16, 10)


def botnet_terminal(i):
    f = Layer()
    bob = step_bob(i)
    spider_legs(f, i, hip_y=20, bob=bob)
    with part(f, dy=bob) as b:
        plate(b, octagon(6, 4, 25, 21, 3), top=5, bottom=20, right=24)
        b.fill(rbox(8, 7, 22, 17, 1.5), "K")
        for n in range(4):                                # signal bars filling up
            if n <= (i // 2) % 4:
                b.fill(box(10 + n * 3, 15 - n * 2, 11 + n * 3, 15), "r" if n < (i // 2) % 4 else "W", on="K")
        for y in (8, 12, 16):
            b.px(20 - (i + y) % 3, y, "q", on="K")
        b.fill(box(9, 19, 11, 19), "K", on="M")
    return f.shadow(16, 12)


def botnet_hive(i):
    f = Layer()
    dy = hover_bob(i)
    talk = (i // 2) % 4

    def hexagon(cx, cy, r=5.6):
        return poly([(cx + r * math.cos(TAU * k / 6), cy + r * math.sin(TAU * k / 6) * 0.95) for k in range(6)])

    with part(f, dy=dy, outline=False) as b:
        b.fill(seg(16, 9, 9, 20, 1.2), "D")
        b.fill(seg(16, 9, 23, 20, 1.2), "D")
        b.fill(seg(9, 20, 23, 20, 1.2), "D")
    for n, (cx, cy) in enumerate(((16, 8), (9, 20), (23, 20))):
        with part(f, dy=dy) as b:
            plate(b, hexagon(cx, cy), top=cy - 4, bottom=cy + 3)
            b.fill(ell(cx, cy, 2.6, 2.6), "K")
            b.fill(box(cx - 1, cy - 1, cx, cy), "W" if talk == n else "r")
    return f.shadow(16, 11)


def botnet_tower(i):
    f = Layer()
    t = i / FRAMES
    with part(f) as b:
        b.fill(seg(16, 4, 8, 28, 1.6), "D")
        b.fill(seg(16, 4, 24, 28, 1.6), "D")
        for y0, y1 in ((10, 16), (16, 22), (22, 28)):
            w0, w1 = (y0 - 4) / 3.0, (y1 - 4) / 3.0
            b.fill(seg(16 - w0, y0, 16 + w1, y1, 1.0), "L")
            b.fill(seg(16 + w0, y0, 16 - w1, y1, 1.0), "L")
            b.fill(box(round(16 - w1), y1, round(16 + w1), y1), "M")
        b.fill(box(6, 27, 26, 28), "D")
    for n, (x, y) in enumerate(((16, 3), (13, 13), (20, 19))):
        with part(f) as b:
            b.fill(box(x - 1, y - 1, x + 1, y + 1), "W" if (i // 2) % 3 == n else "r")
    for k in range(3):                                    # packets hopping between masts
        a = TAU * (t + k / 3)
        x, y = round(16 + 12 * math.cos(a)), round(9 + 3 * math.sin(a))
        f.fill(box(x - 1, y, x, y + 1), "p" if k else "r", on=".")
    return f.shadow(16, 12)


def botnet_twins(i):
    f = Layer()
    t = i / FRAMES
    sag = 20 + wave(t)
    with part(f, outline=False) as b:
        cable = curve((8, 13), (16, sag + 6), (24, 13), 1.0)
        b.fill(cable, "K")
        u = t                                             # pulse running along the tether
        px = (1 - u) ** 2 * 8 + 2 * u * (1 - u) * 16 + u * u * 24
        py = (1 - u) ** 2 * 13 + 2 * u * (1 - u) * (sag + 6) + u * u * 13
        b.fill(ell(px, py, 1.3, 1.3), "W")
    for n, cx in enumerate((8, 24)):
        bob = (i // 2 + n) % 2
        with part(f) as b:
            for s in (-1, 1):
                lift = 1 if (i // 2 + n + (s > 0)) % 2 == 0 else 0
                b.fill(box(cx + s * 3 - (s > 0), 21, cx + s * 3 - (s > 0), 27 - lift), "D")
                b.fill(box(cx + s * 3 - 1, 28 - lift, cx + s * 3, 28 - lift), "D")
        with part(f, dy=bob) as b:
            antenna(b, cx, 7, 10, i + n * 2)
            plate(b, octagon(cx - 5, 11, cx + 5, 21, 2), top=12, bottom=20)
            b.fill(box(cx - 3, 14, cx + 3, 16), "K")
            lit = (t < 0.5) == (n == 0)
            b.fill(box(cx - 2, 15, cx - 1, 15), "W" if lit else "r")
            b.fill(box(cx + 1, 15, cx + 2, 15), "W" if lit else "r")
    return f.shadow(16, 13)


# --- Backdoor ----------------------------------------------------------------

def backdoor_walker(i):
    f = Layer()
    bob = step_bob(i)
    biped_legs(f, i, hip_y=20, bob=bob, knee_y=23)
    opening = (0, 0, 1, 3, 5, 5, 3, 1)[i]
    with part(f, dy=bob) as b:
        plate(b, rbox(7, 3, 24, 21, 2), top=4, right=23)
        b.fill(box(10, 6, 21, 21), "K")
        for y in range(7, 21, 2):
            b.fill(box(11, y, 20, y), "r" if (y + i) % 4 < 2 else "q", on="K")
        edge = 21 - opening
        b.fill(box(10, 6, edge, 21), "L")
        b.fill(box(10, 6, 10, 21), "W", on="L")
        if edge - 12 >= 3:
            b.fill(box(12, 8, edge - 2, 12), "M", on="L")
            b.fill(box(12, 15, edge - 2, 19), "M", on="L")
        hazard(b, edge - 1, 6, edge, 21, on="LM")
        b.fill(box(13, 4, 18, 4), "K")
        scanner(b, 13, 18, 4, i)
    return f.shadow(16, 11)


def backdoor_portal(i):
    f = Layer()
    t = i / FRAMES
    with part(f) as b:
        b.fill(box(6, 25, 12, 28), "D")
        b.fill(box(19, 25, 25, 28), "D")
    with part(f) as b:
        ring = ell(16, 14.5, 11.5, 12.5)
        plate(b, ring, top=5, bottom=23)
        b.fill(ell(16, 14.5, 8.2, 9.2), "K")

        def swirl(x, y):
            dx, dy = x - 16, y - 14.5
            return ((math.atan2(dy, dx) + math.hypot(dx, dy) * 0.45 - t * TAU) / (TAU / 3)) % 1.0
        for y in range(5, 25):
            for x in range(7, 26):
                if ell(16, 14.5, 7.3, 8.3)(x + 0.5, y + 0.5):
                    s = swirl(x + 0.5, y + 0.5)
                    b.px(x, y, "p" if s < 0.25 else "q" if s < 0.55 else "r")
        b.fill(box(15, 14, 16, 15), "W")
        for k in range(4):
            a = TAU * k / 4 + 0.4
            b.px(16 + math.cos(a) * 10 - 0.5, 14.5 + math.sin(a) * 11 - 0.5, "K", on="MLD")
    return f.shadow(16, 12)


def backdoor_hatch(i):
    f = Layer()
    opened = (0, 0, 1, 2, 3, 3, 2, 1)[i]
    with part(f) as b:
        plate(b, ell(16, 23, 12.5, 5.2), top=20, bottom=26)
        b.fill(ell(16, 22.5, 9.5, 3.4), "K")
        b.fill(ell(16, 22.8, 6.5, 2.0), "r" if opened else "K")
        b.fill(ell(16, 23, 3.4, 1.0), "p" if opened > 1 else "r" if opened else "K")
    if opened:
        with part(f) as b:
            for x in (8, 24):
                b.fill(seg(x, 21, x, 22 - opened * 3.2, 1.2), "D")
        for k in range(opened):                           # light spilling up
            f.px(13 + (k * 3 + i) % 7, 20 - k * 3 - i % 2, "p", on=".")
    with part(f) as b:
        cy = 22.2 - opened * 3.4
        lid = ell(16, cy, 10.2, 3.6)
        b.fill(lid, "L")
        b.fill(minus(lid, moved(lid, 0, -1.3)), "M", on="L")
        b.fill(ell(16, cy - 0.4, 6.5, 1.6), "M", on="L")
        b.fill(ell(16, cy - 0.6, 4.5, 0.9), "L", on="M")
    return f.shadow(16, 13)


def backdoor_blast(i):
    f = Layer()
    gap = (0, 0, 1, 3, 5, 5, 3, 1)[i]
    with part(f) as b:
        plate(b, octagon(4, 4, 27, 28, 3), top=5, right=26)
        b.fill(box(7, 8, 24, 27), "K")
        for y in range(9, 27, 2):
            b.fill(box(8, y, 23, y), "r" if (y + i) % 4 < 2 else "q", on="K")
        b.fill(box(7, 8, 15 - gap, 27), "L")
        b.fill(box(16 + gap, 8, 24, 27), "L")
        b.fill(box(7, 26, 15 - gap, 27), "M", on="L")
        b.fill(box(16 + gap, 26, 24, 27), "M", on="L")
        if 15 - gap >= 9:
            hazard(b, 14 - gap, 8, 15 - gap, 27, on="LM")
            hazard(b, 16 + gap, 8, 17 + gap, 27, on="LM")
        if gap:
            b.fill(box(16 - gap, 8, 15 + gap, 8), "W", on="Krq")
        b.fill(box(12, 5, 19, 6), "K")
        scanner(b, 12, 19, 5, i)
    return f.shadow(16, 13)


def backdoor_monolith(i):
    f = Layer()
    dy = hover_bob(i)
    pulse = (0, 1, 2, 3, 3, 2, 1, 0)[i]
    with part(f, dy=dy) as b:
        slab = poly([(10, 3), (22, 3), (25, 26), (7, 26)])
        plate(b, slab, top=4, right=22)
        b.fill(all_of(slab, box(0, 25, 31, 31)), "D")
        hole = any_of(ell(16, 11, 3.0, 3.0), poly([(15, 12), (17, 12), (18.6, 21), (13.4, 21)]))
        b.fill(any_of(moved(hole, -1, 0), moved(hole, 1, 0), moved(hole, 0, -1), moved(hole, 0, 1)), "K")
        b.fill(hole, ("K", "r", "q", "p")[pulse])
        if pulse == 3:
            b.fill(box(15, 10, 16, 11), "W")
        for y in (6, 23):
            b.fill(box(11, y, 13, y), "D", on="M")
    wash(f, i, (11, 19), 28 + dy if dy < 1 else 28)
    return f.shadow(16, 9)


def backdoor_pod(i):
    f = Layer()
    ramp = (0, 0, 1, 2, 3, 3, 2, 1)[i]
    with part(f) as b:
        for s in (-1, 1):
            b.fill(seg(16 + s * 6, 18, 16 + s * 11, 27.5, 1.8), "D")
            b.fill(box(16 + s * 11 - 1, 28, 16 + s * 11, 28), "D")
    with part(f) as b:
        antenna(b, 16, 2, 4, i)
        plate(b, rbox(8, 4, 23, 23, 6), top=7, bottom=22, right=22)
        b.fill(box(10, 9, 21, 11), "K")
        scanner(b, 10, 21, 10, i)
        b.fill(box(11, 14, 20, 22), "K")
        if ramp:
            for y in range(15, 22, 2):
                b.fill(box(12, y, 19, y), "r" if (y + i) % 4 < 2 else "q", on="K")
        else:
            b.fill(box(11, 14, 20, 22), "L")
            b.fill(box(12, 15, 19, 21), "M", on="L")
    if ramp:
        with part(f) as b:
            b.fill(poly([(11, 22), (21, 22), (21 + ramp, 22 + ramp * 2.2), (11 - ramp, 22 + ramp * 2.2)]), "L")
            hazard(b, 8, 22, 23, 23, on="L")
    return f.shadow(16, 12)


# --- Injector ----------------------------------------------------------------

def injector_gun(i):
    f = Layer()
    bob = step_bob(i)
    biped_legs(f, i, hip_y=20, bob=bob, knee_y=23)
    push = (0, 1, 2, 3, 3, 2, 1, 0)[i]
    with part(f, dy=bob) as b:
        b.fill(box(3 + push, 7, 4 + push, 12), "M")       # thumb plate and rod
        b.fill(box(5 + push, 9, 9 + push, 10), "D")
        b.fill(box(23, 9, 28, 9), "L")                    # needle
    with part(f, dy=bob) as b:
        b.fill(rbox(8, 6, 21, 13, 1.5), "L")
        b.fill(box(11 + push, 7, 20, 12), "q")
        b.fill(box(11 + push, 7, 20, 8), "p", on="q")
        b.fill(box(9 + push, 7, 10 + push, 12), "K")
        b.fill(box(21, 8, 22, 11), "M")
        for x in (13, 16, 19):
            b.px(x, 12, "K")
    with part(f, dy=bob) as b:
        plate(b, octagon(9, 13, 22, 21, 3), top=14, bottom=20)
        visor(b, 11, 16, 20, 17, i)
    if i >= 2:
        f.fill(box(28, 10 + (i - 2) * 3, 28, 11 + (i - 2) * 3), "r", on=".")
    return f.shadow(16, 11)


def injector_vial(i):
    f = Layer()
    t = i / FRAMES
    dy = hover_bob(i)
    with part(f, dy=dy) as b:
        b.fill(box(16, 21, 16, 25), "L")
    with part(f, dy=dy) as b:
        plate(b, octagon(8, 4, 23, 9, 2), top=5, bottom=9)
        visor(b, 10, 6, 21, 7, i)
        b.fill(rbox(10, 10, 21, 20, 2.5), "L")
        level = 13 + round(wave(t))
        b.fill(all_of(rbox(11, 11, 20, 19, 2), box(0, level, 31, 31)), "q")
        b.fill(box(11, level, 20, level), "p", on="q")
        b.fill(box(19, level + 1, 20, 19), "r", on="q")
        for k in range(3):
            y = 19 - (i + k * 3) % 6
            b.px(13 + k * 2, y, "W", on="q")
        b.fill(box(14, 21, 18, 21), "M")
    wash(f, i, (8, 22), 11 + dy)
    drop = (i * 2) % 8
    if drop < 4:
        f.fill(box(16, 26 + dy + drop // 2, 16, 27 + dy + drop // 2), "r", on=".")
    return f.shadow(16, 8)


def injector_mosquito(i):
    f = Layer()
    dy = (0, -1)[i % 2]
    with part(f, dy=dy) as b:
        for x0, x1 in ((13, 9), (15, 16), (17, 23)):
            b.fill(seg(x0, 15, x1, 21, 1.0), "D")
            b.fill(seg(x1, 21, x1 + 1, 27.5, 1.0), "D")
    with part(f, dy=dy) as b:
        ry = (4.6, 1.2)[i % 2]
        b.fill(ell(11, 10 - ry * 0.4, 5.5, ry), "L")
        b.fill(ell(17, 9 - ry * 0.4, 4.5, ry), "L")
        for x in (8, 11, 14):
            b.px(x, round(10 - ry * 0.4), "W", on="L")
    with part(f, dy=dy) as b:
        b.fill(ell(8, 16, 5.5, 3.2), "q")                 # tank abdomen
        b.fill(all_of(ell(8, 16, 5.5, 3.2), box(0, 17, 31, 31)), "r")
        for x in (5, 8, 11):
            b.fill(box(x, 12, x, 20), "K", on="qr")
        b.fill(seg(22, 13, 28, 21, 1.0), "L")
        b.px(28, 21, "r")
    with part(f, dy=dy) as b:
        plate(b, ell(15.5, 13.5, 4.6, 3.8), top=11, bottom=16)
        plate(b, ell(21, 11.5, 2.8, 2.8), top=9, bottom=13)
        b.fill(box(21, 11, 22, 12), "r" if i % 4 < 2 else "W")
    return f.shadow(15, 11)


def injector_scorpion(i):
    f = Layer()
    t = i / FRAMES
    bob = step_bob(i)
    spider_legs(f, i, hip_y=21, bob=bob)
    dip = round(1.5 * wave(t))
    with part(f, dy=bob) as b:
        pts = [(8, 17), (5, 14), (5, 9.5), (9, 6.5), (14, 6 + dip * 0.5), (18, 8 + dip)]
        for k, (x, y) in enumerate(pts):
            b.fill(ell(x, y, 2.3, 2.3), "M" if k % 2 == 0 else "L")
    with part(f, dy=bob) as b:
        sx, sy = 19, 9 + dip
        b.fill(poly([(sx - 1, sy - 2), (sx + 3, sy + 1), (sx + 1, sy + 5), (sx - 1, sy + 2)]), "r")
        b.px(sx, sy, "p")
    with part(f, dy=bob) as b:
        for s in (-1, 1):
            b.fill(seg(22, 18 + s, 27, 16 + s * 2, 1.6), "L")
    with part(f, dy=bob) as b:
        plate(b, octagon(7, 16, 23, 23, 3), top=17, bottom=22)
        visor(b, 12, 18, 21, 20, i)
    drop = (i - 2) % FRAMES
    if drop < 3:
        f.fill(box(20, 15 + dip + drop * 2, 20, 16 + dip + drop * 2), "r", on=".")
    return f.shadow(16, 12)


def injector_sprayer(i):
    f = Layer()
    treads(f, i, 4, 23, 23)
    with part(f, dy=-(i % 2)) as b:
        b.fill(seg(17, 13, 23, 9, 1.8), "D")
        b.fill(box(23, 7, 25, 10), "L")
    with part(f, dy=-(i % 2)) as b:
        plate(b, rbox(5, 8, 17, 22, 3), top=9, bottom=21)
        b.fill(box(10, 5, 12, 7), "D")
        b.fill(rbox(7, 11, 11, 19, 1), "K")
        level = 13 + i % 3
        b.fill(box(8, level, 10, 18), "q")
        b.px(8, level, "p")
        visor(b, 12, 12, 16, 13, i)
    for k in range(9):                                    # drifting mist
        n = (k * 5 + i * 3) % 11
        x, y = 26 + (k * 2 + i) % 4, 2 + (k * 3 + i * 2) % 13
        if n < 6 and x <= 30:
            f.px(x, y, "p" if n < 2 else "q" if n < 4 else "r", on=".")
    return f.shadow(15, 12)


def injector_tripod(i):
    f = Layer()
    outriggers(f, hip_y=20, reach=11.5)
    push = (0, 1, 2, 3, 3, 2, 1, 0)[i]
    stopper = 13 - push
    with part(f) as b:
        b.fill(box(16, 2, 16, 6), "L")
    with part(f) as b:
        b.fill(box(15, 6, 17, 7), "M")
        b.fill(rbox(11, 8, 21, 19, 2), "L")
        b.fill(box(12, 9, 20, stopper), "q")
        b.fill(box(12, 9, 13, stopper), "p", on="q")
        b.fill(box(20, 9, 20, stopper), "r", on="q")
        b.fill(box(12, stopper + 1, 20, stopper + 2), "K")
        b.fill(box(15, stopper + 3, 17, 19), "D")
        for y in (10, 13, 16):
            b.fill(box(19, y, 20, y), "K")
    with part(f) as b:
        plate(b, octagon(8, 19, 24, 24, 2), top=20, bottom=24)
        visor(b, 11, 21, 21, 22, i)
    if 2 <= i <= 6:
        d = (i - 2) / 4
        x, y = 18 + round(7 * d), 3 + round(-3 * d + 9 * d * d)
        f.fill(box(x, y, x + 1, y + 1), "r", on=".")
        f.px(x, y, "p", on="r")
    return f.shadow(16, 12)


# --- Man in the middle -------------------------------------------------------

def mitm_agent(i):
    f = Layer()
    look = (0, -1, -1, -1, 0, 1, 1, 1)[i]
    sway = (0, 0, 1, 0, 0, 0, -1, 0)[i]
    with part(f) as b:
        b.fill(box(10, 27, 13, 28), "D")
        b.fill(box(18, 27, 21, 28), "D")
    with part(f) as b:
        coat = poly([(10, 15), (22, 15), (25 + sway * 0.6, 27), (7 + sway * 0.6, 27)])
        b.shade(coat, "M", dark="D", depth=2.0)
        b.fill(poly([(10, 15), (16, 15), (16, 16), (13, 21), (10, 18)]), "L", on="MD")
        b.fill(poly([(22, 15), (16, 15), (16, 16), (19, 21), (22, 18)]), "L", on="MD")
        b.fill(box(16, 16, 16, 26), "D", on="MLD")
        b.fill(box(7, 22, 25, 22), "D", on="ML")
    with part(f, dx=look) as b:
        b.fill(rbox(11, 9, 20, 15, 2), "K")               # nothing under the brim but a visor
        b.fill(box(12, 11, 19, 11), "r")
        b.px(12 + (0, 1, 3, 5, 7, 5, 3, 1)[i], 11, "W")
    with part(f, dx=look) as b:
        b.shade(rbox(10, 2, 21, 7, 2.5), "D", dark="K", depth=1.2)
        b.fill(box(10, 6, 21, 7), "M")
        b.fill(box(6, 8, 25, 9), "D")
        b.fill(box(7, 8, 14, 8), "M", on="D")
    return f.shadow(16, 10)


def mitm_tap(i):
    f = Layer()
    dy = hover_bob(i)
    with part(f) as b:
        b.fill(box(2, 23, 29, 23), "L")                   # the line being tapped
    for k in range(4):
        x = (3 + k * 7 + i * 7 // 8 * 1 + i) % 27 + 2
        f.fill(box(x, 22, x + 1, 24), "p" if x < 15 else "r")
    with part(f, dy=dy) as b:
        for x in (11, 20):
            b.fill(seg(x, 16, x, 22 - dy, 1.4), "D")
    with part(f) as b:
        for x in (11, 20):
            b.fill(box(x - 1, 21, x + 1, 25), "M")
            b.px(x, 23, "W" if i % 2 else "r")
    with part(f, dy=dy) as b:
        antenna(b, 21, 3, 5, i)
        plate(b, octagon(8, 6, 23, 16, 3), top=7, bottom=15)
        visor(b, 10, 9, 21, 11, i)
    wash(f, i, (9, 21), 18 + dy)
    return f.shadow(16, 9)


def mitm_relay(i):
    f = Layer()
    bob = step_bob(i)
    biped_legs(f, i, hip_y=20, bob=bob, knee_y=23)
    for s in (-1, 1):
        with part(f, dy=bob) as b:
            cx = 16 + s * 9
            dish = minus(ell(cx, 11, 5.5, 6.5), ell(cx + s * 3.5, 11, 5.5, 6.5))
            b.fill(dish, "L")
            b.fill(all_of(dish, box(0, 13, 31, 31)), "M")
            b.fill(seg(cx - s * 2, 11, cx + s * 2.5, 11, 1.0), "D")
    with part(f, dy=bob) as b:
        plate(b, octagon(10, 6, 21, 21, 3), top=7, bottom=20)
        visor(b, 12, 9, 19, 10, i)
        b.fill(box(12, 13, 19, 17), "K")
        b.fill(box(13 + i % 6, 14, 13 + i % 6, 16), "p" if i < 4 else "r")
    step = i % 4
    f.px(1 + step, 6 + step, "p", on=".")                   # in one side
    f.px(27 + step - 1, 9 - step, "r", on=".")              # altered out the other
    return f.shadow(16, 11)


def mitm_periscope(i):
    f = Layer()
    treads(f, i, 4, 27, 23)
    look = (-2, -2, -1, 0, 2, 2, 1, 0)[i]
    with part(f) as b:
        plate(b, octagon(5, 17, 26, 23, 2), top=18, bottom=23)
        for x in (8, 11, 20, 23):
            b.px(x, 20, "K", on="M")
    with part(f) as b:
        b.fill(box(15, 8, 17, 18), "D")
        b.fill(box(15, 8, 15, 18), "M")
        for y in (11, 14):
            b.fill(box(14, y, 18, y), "L")
    with part(f, dx=look) as b:
        plate(b, octagon(11, 2, 21, 8, 2), top=3, bottom=8)
        b.fill(box(13, 4, 19, 6), "K")
        lx = 15 + look
        b.fill(box(lx, 4, lx + 2, 6), "r", on="K")
        b.px(lx + 1, 5, "W")
    return f.shadow(16, 13)


def mitm_splitter(i):
    f = Layer()
    bob = step_bob(i)
    biped_legs(f, i, hip_y=20, bob=bob, knee_y=23)
    with part(f, dy=bob) as b:
        b.fill(box(15, 3, 17, 9), "L")
        b.fill(box(13, 2, 19, 3), "M")
        b.fill(seg(11, 13, 5, 10, 3.0), "L")
        b.fill(seg(21, 13, 27, 10, 3.0), "L")
        b.fill(ell(4.5, 9.5, 2.0, 2.0), "M")
        b.fill(ell(27.5, 9.5, 2.0, 2.0), "M")
    with part(f, dy=bob) as b:
        plate(b, octagon(9, 9, 22, 21, 3), top=10, bottom=20)
        visor(b, 11, 12, 20, 13, i)
        b.fill(box(15, 15, 16, 18), "K")
        b.fill(seg(15.5, 16, 12, 18.5, 1.0), "K")
        b.fill(seg(16.5, 16, 20, 18.5, 1.0), "K")
    step = i % 4
    f.px(16, 1 if step == 0 else 5 + bob, "p", on="L.")     # packet drops in the top
    if step >= 1:
        side = -1 if i < 4 else 1                           # and leaves by alternate sides
        f.fill(box(16 + side * (11 + step) - (side > 0), 8 - step, 16 + side * (11 + step) - (side > 0), 8 - step), "r", on=".")
    return f.shadow(16, 11)


def mitm_mask(i):
    f = Layer()
    t = i / FRAMES
    dy = hover_bob(i)
    sway = 2 * wave(t)
    with part(f, dy=dy) as b:
        for s in (-1, 1):
            tip = (16 + s * 9 + sway, 27)
            b.fill(curve((16 + s * 5, 15), (16 + s * 12 - sway, 21), tip, 1.4), "D")
            b.fill(box(round(tip[0]) - 1, 26, round(tip[0]), 27), "L")
    with part(f, dy=dy) as b:
        plate(b, poly([(8, 5), (24, 5), (26, 12), (16, 24), (6, 12)]), top=6, right=23)
        b.fill(poly([(9, 10), (14.5, 12), (14.5, 14), (9, 12.4)]), "K")
        b.fill(poly([(23, 10), (17.5, 12), (17.5, 14), (23, 12.4)]), "K")
        lit = (0, 1, 2, 3, 3, 2, 1, 0)[i]
        b.px(10 + lit, 11 + (lit > 1), "r", on="K")
        b.px(21 - lit, 11 + (lit > 1), "r", on="K")
        b.fill(box(15, 17, 16, 19), "D", on="M")
        b.fill(box(11, 7, 20, 7), "D", on="M")
    return f.shadow(16, 9)


# --- Optimiser ---------------------------------------------------------------

def plus(layer, x, y, colour="W", on=None):
    layer.fill(box(x - 1, y, x + 1, y), colour, on)
    layer.fill(box(x, y - 1, x, y + 1), colour, on)


def optimiser_welder(i):
    f = Layer()
    bob = step_bob(i)
    biped_legs(f, i, bob=bob)
    reach = (0, 1, 1, 0, 0, 1, 1, 0)[i]
    with part(f, dy=bob) as b:
        b.fill(seg(24, 10, 27.5, 15 + reach, 2.0), "D")     # torch arm
        b.fill(box(27, 16 + reach, 28, 18 + reach), "L")
        b.fill(seg(8, 10, 4.5, 14, 2.0), "D")               # wrench arm
        turn = (i // 2) % 2
        b.fill(box(3, 15, 5, 20), "L")
        b.fill(box(2 if turn else 3, 20, 5 if turn else 6, 21), "L")
        b.px(4, 21, ".")
    with part(f, dy=bob) as b:
        antenna(b, 21, 2, 5, i)
        plate(b, octagon(7, 5, 24, 17, 3), top=6, bottom=16, right=23)
        visor(b, 9, 8, 22, 10, i)
        b.fill(box(13, 11, 18, 16), "K")
        plus(b, 15, 13, "W" if i % 4 < 2 else "p")
        plus(b, 16, 14, "W" if i % 4 < 2 else "p")
    if i % 2 == 0:
        f.stamp(["W W", " p ", "W W"], 26, 20 + reach + bob, on=".")
    else:
        f.stamp([" p ", "pWp", " p "], 26, 20 + reach + bob, on=".")
    return f.shadow(16, 11)


def optimiser_medic(i):
    f = Layer()
    dy = hover_bob(i)
    with part(f, dy=dy) as b:
        b.fill(box(16, 3, 16, 6), "D")
        blade = (10, 6, 2, 6)[i % 4]
        b.fill(box(16 - blade, 3, 16 + blade, 3), "L")
        plate(b, octagon(7, 7, 24, 19, 4), top=8, bottom=18)
        b.fill(rbox(11, 9, 20, 18, 1.5), "K")
        cross = "W" if i % 4 < 2 else "p"
        b.fill(box(15, 10, 16, 17), cross)
        b.fill(box(12, 13, 19, 14), cross)
        b.fill(box(8, 12, 9, 13), "r")
        b.fill(box(22, 12, 23, 13), "r")
    for k in range(3):                                    # repair beam
        y = 21 + dy + (k * 3 + i) % 8
        if y <= 28:
            f.fill(box(15, y, 16, y), "p" if (k + i) % 2 else "W", on=".")
    return f.shadow(16, 8)


def optimiser_gear(i):
    f = Layer()
    t = i / FRAMES
    bob = step_bob(i)
    biped_legs(f, i, hip_y=21, bob=bob, knee_y=24)
    with part(f, dy=bob) as b:
        shape = cog(16, 13, 8.2, 10.6, 8, t * TAU / 8)
        b.fill(shape, "M")
        b.fill(minus(shape, ell(14.6, 11, 10.2, 10.2)), "D", on="M")
        b.fill(all_of(shape, box(0, 0, 31, 5)), "L", on="M")
    with part(f, dy=bob) as b:
        b.fill(ell(16, 13, 5.2, 5.2), "K")
        b.fill(box(12, 12, 19, 14), "D")
        b.fill(box(12, 13, 19, 13), "K")
        scanner(b, 12, 19, 13, i)
    return f.shadow(16, 11)


def optimiser_crane(i):
    f = Layer()
    treads(f, i, 4, 24, 22)
    lift = (0, 1, 2, 3, 3, 2, 1, 0)[i]
    elbow = (19, 5 + lift * 0.5)
    hand = (26, 12 + lift)
    with part(f) as b:
        b.fill(seg(11, 14, *elbow, 2.6), "M")
        b.fill(seg(*elbow, *hand, 2.0), "D")
        b.fill(box(25, round(hand[1]) + 1, 27, round(hand[1]) + 2), "L")
    with part(f, outline=False) as b:
        b.fill(ell(*elbow, 1.3, 1.3), "L")
        b.fill(ell(11, 14, 1.3, 1.3), "L")
    with part(f) as b:
        plate(b, octagon(4, 13, 17, 21, 2), top=14, bottom=21)
        visor(b, 6, 15, 14, 17, i)
        plus(b, 15, 19, "W", on="MD")
    if lift >= 2:
        f.stamp(["W W", " p ", "W W"] if i % 2 else [" p ", "pWp", " p "], 25, round(hand[1]) + 4, on=".")
    return f.shadow(15, 12)


def optimiser_nanites(i):
    f = Layer()
    outriggers(f, hip_y=18, reach=11.5)
    with part(f) as b:
        plate(b, rbox(9, 9, 22, 25, 2), top=10, bottom=24, right=21)
        b.fill(box(11, 6, 20, 9), "D")
        b.fill(box(12, 6, 19, 6), "K")
        b.fill(rbox(11, 12, 19, 21, 1.5), "K")
        for k in range(6):                                # nanites swarming inside
            a = TAU * (i / FRAMES + k / 6)
            b.px(15 + math.cos(a) * 2.6, 16.5 + math.sin(a * 2) * 3, "p" if k % 2 else "r", on="K")
        visor(b, 11, 23, 19, 23, i)
    for k in range(3):                                    # repair motes rising
        age = (i + k * 3) % FRAMES
        x, y = 12 + k * 4 - (age % 2), 4 - age // 2
        if y >= 2 and age < 6:
            plus(f, x, y, "W" if age < 2 else "p", on=".")
    return f.shadow(16, 12)


def optimiser_defrag(i):
    f = Layer()
    bob = step_bob(i)
    biped_legs(f, i, hip_y=20, bob=bob, knee_y=23)
    with part(f, dy=bob) as b:
        plate(b, octagon(5, 3, 26, 21, 3), top=4, bottom=20, right=25)
        b.fill(box(7, 6, 24, 17), "K")
        cells = [(c, r) for r in range(4) for c in range(6)]
        done = i * 3                                       # blocks tidied so far this pass
        for n, (c, r) in enumerate(cells):
            x, y = 8 + c * 3 - (0 if c < 5 else 0), 7 + r * 3
            if n < done:
                colour = "p"
            elif n == done:
                colour = "W"
            else:
                colour = "r" if (n * 7 + 3) % 5 < 2 else None
            if colour:
                b.fill(box(x, y, x + 1, y + 1), colour, on="K")
        b.fill(box(7, 19, 9, 19), "K", on="MD")
        b.px(23, 19, "W" if i % 2 else "r")
    return f.shadow(16, 11)


# --- Overclocker -------------------------------------------------------------

def overclocker_turbine(i):
    f = Layer()
    bob = step_bob(i)
    biped_legs(f, i, hip_y=19, bob=bob, knee_y=22.5)
    jitter = (0, 1, 0, -1)[i % 4]
    with part(f, dx=jitter, dy=bob) as b:
        plate(b, octagon(6, 3, 25, 20, 5), top=4, bottom=19, right=24)
        b.fill(ell(16, 11.5, 7.2, 7.2), "K")
        for k in range(3):
            a = TAU * (k / 3 + i / FRAMES)
            for d in (-0.35, 0.0, 0.35):
                b.fill(seg(16, 11.5, 16 + math.cos(a + d) * 6.2, 11.5 + math.sin(a + d) * 6.2, 1.3), "L", on="KL")
        b.fill(ell(16, 11.5, 1.8, 1.8), "r")
        b.px(15, 11, "W")
    for y in (7, 12, 17):                                 # air rushing through
        x = 1 + (i * 2 + y) % 4
        f.px(x, y, "L", on=".")
        f.px(30 - x, y + 1, "L", on=".")
    return f.shadow(16, 11)


def overclocker_dial(i):
    f = Layer()
    t = i / FRAMES
    bob = step_bob(i)
    biped_legs(f, i, hip_y=20, bob=bob, knee_y=23)
    with part(f, dy=bob) as b:
        b.fill(box(14, 2, 17, 3), "M")
        b.fill(box(15, 4, 16, 5), "D")
        plate(b, ell(16, 13, 8.6, 8.6), top=7, bottom=19)
        b.fill(ell(16, 13, 6.6, 6.6), "K")
        b.fill(ell(16, 13, 5.8, 5.8), "L")
        for k in range(12):
            a = TAU * k / 12
            b.px(16 + math.cos(a) * 4.8 - 0.5, 13 + math.sin(a) * 4.8 - 0.5, "K" if k % 3 == 0 else "D", on="L")
        a = TAU * t
        b.fill(seg(16, 13, 16 + math.sin(a) * 4.6, 13 - math.cos(a) * 4.6, 1.4), "r", on="LDK")
        b.fill(box(15, 12, 16, 13), "K")
    return f.shadow(16, 11)


def overclocker_jet(i):
    f = Layer()
    dy = hover_bob(i)
    with part(f, dy=dy) as b:
        plate(b, poly([(9, 10), (20, 8), (29.5, 14.5), (20, 20), (9, 19)]), top=10, bottom=17)
        b.fill(poly([(12, 8), (17, 8), (14, 3), (11, 3)]), "M")
        b.fill(box(11, 3, 14, 3), "L")
        b.fill(box(17, 12, 25, 14), "K")
        scanner(b, 17, 25, 13, i)
        b.fill(box(7, 11, 9, 18), "D")
    for y in range(12, 18):                               # afterburner
        ln = 2 + (i * 3 + y * 2) % 4
        for d in range(ln):
            f.px(6 - d, y + dy, "W" if d == 0 else "p" if d < 2 else "r", on=".")
    for y, x in ((6, 3), (22, 5)):
        f.fill(box(x + i % 3, y + dy, x + 2 + i % 3, y + dy), "L", on=".")
    return f.shadow(17, 10)


def overclocker_tesla(i):
    f = Layer()
    wheels(f, i, (9, 23), y=25.5, r=3.0)
    with part(f) as b:
        plate(b, octagon(5, 17, 26, 23, 2), top=18, bottom=23)
        visor(b, 9, 19, 22, 21, i)
        b.fill(box(13, 9, 18, 17), "D")
        for y in range(9, 18):
            if (y + i) % 2 == 0:
                b.fill(box(13, y, 18, y), "L")
    with part(f) as b:
        b.fill(ell(16, 6.5, 6.5, 2.8), "L")
        b.fill(all_of(ell(16, 6.5, 6.5, 2.8), box(0, 8, 31, 31)), "M")
    arcs = (
        ((22, 6), (25, 4), (26, 8), (29, 7)),
        ((10, 6), (7, 9), (5, 7), (2, 11)),
        ((21, 8), (24, 11), (26, 10), (28, 14)),
        ((11, 5), (8, 3), (5, 4), (3, 2)),
    )
    for n in (i % 4, (i + 2) % 4) if i % 2 == 0 else (i % 4,):
        pts = arcs[n]
        for a, c in zip(pts, pts[1:]):
            f.fill(seg(a[0] + 0.5, a[1] + 0.5, c[0] + 0.5, c[1] + 0.5, 0.9), "p", on=".")
        f.px(pts[-1][0], pts[-1][1], "W")
    return f.shadow(16, 12)


def overclocker_engine(i):
    f = Layer()
    t = i / FRAMES
    treads(f, i, 5, 26, 23)
    jitter = i % 2
    with part(f, dy=-jitter) as b:
        for k, order in enumerate((0, 2, 3, 1)):          # firing order
            off = round(2.2 * wave(t, order / 4))
            x = 7 + k * 5
            b.fill(box(x + 1, 9 + off, x + 2, 13), "D")
            b.fill(box(x, 6 + off, x + 3, 8 + off), "L")
            if off > 1:
                b.fill(box(x + 1, 6 + off, x + 2, 6 + off), "W")
    with part(f, dy=-jitter) as b:
        plate(b, rbox(5, 13, 26, 22, 2), top=14, bottom=21)
        visor(b, 8, 16, 23, 18, i)
        b.fill(box(2, 15, 4, 16), "D")
    for k in range(2):
        age = (t + k / 2) % 1.0
        f.px(2 - round(age), 13 - round(age * 5), "L" if age < 0.5 else "p", on=".")
    return f.shadow(16, 13)


def overclocker_wheel(i):
    f = Layer()
    t = i / FRAMES
    cx, cy = 17.0, 19.0
    spin = t * TAU / 2
    with part(f) as b:
        b.fill(ell(cx, cy, 9.5, 9.5), "D")

        def lugs(x, y):
            dx, dy = x - cx, y - cy
            return math.hypot(dx, dy) >= 8.0 and ((math.atan2(dy, dx) - spin) / (TAU / 12)) % 1.0 < 0.5
        b.fill(lugs, "M", on="D")
        b.fill(ell(cx, cy, 6.4, 6.4), "K")
        for k in range(4):
            a = spin + k * TAU / 4
            b.fill(seg(cx, cy, cx + math.cos(a) * 6.2, cy + math.sin(a) * 6.2, 1.7), "M", on="K")
    with part(f) as b:
        b.fill(seg(14, 8, cx, cy, 2.6), "L")
        b.fill(ell(cx, cy, 2.6, 2.6), "L")
        b.fill(box(16, 18, 17, 19), "W" if i % 2 else "r")
    with part(f) as b:
        plate(b, poly([(7, 3), (19, 2), (22, 5), (20, 9), (8, 9)]), top=4, bottom=8)
        b.fill(box(12, 5, 19, 6), "K")
        scanner(b, 12, 19, 5, i)
    for k in range(3):                                    # speed lines
        x = 1 + (i * 2 + k * 3) % 5
        f.fill(box(x, 13 + k * 6, x + 2, 13 + k * 6), "L", on=".")
    return f.shadow(17, 10)


# --- Ransomware --------------------------------------------------------------

def keyhole(layer, cx, cy, glow):
    layer.fill(ell(cx, cy, 1.9, 1.9), "K")
    layer.fill(poly([(cx - 0.9, cy), (cx + 0.9, cy), (cx + 1.6, cy + 4.4), (cx - 1.6, cy + 4.4)]), "K")
    if glow:
        layer.px(cx - 0.5, cy - 0.5, glow)


def shackle(cx, top, width=6.5, thick=2.8, depth=10):
    outer = any_of(all_of(ell(cx, top + width, width, width), box(0, 0, 31, top + width - 1)),
                   box(cx - width, top + width, cx + width - 0.01, top + depth))
    w2 = width - thick
    inner = any_of(all_of(ell(cx, top + width, w2, w2), box(0, 0, 31, top + width - 1)),
                   box(cx - w2, top + width, cx + w2 - 0.01, top + depth))
    return minus(outer, inner)


def ransomware_walker(i):
    f = Layer()
    bob = step_bob(i)
    biped_legs(f, i, hip_y=21, bob=bob, knee_y=24)
    lift = (0, 0, 1, 2, 2, 2, 0, 0)[i]
    with part(f, dy=bob - lift) as b:
        bar = shackle(16, 4, 6.0, 2.6, 9)
        b.fill(bar, "L")
        b.fill(minus(bar, moved(bar, -1.2, -1.2)), "M", on="L")
    with part(f, dy=bob) as b:
        plate(b, rbox(7, 11, 24, 22, 2), top=12, bottom=21, right=23)
        b.fill(box(10, 13, 21, 13), "K")
        scanner(b, 10, 21, 13, i)
        keyhole(b, 16, 16.5, "r" if lift else None)
    return f.shadow(16, 11)


def ransomware_vault(i):
    f = Layer()
    t = i / FRAMES
    treads(f, i, 5, 26, 23)
    with part(f, dy=-(i % 2)) as b:
        plate(b, octagon(5, 3, 26, 22, 2), top=4, bottom=21, right=25)
        b.fill(box(3, 7, 4, 10), "D")
        b.fill(box(3, 15, 4, 18), "D")
        b.fill(ell(16, 12.5, 8.0, 8.0), "K")
        b.fill(ell(16, 12.5, 7.0, 7.0), "L")
        b.fill(minus(ell(16, 12.5, 7.0, 7.0), ell(15, 11.3, 7.0, 7.0)), "M", on="L")
        for k in range(4):                                # locking wheel
            a = TAU * (k / 4 + t / 4)
            b.fill(seg(16, 12.5, 16 + math.cos(a) * 5.2, 12.5 + math.sin(a) * 5.2, 1.5), "D")
            b.fill(ell(16 + math.cos(a) * 5.2, 12.5 + math.sin(a) * 5.2, 1.1, 1.1), "K")
        b.fill(ell(16, 12.5, 2.0, 2.0), "K")
        b.fill(box(15, 12, 16, 12), "W" if i % 4 < 2 else "r")
        b.fill(box(21, 20, 23, 20), "K", on="MD")
    return f.shadow(16, 13)


def ransomware_claw(i):
    f = Layer()
    dy = hover_bob(i)
    grip = (0, 0, 1, 1, 0, 0, 1, 1)[i]
    with part(f, dy=dy) as b:
        b.fill(rbox(11, 17, 20, 26, 1), "L")              # the file it is holding hostage
        b.fill(box(11, 25, 20, 26), "M")
        b.fill(box(18, 17, 20, 19), "M")
        b.fill(rbox(13, 21, 18, 24, 1), "K")
        b.fill(minus(ell(15.5, 21, 2.2, 2.2), ell(15.5, 21, 1.0, 1.0)), "K", on="L")
        b.px(15, 22, "r" if i % 4 < 2 else "W")
    with part(f, dy=dy) as b:
        for s in (-1, 1):
            b.fill(seg(16 + s * 4, 13, 16 + s * (9 - grip), 17, 2.0), "D")
            b.fill(seg(16 + s * (9 - grip), 17, 16 + s * (7.5 - grip), 24, 2.0), "D")
            b.fill(seg(16 + s * (7.5 - grip), 24, 16 + s * (5.5 - grip), 25, 1.6), "L")
    with part(f, dy=dy) as b:
        antenna(b, 16, 3, 4, i)
        plate(b, octagon(8, 5, 23, 14, 3), top=6, bottom=13)
        visor(b, 10, 8, 21, 10, i)
    wash(f, i, (7, 23), 14 + dy)
    return f.shadow(16, 8)


def ransomware_chains(i):
    f = Layer()
    t = i / FRAMES
    bob = step_bob(i)
    biped_legs(f, i, bob=bob)
    for s in (-1, 1):
        with part(f, dy=bob) as b:
            b.fill(seg(16 + s * 9, 9, 16 + s * 11, 10, 2.2), "D")
            for n in range(7):                            # swinging chain
                x = 16 + s * 11 + 1.2 * wave(t, 0.25 * (s > 0) + n * 0.06) * n / 6
                y = 11 + n * 2
                b.fill(box(round(x) - (n % 2 == 0), y, round(x), y + 1), "L" if n % 2 == 0 else "D")
            hx = round(16 + s * 11 + 1.2 * wave(t, 0.25 * (s > 0) + 0.4))
            b.fill(box(hx - 1, 25, hx, 26), "L")
            b.px(hx - (1 if s > 0 else 0), 27, "L")
    with part(f, dy=bob) as b:
        plate(b, octagon(7, 5, 24, 18, 3), top=6, bottom=17, right=23)
        visor(b, 9, 8, 22, 10, i)
        keyhole(b, 16, 12.5, "r" if i % 4 < 2 else None)
    return f.shadow(16, 11)


def ransomware_cage(i):
    f = Layer()
    t = i / FRAMES
    bob = step_bob(i)
    spider_legs(f, i, hip_y=20, bob=bob)
    with part(f, dy=bob) as b:
        b.fill(box(8, 6, 23, 19), "K")
        cx, cy = 15 + round(3 * wave(t)), 12 + round(2 * wave(2 * t, 0.2))
        b.fill(box(cx - 2, cy - 2, cx + 2, cy + 2), "r")   # the data it has locked away
        b.fill(box(cx - 2, cy - 2, cx + 2, cy - 2), "p")
        b.px(cx - 1, cy - 1, "W")
        for x in range(8, 24, 3):
            b.fill(box(x, 6, x, 19), "L")
        b.fill(box(7, 3, 24, 5), "M")
        b.fill(box(7, 3, 24, 3), "L")
        b.fill(box(15, 2, 16, 2), "D")
        plate(b, box(7, 20, 24, 23), top=20, bottom=23)
        b.fill(box(11, 21, 20, 22), "K")
        scanner(b, 11, 20, 21, i)
    return f.shadow(16, 12)


def ransomware_press(i):
    f = Layer()
    drop = (0, 1, 3, 6, 8, 8, 4, 1)[i]
    with part(f) as b:
        b.fill(box(3, 25, 28, 28), "D")
        b.fill(box(3, 25, 28, 25), "M")
        for x in (5, 24):
            b.fill(box(x, 6, x + 2, 24), "M")
            b.fill(box(x + 2, 6, x + 2, 24), "D")
    with part(f) as b:
        h = max(2, 9 - max(0, drop - 3))                   # the file being crushed
        b.fill(box(11, 25 - h, 20, 24), "L")
        b.fill(box(11, 25 - h, 20, 25 - h), "W")
        b.fill(box(13, 26 - h, 18, 26 - h), "r")
        if h > 4:
            b.fill(box(13, 28 - h, 16, 28 - h), "r")
    with part(f) as b:
        b.fill(box(15, 6, 16, 8 + drop), "D")
        b.fill(box(9, 8 + drop, 22, 11 + drop), "L")
        b.fill(box(9, 10 + drop, 22, 11 + drop), "M")
        hazard(b, 9, 11 + drop, 22, 11 + drop, on="M")
    with part(f) as b:
        plate(b, octagon(3, 2, 28, 7, 2), top=3, bottom=7)
        visor(b, 9, 4, 22, 5, i)
    if drop >= 8:
        f.px(8, 21 + i % 2, "W", on=".")
        f.px(23, 22 - i % 2, "p", on=".")
    return f.shadow(16, 13)


SAMPLES = {
    "virus": [("Mine walker", virus_mine_walker), ("Hover mine", virus_hover_mine), ("Phage lander", virus_phage),
              ("Saw drone", virus_saw), ("Pincer crab", virus_crab), ("Glitch block", virus_glitch)],
    "worm": [("Centipede", worm_centipede), ("Tunneller", worm_tunneller), ("Cable cobra", worm_cobra),
             ("Data train", worm_train), ("Inchworm", worm_inch), ("Borer", worm_borer)],
    "firewall": [("Shield walker", firewall_shield_walker), ("Battlement", firewall_bunker),
                 ("Energy gate", firewall_gate), ("Riot shield", firewall_riot), ("Dome bunker", firewall_dome),
                 ("Shutter", firewall_shutter)],
    "bruteforcer": [("Fist mech", brute_fists), ("Battering ram", brute_ram), ("Wrecking ball", brute_ball),
                    ("Hammer mech", brute_hammer), ("Piston puncher", brute_pistons),
                    ("Dial cracker", brute_tumbler)],
    "ddos": [("Mortar walker", ddos_mortar), ("Missile rack", ddos_rack), ("Triple gun", ddos_hydra),
             ("Dish emitter", ddos_dish), ("Swarm carrier", ddos_swarm), ("Rail gun", ddos_rail)],
    "botnet": [("Drone trio", botnet_trio), ("Antenna walker", botnet_antenna), ("Zombie terminal", botnet_terminal),
               ("Hive nodes", botnet_hive), ("Relay mast", botnet_tower), ("Tethered twins", botnet_twins)],
    "backdoor": [("Hatch walker", backdoor_walker), ("Portal ring", backdoor_portal), ("Floor hatch", backdoor_hatch),
                 ("Blast door", backdoor_blast), ("Keyhole slab", backdoor_monolith), ("Drop pod", backdoor_pod)],
    "injector": [("Syringe gun", injector_gun), ("Vial drone", injector_vial), ("Mosquito", injector_mosquito),
                 ("Scorpion", injector_scorpion), ("Sprayer", injector_sprayer), ("Syringe tripod", injector_tripod)],
    "maninthemiddle": [("Agent", mitm_agent), ("Line tap", mitm_tap), ("Relay box", mitm_relay),
                       ("Periscope", mitm_periscope), ("Splitter", mitm_splitter), ("Mask", mitm_mask)],
    "optimiser": [("Welder", optimiser_welder), ("Medic drone", optimiser_medic), ("Gear core", optimiser_gear),
                  ("Crane arm", optimiser_crane), ("Nanite tank", optimiser_nanites),
                  ("Defrag screen", optimiser_defrag)],
    "overclocker": [("Turbine", overclocker_turbine), ("Stopwatch", overclocker_dial), ("Jet sled", overclocker_jet),
                    ("Tesla coil", overclocker_tesla), ("Engine block", overclocker_engine),
                    ("Flywheel", overclocker_wheel)],
    "ransomware": [("Padlock walker", ransomware_walker), ("Vault", ransomware_vault),
                   ("Hostage claw", ransomware_claw), ("Chain mech", ransomware_chains),
                   ("Cage walker", ransomware_cage), ("Crusher", ransomware_press)],
}


# --- Sheets ------------------------------------------------------------------

def render_all(units):
    rendered = {}
    problems = []
    for unit in units:
        rendered[unit] = []
        for name, draw in SAMPLES[unit]:
            frames = [draw(i).image() for i in range(FRAMES)]
            try:
                g.check(f"{unit} / {name}", frames)
            except SystemExit as e:
                problems.append(str(e))
            rendered[unit].append((name, frames))
    if problems:
        raise SystemExit("\n".join(problems))
    return rendered


def build_sheet(rows, path, ground, scale, cols, title_rows=True):
    """rows: list of (heading or None, [(label, frames), ...])"""
    font = ImageFont.load_default(size=14)
    head = ImageFont.load_default(size=18)
    teams = list(g.TEAM_PREVIEW.values())
    pad, label = 8, 20
    tile = g.SIZE * scale
    cell_w = tile * len(teams) + pad
    cell_h = tile + label + pad
    layout = []
    y = pad
    for heading, cells in rows:
        if heading:
            layout.append(("head", heading, y))
            y += 26
        for n, cell in enumerate(cells):
            layout.append(("cell", cell, (pad + (n % cols) * cell_w, y + (n // cols) * cell_h)))
        y += -(-len(cells) // cols) * cell_h
    width, height = cols * cell_w + pad, y + pad
    out = []
    for n in range(FRAMES):
        im = Image.new("RGBA", (width, height), (24, 22, 40, 255))
        pen = ImageDraw.Draw(im)
        for kind, item, pos in layout:
            if kind == "head":
                pen.text((pad, pos), item, fill=(190, 160, 240, 255), font=head)
                continue
            (text, frames), (x, yy) = item, pos
            pen.text((x, yy), text, fill=(235, 235, 245, 255), font=font)
            for k, mapping in enumerate(teams):
                bg = ground.copy()
                bg.alpha_composite(g.recolour(frames[n], mapping))
                im.paste(bg.resize((tile, tile), Image.NEAREST), (x + k * tile, yy + label))
        out.append(im.convert("RGB"))
    out[0].save(path, save_all=True, append_images=out[1:], duration=125, loop=0)
    return out[0]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ground = Image.open(os.path.normpath(os.path.join(
        here, "..", "..", "config", "hacktics", "version1", "entities", "types", "terrain", "ground.png"))).convert("RGBA")
    units = sys.argv[1:] or list(SAMPLES)
    rendered = render_all(units)
    out_dir = os.path.join(here, "samples")
    os.makedirs(out_dir, exist_ok=True)

    for unit, cells in rendered.items():
        labelled = [(f"{n + 1}  {name}", frames) for n, (name, frames) in enumerate(cells)]
        still = build_sheet([(None, labelled)], os.path.join(out_dir, unit + ".gif"), ground, scale=5, cols=3)
        still.save(os.path.join(out_dir, unit + ".png"))
    if len(units) == len(SAMPLES):
        rows = [(unit, [(f"{n + 1}  {name}", frames) for n, (name, frames) in enumerate(cells)])
                for unit, cells in rendered.items()]
        build_sheet(rows, os.path.join(out_dir, "all_units.gif"), ground, scale=3, cols=6)
    print("Wrote", len(units), "sheets to", out_dir)


if __name__ == "__main__":
    main()
