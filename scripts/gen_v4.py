#!/usr/bin/env python3
"""v4 art generator (xAI image edit from the standing reference). usage: gen_v4.py <feature>/<name>_<n>  [extra prompt]
Writes _gen/v4/raw_<name>_<n>.png and logs the call (<= 15 calls per feature, see PROMPTS keys' feature prefix)."""
from __future__ import annotations
import sys
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).parent))
import gen_hires_sprites as g  # noqa: E402
OUT = g.ROOT / "_gen" / "v4"
KEEP = ("Edit the FIRST reference image: same character, same outfit, same hair, hairpin with X, ahoge, cat ears, maid headband, tail, "
        "same art style, same line weight, same solid pure green #00FF00 background with no shadows or floor. ")
CLING_L = ("NEW POSE: she is clinging to a vertical edge on the LEFT border of the image, as if hiding behind a wall corner: the image's left border IS the edge. "
           "Her body is pressed against that left border and the figure is CUT OFF by the left border of the image so only her right half is visible: the left half of her body, left ear and left side of the hair are outside the image. "
           "Her visible hand grips the left border with tiny fingers, she leans her head out a little toward the right and peeks at the viewer with one curious, shy but happy look, visible ear perked up, "
           "tail curling out low from behind the border and hanging down on the right side. Full height from ears to shoes, feet at the bottom, hairpin with the X kept on her left bangs, same scale as the reference, "
           "figure touching the left image border over its whole height.")
CLING_R = ("NEW POSE: she is clinging to a vertical edge on the RIGHT border of the image, as if hiding behind a wall corner: the image's right border IS the edge. "
           "Her body is pressed against that right border and the figure is CUT OFF by the right border of the image so only her left half is visible: the right half of her body, right ear and right side of the hair are outside the image. "
           "Her visible hand grips the right border with tiny fingers, she leans her head out a little toward the left and peeks at the viewer with one curious, shy but happy look, visible ear perked up, "
           "tail curling out low from behind the border and hanging down on the left side. Full height from ears to shoes, feet at the bottom, the cream hairpin with the bold X stays on her left bangs (viewer's right of her face, which is near the border) - keep it NOT mirrored, same scale as the reference, "
           "figure touching the right image border over its whole height.")
PEEK = (" Same character and style as the previous clinging pose, but now she is PEEKING OUT MORE: she leans noticeably further away from the border, "
        "about two thirds of her body now visible, head tilted toward the open side with wide curious sparkling eyes looking straight at the viewer, ears perked high, a small happy open smile, "
        "one hand still gripping the border, the other hand lifted in a tiny wave, tail swinging out more.")
PROP = ("Use the first image ONLY as an art style reference (same anime line art, soft cel shading, colour palette: cream, tan, dark navy, white ruffles); DO NOT draw the character or any face. "
        "Draw just ONE small prop object, centered, filling about 80 percent of the frame, on a solid pure chroma-key green #00FF00 background with no shadow and no floor. ")
SHEET = ("Use the first image ONLY as an art style reference (same anime line art, soft cel shading, cute chibi proportions, clean dark-navy outlines); DO NOT draw the character or any face. "
         "Draw a STICKER SHEET of exactly four separate small items arranged in a 2 by 2 grid with wide empty green gaps between them (no item touches another or the border), each item complete, "
         "on a solid pure chroma-key green #00FF00 background with no shadow and no floor. The four items: ")
PROMPTS = {
    "fest_flag": ("fest", PROP + "The object: a small hand flag on a thin wooden pole, the flag red and gently waving, with one large yellow five-pointed star in the upper-left corner and four smaller yellow five-pointed stars in an arc to its right, as on the national flag of China; cute chibi style.", "1:1"),
    "fest_hats": ("fest", SHEET + "(1) a cute black witch hat with a purple band and a tiny gold buckle, tilted slightly; (2) a red-and-white Santa hat with a fluffy white pom-pom, slightly tilted; (3) a pastel party cone hat with confetti dots and a pom-pom on top; (4) a pair of small red festive hair flowers (silk peony) with a gold tassel, as a hair ornament. All hats are seen from the front, a bit tilted, with the opening at the bottom.", "1:1"),
    "fest_items": ("fest", SHEET + "(1) a red envelope (hongbao) with golden cloud patterns and a gold tassel tag; (2) a round red paper lantern with gold caps and a long tassel; (3) a carved jack-o'-lantern pumpkin with a cute glowing smile and a small green stem; (4) a tiny red flag on a thin pole with a yellow star pattern (waving slightly).", "1:1"),
    "fest_food": ("fest", SHEET + "(1) a small white porcelain bowl of round white tangyuan glutinous rice balls in clear soup; (2) a pyramid-shaped zongzi rice dumpling wrapped in green bamboo leaves tied with a red string; (3) a round mooncake with an embossed pattern on a small plate; (4) a small decorated gingerbread cookie in a cute shape with icing.", "1:1"),
    "prop_book": ("work", PROP + "The object: a pair of tiny chibi cream-skinned hands (each with a dark navy sleeve end and a white ruffled cuff) holding an open hardcover picture book upright in front, seen from the OUTSIDE so we see the back cover: navy blue cloth with tiny gold star embroidery and a ribbon bookmark hanging from the bottom; the hands grip the lower left and lower right corners of the book.", "1:1"),
    "prop_laptop": ("work", PROP + "The object: a small slim laptop seen from BEHIND (only the back of its lid faces the viewer: brushed silver with a navy edge and a tiny cat paw emblem), standing open at a slight angle, with two tiny chibi cream-skinned hands (each with a dark navy sleeve end and a white ruffled cuff) resting on the top edge of the lid as if typing behind it.", "1:1"),
    "prop_palette": ("work", PROP + "The object: a wooden painter's palette with a thumb hole and bright colourful paint dabs (red, yellow, blue, green, white), held by one tiny chibi cream-skinned hand at the left, and in the other tiny hand at the right a fine paintbrush with a coloured tip; both hands have a dark navy sleeve end and a white ruffled cuff.", "1:1"),
    "peek_L": ("cling", KEEP + CLING_L + PEEK),
    "peek_R": ("cling", KEEP + CLING_R + PEEK),
    "cling_L": ("cling", KEEP + CLING_L),
    "cling_R": ("cling", KEEP + CLING_R),
    "sulk_back": ("shake", KEEP + "NEW POSE: she is standing with her BACK completely turned to the viewer (seen from behind), arms crossed "
                  "in a huff, her head turned only slightly so a bit of one puffed cheek shows at the edge, ears flattened sideways, the long "
                  "tan tail visible from behind swishing up angrily with a slight curve, hair seen from behind with the maid headband bow and the "
                  "navy dress back with the apron bow. Full body, same scale, feet visible, same camera height, centered."),
}
def main():
    tag = sys.argv[1]; name = tag.rsplit("_", 1)[0]
    ent = PROMPTS[name]
    feat, prompt = ent[0], ent[1]
    aspect = ent[2] if len(ent) > 2 else "2:3"
    OUT.mkdir(parents=True, exist_ok=True)
    log = OUT / "calls.log"
    n = sum(1 for l in (log.read_text().splitlines() if log.exists() else []) if l.startswith(feat + " "))
    assert n < 15, f"{feat}: call budget used up"
    with log.open("a") as f: f.write(f"{feat} {tag}\n")
    h = {"Authorization": f"Bearer {g.load_key()}", "Content-Type": "application/json"}
    extra = sys.argv[2] if len(sys.argv) > 2 else ""
    with httpx.Client(headers=h, timeout=300.0) as c:
        g.edit(c, prompt + " " + extra, [g.OUT / "raw_front.png"], out_path=OUT / f"raw_{tag}.png", aspect_ratio=aspect)
main()
