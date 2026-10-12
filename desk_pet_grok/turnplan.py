"""Qt-free planning for the part-rig turn: per-part yaw (head leads, trunk follows, tail trails) and which key
view images (with opacity) each part shows. Used by the runtime (partturn.py) and by the QA script."""

from __future__ import annotations

KEYS = (0.0, 4.0, 22.5, 33.0, 56.0, 67.5, 78.0, 90.0)
BAND = 3.0  # deg half-width of the (<=3 frame) crossfade around the midpoint between key views
HARD = ('tail', 'head')  # hard swap: the head carries the hairpin / eyes, a crossfade would double them
TAIL_BAND = 0.01  # tail swaps hard (it is hidden behind the body at the swap), no double tail
LEAD = {"head": (0.05, 0.97), "trunk": (0.0, 1.0), "tail": (-0.08, 0.92)}  # (offset, span) of tp -> eased yaw


EASE_MIX = 0.15  # 1 = smoothstep, 0 = linear; gentler start/stop keeps per-frame yaw steps small


def _ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return EASE_MIX * x * x * (3.0 - 2.0 * x) + (1.0 - EASE_MIX) * x


def part_yaw(part: str, tp: float) -> float:
    off, span = LEAD[part]
    return 90.0 * _ease((tp + off) / span)


IOU_BLEND = 0.8  # neighbouring registered keys blend only where their silhouettes agree at least this much; else hard swap


def views_for(yaw: float, band: float = BAND, ious: list[float] | None = None) -> list[tuple[int, float]]:
    """[(key index, opacity)] drawn in order (first fully opaque, optional second blended on top)."""
    yaw = max(0.0, min(90.0, yaw))
    for i in range(len(KEYS) - 1):
        a, b = KEYS[i], KEYS[i + 1]
        if yaw <= b or i == len(KEYS) - 2:
            mid = 0.5 * (a + b)
            band = min(band, mid - a)  # never start blending before the first key view is reached
            if i > 0 and ious is not None and ious[i] < IOU_BLEND:
                band = 0.01
            if yaw < mid - band:
                return [(i, 1.0)]
            if yaw > mid + band:
                return [(i + 1, 1.0)]
            t = (yaw - (mid - band)) / (2 * band)
            t = t * t * (3.0 - 2.0 * t)
            return [(i, 1.0), (i + 1, t)]
    return [(len(KEYS) - 1, 1.0)]


def plan(tp: float, pair_iou: dict | None = None) -> dict[str, list[tuple[int, float]]]:
    return {p: views_for(part_yaw(p, tp), TAIL_BAND if p in HARD else BAND, (pair_iou or {}).get(p)) for p in LEAD}


def lerp_keys(yaw: float, values: list[float]) -> float:
    """Piecewise-linear interpolation of a per-key value over the key yaws (continuous anchor path for a part)."""
    yaw = max(0.0, min(90.0, yaw))
    for i in range(len(KEYS) - 1):
        if yaw <= KEYS[i + 1]:
            t = (yaw - KEYS[i]) / (KEYS[i + 1] - KEYS[i])
            return values[i] + (values[i + 1] - values[i]) * t
    return values[-1]


def xform(ext: list[list[float]], yaw: float, vi: int) -> tuple[float, float, float]:
    """Landmark registration along x for part view `vi` at part-yaw `yaw`: the part's left/right extent landmarks are mapped to the
    smooth (piecewise-linear over the key yaws) extent trajectory, so neighbouring key views have the same silhouette width and
    centre at their swap point. Returns (target centre, x scale, source centre) in canvas px."""
    cs = [0.5 * (a + b) for a, b in ext]
    ws = [max(b - a, 1.0) for a, b in ext]
    return lerp_keys(yaw, cs), lerp_keys(yaw, ws) / ws[vi], cs[vi]
