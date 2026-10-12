#!/usr/bin/env python3
"""F6: generate one mood face (same pose, only the expression changes). Key: XAI_API_KEY env. Budget: 12 calls (_gen/f6/calls.log).
usage: gen_f6_face.py <mood>_<attempt>  e.g. surprised_1"""
from __future__ import annotations
import sys
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).parent))
import gen_hires_sprites as g  # noqa: E402
OUT = g.ROOT / "_gen" / "f6"
KEEP = (
    "Edit the FIRST reference image: keep EVERYTHING identical in layout - same character, same pose with both fists raised, same outfit, same hair, "
    "X hairpin, ahoge, cat ears, maid headband, tail, same camera, same scale, same head size and position, same solid green background. "
    "Do not change the face shape, bangs or any hair strand; keep the three whisker marks on each cheek. ONLY change the facial expression: "
)
EXPR = {
    "surprised": "SURPRISED: eyes opened wider and rounder than normal with slightly smaller pupils and the same brown amber colour and highlights, eyebrows raised, a small round open 'o' mouth, a tiny sweat-drop-free clean face, blush kept light.",
    "annoyed": "ANNOYED / IRRITATED: eyes half-lidded and flat looking sideways-ish toward the viewer with the same brown amber colour, eyebrows slightly furrowed and angled down toward the nose, mouth a small flat pout line, cheeks lightly puffed, little blush.",
    "sleepy": "SLEEPY: eyes heavy and droopy, upper eyelids covering about half of each iris, soft relaxed eyebrows, small relaxed closed mouth (tiny flat 'w'), slightly rosy cheeks, calm drowsy look.",
    "cheerful": "CHEERFUL / HAPPY: eyes wide open, bright and sparkling with extra star-like highlights, same brown amber colour, eyebrows lifted slightly, a big bright open smile with the mouth open in a happy curved 'u' shape showing a tiny pink tongue, cheeks clearly flushed with blush.",
    "dizzy": "DIZZY: both eyes turned into simple spiral swirls (hypnotic dizzy spirals drawn in the same brown amber colour inside the eye shapes, no pupils), eyebrows tilted up and wobbly, the mouth a small wavy squiggle line, face slightly pale-flushed, no sweat drops, no stars.",
    "puffed": "PUFFED CHEEKS SULKING: both cheeks clearly inflated and round like a puffer fish, eyes narrowed into annoyed half-lidded slits looking sideways, eyebrows pushed down and together, tiny closed pressed mouth hidden between the puffed cheeks, light blush, the whisker marks stretched on the puffed cheeks.",
    "fuming": "FUMING / ANGRY RED-FACED: whole face flushed deep red-pink (red cheeks, red forehead and nose, strong blush all over the face skin), eyes sharp and angry with small pupils, eyebrows slanted steeply down toward the nose, the mouth a tight wavy angry line with a tiny fang visible, a tiny anger cross-popping vein mark on the forehead.",
    "pouty": "POUTY / WRONGED: big watery glossy eyes looking up at the viewer with extra highlights and a hint of tears in the lower lids, eyebrows tilted up in the middle (sad), a small downturned wobbly mouth, cheeks slightly flushed.",
}
def main():
    tag = sys.argv[1]; mood = tag.rsplit("_", 1)[0]
    log = OUT / "calls.log"; OUT.mkdir(parents=True, exist_ok=True)
    n = len(log.read_text().splitlines()) if log.exists() else 0
    assert n < 40, "F6/v4 call budget used up"
    with log.open("a") as f: f.write(tag + "\n")
    key = g.load_key()
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    extra = sys.argv[2] if len(sys.argv) > 2 else ""
    with httpx.Client(headers=h, timeout=300.0) as c:
        g.edit(c, KEEP + EXPR[mood] + " " + extra, [g.OUT / "raw_front.png"], out_path=OUT / f"raw_{tag}.png")
main()
