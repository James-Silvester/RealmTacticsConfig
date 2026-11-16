#!/usr/bin/env python3
"""The bare-frame worker drawn in nine overall styles, to pick one look for every unit.

    python3 PixelArt/HackticsUnits/worker_style_samples.py     # writes samples/worker_styles.gif

Each style is shown facing right in Team 1 colours and mirrored to face left in
Team 2 colours. Nothing here touches the game files.
"""
import os
import warnings

from PIL import Image, ImageDraw, ImageFont, ImageOps

import generate_units as g
from generate_units import FRAMES, Layer, all_of, box, ell, poly, seg
from worker_side_samples import foot_offset, grime, knee_for, rivets, scratch, smoke, stride_bob

warnings.filterwarnings("ignore", category=DeprecationWarning)

# Extra fixed colours used by single styles
g.PALETTE.update({
    "u": (118, 66, 46, 255),    # rust
    "U": (76, 44, 38, 255),     # deep rust
})

BASE = dict(
    outline="K",            # colour of the outline drawn round every part
    tube="G", tube_hi="h", tube_w=1.6,
    block="g", fins="G",
    far="g", thigh="G", shin="G", piston="h", foot="g", joint="h",
    leg_w=(3.0, 2.2), bones=(5.0, 5.4), stride=3.0, foot_w=2, hip_y=18,
    plate="M", head="G", cover=False, thigh_plate=False,
    rust=False, glow=False, rim=False, heavy=0, smoke=True,
)

CAGE = (((8, 6), (18, 6)), ((8, 6), (6, 18)), ((18, 6), (22, 12)), ((22, 12), (20, 19)), ((6, 18), (20, 19)),
        ((8, 6), (20, 19)))


class spart:
    """Like unit_samples.part, but applies the style's outline, rust and rim light."""

    def __init__(self, frame, st, dx=0, dy=0, outline=True, weather=True):
        self.frame, self.st, self.dx, self.dy, self.outlined, self.weather = frame, st, dx, dy, outline, weather

    def __enter__(self):
        self.layer = Layer()
        return self.layer

    def __exit__(self, *exc):
        layer, st = self.layer, self.st
        size, res = g.SIZE, g.RES
        if st["rust"] and self.weather:
            for y in range(size):
                for x in range(size):
                    lx, ly, c = x // res, y // res, layer.g[y][x]
                    if c in "Gh" and (lx * 5 + ly * 3) % 13 < 3:
                        layer.g[y][x] = "u"
                    elif c == "g" and (lx * 3 + ly * 7) % 11 < 2:
                        layer.g[y][x] = "U"
                    elif c == "M" and (lx * 7 + ly * 5) % 17 < 2:
                        layer.g[y][x] = "G"                # paint chipped back to metal
        if st["rim"]:
            for y in range(size):
                for x in range(size):
                    if layer.g[y][x] == "g" and (y == 0 or layer.g[y - 1][x] == "."):
                        layer.g[y][x] = "h" if (x == 0 or layer.g[y][x - 1] == ".") else "G"
        if self.outlined:
            layer.outline(st["outline"])
        self.frame.over(layer, self.dx, self.dy)


def styled_leg(f, hip, phase, near, st):
    l1, l2 = st["bones"]
    w1, w2 = st["leg_w"]
    ox, oy = foot_offset(phase, st["stride"], 2.6)
    ankle = (hip[0] + 1.5 + ox, 26.0 - oy)
    knee = knee_for(hip, ankle, l1, l2)
    fx, fy = round(ankle[0]), round(ankle[1])
    fw = st["foot_w"]
    with spart(f, st, weather=False) as b:
        b.fill(seg(*hip, *knee, w1), st["thigh"] if near else st["far"])
        b.fill(seg(*knee, *ankle, w2), st["shin"] if near else st["far"])
        if near and st["piston"]:
            b.fill(seg(knee[0] + 1.4, knee[1] - 0.4, ankle[0] + 1.0, ankle[1] - 2.2, 1.0), st["piston"])
        b.fill(box(fx - 2, fy + 1, fx + 1 + fw, fy + 2), st["foot"] if near else st["far"])
        if near:
            b.fill(box(fx + fw, fy + 1, fx + 1 + fw, fy + 1), st["joint"])
    if near:
        if st["thigh_plate"]:
            with spart(f, st) as b:
                mx, my = hip[0] + (knee[0] - hip[0]) * 0.62, hip[1] + (knee[1] - hip[1]) * 0.62
                b.fill(seg(hip[0], hip[1], mx, my, 4.4), "M")
                b.fill(seg(hip[0] + 1.2, hip[1] + 1.2, mx + 1.2, my + 1.2, 1.4), "D", on="M")
        f.fill(ell(knee[0], knee[1], 1.3, 1.3), st["joint"])
        f.px(knee[0] - 0.5, knee[1] - 0.5, "r" if st["glow"] else "K")


def bare_frame(i, **changes):
    st = dict(BASE)
    st.update(changes)
    f = Layer()
    p = i / FRAMES
    bob = stride_bob(i)
    hy = st["hip_y"] + bob
    w = st["tube_w"]
    heavy = int(st["heavy"])                               # -1 slighter, 0 normal, 1 bulkier

    styled_leg(f, (15.5, hy), p + 0.5, False, st)

    with spart(f, st, dy=bob) as b:                        # roll cage
        for a, c in CAGE:
            b.fill(seg(*a, *c, w), st["tube"])
        b.fill(seg(8, 5.5, 18, 5.5, 0.8), st["tube_hi"])
        if st["glow"]:                                     # power running through the frame
            b.fill(seg(8, 6, 20, 19, 0.8), "r")
            b.fill(seg(18, 6, 22, 12, 0.8), "r")
            n = i % 4
            b.px(9 + n * 3, 7 + n * 3.2, "W")

    with spart(f, st, dy=bob) as b:                        # engine block
        b.fill(box(9 - heavy, 10 - heavy, 16, 17), st["block"])
        for y in (11, 13, 15):
            b.fill(box(10 - heavy, y, 15, y), st["fins"])
        b.fill(box(17, 12, 18, 16), st["block"])
        b.px(17, 13, st["tube_hi"])
        if st["glow"]:
            b.fill(box(11, 12, 14, 15), "r")
            b.fill(box(12, 13, 13, 14), "W" if i % 4 < 2 else "p")
        else:
            b.fill(box(11, 16, 14, 16), "r" if i % 4 < 2 else "q")

    if st["cover"]:                                        # painted engine cover
        with spart(f, st, dy=bob) as b:
            cover = poly([(7, 11), (13, 10), (13, 18), (6, 18)])
            b.fill(cover, "M")
            b.fill(all_of(cover, box(0, 17, 31, 31)), "D")
            grime(b, all_of(cover, box(0, 15, 31, 16)))
            rivets(b, [(8, 12), (11, 12), (8, 16)], on="M")
            scratch(b, 9, 15, 2)

    with spart(f, st, dy=bob) as b:                        # shoulder plate
        shape = poly([(12 - heavy, 3), (21, 4), (24 + heavy, 10), (15 - heavy, 9 + heavy)])
        if st["plate"] == "stripe":                        # dark plate with one painted band
            b.fill(shape, "g")
            b.fill(all_of(shape, box(17, 0, 19, 31)), "M")
        else:
            b.fill(shape, "M")
            b.fill(all_of(shape, box(0, 0, 31, 4)), "L")
            grime(b, all_of(shape, box(0, 7, 31, 31)))
            scratch(b, 16, 8, 3)
            rivets(b, [(14, 5), (20, 6)], on="ML")

    with spart(f, st, dy=bob) as b:                        # sensor on a stalk
        b.fill(seg(21, 13, 25, 11.5, max(1.2, w)), st["tube"] if st["tube"] != "D" else "g")
        b.fill(box(24 - heavy, 8 - heavy, 28, 12), st["head"])
        b.fill(box(24 - heavy, 8 - heavy, 28, 8 - heavy), "L" if st["head"] == "M" else st["tube_hi"])
        b.fill(box(26, 10, 28, 11), "K")
        b.px(27, 10, "r")
        b.px(28, 10, "W" if i % 4 < 2 else "p")

    with spart(f, st, dy=bob) as b:                        # grab claw
        grip = (0, 0, 1, 1, 0, 0, 1, 1)[i]
        b.fill(seg(19, 17, 25, 19, max(1.4, w + 0.2)), st["far"] if st["tube"] != "D" else "D")
        b.fill(seg(25, 19, 28, 18 - grip, max(0.9, 1.0 + heavy * 0.6)), st["joint"])
        b.fill(seg(25, 19, 28, 21 + grip, max(0.9, 1.0 + heavy * 0.6)), st["joint"])

    styled_leg(f, (12, hy), p, True, st)

    if st["glow"]:                                         # light spilling onto the ground
        for x in (10, 13, 16):
            f.px(x + i % 2, 27, "q", on=".")
    if st["smoke"]:
        smoke(f, 8, 5 + bob, i, drift=-4.0, rise=4.0)
    return f.shadow(15, 11)


STYLES = [
    ("As picked", "Steel frame, one team plate, black outline", dict()),
    ("Team paint", "Frame and covers painted in team colours", dict(
        tube="D", tube_hi="M", cover=True, thigh_plate=True, head="M")),
    ("Rusted", "Corroded steel, chipped paint", dict(rust=True)),
    ("Silhouette", "Near-black machine picked out by rim light", dict(
        tube="g", tube_hi="G", fins="g", thigh="g", shin="g", piston=None, joint="G", head="g", plate="stripe",
        rim=True, smoke=False)),
    ("Powered", "Dark frame with glowing conduits and core", dict(
        tube="g", tube_hi="G", fins="g", thigh="g", shin="g", joint="G", head="g", glow=True, smoke=False)),
    ("Spindly", "Thin tubing, long insect legs", dict(
        tube_w=1.0, leg_w=(1.6, 1.3), bones=(5.6, 5.9), stride=3.4, foot_w=1, hip_y=17, piston=None, heavy=-1)),
    ("Heavy", "Thick tubing, big feet, bulkier block", dict(
        tube_w=2.4, leg_w=(3.8, 3.0), bones=(4.8, 5.2), stride=2.6, foot_w=3, heavy=1)),
    ("Soft outline", "Dark steel outlines instead of black", dict(outline="g")),
    ("Fine detail", "Same design at 64px, double resolution", dict()),
]
HI_RES = {"Fine detail"}


def render(name, changes):
    if name in HI_RES:
        g.SIZE, g.RES = 64, 2
    try:
        frames = [bare_frame(i, **changes).image() for i in range(FRAMES)]
        g.check(name, frames)
    finally:
        g.SIZE, g.RES = 32, 1
    return frames


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ground = Image.open(os.path.normpath(os.path.join(
        here, "..", "..", "config", "hacktics", "version1", "entities", "types", "terrain", "ground.png"))).convert("RGBA")
    font = ImageFont.load_default(size=15)
    small = ImageFont.load_default(size=11)
    teams = list(g.TEAM_PREVIEW.values())

    rendered = [(name, note, render(name, changes)) for name, note, changes in STYLES]

    tile, cols, pad, label = 192, 3, 10, 40
    cell_w, cell_h = tile * 2 + pad, tile + label + pad
    rows = -(-len(rendered) // cols)
    out = []
    for n in range(FRAMES):
        im = Image.new("RGBA", (cols * cell_w + pad, rows * cell_h + pad), (24, 22, 40, 255))
        pen = ImageDraw.Draw(im)
        for idx, (name, note, frames) in enumerate(rendered):
            x = pad + (idx % cols) * cell_w
            y = pad + (idx // cols) * cell_h
            pen.text((x, y), f"{idx + 1}  {name}", fill=(235, 235, 245, 255), font=font)
            pen.text((x, y + 20), note, fill=(150, 150, 170, 255), font=small)
            for k, mapping in enumerate(teams):
                sprite = g.recolour(frames[n], mapping)
                if k == 1:
                    sprite = ImageOps.mirror(sprite)
                bg = ground.resize(sprite.size, Image.NEAREST)
                bg.alpha_composite(sprite)
                im.paste(bg.resize((tile, tile), Image.NEAREST), (x + k * tile, y + label))
        out.append(im.convert("RGB"))

    out_dir = os.path.join(here, "samples")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "worker_styles.gif")
    out[0].save(path, save_all=True, append_images=out[1:], duration=125, loop=0)
    out[0].save(os.path.join(out_dir, "worker_styles.png"))
    print("Wrote", path)


if __name__ == "__main__":
    main()
