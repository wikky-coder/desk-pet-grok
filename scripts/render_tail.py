"""Tail swing extremes for every lying pose set -> _gen25d/rounds/tail/ (full frames + tail-region zooms)."""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from PIL import Image
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from desk_pet_grok import loungeart

OUT = Path(__file__).resolve().parents[1] / "_gen25d" / "rounds" / "tail"
OUT.mkdir(parents=True, exist_ok=True)
H = 600; W = int(H * 0.7659)
SETS = [("base", None), ("side", "side"), ("chin", "chin"), ("stretch", "stretch")]  # curl: tail wraps in front of the body, no tail layer
ANG = (-18, 0, 18)


def render(art, ang, droop=0.0, yawn=0.0, pose="rest"):
    art.tail_deg = float(ang)
    art.set_pose(1.0, droop, yawn)
    img = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied); img.fill(QColor(236, 238, 242))
    p = QPainter(img); art.paint(p, W, H, 1.0, 1.0, droop, yawn); p.end()
    p = QPainter(img); p.setPen(QColor(255, 0, 0)); y = int(H * (1 - loungeart.EDGE_UP)); p.drawLine(0, y, W, y); p.end()
    f = OUT / "tmp.png"; img.save(str(f)); return Image.open(f).convert("RGB")


def main():
    rows = []
    for name, v in SETS:
        art = loungeart.LoungeArt(loungeart.VARIANT_DIR / v) if v else loungeart.LoungeArt()
        art.step = lambda dt: None
        tiles = [render(art, a) for a in ANG]
        # zoom on the tail box
        bx, by, bw, bh = art.tail_meta["box"]; k = H / art.canvas[1]
        left = (W - art.fw * k) / 2; top = H * (1 - loungeart.EDGE_UP) + loungeart.sink_px(H) + art.base_off * k - art.fh * k
        box = (int(left + bx * k) - 10, int(top + by * k) - 10, int(left + (bx + bw) * k) + 10, int(top + (by + bh) * k) + 10)
        z = [t.crop(box).resize(((box[2] - box[0]) * 2, (box[3] - box[1]) * 2), Image.LANCZOS) for t in tiles]
        zs = Image.new("RGB", (sum(i.width for i in z), max(i.height for i in z)), (236, 238, 242))
        x = 0
        for i in z: zs.paste(i, (x, 0)); x += i.width
        zs.save(OUT / f"tail_zoom_{name}.png")
        s = Image.new("RGB", (W * 3, H)); [s.paste(t, (i * W, 0)) for i, t in enumerate(tiles)]
        s.save(OUT / f"tail_{name}.png"); rows.append(s)
    sheet = Image.new("RGB", (W * 3, H * len(rows))); [sheet.paste(r, (0, i * H)) for i, r in enumerate(rows)]
    sheet.resize((sheet.width // 2, sheet.height // 2), Image.LANCZOS).save(OUT / "tail_sheet.png")
    (OUT / "tmp.png").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
