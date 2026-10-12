#!/usr/bin/env python3
"""Generate the standing 'enjoying a head-pat' face (same pose, only the expression changes). Key: XAI_API_KEY env.
usage: gen_happyface.py <name> ; max 8 calls overall (see _gen/happy/calls.log)."""
from __future__ import annotations
import sys
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).parent))
import gen_hires_sprites as g  # noqa: E402
OUT = g.ROOT / "_gen" / "happy"
PROMPT = (
    "Edit the FIRST reference image: keep EVERYTHING identical pixel-for-pixel in layout - same character, same pose with both fists raised, "
    "same outfit, same hair, X hairpin, ahoge, cat ears, maid headband, tail, same camera, same scale, same head size and position, same solid green background. "
    "ONLY change the facial expression to being blissfully petted: both eyes closed into happy upward-curving crescent arcs (^ ^ shape, the arc bulges UP like a smile, "
    "thin dark brown lashes only, no pupils, no white of the eye, no highlights), slightly stronger soft pink blush on the cheeks right under the eyes, "
    "a gently smiling small cat mouth 'w' with corners lifted. Keep the three whisker marks on each cheek exactly as before. "
    "The second reference only shows the style of the happy closed eyes. Do not change the face shape, bangs, or any hair strand."
)
def main():
    name = sys.argv[1]
    log = OUT / "calls.log"; OUT.mkdir(parents=True, exist_ok=True)
    n = len(log.read_text().splitlines()) if log.exists() else 0
    assert n < 8, "call budget used up"
    with log.open("a") as f: f.write(name + "\n")
    key = g.load_key()
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    extra = sys.argv[2] if len(sys.argv) > 2 else ""
    with httpx.Client(headers=h, timeout=300.0) as c:
        g.edit(c, PROMPT + " " + extra, [g.OUT / "raw_front.png", OUT / "ref_avatar.jpg"], out_path=OUT / f"raw_{name}.png")
main()
