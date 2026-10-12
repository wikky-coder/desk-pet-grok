"""Generated lounge art (assets/lounge25d, built by _gen25d/build_lounge.py): belly-down on a ledge, bottom row = ledge.

Poses base / half / yawn / sleep share one frame size and alignment, so they are simply cross-faded:
half = drowsy eyes (droop 0..0.5), sleep = eyes closed (droop 0.5..1), yawn = open mouth (yawn amount).
Per pose frames 0..6 are a breath + tail-sway ping-pong; the base pose also has frames 7..10, an ear flick.
Falls back (caller) to the squashed standing rig when the assets are missing."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPainter

from desk_pet_grok.tailmotion import TailDriver

ROOT = Path(__file__).resolve().parents[1] / "assets" / "lounge25d"
VARIANT_DIR = ROOT / "variants"  # F7: extra lying poses (side / chin / stretch / curl), same json + sheet layout
BREATH_FPS = 6.0
FLICK_FPS = 12.0
FLICK_GAP_S = (7.0, 15.0)
DROP_FRAC = 0.10  # lie_down: sprite starts this fraction of the window height higher and settles onto the ledge
EDGE_UP = 8.0 / 940.0  # the edge line sits this fraction of the window height above the window bottom (lounge_driver.window_target: (FOOT_PAD - SINK) canvas px)
TAIL_SPAN = 19.0  # tailmotion.LIMIT
BASELINE_MIN_FRAC = 0.06  # a row counts as 'body bottom' when this fraction of the frame width is opaque there (ignores tail tips / stray pixels)
FOOT_PAD = 12.0 / 470.0  # window-bottom margin used by the standing sprite (see Pet25D); ledge sits on it minus a small sink


# head-pat zone inside one 640x656 art frame (hair / forehead area, ears excluded); checked against lounge_base frame 0
# whole head incl. ears and the headband (frame x 125..565, y 33..420) plus ~20 % margin, stopping above the forearms (y ~ 470)
HEAD_ZONE_FRAME = (40.0, -45.0, 650.0, 470.0)
PAT_EYES_DELAY_S = 0.35  # ears twitch first with open eyes, then the eyes close happily


def variant_names(root: Path | None = None) -> list[str]:
    """Pose variants whose assets are present (order is stable)."""
    base = Path(root) if root else VARIANT_DIR
    return [n for n in VARIANT_ORDER if (base / n / "lounge.json").is_file()]


VARIANT_ORDER = ("side", "chin", "stretch", "curl")


def available(root: Path | None = None) -> bool:
    return ((Path(root) if root else ROOT) / "lounge.json").is_file()


def _smooth(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def standing_opacity(loaf: float) -> float:
    """The standing rig stays solid until the lying art is nearly in, then drops out underneath it (and the reverse when getting up / falling):
    combined coverage 1 - (1-stand)(1-art) never dips, so the figure never thins out to a few stray face pixels mid hand-off."""
    return 1.0 - _smooth((loaf - 0.45) / 0.2)


def art_opacity(loaf: float) -> float:
    return _smooth((loaf - 0.3) / 0.3)


def coverage(loaf: float) -> float:
    s, a = standing_opacity(loaf), art_opacity(loaf)
    return 1.0 - (1.0 - s) * (1.0 - a)


def overlay_weights(droop: float, yawn: float) -> dict[str, float]:
    """Opacity of each pose layer drawn over the base pose."""
    return {
        "half": max(0.0, min(1.0, droop * 2.0)),
        "sleep": max(0.0, min(1.0, (droop - 0.5) * 2.0)),
        "yawn": max(0.0, min(1.0, yawn * 2.5)),
    }


def pingpong(pos: float, nb: int) -> int:
    n = 2 * (nb - 1)
    p = int(pos) % n
    return p if p <= nb - 1 else n - p


def sink_px(h: float) -> float:
    """Body presses 1-2 px into the edge line, like a cat lying on a table edge."""
    return max(1.0, min(2.0, 0.004 * h))


def ledge_y(h: float, off: float = 0.0, canvas_h: float = 940.0, ph: float | None = None) -> float:
    """Window-local y (logical px) of the art frame's bottom row: the body baseline lands `sink_px` below the edge line."""
    k = h / canvas_h
    return h * (1.0 - EDGE_UP) + sink_px(h) + off * k


def head_zone(w: float, h: float, fw: float = 640.0, fh: float = 656.0, canvas_h: float = 940.0,
              zone=HEAD_ZONE_FRAME, off: float = 0.0) -> tuple[float, float, float, float]:
    """Head-pat zone (x0, y0, x1, y1) in window-local logical px for the lying pose (frame centred, bottom row = ledge)."""
    k = h / canvas_h
    ledge = ledge_y(h, off, canvas_h)
    left = (w - fw * k) / 2.0
    top = ledge - fh * k
    x0, y0, x1, y1 = left + zone[0] * k, top + zone[1] * k, left + zone[2] * k, top + zone[3] * k
    return (max(0.0, x0), max(0.0, y0), min(float(w), x1), min(float(h), y1))


class LoungeArt:
    def __init__(self, root: Path | None = None, rng: random.Random | None = None) -> None:
        self.root = Path(root) if root else ROOT
        j = json.loads((self.root / "lounge.json").read_text())
        self.fw, self.fh, self.cols, self.nb = j["fw"], j["fh"], j["cols"], j["breath_frames"]
        self.canvas = j["canvas_ref"]
        self.head_zone_frame = tuple(j["head_zone"]) if j.get("head_zone") else HEAD_ZONE_FRAME
        self.variant = j.get("variant", "base")
        self._src: dict[str, QImage] = {}
        for name, meta in j["poses"].items():
            im = QImage(str(self.root / meta["file"]))
            if im.isNull():
                raise RuntimeError(f"cannot read {meta['file']}")
            self._src[name] = im.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        if "base" not in self._src:
            raise RuntimeError("base pose missing")
        self._scaled: dict[str, QImage] = {}
        self._scaled_ph = 0
        self.runtime_breath = j.get("breath") == "runtime"  # rest frames only: breathing is a painter scale, the tail is a separate crop layer
        self.tail_meta = j.get("tail")
        self._tail_src: QImage | None = None
        if self.tail_meta:
            try:
                im = QImage(str(self.root / self.tail_meta["file"]))
                self._tail_src = None if im.isNull() else im.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            except Exception:
                self._tail_src = None
        self.tail_on = True  # 「尾巴摆动增强」: False = the old small regular sway
        self.happy = 0.0
        self.tail_driver = TailDriver(rng)
        self.tail_deg = 0.0
        self.base_off = self._baseline_off()  # rows of the frame below the stable body baseline
        self.has_flick = j["poses"]["base"]["frames"] > self.nb  # ear-flick frames 7..10 exist (not for every variant)
        self.rng = rng or random.Random()
        self.loaf = self.droop = self.yawn = 0.0
        self.phase = 0.0
        self.flick_t = -1.0
        self.next_flick = self.rng.uniform(*FLICK_GAP_S)
        self.t = 0.0
        self.pat = 0.0  # eased head-pat amount from the pet: tail sways faster

    def _baseline_off(self) -> float:
        """Frame rows below the body's stable bottom (>= BASELINE_MIN_FRAC of the width opaque), worst case over the base pose frames."""
        im = self._src["base"]
        n = (im.width() // self.fw) * (im.height() // self.fh)
        need = max(2, int(BASELINE_MIN_FRAC * self.fw))
        worst = 0
        for i in range(min(n, self.nb)):
            x0, y0 = (i % self.cols) * self.fw, (i // self.cols) * self.fh
            for y in range(self.fh - 1, -1, -1):
                cnt = 0
                for x in range(x0, x0 + self.fw, 2):
                    if (im.pixel(x, y0 + y) >> 24) > 128:
                        cnt += 1
                if cnt * 2 >= need:
                    worst = max(worst, self.fh - 1 - y)
                    break
        return float(worst)

    def tail_layer(self) -> bool:
        return self._tail_src is not None

    def breath(self) -> float:
        return -math.cos(2 * math.pi * self.phase / 12.0)

    def tail_index(self) -> int:
        a = self.tail_meta["angles"]
        lo, hi = self.tail_meta.get("limits", (a[0], a[-1]))
        lo, hi = float(lo), float(hi)
        if lo > -0.6 * hi:  # no room to swing one way (tail against the frame edge): use the whole free range, centred in it
            u = (max(-TAIL_SPAN, min(TAIL_SPAN, self.tail_deg)) + TAIL_SPAN) / (2 * TAIL_SPAN)
            d = lo + u * (hi - lo)
        else:
            d = max(lo, min(hi, self.tail_deg))
        step = (a[-1] - a[0]) / (len(a) - 1)
        return max(0, min(len(a) - 1, int(round((d - a[0]) / step))))

    def start_flick(self) -> None:
        """Ear twitch (open-eye frames 7..10) right when a pat starts."""
        if self.has_flick:
            self.flick_t = 0.0

    def set_pose(self, loaf: float, droop: float, yawn: float) -> None:
        self.loaf, self.droop, self.yawn = loaf, droop, yawn

    def step(self, dt: float) -> None:
        dt = max(0.0, min(dt, 0.1))
        self.t += dt
        if self.tail_layer():
            if self.tail_on:
                self.tail_deg = self.tail_driver.step(dt, pat=self.pat, happy=self.happy, asleep=1.0 if self.droop > 0.85 else 0.0)
            else:
                self.tail_deg = -5.0 * math.cos(2 * math.pi * self.phase / 12.0)  # the pre-F8 gentle sway
        self.phase += dt * BREATH_FPS * (1.0 - 0.4 * self.droop) * (1.0 + 1.3 * self.pat)
        if self.flick_t >= 0:
            self.flick_t += dt
            if self.flick_t * FLICK_FPS >= 4:
                self.flick_t = -1.0
                self.next_flick = self.t + self.rng.uniform(*FLICK_GAP_S)
        elif self.has_flick and self.t >= self.next_flick and self.pat < 0.05 and self.droop < 0.05 and self.yawn < 0.05 and self.loaf > 0.9:
            self.flick_t = 0.0

    def frame_index(self, pose: str = "base") -> int:
        if pose == "base" and self.has_flick and self.flick_t >= 0 and self.droop < 0.12 and self.yawn < 0.05:
            return self.nb + min(3, int(self.flick_t * FLICK_FPS))
        if self.runtime_breath:
            return 0
        return pingpong(self.phase, self.nb)

    def state_key(self) -> tuple:
        k = (self.frame_index(), round(self.loaf * 20), round(self.droop * 10), round(self.yawn * 10))
        if self.runtime_breath:
            k += (round(self.breath() * 12), self.tail_index() if self.tail_layer() else 0)
        return k

    def _sheet(self, pose: str, ph: int) -> QImage:
        if ph != self._scaled_ph:
            self._scaled.clear()
            self._scaled_ph = ph
        hit = self._scaled.get(pose)
        if hit is None:
            k = ph / self.canvas[1]
            src = self._tail_src if pose == "~tail" else self._src[pose]
            hit = src.scaled(max(1, round(src.width() * k)), max(1, round(src.height() * k)),
                             Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self._scaled[pose] = hit
        return hit

    def _draw(self, p: QPainter, pose: str, idx: int, ph: int, dpr: float, w: int, h: int, opacity: float, dy: float) -> None:
        if opacity <= 0.003 or pose not in self._src:
            return
        sheet = self._sheet(pose, ph)
        k = ph / self.canvas[1]
        fw, fh = self.fw * k, self.fh * k
        n = self._src[pose].width() // self.fw * (self._src[pose].height() // self.fh)
        idx = min(idx, n - 1)
        # inset 1.5 device px at the top: smooth-scaling the sheet bleeds the previous row's opaque bottom edge (a thin grey
        # line above her head on frames of rows >= 1); the art has >= 16 transparent rows there
        inset = 1.5
        src = QRectF((idx % self.cols) * fw, (idx // self.cols) * fh + inset, fw, fh - inset)
        x = (w * dpr - fw) / 2.0
        ledge = ledge_y(h, self.base_off, self.canvas[1]) * dpr + dy * dpr  # body baseline = edge line + 1-3 px sink (same for every pose)
        p.save()
        p.setOpacity(opacity)
        p.scale(1.0 / dpr, 1.0 / dpr)
        if self.runtime_breath:
            b = self.breath()
            cx = x + fw / 2.0
            p.translate(cx, ledge)
            p.scale(1.0 + 0.004 * b, 1.0 + 0.014 * b)
            p.translate(-cx, -ledge)
        if self.tail_layer():
            p.drawImage(QPointF(x, ledge - fh + inset), self._compose_tail(sheet, src, fw, fh - inset, k, ph, inset))
        else:
            p.drawImage(QPointF(x, ledge - fh + inset), sheet, src)
        p.restore()

    def _compose_tail(self, sheet: QImage, src: QRectF, fw: float, fh: float, k: float, ph: int, inset: float) -> QImage:
        """Rest frame with the tail region replaced (Source) by the crop for the current angle: no ghost of the rest tail."""
        tm = self.tail_meta
        tsheet = self._sheet("~tail", ph)
        out = QImage(max(1, int(math.ceil(fw))), max(1, int(math.ceil(fh))), QImage.Format.Format_ARGB32_Premultiplied)
        out.fill(0)
        q = QPainter(out)
        q.drawImage(QPointF(0, 0), sheet, src)
        bx, by, bw, bh = tm["box"]
        i = self.tail_index()
        g = tm.get("gutter", 0)
        cw, ch = round(bw * k), round(bh * k)
        csrc = QRectF(round(((i % tm["cols"]) * (bw + 2 * g) + g) * k), round(((i // tm["cols"]) * (bh + 2 * g) + g) * k), cw, ch)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        ins = 2.0  # skip the crop's outermost device pixel: it blends with the sheet gutter and would draw a faint line at the box edge
        csrc = QRectF(csrc.x() + ins, csrc.y() + ins, csrc.width() - 2 * ins, csrc.height() - 2 * ins)
        q.drawImage(QPointF(round(bx * k) + ins, round(by * k - inset) + ins), tsheet, csrc)
        q.end()
        return out

    def paint(self, p: QPainter, w: int, h: int, dpr: float, loaf: float, droop: float, yawn: float,
              mult: float = 1.0, sink: float = 0.0) -> None:
        """mult / sink: pose-variant switch (fade the art out while it ducks down by `sink` window heights, or back up)."""
        ph = max(1, int(h * dpr))
        a = art_opacity(loaf) * mult
        dy = -(1.0 - _smooth(loaf)) * DROP_FRAC * h + sink * h  # settles down onto the ledge
        idx = self.frame_index()
        bi = 0 if self.runtime_breath else pingpong(self.phase, self.nb)
        if a < 0.995 and a > 0.003:
            # fade the *composited* pose as one group: base + eye / yawn overlays drawn at `a` each would stack (eyes more opaque than the body)
            grp = QImage(max(1, int(w * dpr)), max(1, int(h * dpr)), QImage.Format.Format_ARGB32_Premultiplied)
            grp.setDevicePixelRatio(dpr)
            grp.fill(0)
            q = QPainter(grp)
            q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            self._draw(q, "base", idx, ph, dpr, w, h, 1.0, dy)
            for pose, wgt in overlay_weights(droop, yawn).items():
                self._draw(q, pose, bi, ph, dpr, w, h, wgt, dy)
            q.end()
            p.save()
            p.setOpacity(p.opacity() * a)
            p.drawImage(0, 0, grp)
            p.restore()
            return
        self._draw(p, "base", idx, ph, dpr, w, h, a, dy)
        for pose, wgt in overlay_weights(droop, yawn).items():
            self._draw(p, pose, bi, ph, dpr, w, h, a * wgt, dy)
