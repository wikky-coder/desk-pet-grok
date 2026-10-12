"""EXPERIMENTAL part-rig turn: head / trunk / tail each swap between existing key-view images on their own yaw
schedule (turnplan.py: head leads, trunk follows, tail trails) with a <=3-frame blend, no whole-image morph.
Off by default (menu: 实验：部件转身). The pre-rendered flow-morph sheet turn is still smoother (see docs)."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage, QPainter

from desk_pet_grok import turnplan

TURN_DIR = Path(__file__).resolve().parents[1] / "assets" / "rig25d" / "turn"


def available(root: Path | None = None) -> bool:
    return ((Path(root) if root else TURN_DIR) / "turn.json").is_file()


class TurnRig:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else TURN_DIR
        j = json.loads((self.root / "turn.json").read_text())
        self.cw, self.ch = j["canvas"]
        self.neck = j["neck"]
        self.views = j["views"]
        self.pair_iou = j.get("pair_iou")
        self._src: dict[tuple[int, str], QImage] = {}
        for i, v in enumerate(self.views):
            for part, d in v["parts"].items():
                self._src[(i, part)] = QImage(str(self.root / d["file"])).convertToFormat(
                    QImage.Format.Format_ARGB32_Premultiplied)
        self._scaled: dict[tuple[int, str], QImage] = {}
        self._scaled_h = 0

    def _get(self, key: tuple[int, str], ph: int) -> QImage:
        if ph != self._scaled_h:
            self._scaled.clear()
            self._scaled_h = ph
        im = self._scaled.get(key)
        if im is None:
            k = ph / self.ch
            src = self._src[key]
            im = src.scaled(max(1, round(src.width() * k)), max(1, round(src.height() * k)),
                            Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self._scaled[key] = im
        return im

    def paint(self, p: QPainter, w: int, h: int, dpr: float, tp: float, head_deg: float = 0.0) -> None:
        ph = max(1, int(h * dpr))
        kl = h / self.ch
        plan = turnplan.plan(tp, self.pair_iou)
        nx, ny = self.neck
        for part in ("tail", "trunk", "head"):
            ext = [v["parts"][part].get("ext") for v in self.views]
            yaw = turnplan.part_yaw(part, tp)
            for vi, op in plan[part]:
                d = self.views[vi]["parts"][part]
                im = self._get((vi, part), ph)
                im.setDevicePixelRatio(dpr)
                p.save()
                if part == "head" and head_deg:
                    p.translate(nx * kl, ny * kl)
                    p.rotate(head_deg)
                    p.translate(-nx * kl, -ny * kl)
                if part != "tail" and all(ext):
                    # landmark registration: map this key view's silhouette extent to the smooth extent trajectory
                    tc, sx, sc = turnplan.xform(ext, yaw, vi)
                    p.translate(tc * kl, 0)
                    p.scale(sx, 1.0)
                    p.translate(-sc * kl, 0)
                p.setOpacity(op)
                p.drawImage(QPointF(d["x"] * kl, d["y"] * kl), im)
                p.restore()
