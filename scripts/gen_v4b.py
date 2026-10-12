#!/usr/bin/env python3
"""v4b: full standing poses holding the work props with BOTH hands (xAI image edit from the standing reference).
usage: gen_v4b.py <name>_<n> [extra]  -> _gen/v4/raw_<name>_<n>.png  (budget 12 calls, feature 'hands')"""
from __future__ import annotations
import sys
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).parent))
import gen_hires_sprites as g  # noqa: E402
OUT = g.ROOT / "_gen" / "v4"
KEEP = ("Edit the FIRST reference image: same character, same face, same outfit and dress embroidery, same hair, hairpin with X, ahoge, cat ears, maid headband, tail, "
        "same art style, same line weight, same camera, same scale, same position, full body from ears to shoes, same solid pure green #00FF00 background with no shadows or floor. "
        "CHANGE ONLY HER ARMS AND HANDS: she must have EXACTLY TWO arms and EXACTLY TWO hands in total (no extra hands, no fists left over at her sides or chest), each hand with five small fingers. ")
POSES = {
    "hold_book": "She holds an open hardcover book upright in front of her chest at chest height, below her chin so her whole face stays visible. We see the BACK cover of the book (navy cloth with tiny gold stars, a spine in the middle), her two hands grip its lower left and lower right sides with fingers curled around the edges, forearms in dark sleeves with white ruffled cuffs. The book hides her bodice but not her face.",
    "hold_laptop": "She holds a slim silver laptop open in front of her chest at chest height, below her chin so her whole face stays visible, seen from BEHIND (back of the lid faces the viewer, brushed silver with a tiny dark cat paw emblem). Her two hands rest on the top edge of the lid with fingertips curled over it. Her forearms in dark sleeves with white ruffled cuffs come from her sides.",
    "hold_terminal": "She holds a small floating-style dark screen panel (like a tiny tablet showing a terminal window: three small coloured dots in a cream title bar and several short coloured text lines on dark navy) upright in front of her chest at chest height, below her chin so her whole face stays visible. Her two hands hold its lower left and lower right corners from behind/below, fingertips visible on the front edges, forearms in dark sleeves with white ruffled cuffs.",
    "hold_palette": "She holds a wooden painter's palette with colourful paint dabs (red, yellow, blue, white, green) in front of her chest in her LEFT hand (the viewer's right side) with the thumb through the hole, and a fine paintbrush in her other hand held up to the palette as if painting. Palette at chest height, below her chin so her whole face stays visible. Exactly two hands, forearms in dark sleeves with white ruffled cuffs.",
}
def main():
    tag = sys.argv[1]; name = tag.rsplit("_", 1)[0]
    OUT.mkdir(parents=True, exist_ok=True)
    log = OUT / "calls.log"
    n = sum(1 for l in (log.read_text().splitlines() if log.exists() else []) if l.startswith("hands "))
    assert n < 12, "hands: call budget used up"
    with log.open("a") as f: f.write(f"hands {tag}\n")
    h = {"Authorization": f"Bearer {g.load_key()}", "Content-Type": "application/json"}
    extra = sys.argv[2] if len(sys.argv) > 2 else ""
    with httpx.Client(headers=h, timeout=300.0) as c:
        g.edit(c, KEEP + POSES[name] + " " + extra, [g.OUT / "raw_front.png"], out_path=OUT / f"raw_{tag}.png", aspect_ratio="2:3")
main()
