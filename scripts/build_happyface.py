#!/usr/bin/env python3
"""Cut the generated happy face (raw_<name>.png) into assets/rig25d/face_happy.png, pixel-aligned with head_base.png.
usage: build_happyface.py <raw name> ; writes the layer + before/after sheets to _gen25d/rounds/happyface/."""
from __future__ import annotations
import sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
HB = ROOT / "assets/rig25d/head_base.png"
FRONT = ROOT / "_gen/hires2026/raw_front.png"
RAWDIR = ROOT / "_gen/happy"
M = np.load(ROOT / "_gen/happy/hb2raw.npy")  # head_base px -> raw_front px (SIFT + RANSAC similarity)
# face box in head_base px: eyes+cheeks+mouth (x, y of the head layer)
def face_mask(shape, alpha):
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy, rx, ry = 0.5 * w + 3, 345.0, 215.0, 98.0
    d = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
    m = np.clip((1.0 - d) / 0.35, 0, 1)   # feathered edge
    m = m * m * (3 - 2 * m)
    return m * (alpha > 0.9)
def main():
    name = sys.argv[1]
    dest = sys.argv[2] if len(sys.argv) > 2 else "face_happy"  # asset name; F6 moods: face_<mood>, raw in _gen/f6
    rawdir = ROOT / "_gen/f6" if dest != "face_happy" else RAWDIR
    out = ROOT / ("_gen25d/rounds/f6" if dest != "face_happy" else "_gen25d/rounds/happyface"); out.mkdir(parents=True, exist_ok=True)
    hb = np.array(Image.open(HB).convert("RGBA")); H, Wd = hb.shape[:2]
    a0 = cv2.imread(str(FRONT)); a1 = cv2.imread(str(rawdir / f"raw_{name}.png"))
    g0 = cv2.cvtColor(a0, cv2.COLOR_BGR2GRAY).astype(np.float32); g1 = cv2.cvtColor(a1, cv2.COLOR_BGR2GRAY).astype(np.float32)
    # residual registration of the generated image onto raw_front, on the head area minus the face band
    W = np.eye(2, 3, dtype=np.float32)
    msk = np.zeros(g0.shape, np.uint8); msk[60:1500] = 255; msk[900:1250, 250:1450] = 0
    _, W = cv2.findTransformECC(g0, g1, W, cv2.MOTION_AFFINE, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-7), msk, 5)
    a1r = cv2.warpAffine(a1, W, (a1.shape[1], a1.shape[0]), flags=cv2.INTER_CUBIC + cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
    print("ECC residual", W.round(4).tolist())
    def to_head(img):
        return cv2.warpAffine(img, M, (Wd, H), flags=cv2.INTER_AREA | cv2.WARP_INVERSE_MAP)
    h0, h1 = to_head(a0), to_head(a1r)
    alpha = hb[..., 3].astype(np.float32) / 255
    m = face_mask((H, Wd), alpha)
    # mean-colour match of skin around the mask border (small), computed on a ring outside the changed area
    ring = ((m > 0.02) & (m < 0.6)).astype(bool)
    d = (h1.astype(np.float32) - h0.astype(np.float32))
    corr = d[ring].mean(0) if ring.any() else np.zeros(3)
    print("ring colour offset (BGR)", corr.round(2))
    h1c = np.clip(h1.astype(np.float32) - corr * 0.0, 0, 255)  # offsets are tiny; not applied
    rgba = np.zeros((H, Wd, 4), np.uint8)
    rgba[..., :3] = cv2.cvtColor(h1c.astype(np.uint8), cv2.COLOR_BGR2RGB)
    rgba[..., 3] = np.round(m * 255).astype(np.uint8)
    Image.fromarray(rgba).save(out / f"{dest}_{name}.png" if dest != "face_happy" else ROOT / "assets/rig25d/face_happy.png", optimize=True)
    # comparison sheets
    base = Image.fromarray(hb); base_bg = Image.new("RGBA", base.size, (255, 255, 255, 255)); base_bg.alpha_composite(base)
    happy = base_bg.copy(); happy.alpha_composite(Image.fromarray(rgba))
    sheet = Image.new("RGB", (Wd * 2, H), "white"); sheet.paste(base_bg.convert("RGB"), (0, 0)); sheet.paste(happy.convert("RGB"), (Wd, 0))
    sheet.save(out / f"compare_head_{name}.png")
    box = (130, 250, Wd - 130, 440)
    z = Image.new("RGB", ((box[2] - box[0]) * 2, (box[3] - box[1]) * 2 * 2), "white")
    for i, im in enumerate((base_bg, happy)):
        c = im.convert("RGB").crop(box).resize(((box[2] - box[0]) * 2, (box[3] - box[1]) * 2), Image.LANCZOS)
        z.paste(c, (0, i * c.height))
    z.save(out / f"compare_face_zoom_{name}.png")
    Image.fromarray((m * 255).astype(np.uint8)).save(out / "mask.png")
    Image.fromarray(cv2.cvtColor(np.abs(h1.astype(int) - h0.astype(int)).clip(0, 255).astype(np.uint8), cv2.COLOR_BGR2RGB)).save(out / "diff_head.png")
main()
