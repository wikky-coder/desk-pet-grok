"""Build 32-frame walk loop from 8 key frames via DIS optical-flow warp (not crossfade)."""
import cv2, numpy as np
from pathlib import Path
R = Path(__file__).resolve().parents[1] / "assets/sprites"
H = 1000
def load(p):
    im = cv2.imread(str(p), cv2.IMREAD_UNCHANGED).astype(np.float32) / 255
    s = H / im.shape[0]
    im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    a = im[..., 3:4]; rgb = im[..., :3] * a  # premultiplied
    return np.concatenate([rgb, a], -1)
keys = [load(R / f"walk_keys/{i:02d}.png") for i in range(1, 9)]
dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
dis.setFinestScale(0); dis.setPatchSize(12); dis.setPatchStride(4); dis.setVariationalRefinementIterations(10)
def gray(p):
    bg = 0.5 * (1 - p[..., 3:4])
    g = cv2.cvtColor(np.clip(p[..., :3] + bg, 0, 1).astype(np.float32), cv2.COLOR_BGR2GRAY)
    return (g * 255).astype(np.uint8)
def warp(img, flow, t):
    h, w = img.shape[:2]
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return cv2.remap(img, gx - flow[..., 0] * t, gy - flow[..., 1] * t, cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_CONSTANT, borderValue=0)
out = []
for i in range(8):
    A, B = keys[i], keys[(i + 1) % 8]
    ga, gb = gray(A), gray(B)
    fab = dis.calc(ga, gb, None); fba = dis.calc(gb, ga, None)
    out.append(A)
    for k in (1, 2, 3):
        t = k / 4
        wa = warp(A, fab, t)
        wb = warp(B, fba, 1 - t)
        # fwd-bwd consistency: where flows disagree, blending double-exposes -> use nearer key only
        back = warp(fba, -fab, 1.0)  # fba sampled at x+fab
        err = np.linalg.norm(fab + back, axis=-1)
        bad = cv2.GaussianBlur((err > 2.5).astype(np.float32), (0, 0), 3)[..., None]
        bad = np.clip(bad * 2, 0, 1)
        near = (A if t < .5 else B) if False else (wa if t < .5 else wb)
        f = (1 - bad) * ((1 - t) * wa + t * wb) + bad * near
        out.append(f)
for n, p in enumerate(out, 1):
    a = p[..., 3:4]
    rgb = np.where(a > 1e-3, p[..., :3] / np.maximum(a, 1e-3), 0)
    a = np.where(a < 0.04, 0, a)
    im = np.concatenate([np.clip(rgb, 0, 1), np.clip(a, 0, 1)], -1)
    cv2.imwrite(str(R / f"walk/{n:02d}.png"), (im * 255 + .5).astype(np.uint8))
print(len(out))
