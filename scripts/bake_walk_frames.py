#!/usr/bin/env python3
"""Bake assets/sprites/walk/01..06.png from side.png (masked dual-leg hip swing).

Skirt stays on the upper layer so the hip join is covered. Re-run after
replacing side.png. Does not change front/back sprites.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SIDE = ROOT / "assets" / "sprites" / "side.png"
OUT = ROOT / "assets" / "sprites" / "walk"

LEG_Y = 505
OVERLAP = 18
PAD = 48
SWINGS = [10, 26, 16, -10, -26, -16]


def main() -> None:
    src = Image.open(SIDE).convert("RGBA")
    w, h = src.size
    upper = src.crop((0, 0, w, LEG_Y + OVERLAP))
    legs_full = np.array(src.crop((0, LEG_Y, w, h)))
    lh, lw = legs_full.shape[:2]
    alpha = legs_full[:, :, 3].astype(np.float32)
    xs = np.arange(lw)

    back = legs_full.copy()
    front = legs_full.copy()
    for y in range(lh):
        t = y / max(1, lh - 1)
        bw = np.clip((228 - xs) / 28.0, 0, 1) ** (0.5 + 1.0 * t)
        fw = np.clip((xs - 200) / 32.0, 0, 1) ** (0.5 + 1.0 * t)
        if t < 0.2:
            bw = np.maximum(bw, 0.55)
            fw = np.maximum(fw, 0.55)
        back[y, :, 3] = (alpha[y] * bw).astype(np.uint8)
        front[y, :, 3] = (alpha[y] * fw).astype(np.uint8)

    back_img = Image.fromarray(back)
    front_img = Image.fromarray(front)
    ys, xs_o = np.where(alpha[:25] > 40)
    hip_x = int(xs_o.mean()) if len(xs_o) else lw // 2

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()

    cw, ch = w + PAD * 2, h + PAD * 2 + 12

    def rot_leg(img: Image.Image, angle: float):
        pad = 60
        iw, ih = img.size
        big = Image.new("RGBA", (iw + pad * 2, ih + pad * 2), (0, 0, 0, 0))
        big.paste(img, (pad, pad), img)
        cx, cy = pad + hip_x, pad + 4
        out = big.rotate(angle, resample=Image.BICUBIC, center=(cx, cy))
        return out, cx, cy

    for i, swing in enumerate(SWINGS):
        ang_f = float(swing)
        ang_b = -0.9 * float(swing)
        bob = -4 if abs(swing) >= 24 else (-2 if abs(swing) >= 14 else 0)
        lift_f = 10 if abs(swing) >= 24 else (4 if abs(swing) >= 14 else 0)

        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        ox, oy = PAD, PAD + 6
        bimg, bcx, bcy = rot_leg(back_img, ang_b)
        fimg, fcx, fcy = rot_leg(front_img, ang_f)

        def paste(limg, lcx, lcy, yn=0):
            px = ox + hip_x - lcx
            py = oy + LEG_Y + yn - lcy
            canvas.alpha_composite(limg, (int(px), int(py)))

        paste(bimg, bcx, bcy, yn=2)
        paste(fimg, fcx, fcy, yn=-lift_f)
        canvas.alpha_composite(upper, (ox, oy + bob))
        canvas.save(OUT / f"{i + 1:02d}.png")
        print(f"{i + 1:02d}.png F={ang_f:+.0f} B={ang_b:+.0f}")


if __name__ == "__main__":
    main()
