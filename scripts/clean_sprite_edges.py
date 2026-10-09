#!/usr/bin/env python3
"""Remove generator UI leftovers (e.g. Next button) and white matte fringe from sprites."""

from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / "assets" / "sprites"


def keep_only_main(arr: np.ndarray, alpha_thr: int = 15) -> np.ndarray:
    opaque = arr[:, :, 3] > alpha_thr
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
    out = arr.copy()
    out[labels != best_l] = 0
    return out


def clear_next_button(arr: np.ndarray) -> np.ndarray:
    """Remove dark-gray 'Ne/Next' generator chrome touching the right edge."""
    out = arr.copy()
    h, w = out.shape[:2]
    y0, x0 = int(h * 0.70), int(w * 0.55)
    sub = out[y0:, x0:]
    rgb = sub[:, :, :3].astype(np.int16)
    a = sub[:, :, 3]
    dark = (
        (a > 150)
        & (rgb[:, :, 0] > 20)
        & (rgb[:, :, 0] < 110)
        & (np.abs(rgb[:, :, 0] - rgb[:, :, 1]) < 20)
        & (np.abs(rgb[:, :, 0] - rgb[:, :, 2]) < 20)
    )
    whit = (a > 150) & (rgb[:, :, 0] > 210) & (rgb[:, :, 1] > 210) & (rgb[:, :, 2] > 210)
    if int(dark.sum()) < 250:
        return out
    m = dark.copy()
    m[1:] |= dark[:-1]
    m[:-1] |= dark[1:]
    m[:, 1:] |= dark[:, :-1]
    m[:, :-1] |= dark[:, 1:]
    ys, xs = np.where(m | whit)
    if len(xs) == 0 or int(xs.max()) + x0 < w - 2:
        return out
    bw = int(xs.max() - xs.min() + 1)
    bh = int(ys.max() - ys.min() + 1)
    if not (25 <= bw <= 150 and 18 <= bh <= 110):
        return out
    xa = max(0, int(xs.min()) - 6 + x0)
    xb = min(w, int(xs.max()) + 6 + x0)
    ya = max(0, int(ys.min()) - 6 + y0)
    yb = min(h, int(ys.max()) + 6 + y0)
    block = out[ya:yb, xa:xb].copy()
    brgb = block[:, :, :3].astype(np.int16)
    ba = block[:, :, 3]
    kill = (ba > 8) & (
        ((brgb[:, :, 0] < 125) & (np.abs(brgb[:, :, 0] - brgb[:, :, 1]) < 28))
        | ((brgb[:, :, 0] > 185) & (brgb[:, :, 1] > 185) & (brgb[:, :, 2] > 185))
        | (
            (brgb[:, :, 0] > 125)
            & (brgb[:, :, 0] < 205)
            & (np.abs(brgb[:, :, 0] - brgb[:, :, 1]) < 30)
        )
    )
    block[kill] = 0
    out[ya:yb, xa:xb] = block
    return out


def harden_edges(arr: np.ndarray, passes: int = 6) -> np.ndarray:
    out = arr.copy()
    for _ in range(passes):
        a = out[:, :, 3].astype(np.int16)
        rgb = out[:, :, :3].astype(np.int16)
        clear = np.zeros(a.shape, dtype=bool)
        clear[1:] |= a[:-1] < 25
        clear[:-1] |= a[1:] < 25
        clear[:, 1:] |= a[:, :-1] < 25
        clear[:, :-1] |= a[:, 1:] < 25
        clear[0] = True
        clear[-1] = True
        clear[:, 0] = True
        clear[:, -1] = True
        edge = (a > 5) & clear
        r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        mx = np.maximum(np.maximum(r, g), b)
        mn = np.minimum(np.minimum(r, g), b)
        kill = edge & (
            (a < 200)
            | ((mn > 150) & ((mx - mn) < 35))
            | ((r > 230) & (g > 230) & (b > 230))
        )
        out[kill] = 0
    return out


def clean_file(path: Path) -> None:
    arr = np.array(Image.open(path).convert("RGBA"))
    arr = clear_next_button(arr)
    arr = keep_only_main(arr)
    arr = harden_edges(arr, passes=6)
    arr = keep_only_main(arr)
    arr[-16:, -16:] = 0
    arr = keep_only_main(arr)
    Image.fromarray(arr).save(path)


def main() -> None:
    for path in sorted(ROOT.rglob("*.png")):
        if path.name.endswith(".prev.png"):
            continue
        clean_file(path)
        print("cleaned", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
