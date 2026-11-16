#!/usr/bin/env python3
"""Generates the Hacktics terrain tiles in the same house style as the units.

    python3 PixelArt/HackticsUnits/generate_terrain.py                       # write sheets + piskel files
    python3 PixelArt/HackticsUnits/generate_terrain.py --preview out.gif     # also write a preview grid
    python3 PixelArt/HackticsUnits/generate_terrain.py --scene out.gif       # also write a mock battlefield
    python3 PixelArt/HackticsUnits/generate_terrain.py --only compute void   # limit to some tiles

Buildings are worn steel with team coloured plating, so a neutral building shows
bare grey plates and a captured one takes its owner's colours. They keep a 1px
transparent margin like the units. Ground, void and the connector are meant to
run into their neighbours, so they are drawn right up to the tile edge.
"""
import argparse
import json
import math
import os
import warnings

from PIL import Image

import generate_units as g
from generate_units import (FRAMES, TAU, Layer, all_of, armour, box, ell, grime, hazard, lens, minus, part, poly, rbox,
                            rivets, scratch, seg, smoke, steel)

warnings.filterwarnings("ignore", category=DeprecationWarning)

# Fixed floor colours. None of these are team greys, so the game never recolours them.
g.PALETTE.update({
    "a": (186, 197, 191, 255),  # floor plate
    "b": (208, 216, 210, 255),  # floor highlight
    "d": (156, 169, 164, 255),  # floor seam
    "e": (172, 184, 178, 255),  # floor stain
    "v": (122, 136, 134, 255),  # floor rivet
    "x": (11, 11, 24, 255),     # void
    "y": (24, 22, 46, 255),     # void crack
    "z": (58, 34, 104, 255),    # void static
})


def octagon(x0, y0, x1, y1, c=3):
    """Chamfered box in inclusive pixel coordinates."""
    x1 += 1
    y1 += 1
    return poly([(x0 + c, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1 - c), (x1 - c, y1), (x0 + c, y1), (x0, y1 - c),
                 (x0, y0 + c)])


def cog(cx, cy, r_in, r_out, teeth, spin):
    def inside(x, y):
        dx, dy = x - cx, y - cy
        r = math.hypot(dx, dy)
        if r <= r_in:
            return True
        if r > r_out:
            return False
        return 0.2 < ((math.atan2(dy, dx) - spin) / (TAU / teeth)) % 1.0 < 0.8
    return inside


# --- Tiles -------------------------------------------------------------------

def ground(i):
    """Worn floor plate. Kept pale so the dark steel units stand out on it."""
    f = Layer()
    f.fill(box(0, 0, 31, 31), "a")
    f.fill(box(0, 0, 31, 0), "b")                          # bevel: lit top and left, seam bottom and right
    f.fill(box(0, 0, 0, 31), "b")
    f.fill(box(0, 31, 31, 31), "d")
    f.fill(box(31, 0, 31, 31), "d")
    for x, y in ((3, 3), (28, 3), (3, 28), (28, 28)):      # corner bolts
        f.px(x, y, "v")
        f.px(x - 1, y - 1, "b")
    for cx, cy, rx, ry in ((9, 21, 5, 3), (23, 9, 4, 3)):  # stains
        grime(f, ell(cx, cy, rx, ry), "e", on="a")
    for k in range(5):                                     # a scratch
        f.px(17 + k, 20 - k, "b", on="ae")
        f.px(18 + k, 20 - k, "d", on="ae")
    f.fill(box(6, 12, 13, 12), "e", on="a")                # faint trace with a via
    f.fill(box(13, 7, 13, 12), "e", on="a")
    f.px(13, 6, "d")
    f.px(5, 12, "d")
    f.fill(box(21, 24, 25, 24), "d", on="a")               # stamped panel mark
    f.px(21, 25, "d", on="a")
    return f


def void(i):
    """Dead space: nothing but cracks and the odd flicker of static."""
    f = Layer()
    f.fill(box(0, 0, 31, 31), "x")
    for a, c in (((4, 6), (9, 10)), ((9, 10), (8, 15)), ((9, 10), (14, 11)), ((20, 22), (25, 20)),
                 ((25, 20), (28, 24)), ((22, 5), (24, 9))):
        f.fill(seg(a[0] + 0.5, a[1] + 0.5, c[0] + 0.5, c[1] + 0.5, 0.8), "y")
    specks = ((5, 24, 0), (12, 4, 3), (18, 16, 5), (27, 11, 2), (15, 27, 6), (26, 28, 1), (3, 14, 4), (21, 2, 7))
    for x, y, ph in specks:
        age = (i + ph) % FRAMES
        if age < 3:
            f.px(x, y, "r" if age == 1 else "z")
    if i in (5, 6):                                        # a line of static tearing across
        f.fill(box(6 + (i - 5) * 3, 19, 13 + (i - 5) * 3, 19), "z")
    return f


def connector(i):
    """Network trunking: steel conduit running off all four sides into a junction box."""
    f = Layer()
    band = ((13, "K"), (14, "h"), (15, "G"), (16, "G"), (17, "g"), (18, "K"))
    for vertical in (False, True):
        for along in range(32):
            for across, colour in band:
                f.px(across if vertical else along, along if vertical else across, colour)
        for along in (4, 5, 26, 27):                       # pipe clamps
            for across in range(12, 20):
                colour = "K" if across in (12, 19) else "h" if along in (4, 26) else "g"
                f.px(across if vertical else along, along if vertical else across, colour)
    for along in range(32):                                # soft shadow below and right of the runs
        f.px(along, 19, "S", on=".")
        f.px(19, along, "S", on=".")
    step = (i * 10) // FRAMES                              # traffic heading out along each arm
    for x, y in ((22 + step, 15), (9 - step, 16), (15, 9 - step), (16, 22 + step)):
        f.px(x, y, "W", on="G")
    for x, y in ((21 + step, 15), (10 - step, 16), (15, 10 - step), (16, 21 + step)):
        f.px(x, y, "p", on="G")
    with part(f) as b:                                     # junction box
        armour(b, octagon(9, 9, 22, 22, 3), lit=10, shade=21, dirty=19)
        rivets(b, [(11, 11), (20, 11), (11, 20), (20, 20)], on="MLD")
        scratch(b, 17, 14, 2)
        b.fill(ell(16, 16, 3.7, 3.7), "K")
        b.fill(ell(16, 16, 2.5, 2.5), "r" if i % 4 < 2 else "q")
        b.fill(box(15, 15, 16, 16), ("W", "p", "q", "p")[i % 4])
    return f


def compute(i):
    """Server cabinet: drive bays chattering away, a fan and a power unit below."""
    f = Layer()
    with part(f) as b:                                     # side of the cabinet
        b.fill(poly([(4, 7), (8, 4), (8, 28), (4, 26)]), "g")
        for y in (10, 14, 18, 22):
            b.fill(box(5, y, 6, y), "G")
    with part(f) as b:
        steel(b, box(8, 4, 26, 27), shade=27)
        b.fill(box(8, 4, 8, 27), "h")
        for k, y in enumerate((9, 13, 17)):                # drive bays
            b.fill(box(10, y, 21, y + 2), "K")
            b.px(11, y + 1, "G")
            for n in range(4):
                state = (i + k * 3 + n * 5) % FRAMES
                colour = "W" if state == 0 else "p" if state < 3 else "r" if state < 5 else None
                if colour:
                    b.px(14 + n * 2, y + 1, colour)
        b.fill(box(23, 9, 25, 19), "g")                    # cable riser
        b.fill(box(24, 9, 24, 19), "r")
        b.px(24, 9 + (i * 11) // FRAMES, "W")
        rivets(b, [(23, 9), (25, 19)], "h")
        b.fill(box(10, 21, 16, 26), "K")                   # fan
        if i % 2:
            b.fill(box(13, 22, 13, 25), "G")
            b.fill(box(11, 23, 15, 24), "G")
        else:
            for k in range(4):
                b.px(11 + k, 22 + k, "G")
                b.px(15 - k, 22 + k, "G")
        b.fill(box(13, 23, 13, 24), "h")
        b.fill(box(18, 21, 25, 26), "g")                   # power unit
        b.fill(box(18, 21, 25, 21), "G")
        b.fill(box(20, 23, 21, 24), "K")
        hazard(b, 18, 26, 25, 26)
        b.px(24, 23, "r" if i % 4 < 2 else "W")
    with part(f) as b:                                     # painted header
        armour(b, rbox(7, 2, 27, 7, 1.5), lit=2, shade=7, dirty=5)
        b.fill(box(10, 4, 16, 5), "K")
        b.px(10 + i % 7, 4, "r")
        b.fill(box(21, 4, 24, 5), "K")
        lens(b, 22, 4, i)
        rivets(b, [(8, 4), (26, 4)], on="ML")
        scratch(b, 17, 6, 2)
    return f.shadow(16, 13)


def encryptor(i):
    """Cipher tower: code wheels turning over an armoured base, emitter on top."""
    f = Layer()
    with part(f) as b:                                     # emitter mast
        b.fill(box(15, 3, 16, 9), "g")
        b.fill(box(13, 5, 18, 5), "h")
        b.fill(box(14, 7, 17, 7), "h")
        b.fill(box(15, 2, 16, 2), "W" if i % 4 < 2 else "r")
    with part(f) as b:                                     # drum of code wheels
        steel(b, rbox(8, 9, 23, 17, 2), lit=9, shade=17)
        b.fill(box(10, 11, 21, 15), "K")
        for row, y in enumerate((11, 13, 15)):
            for n in range(6):
                x = 10 + (n * 2 + (i if row % 2 == 0 else -i)) % 12
                state = (n * 3 + row * 5) % 7
                b.px(x, y, "W" if state == 0 else "p" if state < 3 else "r", on="K")
        rivets(b, [(9, 13), (22, 13)], "h")
    with part(f) as b:                                     # armoured base
        base = octagon(4, 17, 27, 27, 3)
        armour(b, base, lit=17, shade=26, dirty=24)
        b.fill(ell(16, 21, 1.9, 1.9), "K")                 # keyhole
        b.fill(poly([(15.1, 21), (16.9, 21), (17.7, 25.5), (14.3, 25.5)]), "K")
        b.px(15, 20, "r" if i % 4 < 2 else "p")
        for x in (7, 24):                                  # tall firing slits, well clear of the keyhole
            b.fill(box(x, 19, x, 23), "K")
            b.px(x, 19 + (i // 2) % 4, "r")
        rivets(b, [(6, 19), (25, 19), (11, 19), (20, 19)], on="M")
        scratch(b, 9, 24, 3)
        hazard(b, 11, 26, 20, 26, on="D")
    if i % 4 == 0:                                         # scramble pulse leaving the emitter
        for x in (12, 19):
            f.px(x, 2, "p", on=".")
    elif i % 4 == 1:
        for x in (10, 21):
            f.px(x, 3, "q", on=".")
    return f.shadow(16, 13)


def generator(i):
    """Fabricator: a small works turning out programs on a conveyor."""
    f = Layer()
    with part(f) as b:                                     # stack
        b.fill(box(23, 3, 25, 12), "g")
        b.fill(box(23, 3, 23, 12), "G")
        b.fill(box(22, 3, 26, 3), "h")
    with part(f) as b:
        steel(b, box(4, 12, 27, 27), shade=27)
        b.fill(box(4, 12, 4, 27), "h")
        b.fill(box(8, 16, 19, 27), "K")                    # loading door
        b.fill(box(8, 26, 19, 27), "g")                    # conveyor
        for x in range(8, 20):
            if (x - i) % 3 == 0:
                b.px(x, 26, "h")
        x0 = 6 + (i * 13) // FRAMES                        # a finished program riding out
        for y in range(21, 26):
            for x in range(x0, x0 + 5):
                if 8 <= x <= 19:
                    b.px(x, y, "p" if y == 21 else "r")
        if 8 <= x0 + 1 <= 19:
            b.px(x0 + 1, 22, "W")
        b.px(9 + (i * 3) % 10, 17, "W" if i % 2 else "p", on="K")   # assembly flash inside
        hazard(b, 8, 14, 19, 15)
        b.fill(box(22, 15, 25, 18), "K")                   # control window
        b.px(23 + i % 2, 16, "p")
        b.px(24 - i % 2, 17, "r")
        b.fill(cog(23.5, 23, 1.7, 3.2, 6, i / FRAMES * TAU / 6 * 2), "h")
        b.fill(ell(23.5, 23, 1.0, 1.0), "g")
        rivets(b, [(5, 14), (5, 25), (26, 14)], "g")
    with part(f) as b:                                     # sawtooth roof
        for x in (4, 11, 18):
            tooth = poly([(x, 12.9), (x, 6), (x + 7.9, 12.9)])
            armour(b, tooth)
            b.fill(box(x, 6, x, 12), "L", on="M")
            grime(b, all_of(tooth, box(0, 11, 31, 31)))
        b.fill(box(26, 12, 27, 12), "M")
        scratch(b, 13, 11, 2)
    smoke(f, 24.5, 2, i, drift=3.0, rise=1.0)
    return f.shadow(16, 13)


def origin(i):
    """Headquarters: a fortified block cradling a live core, colours flying."""
    f = Layer()
    flap = (0, 1, 1, 0, 0, -1, -1, 0)[i]
    with part(f) as b:                                     # mast and colours
        b.fill(box(25, 2, 25, 14), "g")
        b.fill(poly([(26, 3), (30, 3 + flap), (30, 7.9 + flap), (26, 7.9)]), "M")
        b.fill(seg(26, 3.5, 30, 3.5 + flap, 1.0), "L", on="M")
        b.px(28, 6 + (flap > 0), "D", on="M")
    with part(f) as b:                                     # cradle behind the core
        b.fill(ell(14, 9, 6.8, 6.8), "g")
    pulse = (0, 1, 2, 3, 3, 2, 1, 0)[i] * 0.35
    with part(f, outline=False) as b:                      # the core itself
        b.fill(ell(14, 9, 5.0, 5.0), "r")
        b.fill(ell(14, 9, 3.2 + pulse, 3.2 + pulse), "q")
        b.fill(ell(14, 9, 1.8 + pulse, 1.8 + pulse), "p")
        b.fill(box(13, 8, 14, 9), "W")
        b.fill(box(14, 3, 14, 14), "g")                    # cage ribs
        b.fill(box(8, 9, 20, 9), "G")
        b.px(14, 9, "h")
    with part(f) as b:                                     # fortified base
        base = poly([(2, 28.9), (5, 15), (27, 15), (30, 28.9)])
        armour(b, base, lit=15, shade=27, dirty=25)
        for x0, x1 in ((4, 7), (22, 26)):                  # battlements either side of the core
            b.fill(box(x0, 12, x1, 15), "M")
            b.fill(box(x0, 12, x1, 12), "L")
        b.fill(box(13, 20, 18, 28), "K")                   # gate
        for y in range(21, 28, 2):
            b.fill(box(14, y, 17, y), "r" if (y + i) % 4 < 2 else "q")
        hazard(b, 12, 18, 19, 19)
        for x in (7, 24):                                  # arrow slits
            b.fill(box(x, 18, x, 23), "K")
            b.px(x, 18 + (i + x) % 6, "r")
        b.fill(box(10, 16, 10, 27), "D", on="M")           # plate seams
        b.fill(box(21, 16, 21, 27), "D", on="M")
        rivets(b, [(5, 22), (8, 22), (23, 22), (26, 22), (12, 16), (19, 16)], on="M")
        scratch(b, 6, 26, 3)
        scratch(b, 23, 25, 2)
    return f.shadow(16, 14)


TILES = {
    "ground": ground,
    "void": void,
    "connector": connector,
    "compute": compute,
    "encryptor": encryptor,
    "generator": generator,
    "origin": origin,
}
EDGE_TO_EDGE = {"ground", "void", "connector"}             # allowed to touch the tile edge
STATIC = {"ground"}                                        # one frame is enough


def render(name):
    frames = [TILES[name](i).image() for i in range(1 if name in STATIC else FRAMES)]
    if name not in EDGE_TO_EDGE:
        g.check(name, frames)
    return frames


def frame_at(frames, n):
    return frames[n % len(frames)]


def preview(rendered, floor, path, fps, scale=4):
    """Each tile on the new floor: neutral, then captured by each team."""
    schemes = [None] + list(g.TEAM_PREVIEW.values())
    names = [n for n in rendered if n != "ground"]
    pad, tile = 6, g.SIZE * scale
    cols = 4
    block = len(schemes) * tile + pad * 2
    rows = -(-len(names) // cols)
    out = []
    for n in range(FRAMES):
        im = Image.new("RGBA", (cols * block + pad, rows * (tile + pad) + pad), (24, 22, 40, 255))
        for idx, name in enumerate(names):
            bx = pad + (idx % cols) * block
            by = pad + (idx // cols) * (tile + pad)
            for s, mapping in enumerate(schemes):
                cell = floor.copy()
                frame = frame_at(rendered[name], n)
                cell.alpha_composite(frame if mapping is None else g.recolour(frame, mapping))
                im.paste(cell.resize((tile, tile), Image.NEAREST), (bx + s * tile, by))
        out.append(im.convert("RGB"))
    out[0].save(path, save_all=True, append_images=out[1:], duration=int(1000 / fps), loop=0)


def scene(rendered, floor, path, fps, scale=3):
    """A mock battlefield so terrain and units can be judged together."""
    t1, t2 = g.TEAM_PREVIEW.values()
    layout = [
        "v v . . . . . . v v",
        "v O1c c1c G1. . . v",
        ". c . . c . . E2. .",
        ". C0. . c c c c2C2.",
        ". . . G0. . c . c .",
        "v . . . . . c c O2v",
        "v v . . . . . . v v",
    ]
    codes = {"v": "void", "c": "connector", "O": "origin", "G": "generator", "E": "encryptor", "C": "compute"}
    units = [("worker", 1, 2, 1), ("virus", 4, 2, 1), ("bruteforcer", 2, 4, 1), ("botnet", 5, 1, 1),
             ("ddos", 7, 4, 2), ("maninthemiddle", 5, 5, 2), ("injector", 8, 4, 2), ("firewall", 6, 2, 2)]
    unit_frames = {name: g.render(name) for name, *_ in units}
    rows = [[(row + ' ')[k:k + 2] for k in range(0, len(row), 2)] for row in layout]
    width, height = len(rows[0]), len(rows)
    out = []
    for n in range(FRAMES):
        im = Image.new("RGBA", (width * g.SIZE, height * g.SIZE))
        for y, row in enumerate(rows):
            for x, cell in enumerate(row):
                im.alpha_composite(floor, (x * g.SIZE, y * g.SIZE))
                kind, owner = cell[0], cell[1]
                if kind in codes:
                    frame = frame_at(rendered[codes[kind]], n)
                    if owner in "12":
                        frame = g.recolour(frame, t1 if owner == "1" else t2)
                    im.alpha_composite(frame, (x * g.SIZE, y * g.SIZE))
        for name, x, y, team in units:
            frame = g.recolour(unit_frames[name][n], t1 if team == 1 else t2)
            if team == 2:
                frame = frame.transpose(Image.FLIP_LEFT_RIGHT)
            im.alpha_composite(frame, (x * g.SIZE, y * g.SIZE))
        out.append(im.resize((im.width * scale, im.height * scale), Image.NEAREST).convert("RGB"))
    out[0].save(path, save_all=True, append_images=out[1:], duration=int(1000 / fps), loop=0)
    out[0].save(os.path.splitext(path)[0] + ".png")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    types = os.path.normpath(os.path.join(here, "..", "..", "config", "hacktics", "version1", "entities", "types"))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=os.path.join(types, "terrain"), help="folder to write the sheets into")
    parser.add_argument("--only", nargs="*", help="tile names to generate (default: all)")
    parser.add_argument("--preview", help="write an animated .gif of every tile, neutral and captured")
    parser.add_argument("--scene", help="write an animated .gif of a mock battlefield with units on it")
    parser.add_argument("--fps", type=int, default=8, help="playback speed, should match Framerate in the json")
    parser.add_argument("--no-write", action="store_true", help="skip writing the sheets, only build previews")
    args = parser.parse_args()

    rendered = {name: render(name) for name in TILES}
    floor = rendered["ground"][0]

    if not args.no_write:
        os.makedirs(args.out, exist_ok=True)
        for name in (args.only or list(TILES)):
            frames = rendered[name]
            g.sheet(frames).save(os.path.join(args.out, name + ".png"))
            with open(os.path.join(args.out, name + ".piskel"), "w") as fh:
                json.dump(g.piskel(name, frames, args.fps), fh)
        print(f"Wrote {len(args.only or TILES)} sheets to {args.out}")
    if args.preview:
        preview(rendered, floor, args.preview, args.fps)
        print("Wrote preview to", args.preview)
    if args.scene:
        scene(rendered, floor, args.scene, args.fps)
        print("Wrote scene to", args.scene)


if __name__ == "__main__":
    main()
