"""Offline: build assets/sprites25d/eyes_closed.png (two plates, RGBA) from the Q-version smiling-eyes art.

Plate = old-eye footprint filled with inpainted surrounding skin, with the smiling closed eyes from the reference art
Poisson-blended in (colour matched to the sprite's own cheeks), alpha = feathered footprint. Runtime (eyefx) just draws
the plate over the open front pose. Usage: python scripts/build_closed_eyes.py <reference.jpg> [out_dir]"""
import json
import sys

import cv2
import numpy as np

EYES = ((156.0, 210.0), (231.0, 210.0))
HALF = (34, 30)  # plate half size (canvas px)
CLIP = (21.0, 17.0)
DY = 4.0
FIX_SPOTS = ((130, 201, 2), (262, 207, 3))  # (x, y, radius) canvas px: stray old-lash specks outside the footprint


def build(ref_path, sheet_path, out_png, out_json, dy=DY, debug=None, arch=0.26, droop=1.5):
    sheet = cv2.imread(sheet_path, cv2.IMREAD_UNCHANGED)
    base = sheet[0:470, 0:360, :3].copy()
    ref = cv2.imread(ref_path)
    g = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
    sub = g[250:420, 450:850]
    n, lab, st, cen = cv2.connectedComponentsWithStats((sub < 95).astype(np.uint8))
    comps = sorted([(cen[i][0] + 450, i) for i in range(1, n) if st[i, 4] > 300 and st[i, 3] < 40 and 40 < st[i, 2] < 100 and cen[i][1] < 120])
    assert len(comps) == 2, comps
    (cx0, i0), (cx1, i1) = comps
    s = (EYES[1][0] - EYES[0][0]) / (cx1 - cx0)
    H, W = base.shape[:2]
    # footprint of the open eye in the sprite: wide ellipse incl. lash tail / crease, never eating hair
    fp = np.zeros((H, W), np.uint8)
    b_, g_, r_ = [base[..., k].astype(int) for k in range(3)]
    hairlike = (r_ > 205) & (g_ > 150) & (g_ < 218) & (b_ < 175) & (np.abs(r_ - g_) > 25)
    for ex, ey in EYES:
        ell = np.zeros((H, W), np.uint8)
        cv2.ellipse(ell, (int(ex), int(ey - 2)), (int(CLIP[0] * 1.22), int(CLIP[1] * 1.45)), 0, 0, 360, 255, -1)
        inner = np.zeros((H, W), np.uint8)
        cv2.ellipse(inner, (int(ex), int(ey)), (int(CLIP[0] * 0.85), int(CLIP[1] * 0.9)), 0, 0, 360, 255, -1)
        fp |= (((ell > 0) & ((inner > 0) | ~hairlike)).astype(np.uint8) * 255)
    # lash tails reach past the ellipse: grow the footprint through connected dark pixels near the outer corners
    gray0 = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
    dark = (gray0 < 135).astype(np.uint8)
    box = np.zeros((H, W), np.uint8)
    for ex, ey in EYES:
        cv2.rectangle(box, (int(ex - CLIP[0] * 1.38), int(ey - CLIP[1] * 1.3)), (int(ex + CLIP[0] * 1.38), int(ey + CLIP[1] * 0.8)), 1, -1)
    cand = ((dark & box) > 0) | (fp > 0)
    nlab, lab2 = cv2.connectedComponents(cand.astype(np.uint8))
    seeds = np.unique(lab2[fp > 0])
    grown = np.isin(lab2, seeds[seeds > 0])
    fp = np.maximum(fp, cv2.dilate((grown & (dark > 0)).astype(np.uint8) * 255, np.ones((3, 3), np.uint8), iterations=0))
    fp = cv2.morphologyEx(fp, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    fp = cv2.dilate(fp, np.ones((3, 3), np.uint8), iterations=1)
    # smooth skin fill: normalised convolution over clean skin pixels around the footprint
    lum = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY).astype(np.float32)
    hair_d = cv2.dilate(hairlike.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    ring = cv2.dilate(fp, np.ones((3, 3), np.uint8), iterations=7) > 0
    clean = ((lum > 192) & ~hair_d & ring & (fp == 0)).astype(np.float32)
    bf = base.astype(np.float32)
    num = cv2.GaussianBlur(bf * clean[..., None], (0, 0), 5)
    den = cv2.GaussianBlur(clean, (0, 0), 5)[..., None] + 1e-6
    fill = num / den
    # where the ring was too sparse (den tiny) fall back to a wider average
    num2 = cv2.GaussianBlur(bf * clean[..., None], (0, 0), 14)
    den2 = cv2.GaussianBlur(clean, (0, 0), 14)[..., None] + 1e-6
    w = np.clip(den / 0.05, 0, 1)
    fill = fill * w + (num2 / den2) * (1 - w)
    result = base.astype(np.float32).copy()
    f3 = (fp > 0)[..., None]
    result = np.where(f3, fill, result)
    # smiling eyes from the reference art, alpha-composited (their own colours / line weight, scaled to the sprite)
    strokes = np.zeros((H, W), np.uint8)
    # the reference closed eye (left one), sheen removed, then bent into an upward smile arc and mirrored for the right
    ref_fixed = ref.copy()
    cx_l, i_l = comps[0]
    comp = np.zeros(g.shape, np.uint8)
    comp[250:420, 450:850] = (lab == i_l).astype(np.uint8) * 255
    comp = cv2.dilate(comp, np.ones((3, 3), np.uint8), iterations=1)
    cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    core = np.zeros_like(comp)
    cv2.drawContours(core, cnts, -1, 255, -1)  # holes (the white sheen) become part of the stroke
    sheen = ((core > 0) & (g > 85)).astype(np.uint8) * 255
    sheen = cv2.dilate(sheen, np.ones((3, 3), np.uint8), iterations=2)
    ref_fixed = cv2.inpaint(ref_fixed, sheen, 4, cv2.INPAINT_TELEA)
    ys, xs = np.where(core > 0)
    cxr, cyr = xs.mean(), ys.mean()
    (ex0, ey0), (ex1, ey1) = EYES
    M = np.float32([[s, 0, ex0 - cxr * s], [0, s, ey0 + dy - cyr * s]])
    warp_c = cv2.warpAffine(ref_fixed, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    warp_m = cv2.warpAffine(core, M, (W, H), flags=cv2.INTER_AREA).astype(np.float32) / 255.0
    hw = (xs.max() - xs.min()) * s / 2.0
    A, D = arch * 2.0 * hw, droop
    grid_x, grid_y = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    u = (grid_x - ex0) / hw  # left eye: outward = negative x
    uo = np.maximum(0.0, -u)
    shift = A * np.clip(1.0 - u * u, 0.0, None) - D * uo * uo  # content moves up by `shift`
    map_y = (grid_y + shift).astype(np.float32)
    warp_c = cv2.remap(warp_c, grid_x, map_y, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    warp_m = cv2.remap(warp_m, grid_x, map_y, cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    warp_m = np.clip(warp_m, 0, 1)
    flip = np.float32([[-1, 0, ex0 + ex1], [0, 1, 0]])
    layers = [(warp_c, warp_m),
              (cv2.warpAffine(warp_c, flip, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE),
               cv2.warpAffine(warp_m, flip, (W, H), flags=cv2.INTER_CUBIC))]
    for wc, wm in layers:
        a = np.clip(wm, 0, 1)[..., None]
        result = result * (1 - a) + wc.astype(np.float32) * a
        strokes |= cv2.dilate((wm > 0.02).astype(np.uint8) * 255, np.ones((3, 3), np.uint8))
    # tiny leftovers at the outer corners (a dark dot / brown nub of the old lash): local inpaint from neighbours only
    fix = np.zeros((H, W), np.uint8)
    for (fx, fy, r) in FIX_SPOTS:
        cv2.circle(fix, (fx, fy), r, 255, -1)
    result_u8 = np.clip(result, 0, 255).astype(np.uint8)
    result_u8 = cv2.inpaint(result_u8, fix, 3, cv2.INPAINT_TELEA)
    result = result_u8.astype(np.float32)
    result = np.clip(result, 0, 255).astype(np.uint8)
    alpha = cv2.GaussianBlur(np.maximum(fp, strokes), (0, 0), 1.0)
    plates, meta = [], []
    for ex, ey in EYES:
        x0, y0 = int(ex) - HALF[0], int(ey) - HALF[1]
        rgb = result[y0:y0 + 2 * HALF[1], x0:x0 + 2 * HALF[0]]
        a = alpha[y0:y0 + 2 * HALF[1], x0:x0 + 2 * HALF[0]]
        plates.append(np.dstack([rgb, a]))
    out = np.concatenate(plates, axis=1)
    cv2.imwrite(out_png, out)
    json.dump({"half": HALF, "eyes": EYES, "scale": s, "plates": 2}, open(out_json, "w"))
    if debug:
        cv2.imwrite(debug, result)
    return s


if __name__ == "__main__":
    ref = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "assets/sprites25d"
    print(build(ref, "assets/sprites25d/idle_front.png", out + "/eyes_closed.png", out + "/eyes_closed.json",
                debug="/tmp/closed_full.png"))
