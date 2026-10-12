#!/usr/bin/env python3
"""curl v2: natural cat-nest sleeping pose. usage: gen_f7_curl2.py N [ref=side|base]. Shares the F7 call log style (_gen/f7/curl2_calls.log, max 8). Key: XAI_API_KEY env only."""
import sys
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).parent))
import gen_hires_sprites as g  # noqa: E402
OUT = g.ROOT / "_gen" / "f7"
n, ref = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "side")
log = OUT / "curl2_calls.log"; used = len(log.read_text().splitlines()) if log.exists() else 0
assert used < 8, "curl2 budget used up"
with log.open("a") as f: f.write(f"curl2_{n}_{ref}\n")
first = OUT / "raw_side_2.png" if ref == "side" else g.OUT / "raw_lounge_base_a1.png"
KEEP = ("Keep the headband, hairpin (cream square with a black X on the viewer-right bangs), necklace with black square pendant, colours, hair, cat ears and dark navy maid dress with white apron "
        "identical to the references; do NOT add any new embroidery, ornaments, text or extra limbs; two arms with five fingers per visible hand. ")
prompt = (f"{g.CHAR} Background solid pure chroma-key green #00FF00, no shadows, no vignette. Square composition, character centered, large in frame. "
          "Pose: she is sleeping peacefully like a cat in its nest, lying belly-down and relaxed on an invisible horizontal edge, body low and flat in side profile, "
          "her head turned and resting sideways with her cheek on her folded forearms, eyes gently closed with a content sleeping smile, ears relaxed, "
          "her legs tucked neatly under the skirt so NO shoes or legs are visible (the skirt hem just lies along the cut line), and the long tan tail curled round in front of her body. "
          "Proportions, head size and art style exactly like the first reference. The character is only drawn ABOVE a perfectly straight horizontal cut line at the bottom of the image; "
          "everything below that line is empty pure chroma-key green #00FF00. No ledge, no table, no floor, no shadow is drawn. " + KEEP +
          "The first reference gives the body proportions, size and cut-line framing; the others are for identity.")
refs = [first, g.OUT / "raw_lounge_base_a1.png" if ref == "side" else OUT / "raw_side_2.png", g.OUT / "raw_front.png"]
h = {"Authorization": f"Bearer {g.load_key()}", "Content-Type": "application/json"}
with httpx.Client(headers=h, timeout=300.0) as c:
    g.edit(c, prompt, refs, out_path=OUT / f"raw_curl2_{n}.png", aspect_ratio="1:1")
