#!/usr/bin/env python3
"""Generates the animated Hacktics unit sprite sheets.

Each unit is drawn procedurally as an 8 frame idle loop on a 32x32 grid and
written out as a horizontal sprite sheet (256x32) plus a matching .piskel file
so individual frames can still be touched up by hand in Piskel.

Usage:
    python3 PixelArt/HackticsUnits/generate_units.py            # write sheets + piskel files
    python3 PixelArt/HackticsUnits/generate_units.py --preview out.gif   # also write a team colour preview
    python3 PixelArt/HackticsUnits/generate_units.py --only virus worm   # limit to some units

House style:
    Worn machines, no faces, drawn side-on and facing right so a team can be
    mirrored to face left. Exposed structure is fixed steel grey and each unit
    carries a small amount of team coloured armour.

Palette rules (see RealmTacticsCore EntitySpriteMetadata.cs):
    The four greys below are swapped for each team's colours at load time. Any
    other colour is left untouched by the game, which is what the steel greys,
    white and purple accents rely on.

        L (166) -> team light / secondary colour
        M (128) -> team main colour
        D (51)  -> team shadow colour
        K (0)   -> team outline colour

Layout rules (see RealmTacticsCore EntitySpriteConfig.cs):
    Frames are sliced left to right at PixelsPerUnit (32) and fully transparent
    frames are dropped. Runtime textures are bilinear + repeat wrapped, so a 1px
    transparent margin is kept around every frame to stop edges bleeding.
"""
import argparse
import base64
import io
import json
import math
import os

from PIL import Image

SIZE = 32
FRAMES = 8
# Canvas pixels per design pixel. Units are always designed on a 32x32 grid; setting SIZE = 64 and
# RES = 2 renders the same shapes at double resolution for comparing pixel densities.
RES = 1

PALETTE = {
    ".": (0, 0, 0, 0),
    "K": (0, 0, 0, 255),
    "D": (51, 51, 51, 255),
    "M": (128, 128, 128, 255),
    "L": (166, 166, 166, 255),
    "W": (255, 255, 255, 255),
    "p": (210, 189, 232, 255),  # light purple (matches the terrain accents)
    "q": (180, 150, 211, 255),  # mid purple
    "r": (147, 74, 221, 255),   # deep purple
    "S": (0, 0, 0, 56),         # soft ground shadow
    # Fixed steel greys for exposed machinery. These are deliberately NOT the four team greys,
    # so the game leaves them alone and only the armour plating takes the team colour.
    "g": (40, 42, 50, 255),     # dark steel
    "G": (82, 86, 98, 255),     # mid steel
    "h": (142, 148, 162, 255),  # worn steel highlight
    "c": (58, 58, 66, 120),     # exhaust smoke
}

# Only used for the preview so the art can be judged in its in-game colours
TEAM_PREVIEW = {
    "Team 1": {"L": (191, 230, 255), "M": (217, 128, 89), "D": (153, 77, 51), "K": (64, 26, 13)},
    "Team 2": {"L": (230, 242, 217), "M": (204, 255, 0), "D": (26, 102, 89), "K": (5, 38, 31)},
}

TAU = math.pi * 2


def wave(t, phase=0.0):
    """Sine that loops exactly once over the animation."""
    return math.sin(TAU * (t + phase))


# --- Shapes ------------------------------------------------------------------
# A shape is a function (x, y) -> bool which is sampled at each pixel centre.

def ell(cx, cy, rx, ry):
    return lambda x, y: ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0


def box(x0, y0, x1, y1):
    """Rectangle in inclusive pixel coordinates."""
    return lambda x, y: x0 <= x < x1 + 1 and y0 <= y < y1 + 1


def rbox(x0, y0, x1, y1, r):
    """Rounded rectangle in inclusive pixel coordinates."""
    x1 += 1
    y1 += 1

    def inside(x, y):
        if not (x0 <= x < x1 and y0 <= y < y1):
            return False
        cx = min(max(x, x0 + r), x1 - r)
        cy = min(max(y, y0 + r), y1 - r)
        return (x - cx) ** 2 + (y - cy) ** 2 <= r * r
    return inside


def poly(points):
    def inside(x, y):
        hit = False
        j = len(points) - 1
        for i in range(len(points)):
            xi, yi = points[i]
            xj, yj = points[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                hit = not hit
            j = i
        return hit
    return inside


def seg(x0, y0, x1, y1, width):
    """Line segment with round caps."""
    dx, dy = x1 - x0, y1 - y0
    length2 = dx * dx + dy * dy or 1e-9

    def inside(x, y):
        u = max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / length2))
        px, py = x0 + u * dx, y0 + u * dy
        return (x - px) ** 2 + (y - py) ** 2 <= (width / 2) ** 2
    return inside


def curve(p0, p1, p2, width, steps=24):
    """Quadratic bezier drawn as a chain of round segments."""
    pts = []
    for i in range(steps + 1):
        u = i / steps
        pts.append(((1 - u) ** 2 * p0[0] + 2 * u * (1 - u) * p1[0] + u * u * p2[0],
                    (1 - u) ** 2 * p0[1] + 2 * u * (1 - u) * p1[1] + u * u * p2[1]))
    return any_of(*[seg(a[0], a[1], b[0], b[1], width) for a, b in zip(pts, pts[1:])])


def any_of(*shapes):
    return lambda x, y: any(s(x, y) for s in shapes)


def all_of(*shapes):
    return lambda x, y: all(s(x, y) for s in shapes)


def minus(shape, cut):
    return lambda x, y: shape(x, y) and not cut(x, y)


def moved(shape, dx, dy):
    return lambda x, y: shape(x - dx, y - dy)


def rotated(shape, degrees, cx, cy):
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))

    def inside(x, y):
        dx, dy = x - cx, y - cy
        return shape(cx + dx * c + dy * s, cy - dx * s + dy * c)
    return inside


# --- Canvas ------------------------------------------------------------------

class Layer:
    def __init__(self):
        self.g = [["."] * SIZE for _ in range(SIZE)]

    def fill(self, shape, colour, on=None):
        """Fill a shape. `on` limits painting to pixels already one of those colours
        ("*" = any drawn pixel), which is how shading and details are clipped."""
        for y in range(SIZE):
            for x in range(SIZE):
                if shape((x + 0.5) / RES, (y + 0.5) / RES):
                    self.raw(x, y, colour, on)
        return self

    def px(self, x, y, colour, on=None):
        """Set one design pixel (a RES x RES block on the canvas)."""
        x, y = int(x) * RES, int(y) * RES
        for by in range(RES):
            for bx in range(RES):
                self.raw(x + bx, y + by, colour, on)

    def raw(self, x, y, colour, on=None):
        if not (0 <= x < SIZE and 0 <= y < SIZE):
            return
        cur = self.g[y][x]
        if on is not None:
            if on == "*":
                if cur == ".":
                    return
            elif cur not in on:
                return
        self.g[y][x] = colour

    def stamp(self, rows, x, y, on=None):
        """Draw rows of palette characters, spaces are skipped."""
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch != " ":
                    self.px(x + i, y + j, ch, on)
        return self

    def shade(self, shape, base, dark=None, light=None, depth=1.6):
        """Fill a shape with a base colour, a shadow along the lower right edge
        and an optional rim of light along the upper left edge."""
        self.fill(shape, base)
        if dark:
            self.fill(minus(shape, moved(shape, -depth, -depth)), dark, on=base)
        if light:
            self.fill(minus(shape, moved(shape, depth * 0.7, depth * 0.7)), light, on=base)
        return self

    def outline(self, colour="K"):
        edge = []
        for y in range(SIZE):
            for x in range(SIZE):
                if self.g[y][x] != ".":
                    continue
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < SIZE and 0 <= ny < SIZE and self.g[ny][nx] not in (".", "S"):
                        edge.append((x, y))
                        break
        for x, y in edge:
            self.g[y][x] = colour
        return self

    def over(self, other, dx=0, dy=0):
        """Composite another layer on top of this one."""
        for y in range(SIZE):
            for x in range(SIZE):
                c = other.g[y][x]
                if c != ".":
                    self.raw(x + dx * RES, y + dy * RES, c)
        return self

    def shadow(self, cx, rx):
        self.fill(ell(cx, 29.6, rx, 1.6), "S", on=".")
        return self

    def image(self, palette=PALETTE):
        im = Image.new("RGBA", (SIZE, SIZE))
        im.putdata([palette[c] for row in self.g for c in row])
        return im


def plate(layer, shape, top=None, bottom=None, right=None):
    """Hard surface shading: lit top plate, team coloured face, shadowed underside."""
    layer.fill(shape, "M")
    if top is not None:
        layer.fill(all_of(shape, box(0, 0, 31, top)), "L")
    if bottom is not None:
        layer.fill(all_of(shape, box(0, bottom, 31, 31)), "D")
    if right is not None:
        layer.fill(all_of(shape, box(right, 0, 31, 31)), "D", on="M")


def scanner(layer, x0, x1, y, i):
    """A light sweeping back and forth along a dark visor."""
    span = max(0, x1 - x0 - 2)
    pos = x0 + round(span * (0.5 - 0.5 * math.cos(TAU * i / FRAMES)))
    layer.fill(box(pos, y, pos + 2, y), "r", on="K")
    layer.px(pos + 1, y, "W", on="r")


# --- Shared parts ------------------------------------------------------------
# House style: every unit is a worn machine drawn side-on, facing right. Exposed
# structure is fixed steel grey (g / G / h), and each unit carries a small amount of
# team coloured armour (M, lit with L, shaded and dirtied with D).

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


def grime(layer, shape, colour="D", on="M", parity=0):
    """Checker dither, used for dirt building up along the bottom of plates."""
    layer.fill(lambda x, y: shape(x, y) and (int(x) + int(y)) % 2 == parity, colour, on=on)


def armour(layer, shape, lit=None, shade=None, dirty=None):
    """Team coloured plating: rows up to `lit` catch the light, rows from `shade` are in shadow,
    rows from `dirty` down are grimy."""
    layer.fill(shape, "M")
    if lit is not None:
        layer.fill(all_of(shape, box(0, 0, 31, lit)), "L")
    if shade is not None:
        layer.fill(all_of(shape, box(0, shade, 31, 31)), "D")
    if dirty is not None:
        grime(layer, all_of(shape, box(0, dirty, 31, 31)))


def steel(layer, shape, lit=None, shade=None):
    """Bare metal: mid steel with an optional worn highlight on top and dark underside."""
    layer.fill(shape, "G")
    if lit is not None:
        layer.fill(all_of(shape, box(0, 0, 31, lit)), "h")
    if shade is not None:
        layer.fill(all_of(shape, box(0, shade, 31, 31)), "g")


def rivets(layer, points, colour="K", on=None):
    for x, y in points:
        layer.px(x, y, colour, on)


def scratch(layer, x, y, length=3, colour="L", on="MD"):
    for k in range(length):
        layer.px(x + k, y - k, colour, on)


def hazard(layer, x0, y0, x1, y1, on=None):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            layer.px(x, y, "K" if ((x + y) // 2) % 2 else "L", on)


def lens(layer, x, y, i):
    """A single hard sensor light. Sits in a black socket drawn by the caller."""
    layer.px(x, y, "r")
    layer.px(x + 1, y, "W" if i % 4 < 2 else "p")


def smoke(frame, x, y, i, drift=-4.0, rise=5.0):
    inside = box(1, 1, 30, 30)
    for k in range(3):
        age = (i / FRAMES + k / 3) % 1.0
        puff = ell(x + drift * age, y - rise * age, 0.9 + age * 1.6, 0.8 + age * 1.3)
        frame.fill(all_of(puff, inside), "c", on=".")


def stride_bob(i):
    """Walkers dip as each foot lands."""
    return (1, 0, 0, 0, 1, 0, 0, 0)[i]


def hover_bob(i):
    return round(1.2 * wave(i / FRAMES))


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


def leg(frame, hip, phase, near, stride=3.0, lift=2.6, l1=5.0, l2=5.4, plated=True, w1=3.0, w2=2.2):
    """One side-on walking leg. The far leg is drawn darker, the near leg can carry thigh armour."""
    ox, oy = foot_offset(phase, stride, lift)
    ankle = (hip[0] + 1.5 + ox, 26.0 - oy)
    knee = knee_for(hip, ankle, l1, l2)
    fx, fy = round(ankle[0]), round(ankle[1])
    with part(frame) as b:
        b.fill(seg(*hip, *knee, w1), "G" if near else "g")
        b.fill(seg(*knee, *ankle, w2), "G" if near else "g")
        if near:                                           # exposed piston down the shin
            b.fill(seg(knee[0] + 1.4, knee[1] - 0.4, ankle[0] + 1.0, ankle[1] - 2.2, 1.0), "h")
        b.fill(box(fx - 2, fy + 1, fx + 3, fy + 2), "g")
        if near:
            b.fill(box(fx + 2, fy + 1, fx + 3, fy + 1), "h")
    if near:
        if plated:
            with part(frame) as b:
                mx, my = hip[0] + (knee[0] - hip[0]) * 0.62, hip[1] + (knee[1] - hip[1]) * 0.62
                b.fill(seg(hip[0], hip[1], mx, my, w1 + 1.4), "M")
                b.fill(seg(hip[0] + 1.2, hip[1] + 1.2, mx + 1.2, my + 1.2, 1.4), "D", on="M")
                b.px(hip[0] - 1.5, hip[1] - 1.5, "L", on="M")
        frame.fill(ell(knee[0], knee[1], 1.3, 1.3), "h")
        frame.px(knee[0] - 0.5, knee[1] - 0.5, "K")


def tracks(frame, i, x0=4, x1=27, y0=22):
    with part(frame) as t:
        t.fill(rbox(x0, y0, x1, 28, 3), "g")
        t.fill(rbox(x0 + 2, y0 + 2, x1 - 2, 26, 1.5), "K")
        for n, x in enumerate(range(x0 + 3, x1 - 2, 5)):
            t.fill(box(x, y0 + 2, x + 1, 26), "G")
            t.px(x + (i // 2) % 2, y0 + 2 + ((i // 2 + n) % 2) * 2, "h")
        for x in range(x0 + 1, x1):
            if (x - i) % 3 == 0:
                t.px(x, y0, "G", on="g")
            if (x + i) % 3 == 0:
                t.px(x, 28, "h", on="g")


def cart_wheels(frame, i, xs, y=25.5, r=3.0):
    a = TAU * i / FRAMES
    with part(frame) as w:
        for x in xs:
            w.fill(ell(x, y, r, r), "g")
            w.fill(ell(x, y, r - 1.8, r - 1.8), "G")
            w.px(x + math.cos(a) * (r - 1.0) - 0.5, y + math.sin(a) * (r - 1.0) - 0.5, "h", on="g")


# --- Units -------------------------------------------------------------------
# Every unit function takes the frame index and returns a finished Layer.

def worker(i):
    """Bare-frame loader: an open roll cage round an engine block, striding along."""
    f = Layer()
    p = i / FRAMES
    bob = stride_bob(i)
    hy = 18 + bob
    leg(f, (15.5, hy), p + 0.5, near=False)
    with part(f, dy=bob) as b:                             # roll cage
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
        shape = poly([(12, 3), (21, 4), (24, 10), (15, 9)])
        armour(b, shape, lit=4, dirty=7)
        scratch(b, 16, 8, 3)
        rivets(b, [(14, 5), (20, 6)], on="ML")
    with part(f, dy=bob) as b:                             # sensor on a stalk
        b.fill(seg(21, 13, 25, 11.5, 1.6), "G")
        steel(b, box(24, 8, 28, 12), lit=8)
        b.fill(box(26, 10, 28, 11), "K")
        lens(b, 27, 10, i)
    with part(f, dy=bob) as b:                             # grab claw
        grip = (0, 0, 1, 1, 0, 0, 1, 1)[i]
        b.fill(seg(19, 17, 25, 19, 1.8), "g")
        b.fill(seg(25, 19, 28, 18 - grip, 1.0), "h")
        b.fill(seg(25, 19, 28, 21 + grip, 1.0), "h")
    leg(f, (12, hy), p, near=True, plated=False)
    smoke(f, 8, 5 + bob, i, drift=-4.0, rise=4.0)
    return f.shadow(15, 11)


def virus(i):
    """Mine walker: a spiked charge carried on two legs, spikes slowly turning."""
    f = Layer()
    t = i / FRAMES
    bob = stride_bob(i)
    hy = 20 + bob
    cx, cy = 15.0, 13.5
    leg(f, (16.5, hy), t + 0.5, near=False, l1=4.2, l2=4.4, stride=2.6)
    with part(f, dy=bob) as b:
        for k in range(8):
            a = TAU * (k / 8 + t / 8)
            ln = 9.0 + 0.6 * wave(t, k / 2)
            tx, ty = cx + math.cos(a) * ln, cy + math.sin(a) * ln
            b.fill(seg(cx, cy, tx, ty, 2.2), "g")
            b.fill(ell(tx, ty, 1.2, 1.2), "h")
    with part(f, dy=bob) as b:
        ball = ell(cx, cy, 7.0, 7.0)
        steel(b, ball)
        b.fill(minus(ball, ell(cx - 1.0, cy - 1.8, 7.0, 7.0)), "g", on="G")
        armour(b, all_of(ball, box(0, 0, 31, 12)), lit=8, dirty=11)   # casing over the top half
        b.fill(box(8, 13, 22, 13), "g", on="Gg")
        b.fill(box(17, 11, 21, 14), "K")
        lens(b, 19, 12, i)
        rivets(b, [(10, 10), (13, 9), (16, 9)], on="M")
        scratch(b, 10, 11, 2)
        b.fill(box(11, 16, 15, 17), "K", on="Gg")           # arming panel
        b.px(12 + i % 3, 16, "r")
    leg(f, (13, hy), t, near=True, l1=4.2, l2=4.4, stride=2.6, plated=False)
    return f.shadow(15, 10)


def worm(i):
    """Inchworm: plated segments arching up and stretching out."""
    f = Layer()
    t = i / FRAMES
    arch = 0.5 + 0.5 * wave(t)
    pts = []
    for k in range(6):
        pts.append((13.5 + (k - 2.5) / 2.5 * (9.5 - 3.0 * arch), 24.0 - arch * 9 * math.sin(math.pi * k / 5)))
    with part(f) as b:                                     # tail aerial
        tx, ty = pts[0]
        b.fill(seg(tx, ty - 2, tx - 1.5, ty - 6, 0.9), "g")
        b.px(tx - 2, ty - 7, "r" if i % 4 < 2 else "W")
    for x, y in (pts[0], pts[-1]):                         # gripping pads
        with part(f) as b:
            b.fill(box(round(x) - 2, 27, round(x) + 2, 28), "g")
            b.px(round(x) + 2, 27, "h")
    for k, (a, c) in enumerate(zip(pts, pts[1:])):
        with part(f) as b:
            if k % 2 == 0:
                b.fill(seg(*a, *c, 5.0), "M")
                b.fill(seg(a[0], a[1] - 1.9, c[0], c[1] - 1.9, 1.2), "L", on="M")
                b.fill(seg(a[0], a[1] + 1.9, c[0], c[1] + 1.9, 1.4), "D", on="M")
                grime(b, seg(a[0], a[1] + 0.8, c[0], c[1] + 0.8, 1.6))
            else:
                b.fill(seg(*a, *c, 4.4), "G")
                b.fill(seg(a[0], a[1] - 1.6, c[0], c[1] - 1.6, 1.0), "h", on="G")
                b.fill(seg(a[0], a[1] + 1.6, c[0], c[1] + 1.6, 1.4), "g", on="G")
    for x, y in pts[1:-1]:                                 # hinge pins
        f.fill(ell(x, y, 1.2, 1.2), "h")
        f.px(x - 0.5, y - 0.5, "K")
    hx, hy = round(pts[-1][0]) + 1, round(pts[-1][1]) - 2
    with part(f) as b:
        head = poly([(hx - 3, hy - 4), (hx + 3, hy - 4), (hx + 5, hy - 1), (hx + 5, hy + 2), (hx + 3, hy + 4),
                     (hx - 3, hy + 4)])
        steel(b, head, shade=hy + 3)
        armour(b, all_of(head, box(0, 0, 31, hy - 2)), lit=hy - 4)
        b.fill(box(hx + 1, hy - 1, hx + 4, hy), "K")
        lens(b, hx + 2, hy - 1, i)
        b.px(hx + 4, hy + 2, "h")
        b.px(hx - 1, hy + 2, "K", on="G")
    return f.shadow(15, 12)


def firewall(i):
    """Shutter: a heavy roller door that rattles up and slams back down."""
    f = Layer()
    gap = (0, 0, 2, 5, 5, 5, 2, 0)[i]
    with part(f) as b:                                     # side of the frame, giving it depth
        b.fill(poly([(4, 8), (9, 6), (9, 29), (4, 27)]), "g")
        for y in (11, 16, 21):
            b.px(6, y, "G")
    with part(f) as b:
        b.fill(box(9, 8, 27, 28), "K")                      # doorway
        for y in range(10, 28, 2):
            b.fill(box(12, y, 24, y), "r" if (y + i) % 4 < 2 else "q", on="K")
        bottom = 28 - gap
        for y in range(9, bottom + 1):                      # slats
            b.fill(box(12, y, 24, y), "D" if (y - gap) % 3 == 0 else "M")
        b.fill(box(12, 9, 12, bottom), "L", on="M")
        for x, y in ((15, 12), (20, 17), (17, 22), (22, 13)):   # paint chipped back to metal
            if y <= bottom - 2:
                b.px(x, y + (gap % 3 == 1), "G", on="M")
        scratch(b, 18, min(20, bottom - 3), 3)
        hazard(b, 12, bottom - 1, 24, bottom, on="MD")
        if gap:
            b.fill(box(12, bottom + 1, 24, bottom + 1), "W")
        steel(b, box(9, 8, 11, 28))                         # posts
        steel(b, box(25, 8, 27, 28))
        b.fill(box(9, 8, 9, 28), "h")
        b.fill(box(27, 8, 27, 28), "g")
        rivets(b, [(10, 12), (10, 18), (10, 24), (26, 12), (26, 18), (26, 24)])
    with part(f, dy=1 if i == 7 else 0) as b:               # roller housing
        armour(b, rbox(8, 3, 28, 8, 1.5), lit=3, shade=8, dirty=6)
        b.fill(box(20, 5, 23, 6), "K")
        lens(b, 21, 5, i)
        rivets(b, [(10, 5), (14, 5), (26, 5)], on="M")
        b.fill(box(26, 2, 27, 2), "W" if gap else "g")      # warning lamp
    return f.shadow(16, 13)


def bruteforcer(i):
    """Fist mech: a hunched bruiser throwing alternate punches as it runs a password."""
    f = Layer()
    t = i / FRAMES
    bob = stride_bob(i)
    hy = 20 + bob
    near_x = 21 + round(2.6 * wave(t))
    far_x = 22 + round(2.6 * wave(t, 0.5))
    leg(f, (16.5, hy), t + 0.5, near=False, l1=4.2, l2=4.4, stride=2.4, w1=3.6, w2=2.8)
    with part(f, dy=bob) as b:                             # far arm
        b.fill(seg(17, 10, far_x, 15, 3.0), "g")
        b.fill(rbox(far_x - 1, 12, far_x + 4, 17, 1.5), "g")
        b.px(far_x + 1, 13, "G")
        b.px(far_x + 3, 13, "G")
    with part(f, dy=bob) as b:
        b.fill(box(5, 3, 6, 7), "g")                        # exhaust
        b.px(5, 3, "G")
        hull = poly([(7, 6), (16, 4), (21, 8), (21, 17), (18, 21), (8, 21), (5, 17), (5, 9)])
        steel(b, hull, shade=19)
        armour(b, all_of(hull, box(0, 0, 31, 12)), lit=5, dirty=10)   # upper body plating
        b.fill(box(16, 7, 20, 9), "K")
        lens(b, 18, 8, i)
        b.fill(box(7, 14, 16, 17), "K")                     # password read-out
        for d in range(3):
            b.fill(box(8 + d * 3, 15, 9 + d * 3, 16), "W" if (i // 2) % 3 == d else "r")
        rivets(b, [(10, 6), (13, 6), (7, 19), (17, 19)], on="MGg")
        scratch(b, 11, 10, 3)
        b.fill(box(8, 13, 20, 13), "g", on="G")
    with part(f, dy=bob) as b:                             # near arm
        b.fill(seg(13, 10, near_x, 16, 3.6), "G")
        b.fill(seg(13.6, 11.2, near_x, 17.2, 1.2), "g", on="G")
    with part(f, dy=bob) as b:                             # pauldron
        armour(b, ell(12.5, 9.5, 3.6, 3.4), lit=7, dirty=11)
    with part(f, dy=bob) as b:                             # near fist
        fist = rbox(near_x - 1, 13, near_x + 5, 20, 1.5)
        steel(b, fist, lit=13, shade=19)
        for x in (near_x + 1, near_x + 3):
            b.fill(box(x, 14, x, 16), "g", on="G")
        b.fill(box(near_x + 5, 15, near_x + 5, 18), "h", on="G")
    leg(f, (12.5, hy), t, near=True, l1=4.2, l2=4.4, stride=2.4, w1=3.6, w2=2.8, plated=False)
    smoke(f, 5.5, 2 + bob, i, drift=-3.0, rise=3.0)
    return f.shadow(15, 12)


def ddos(i):
    """Missile rack: a tracked launcher sending packets off one tube at a time."""
    f = Layer()
    tube = (i // 2) % 4
    firing = tube < 3 and i % 2 == 0
    tracks(f, i, 3, 27, 22)
    with part(f) as b:                                     # deck
        steel(b, box(4, 19, 26, 21), lit=19, shade=21)
    with part(f) as b:                                     # elevating ram
        b.fill(seg(13, 20, 15, 13, 2.0), "g")
        b.fill(seg(13.6, 19, 15.4, 13, 0.8), "h")
    with part(f) as b:                                     # cab
        cab = poly([(19, 13), (25, 13), (28, 17), (28, 21), (19, 21)])
        steel(b, cab, lit=13, shade=20)
        b.fill(poly([(22, 14), (25, 14), (27.4, 17), (22, 17)]), "K")
        lens(b, 24, 15, i)
        rivets(b, [(20, 15), (20, 19)], "g")
    with part(f, dy=-1 if firing else 0) as b:             # launcher box
        rack = poly([(3, 10.5), (19, 5), (21.5, 11.5), (5.5, 17)])
        b.fill(rack, "M")
        b.fill(seg(4, 10.6, 19, 5.4, 1.3), "L", on="M")
        b.fill(seg(6, 16, 21, 10.8, 1.5), "D", on="M")
        b.fill(seg(4.6, 13.6, 20.2, 8.2, 0.9), "D", on="M")
        grime(b, seg(5.4, 14.8, 20.6, 9.6, 1.6))
        for k in range(3):                                  # tube mouths
            b.px(19 + (k > 0), 6 + k * 2, "W" if firing and tube == k else "K")
        rivets(b, [(7, 12), (11, 10)], on="M")
        scratch(b, 13, 11, 2)
    if tube < 3:                                           # packet away, back-blast behind
        d = i % 2
        x, y = 22 + d * 3, max(1, 5 + tube * 2 - d * 2)
        f.fill(box(x, y, x + 1, y + 1), "r" if d == 0 else "p", on=".")
        if firing:
            f.fill(all_of(ell(3, 15, 1.8, 1.4), box(1, 1, 30, 30)), "c", on=".")
    return f.shadow(15, 13)


def drone(f, cx, cy, i, lit, big=False):
    w = 5 if big else 4
    h = 5 if big else 4
    with part(f) as b:
        blade = (w, w - 2, 1, w - 2)[i % 4]
        b.fill(box(cx - blade, cy - 3, cx + blade, cy - 3), "h")
        b.fill(box(cx, cy - 2, cx, cy - 1), "g")
        b.fill(box(cx - w - 2, cy + 1, cx - w, cy + 1), "g")   # tail boom
        b.fill(box(cx - w - 2, cy - 1, cx - w - 2, cy + 1), "G")
        body = rbox(cx - w, cy, cx + w, cy + h, 2)
        steel(b, body, shade=cy + h)
        armour(b, all_of(body, box(0, 0, cx + 1, cy + 1)), lit=cy)
        b.fill(box(cx + w - 3, cy + 2, cx + w, cy + 3), "K")
        b.px(cx + w - 2, cy + 2, "W" if lit else "r")
        b.px(cx + w - 1, cy + 2, "W" if lit or i % 4 < 2 else "p")
    f.px(cx - 1 + i % 2, cy + h + 2, "p" if i % 2 else "r", on=".")


def botnet(i):
    """Drone trio: three linked drones flying in formation, pinging each other in turn."""
    f = Layer()
    t = i / FRAMES
    talk = (i // 2) % 4
    spots = ((10, 6 + (wave(t, 0.1) > 0)), (9, 19 + (wave(t, 0.6) > 0)), (21, 12 + (wave(t, 0.35) > 0)))
    for a, c in ((0, 2), (1, 2), (0, 1)):                 # link beams
        (x0, y0), (x1, y1) = spots[a], spots[c]
        for n in range(1, 6):
            if (n + i) % 3 == 0:
                f.px(x0 + (x1 - x0) * n / 6, y0 + 3 + (y1 - y0) * n / 6, "p", on=".")
    drone(f, *spots[0], i, talk == 0)
    drone(f, *spots[1], i, talk == 2)
    drone(f, *spots[2], i, talk == 1, big=True)
    return f.shadow(15, 11)


def backdoor(i):
    """Portal ring: a bolted steel ring on a stand with a doorway churning inside it."""
    f = Layer()
    t = i / FRAMES
    cx, cy = 17.0, 14.5
    with part(f, outline=False) as b:                      # feed cable
        b.fill(curve((6, 26), (2, 22), (6, 17), 1.0), "K")
    with part(f) as b:                                     # stand
        steel(b, poly([(6, 25), (25, 25), (28, 28.9), (4, 28.9)]), lit=25, shade=28)
        rivets(b, [(8, 27), (24, 27)], "h")
    with part(f) as b:                                     # back of the ring, showing its depth
        b.fill(ell(cx - 2.5, cy, 9.5, 12), "g")
    with part(f, outline=False) as b:                      # the doorway
        hole = ell(cx, cy, 6.6, 9.1)
        b.fill(hole, "K")
        for y in range(4, 26):
            for x in range(9, 26):
                if ell(cx, cy, 5.8, 8.3)(x + 0.5, y + 0.5):
                    dx, dy = x + 0.5 - cx, y + 0.5 - cy
                    s = ((math.atan2(dy, dx * 1.4) + math.hypot(dx * 1.4, dy) * 0.45 - t * TAU) / (TAU / 3)) % 1.0
                    b.px(x, y, "p" if s < 0.25 else "q" if s < 0.55 else "r")
        b.fill(box(16, 14, 17, 15), "W")
    with part(f) as b:
        ring = minus(ell(cx, cy, 9.5, 12), ell(cx, cy, 6.6, 9.1))
        steel(b, ring)
        b.fill(minus(ring, moved(ring, 1.0, 1.0)), "h", on="G")
        b.fill(minus(ring, moved(ring, -1.0, -1.0)), "g", on="G")
        armour(b, all_of(ring, box(0, 0, 31, 7)), lit=3, dirty=6)   # cladding over the crown
        for k in range(8):                                  # segment bolts
            a = TAU * k / 8 + 0.35
            b.px(cx + math.cos(a) * 8.0 - 0.5, cy + math.sin(a) * 10.5 - 0.5, "K", on="GghMLD")
        b.fill(box(8, 14, 8, 15), "r" if i % 4 < 2 else "W", on="Ggh")
        b.fill(box(25, 14, 25, 15), "r" if i % 4 >= 2 else "W", on="Ggh")
        scratch(b, 13, 6, 2)
    return f.shadow(16, 12)


def injector(i):
    """Scorpion: a low crawler with a venom tank and a stinger held over its back."""
    f = Layer()
    t = i / FRAMES
    bob = (0, 1, 0, 0)[i % 4]
    dip = round(1.4 * wave(t))

    def crawl(off, colour, phase):
        with part(f) as b:
            for k, x in enumerate((8, 13, 18)):
                up = (i // 2 + k + phase) % 2 == 0
                b.fill(seg(x + off, 20, x + off - 1.5, 23, 1.6), colour)
                b.fill(seg(x + off - 1.5, 23, x + off + (1.2 if up else -1.0), 27.6 - (1.5 if up else 0), 1.3), colour)

    crawl(2.5, "g", 1)
    with part(f, dy=bob) as b:                             # tail
        tail = [(7, 17), (4.5, 13), (5, 8.5), (9, 5.5), (14, 5 + dip * 0.5), (18, 7 + dip)]
        for k, (x, y) in enumerate(tail):
            b.fill(ell(x, y, 2.2, 2.2), "G" if k % 2 else "g")
            b.px(x - 1, y - 1.5, "h")
    with part(f, dy=bob) as b:                             # stinger
        sx, sy = 18, 7 + dip
        b.fill(poly([(sx, sy - 1), (sx + 3, sy + 1.5), (sx + 2.6, sy + 5.5), (sx + 0.6, sy + 2.2)]), "h")
        b.px(sx + 2, sy + 4, "r")
    with part(f, dy=bob, outline=False) as b:              # feed line from the tank
        b.fill(curve((9, 13), (6, 14), (5.5, 11), 1.0), "K")
    with part(f, dy=bob) as b:                             # venom tank
        b.fill(rbox(9, 12, 17, 16, 1.5), "q")
        b.fill(box(10, 12, 16, 12), "p")
        b.fill(box(10, 16, 16, 16), "r")
        b.fill(box(9, 12, 9, 16), "g")
        b.fill(box(17, 12, 17, 16), "g")
        b.px(11 + (i * 2) % 5, 14 - i % 2, "W")
    with part(f, dy=bob) as b:
        body = poly([(6, 17), (20, 16), (25, 18.5), (25, 21), (21, 22.9), (7, 22.9), (5, 20)])
        steel(b, body, shade=21)
        armour(b, all_of(body, box(0, 0, 19, 19)), lit=16, dirty=19)   # carapace
        for x in (10, 15):
            b.fill(box(x, 16, x, 20), "D", on="ML")
        rivets(b, [(8, 18), (13, 18), (18, 18)], on="M")
        b.fill(box(21, 18, 24, 19), "K")
        lens(b, 22, 18, i)
    with part(f, dy=bob) as b:                             # pincers
        snap = (0, 0, 1, 1, 0, 0, 0, 0)[i] * 0.7
        b.fill(seg(24, 20.5, 27, 21, 1.8), "g")
        b.fill(seg(27, 21, 29.2, 19.6 + snap, 1.2), "h")
        b.fill(seg(27, 21, 29.2, 22.6 - snap, 1.2), "h")
    crawl(0, "G", 0)
    drop = (i - 2) % FRAMES
    if drop < 3:
        f.fill(box(20, 14 + dip + drop * 2, 20, 15 + dip + drop * 2), "r", on=".")
    return f.shadow(16, 12)


def maninthemiddle(i):
    """Agent: a machine in a hat and coat, checking over its shoulder with a tap in hand."""
    f = Layer()
    glance = i in (5, 6)
    sway = (0, 0, 1, 0, 0, 0, -1, 0)[i]
    with part(f) as b:                                     # steel legs under the hem
        for k, x in enumerate((12, 17)):
            lift = 1 if (i // 2 + k) % 2 == 0 else 0
            b.fill(box(x, 23, x + 1, 27 - lift), "g")
            b.fill(box(x, 27 - lift, x + 3, 28 - lift), "g")
            b.px(x + 3, 27 - lift, "h")
    with part(f) as b:                                     # coat
        coat = poly([(11, 13), (19, 13), (21, 18), (21.5 + sway * 0.5, 25.9), (8 + sway, 25.9), (10, 18)])
        armour(b, coat, dirty=22)
        b.fill(all_of(coat, box(19, 0, 31, 31)), "D", on="M")
        b.fill(all_of(coat, box(0, 25, 31, 31)), "D")
        b.fill(poly([(15, 12), (20, 12), (21, 15), (17, 16.5)]), "L")   # turned-up collar
        b.fill(box(10, 19, 20, 19), "D", on="M")           # belt
        b.px(19, 19, "h")
        b.fill(box(12, 20, 12, 25), "D", on="M")           # vent in the back
        scratch(b, 13, 23, 2)
    with part(f) as b:                                     # arm and the tap it carries
        b.fill(seg(14, 15, 19, 20, 2.6), "M")
        b.fill(seg(14.6, 16.2, 19.4, 21, 1.0), "D", on="M")
        b.fill(box(19, 20, 20, 21), "h")
    with part(f) as b:
        steel(b, box(21, 18, 25, 22), lit=18, shade=22)
        b.fill(box(22, 19, 24, 20), "K")
        b.px(22 + i % 3, 19, "r")
        b.px(23, 20, "W" if i % 2 else "p")
        b.fill(box(25, 14, 25, 17), "g")
        b.px(25, 13, "r" if i % 4 < 2 else "W")
    with part(f) as b:                                     # head: no face, just a slot
        b.fill(rbox(13, 7, 19, 12, 2), "g")
        b.fill(box(13, 7, 14, 9), "G", on="g")
        if glance:
            b.fill(box(13, 9, 16, 10), "K")
            b.px(13, 9, "W")
            b.px(14, 9, "r")
        else:
            b.fill(box(16, 9, 19, 10), "K")
            b.px(18, 9, "r")
            b.px(19, 9, "W" if i % 4 < 2 else "p")
    with part(f) as b:                                     # hat
        b.fill(rbox(12, 2, 19, 6, 2), "g")
        b.fill(box(13, 2, 16, 2), "G")
        b.fill(box(12, 6, 19, 6), "h")
        if glance:
            b.fill(box(8, 7, 21, 8), "g")
            b.fill(box(8, 7, 21, 7), "G")
        else:
            b.fill(box(10, 7, 23, 8), "g")
            b.fill(box(10, 7, 23, 7), "G")
    return f.shadow(15, 10)


def optimiser(i):
    """Medic drone: a rotor craft with a repair arm and a beam playing over the ground."""
    f = Layer()
    dy = hover_bob(i)
    reach = (0, 1, 2, 2, 1, 0, 0, 0)[i]
    with part(f, dy=dy) as b:                              # repair arm
        b.fill(seg(17, 18, 20, 21 + reach * 0.5, 1.8), "g")
        b.fill(seg(20, 21 + reach * 0.5, 22, 23 + reach, 1.2), "h")
    with part(f, dy=dy) as b:
        b.fill(box(15, 4, 15, 7), "g")                      # rotor
        blade = (10, 6, 2, 6)[i % 4]
        b.fill(box(15 - blade, 3, 15 + blade, 3), "h")
        b.fill(box(14, 3, 16, 3), "g")
        b.fill(box(2, 12, 6, 13), "g")                      # tail boom
        b.fill(box(2, 9, 2, 13), "G")
        body = poly([(6, 9), (20, 8), (26, 12), (26, 16), (22, 19.9), (8, 19.9), (5, 16), (5, 11)])
        steel(b, body, shade=18)
        armour(b, all_of(body, box(0, 0, 18, 13)), lit=9, dirty=12)   # upper shell
        b.fill(rbox(8, 10, 16, 17, 1), "K")                 # cross panel
        cross = "W" if i % 4 < 2 else "p"
        b.fill(box(12, 11, 12, 16), cross)
        b.fill(box(10, 13, 14, 14), cross)
        b.fill(box(11, 13, 13, 14), cross)
        b.fill(poly([(20, 10), (24.5, 12.5), (24.5, 15), (20, 15)]), "K")   # nose glass
        lens(b, 22, 13, i)
        rivets(b, [(18, 10), (18, 17), (7, 15)], on="MGg")
    for x in (9, 14):                                      # downwash
        f.px(x + i % 2, 21 + dy, "p" if i % 2 else "r", on=".")
    tip_x, tip_y = 22, 24 + reach + dy
    for k in range(2):                                     # repair beam
        y = tip_y + 1 + (k * 2 + i) % 4
        if y <= 28:
            f.px(tip_x, y, "W" if (k + i) % 2 else "p", on=".")
    return f.shadow(15, 9)


def overclocker(i):
    """Tesla coil: a coil on a cart, throwing arcs as it winds up."""
    f = Layer()
    cart_wheels(f, i, (8, 21), y=25.5, r=3.0)
    with part(f) as b:                                     # chassis with a painted skirt
        steel(b, box(3, 19, 26, 19))
        armour(b, box(4, 20, 25, 22), shade=22, dirty=21)
        hazard(b, 13, 20, 17, 21, on="MD")
        b.fill(box(2, 20, 3, 20), "g")                      # tow hitch
    with part(f) as b:                                     # sensor housing up front
        nose = poly([(21, 14), (25, 14), (28, 17), (28, 20), (21, 20)])
        armour(b, nose, lit=14, shade=20, dirty=18)
        b.fill(box(24, 16, 27, 17), "K")
        lens(b, 25, 16, i)
        rivets(b, [(22, 16), (22, 19)], on="M")
    with part(f) as b:                                     # capacitor bank
        steel(b, box(15, 15, 20, 19), lit=15)
        for x in (16, 18):
            b.fill(box(x, 16, x, 18), "g")
        b.px(19, 17, "r" if i % 2 else "W")
    with part(f) as b:                                     # coil
        b.fill(box(8, 9, 13, 19), "g")
        for y in range(9, 20):
            if (y + i) % 2 == 0:
                b.fill(box(8, y, 13, y), "h")
        b.fill(box(7, 18, 14, 19), "G")
    with part(f) as b:                                     # top load
        top = ell(10.5, 6.5, 6.5, 2.8)
        steel(b, top, lit=5, shade=8)
    arcs = (
        ((17, 6), (20, 4), (22, 7), (26, 5)),
        ((5, 5), (3, 8), (4, 11), (2, 13)),
        ((16, 8), (19, 10), (21, 9), (23, 12)),
        ((8, 4), (6, 2), (12, 2), (15, 3)),
    )
    for n in ((i % 4, (i + 2) % 4) if i % 2 == 0 else (i % 4,)):
        pts = arcs[n]
        for a, c in zip(pts, pts[1:]):
            f.fill(seg(a[0] + 0.5, a[1] + 0.5, c[0] + 0.5, c[1] + 0.5, 0.9), "p", on=".")
        f.px(pts[-1][0], pts[-1][1], "W", on=".p")
    return f.shadow(15, 12)


def ransomware(i):
    """Cage walker: a barred cage on legs with someone's data locked inside."""
    f = Layer()
    t = i / FRAMES
    bob = stride_bob(i)
    hy = 20 + bob
    leg(f, (17, hy), t + 0.5, near=False, l1=4.2, l2=4.4, stride=2.6)
    with part(f, dy=bob, outline=False) as b:              # chain trailing off the back
        for n in range(4):
            x = 5 + round(1.2 * wave(t, n * 0.08) * n / 3)
            b.fill(box(x, 20 + n * 2, x, 21 + n * 2), "h" if n % 2 == 0 else "g")
    with part(f, dy=bob) as b:
        b.fill(box(7, 6, 22, 18), "K")
        cx, cy = 14 + round(3 * wave(t)), 12 + round(2 * wave(2 * t, 0.2))
        b.fill(box(cx - 2, cy - 2, cx + 2, cy + 2), "r")    # the data it has locked away
        b.fill(box(cx - 2, cy - 2, cx + 2, cy - 2), "p")
        b.px(cx - 1, cy - 1, "W")
        for x in range(7, 23, 3):                           # bars
            b.fill(box(x, 6, x, 18), "G")
            b.fill(box(x, 6, x, 9), "h")
        steel(b, box(6, 19, 23, 20), lit=19, shade=20)      # floor rail
        armour(b, poly([(5, 3), (22, 3), (24.9, 6.9), (5, 6.9)]), lit=3, dirty=5)   # roof
        rivets(b, [(7, 5), (12, 5), (17, 5), (22, 5)], on="MD")
        scratch(b, 14, 5, 2)
        b.fill(box(13, 2, 15, 2), "g")
    with part(f, dy=bob) as b:                             # sensor housing on the front
        steel(b, box(23, 9, 27, 13), lit=9, shade=13)
        b.fill(box(25, 10, 27, 11), "K")
        lens(b, 26, 10, i)
    with part(f, dy=bob) as b:                             # padlock on the door
        swing = (0, 1, 1, 0, 0, -1, -1, 0)[i]
        b.fill(box(19 + swing, 12, 22 + swing, 12), "G")
        b.fill(box(19 + swing, 12, 19 + swing, 13), "G")
        b.fill(box(22 + swing, 12, 22 + swing, 13), "G")
        b.fill(box(18 + swing, 14, 23 + swing, 17), "h")
        b.fill(box(18 + swing, 17, 23 + swing, 17), "G")
        b.fill(box(20 + swing, 15, 21 + swing, 16), "K")
    leg(f, (13, hy), t, near=True, l1=4.2, l2=4.4, stride=2.6)
    return f.shadow(15, 12)


UNITS = {
    "worker": worker,
    "virus": virus,
    "worm": worm,
    "firewall": firewall,
    "bruteforcer": bruteforcer,
    "ddos": ddos,
    "botnet": botnet,
    "backdoor": backdoor,
    "injector": injector,
    "maninthemiddle": maninthemiddle,
    "optimiser": optimiser,
    "overclocker": overclocker,
    "ransomware": ransomware,
}


# --- Output ------------------------------------------------------------------

def render(name):
    return [UNITS[name](i).image() for i in range(FRAMES)]


def check(name, frames):
    """Fail loudly if a frame breaks one of the layout rules from the docstring."""
    for n, frame in enumerate(frames):
        px = frame.load()
        for k in range(SIZE):
            for x, y in ((k, 0), (k, SIZE - 1), (0, k), (SIZE - 1, k)):
                if px[x, y][3] != 0:
                    raise SystemExit(f"{name} frame {n}: pixel ({x},{y}) breaks the 1px transparent margin")


def sheet(frames):
    out = Image.new("RGBA", (SIZE * len(frames), SIZE))
    for n, frame in enumerate(frames):
        out.paste(frame, (n * SIZE, 0))
    return out


def piskel(name, frames, fps):
    buf = io.BytesIO()
    sheet(frames).save(buf, format="PNG")
    layer = {
        "name": "Layer 1",
        "opacity": 1,
        "frameCount": len(frames),
        "chunks": [{
            "layout": [[n] for n in range(len(frames))],
            "base64PNG": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(),
        }],
    }
    return {
        "modelVersion": 2,
        "piskel": {
            "name": name,
            "description": "Generated by PixelArt/HackticsUnits/generate_units.py",
            "fps": fps,
            "height": SIZE,
            "width": SIZE,
            "layers": [json.dumps(layer)],
        },
    }


def recolour(frame, mapping):
    lookup = {PALETTE[k][:3]: v for k, v in mapping.items()}
    out = frame.copy()
    out.putdata([(*lookup[p[:3]], p[3]) if p[3] == 255 and p[:3] in lookup else p for p in frame.getdata()])
    return out


def preview(rendered, path, ground_path, fps, scale=4):
    """Animated contact sheet: one row per unit, one column per colour scheme."""
    schemes = [("Raw", None)] + list(TEAM_PREVIEW.items())
    ground = Image.open(ground_path).convert("RGBA") if os.path.exists(ground_path) else None
    pad = 6
    cell = SIZE * scale
    cols = min(5, len(rendered))
    rows = -(-len(rendered) // cols)
    block_w = len(schemes) * cell + pad * 2
    width = cols * block_w + pad
    height = rows * (cell + pad) + pad
    out = []
    for n in range(FRAMES):
        im = Image.new("RGBA", (width, height), (24, 22, 40, 255))
        for idx, (name, frames) in enumerate(rendered.items()):
            bx = pad + (idx % cols) * block_w
            by = pad + (idx // cols) * (cell + pad)
            for s, (_, mapping) in enumerate(schemes):
                tile = (ground.copy() if ground else Image.new("RGBA", (SIZE, SIZE), (216, 255, 244, 255)))
                frame = frames[n] if mapping is None else recolour(frames[n], mapping)
                if s == len(schemes) - 1:                  # last team shown mirrored, as it would face in game
                    frame = frame.transpose(Image.FLIP_LEFT_RIGHT)
                tile.alpha_composite(frame)
                im.paste(tile.resize((cell, cell), Image.NEAREST), (bx + s * cell, by))
        out.append(im.convert("RGB"))
    if path.lower().endswith(".png"):
        out[0].save(path)
    else:
        out[0].save(path, save_all=True, append_images=out[1:], duration=int(1000 / fps), loop=0)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    types = os.path.normpath(os.path.join(here, "..", "..", "config", "hacktics", "version1", "entities", "types"))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=os.path.join(types, "units"), help="folder to write the sheets into")
    parser.add_argument("--only", nargs="*", help="unit names to generate (default: all)")
    parser.add_argument("--preview", help="write an animated .gif (or first-frame .png) preview to this path")
    parser.add_argument("--frames", help="write every frame of every unit side by side to this .png")
    parser.add_argument("--fps", type=int, default=8, help="playback speed, should match Framerate in the unit json")
    parser.add_argument("--no-write", action="store_true", help="skip writing the sheets, only build previews")
    parser.add_argument("--scale", type=int, default=4, help="pixel size used in the preview")
    args = parser.parse_args()

    names = args.only or list(UNITS)
    rendered = {}
    for name in names:
        rendered[name] = render(name)
        check(name, rendered[name])

    if not args.no_write:
        os.makedirs(args.out, exist_ok=True)
        for name, frames in rendered.items():
            sheet(frames).save(os.path.join(args.out, name + ".png"))
            with open(os.path.join(args.out, name + ".piskel"), "w") as f:
                json.dump(piskel(name, frames, args.fps), f)
        print(f"Wrote {len(rendered)} sheets to {args.out}")

    if args.preview:
        preview(rendered, args.preview, os.path.join(types, "terrain", "ground.png"), args.fps, args.scale)
        print(f"Wrote preview to {args.preview}")

    if args.frames:
        scale = 4
        im = Image.new("RGBA", (FRAMES * SIZE * scale, len(rendered) * SIZE * scale), (216, 255, 244, 255))
        for row, frames in enumerate(rendered.values()):
            strip = recolour_strip(frames, row)
            im.alpha_composite(strip.resize((strip.width * scale, strip.height * scale), Image.NEAREST), (0, row * SIZE * scale))
        im.save(args.frames)
        print(f"Wrote frames to {args.frames}")


def recolour_strip(frames, row):
    """Alternate team colours per row so the frame sheet shows both schemes."""
    mapping = list(TEAM_PREVIEW.values())[row % len(TEAM_PREVIEW)]
    return sheet([recolour(f, mapping) for f in frames])


if __name__ == "__main__":
    main()
