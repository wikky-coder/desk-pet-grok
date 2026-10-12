#!/usr/bin/env python3
"""F7: half-closed / closed eye versions of an approved variant (edit only the eyes). usage: gen_f7_eyes.py <variant> <half|sleep> <attempt>
Budget shared with gen_f7.py (_gen/f7/calls.log, 20 total). Key: XAI_API_KEY env only."""
import sys
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).parent))
import gen_hires_sprites as g  # noqa: E402
OUT = g.ROOT / "_gen" / "f7"
var, kind, att = sys.argv[1], sys.argv[2], sys.argv[3]
base = {"side": "raw_side_2.png", "chin": "raw_chin_1.png"}[var]
ch = {"half": "Change ONLY the eyes: very sleepy half-closed eyes: the upper eyelids cover the upper half of each iris so only a thin sliver of brown iris shows, heavy drowsy lids, soft calm smile. ",
      "sleep": "Change ONLY the eyes: both eyes gently closed with curved lashes, peaceful sleeping smile. "}[kind]
SAME = ("Everything else must stay at exactly the same position and shape as the reference: head, hair, ears, hairpin, arms, hands, tail, clothes, framing, scale, "
        "the straight cut at the bottom and the pure chroma-key green #00FF00 background (no posture change, no hand moved). ")
log = OUT / "calls.log"; n = len(log.read_text().splitlines())
assert n < 20, "budget"
with log.open("a") as f: f.write(f"{var}_{kind}_{att}\n")
prompt = f"Edit the first reference image: keep exactly the same character, pose, framing, scale, colours and linework. {ch}{SAME}The second reference is only for identity."
h = {"Authorization": f"Bearer {g.load_key()}", "Content-Type": "application/json"}
with httpx.Client(headers=h, timeout=300.0) as c:
    g.edit(c, prompt, [OUT / base, g.OUT / "raw_front.png"], out_path=OUT / f"raw_{var}_{kind}_{att}.png", aspect_ratio="1:1")
