#!/usr/bin/env python3
"""Chroma-key green cutout + de-spill + crop for hires raw sprites → assets/sprites."""
from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "_gen" / "hires2026"
DEST = ROOT / "assets" / "sprites"
TARGET_H = 1440  # 2× prior ~720 — sharper on Retina, still light
PAD = 12


def is_green(r: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
    """True where pixel is chroma green (not blonde/skin/apron)."""
    # Strong green dominance
    return (g > 90) & (g > r + 40) & (g > b + 40) & ((g.astype(np.int16) - np.maximum(r, b)) > 35)


def flood_from_border(mask: np.ndarray) -> np.ndarray:
    """Keep green connected to image border (true bg), leave interior greens (none expected)."""
    h, w = mask.shape
    bg = np.zeros((h, w), dtype=bool)
    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        if mask[0, x]:
            bg[0, x] = True
            q.append((0, x))
        if mask[h - 1, x]:
            bg[h - 1, x] = True
            q.append((h - 1, x))
    for y in range(h):
        if mask[y, 0]:
            bg[y, 0] = True
            q.append((y, 0))
        if mask[y, w - 1]:
            bg[y, w - 1] = True
            q.append((y, w - 1))
    while q:
        y, x = q.popleft()
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not bg[ny, nx]:
                bg[ny, nx] = True
                q.append((ny, nx))
    return bg


def keep_largest(alpha: np.ndarray, thr: int = 20) -> np.ndarray:
    opaque = alpha > thr
    h, w = opaque.shape
    labels = np.zeros((h, w), dtype=np.int32)
    best_l = best_n = cur = 0
    for y in range(h):
        for x in range(w):
            if not opaque[y, x] or labels[y, x]:
                continue
            cur += 1
            q = deque([(y, x)])
            labels[y, x] = cur
            n = 0
            while q:
                cy, cx = q.popleft()
                n += 1
                for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and opaque[ny, nx] and labels[ny, nx] == 0:
                        labels[ny, nx] = cur
                        q.append((ny, nx))
            if n > best_n:
                best_n, best_l = n, cur
    out = alpha.copy()
    out[labels != best_l] = 0
    return out


def despill(rgb: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """Pull green fringe toward neighboring non-green / reduce G channel on edges."""
    out = rgb.astype(np.float32).copy()
    r, g, b = out[:, :, 0], out[:, :, 1], out[:, :, 2]
    a = alpha
    # edge: opaque with nearby transparent
    near_t = np.zeros(a.shape, dtype=bool)
    near_t[1:] |= a[:-1] < 30
    near_t[:-1] |= a[1:] < 30
    near_t[:, 1:] |= a[:, :-1] < 30
    near_t[:, :-1] |= a[:, 1:] < 30
    fringe = (a > 40) & near_t & (g > r + 8) & (g > b + 8)
    # also mild spill anywhere green-tinted near bg
    spill = (a > 40) & (g > 70) & (g > r + 25) & (g > b + 25)
    fix = fringe | spill
    # replace excess green with avg of r,b
    avg = (r + b) * 0.5
    g2 = np.minimum(g, avg + 8)
    out[:, :, 1] = np.where(fix, g2, g)
    # harden very green fringe to transparent
    kill = fringe & (g > r + 45) & (g > b + 45)
    alpha = alpha.copy()
    alpha[kill] = 0
    return out.astype(np.uint8), alpha


def cut_one(src: Path) -> Image.Image:
    im = Image.open(src).convert("RGB")
    arr = np.array(im)
    r, g, b = arr[:, :, 0].astype(np.int16), arr[:, :, 1].astype(np.int16), arr[:, :, 2].astype(np.int16)
    green = is_green(r, g, b)
    # expand green a bit for soft edges
    g2 = green.copy()
    g2[1:] |= green[:-1]
    g2[:-1] |= green[1:]
    g2[:, 1:] |= green[:, :-1]
    g2[:, :-1] |= green[:, 1:]
    bg = flood_from_border(g2)
    alpha = np.where(bg, 0, 255).astype(np.uint8)
    # soft edge: if mostly green-ish and next to bg, lower alpha
    near_bg = np.zeros_like(bg)
    near_bg[1:] |= bg[:-1]
    near_bg[:-1] |= bg[1:]
    near_bg[:, 1:] |= bg[:, :-1]
    near_bg[:, :-1] |= bg[:, 1:]
    soft = (~bg) & near_bg & ((g > r + 15) & (g > b + 15))
    alpha[soft] = 0
    rgb, alpha = despill(arr, alpha)
    alpha = keep_largest(alpha)
    # second harden pass on remaining green fringe
    for _ in range(3):
        a = alpha
        near_t = np.zeros(a.shape, dtype=bool)
        near_t[1:] |= a[:-1] < 20
        near_t[:-1] |= a[1:] < 20
        near_t[:, 1:] |= a[:, :-1] < 20
        near_t[:, :-1] |= a[:, 1:] < 20
        rr, gg, bb = rgb[:, :, 0].astype(np.int16), rgb[:, :, 1].astype(np.int16), rgb[:, :, 2].astype(np.int16)
        kill = (a > 0) & near_t & (gg > rr + 35) & (gg > bb + 35)
        alpha[kill] = 0
    alpha = keep_largest(alpha)
    rgba = np.dstack([rgb, alpha])
    # crop to content
    ys, xs = np.where(alpha > 10)
    if len(xs) == 0:
        raise RuntimeError(f"empty cutout: {src}")
    y0, y1 = max(0, int(ys.min()) - PAD), min(rgba.shape[0], int(ys.max()) + 1 + PAD)
    x0, x1 = max(0, int(xs.min()) - PAD), min(rgba.shape[1], int(xs.max()) + 1 + PAD)
    cropped = Image.fromarray(rgba[y0:y1, x0:x1], "RGBA")
    # scale to target height
    w, h = cropped.size
    if h != TARGET_H:
        nw = max(1, int(round(w * (TARGET_H / h))))
        cropped = cropped.resize((nw, TARGET_H), Image.Resampling.LANCZOS)
    return cropped


def main() -> None:
    mapping = {
        "raw_front.png": DEST / "front.png",
        "raw_quarter.png": DEST / "quarter.png",
        "raw_side.png": DEST / "side.png",
        "raw_back.png": DEST / "back.png",
    }
    turn = [
        ("raw_front.png", "01.png"),
        ("raw_turn22.png", "02.png"),
        ("raw_quarter.png", "03.png"),
        ("raw_turn67.png", "04.png"),
        ("raw_side.png", "05.png"),
    ]
    walk = [f"raw_walk{i:02d}.png" for i in range(1, 7)]

    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "turn").mkdir(exist_ok=True)
    (DEST / "walk").mkdir(exist_ok=True)

    for src_name, dest in mapping.items():
        img = cut_one(RAW / src_name)
        img.save(dest)
        print("wrote", dest.relative_to(ROOT), img.size)

    for src_name, out_name in turn:
        img = cut_one(RAW / src_name)
        dest = DEST / "turn" / out_name
        img.save(dest)
        print("wrote", dest.relative_to(ROOT), img.size)

    for i, src_name in enumerate(walk, start=1):
        img = cut_one(RAW / src_name)
        dest = DEST / "walk" / f"{i:02d}.png"
        img.save(dest)
        print("wrote", dest.relative_to(ROOT), img.size)


if __name__ == "__main__":
    main()
