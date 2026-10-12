#!/usr/bin/env python3
"""F7: lounge pose variants via xAI image edits. usage: gen_f7.py <name>_<attempt> [extra prompt]. Key: XAI_API_KEY env only.
Budget 20 calls (_gen/f7/calls.log). Names: side, stretch, curl, chin  (+ side_sleep / side_half derived from an approved side)."""
from __future__ import annotations
import sys
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).parent))
import gen_hires_sprites as g  # noqa: E402
R = g.OUT
OUT = g.ROOT / "_gen" / "f7"
KEEP = ("Keep the headband, hairpin (cream square with a black X on the viewer-right bangs), necklace with black square pendant, colours, hair, cat ears and dark navy maid dress with white apron "
        "identical to the references; do NOT add any new embroidery, ornaments, text or extra limbs; exactly two arms and two hands with five fingers each when visible. ")
LINE = ("The character is only drawn ABOVE a perfectly straight horizontal cut line at the bottom of the image; everything below that line is "
        "empty pure chroma-key green #00FF00. No ledge, no table, no floor, no shadow is drawn. ")
BGG = "Background solid pure chroma-key green #00FF00, no shadows, no vignette. Square composition, character centered, large in frame. "
POSES = {
    "side": "Pose: she is lounging belly-down on an invisible horizontal edge with her BODY IN SIDE PROFILE (seen from the side, torso and skirt extending horizontally along the cut line toward the viewer-left), "
            "her head turned to face the viewer almost frontally, her chin resting on one forearm that lies along the cut line, content relaxed smile, ears up, "
            "one thin long tan tail curling upward in a loose curl behind her at the viewer-left end. ",
    "stretch": "Pose: a cute cat-like stretch on an invisible horizontal edge: both arms stretched far forward along the cut line toward the viewer-right with fingers spread softly, chest low, back gently arched, bottom slightly raised, "
               "head lifted a little looking at the viewer with eyes happily closed in a big content smile, ears up, tail raised in a curl behind her. Seen from the side. ",
    "curl": "Pose: she is curled up asleep in a cozy ball on an invisible horizontal edge, body curled sideways, head resting on her folded arms, eyes gently closed with a peaceful sleeping smile, "
            "ears relaxed, long tan tail wrapped around in front of her body. Seen from the front-side, low and compact. ",
    "chin": "Pose: she is lounging belly-down on an invisible horizontal edge, propping her cheek on one hand (elbow resting on the cut line, cheek in her palm) and looking straight at the viewer with a soft sweet smile, "
            "the other arm folded flat along the cut line, ears up, one thin long tan tail curling up beside her on the viewer-left. ",
}
def main():
    tag = sys.argv[1]; name = tag.rsplit("_", 1)[0]
    log = OUT / "calls.log"; OUT.mkdir(parents=True, exist_ok=True)
    n = len(log.read_text().splitlines()) if log.exists() else 0
    assert n < 20, "F7 call budget used up"
    with log.open("a") as f: f.write(tag + "\n")
    extra = sys.argv[2] if len(sys.argv) > 2 else ""
    if name in POSES:
        refs = [R / "raw_lounge_base_a1.png", R / "raw_side.png", R / "raw_front.png"]
        prompt = (f"{g.CHAR} {BGG}{POSES[name]}{LINE}{KEEP}The first reference shows the exact art style, head size, line weight and the lying-on-an-edge cut-line framing to match; "
                  f"the other references show the character's identity (and her side view). {extra}")
    else:
        raise SystemExit("unknown pose " + name)
    h = {"Authorization": f"Bearer {g.load_key()}", "Content-Type": "application/json"}
    with httpx.Client(headers=h, timeout=300.0) as c:
        g.edit(c, prompt, refs, out_path=OUT / f"raw_{tag}.png", aspect_ratio="1:1")
main()
