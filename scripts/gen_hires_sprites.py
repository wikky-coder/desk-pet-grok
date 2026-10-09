#!/usr/bin/env python3
"""Generate high-res consistent desk-pet sprites via xAI Imagine edits API."""
from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_gen" / "hires2026"
KEY_PATH = ROOT / ".secrets" / "xai_api_key"
API = "https://api.x.ai/v1"
MODEL = "grok-imagine-image-2.0"

CHAR = (
    "Same exact character identity every time: Q-version / chibi anime catgirl maid, "
    "large head small body, honey-blonde shoulder-length hair with ahoge cowlick, "
    "large tan cat ears with white fluff inside, long tan cat tail, "
    "large warm brown amber eyes with highlights, small w-shaped cat mouth, "
    "three thin pink whisker marks on each cheek, soft blush, "
    "cream square hairpin with bold black X on her left bangs (viewer right), "
    "white ruffled maid headband between ears, "
    "dark navy long-sleeve maid dress with white ruffled apron, white cuffs, "
    "navy ribbon bow at neck, necklace with black square pendant showing white Grok logo "
    "(circle with diagonal slash), gold constellation embroidery near skirt hem, "
    "white ankle socks with one blue ankle dot, navy Mary Jane shoes with small white bows. "
    "Clean sharp anime linework, fine soft cel shading, high detail fabric folds and hair strands, "
    "crisp edges, no blur, no watermark, no UI buttons, no text overlays."
)

BG = (
    "Full-body character only, centered, standing on empty space. "
    "Background must be solid pure chroma-key green #00FF00 with zero shadows, "
    "zero floor, zero vignette, zero white paper matte."
)


def load_key() -> str:
    env = os.environ.get("XAI_API_KEY", "").strip()
    if env:
        return env
    return KEY_PATH.read_text(encoding="utf-8").strip()


def data_uri(path: Path) -> str:
    raw = path.read_bytes()
    # Prefer smaller jpeg for refs when no alpha needed; keep png for cutouts
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def edit(
    client: httpx.Client,
    prompt: str,
    images: list[Path],
    *,
    out_path: Path,
    aspect_ratio: str = "2:3",
    resolution: str = "2k",
    quality: str = "medium",
    deferred: bool = True,
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and out_path.stat().st_size > 10_000:
        print(f"skip existing {out_path.name}")
        return out_path

    payload: dict = {
        "model": MODEL,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "quality": quality,
        "response_format": "url",
    }
    if len(images) == 1:
        payload["image"] = {"url": data_uri(images[0]), "type": "image_url"}
    else:
        payload["images"] = [
            {"url": data_uri(p), "type": "image_url"} for p in images
        ]
    if deferred:
        payload["deferred"] = True

    print(f"→ request {out_path.name} …")
    r = client.post(f"{API}/images/edits", json=payload, timeout=180.0)
    if r.status_code >= 400:
        # retry without deferred
        if deferred:
            print(f"  deferred rejected {r.status_code}: {r.text[:200]}; retry sync")
            payload.pop("deferred", None)
            r = client.post(f"{API}/images/edits", json=payload, timeout=300.0)
        if r.status_code >= 400:
            raise RuntimeError(f"{out_path.name}: {r.status_code} {r.text[:500]}")

    data = r.json()
    if deferred and "request_id" in data and "data" not in data:
        rid = data["request_id"]
        print(f"  polling {rid}")
        while True:
            time.sleep(4)
            pr = client.get(
                f"{API}/images/{rid}",
                headers={"Authorization": client.headers["Authorization"]},
                timeout=60.0,
            )
            pdata = pr.json()
            st = pdata.get("status")
            if st == "done":
                data = pdata
                break
            if st == "failed":
                raise RuntimeError(f"{out_path.name} failed: {pdata.get('error')}")
            print(f"  … {st}")

    url = data["data"][0]["url"]
    img = client.get(url, timeout=120.0)
    img.raise_for_status()
    out_path.write_bytes(img.content)
    print(f"✓ {out_path.name} ({len(img.content)} bytes)")
    return out_path


def main() -> int:
    key = load_key()
    OUT.mkdir(parents=True, exist_ok=True)
    ref = OUT / "ref_canonical.png"
    if not ref.is_file():
        print("missing ref_canonical.png", file=sys.stderr)
        return 1

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(headers=headers, timeout=300.0) as client:
        # 1) High-res front idle — refine/upscale canonical identity
        front = edit(
            client,
            (
                f"{CHAR} {BG} "
                "Pose: front idle facing camera, both hands raised as cute loose fists "
                "near chest (paw gesture), cheerful neutral expression, full body visible "
                "head to shoes, same proportions and outfit as the reference image. "
                "Increase clarity and fine detail dramatically while keeping identity identical."
            ),
            [ref],
            out_path=OUT / "raw_front.png",
        )

        # Use new front as identity anchor for other views
        id_refs = [front]

        quarter = edit(
            client,
            (
                f"{CHAR} {BG} "
                "Pose: three-quarter view turned about 40 degrees to her right (viewer left), "
                "still standing idle, hands near waist/apron, face clearly visible at 3/4 angle, "
                "ears and X hairpin and Grok necklace clearly readable, full body. "
                "Keep identity identical to the reference character."
            ),
            id_refs,
            out_path=OUT / "raw_quarter.png",
        )

        side = edit(
            client,
            (
                f"{CHAR} {BG} "
                "Pose: strict side profile facing left (viewer left), standing upright idle, "
                "arms naturally at sides, one amber eye visible in profile, cat ears and ahoge "
                "and X hairpin and Grok pendant and apron bow and long tail all visible, "
                "full body from head to shoes. Keep identity identical to the reference."
            ),
            id_refs,
            out_path=OUT / "raw_side.png",
        )

        back = edit(
            client,
            (
                f"{CHAR} {BG} "
                "Pose: rear three-quarter / back view, looking away from camera, "
                "large white apron bow on the back, cat ears from behind, long blonde cat tail, "
                "blonde hair and ahoge visible, full body standing. Same character as reference."
            ),
            id_refs,
            out_path=OUT / "raw_back.png",
        )

        # Turn mid keys (22° and 67° approx) using front+quarter+side
        turn22 = edit(
            client,
            (
                f"{CHAR} {BG} "
                "Pose: slight turn about 20 degrees from front toward her right (viewer left), "
                "in-between front idle and three-quarter. Hands still near chest/apron, "
                "full body. Exact same character as references."
            ),
            [front, quarter],
            out_path=OUT / "raw_turn22.png",
        )
        turn67 = edit(
            client,
            (
                f"{CHAR} {BG} "
                "Pose: strong turn about 65–70 degrees from front, almost profile but not quite, "
                "in-between three-quarter and side profile. Full body. Exact same character."
            ),
            [quarter, side],
            out_path=OUT / "raw_turn67.png",
        )

        # Walk cycle keyframes from side identity
        walk_prompts = [
            (
                "walk01",
                "side-profile walk cycle contact: left foot forward heel just touching ground, "
                "right foot back toe pushing, slight forward lean, arms opposite swing, "
                "facing left, full body",
            ),
            (
                "walk02",
                "side-profile walk cycle passing: legs closest together mid-stride, "
                "body slightly rising, arms mid-swing, facing left, full body",
            ),
            (
                "walk03",
                "side-profile walk cycle down: right foot forward, left foot back, "
                "strong stride, slight bob down, facing left, full body",
            ),
            (
                "walk04",
                "side-profile walk cycle contact opposite: right foot forward heel contact, "
                "left foot back, arms opposite swing, facing left, full body",
            ),
            (
                "walk05",
                "side-profile walk cycle passing opposite: legs close mid-stride other phase, "
                "body slightly rising, facing left, full body",
            ),
            (
                "walk06",
                "side-profile walk cycle down opposite: left foot forward strong stride, "
                "right foot back, slight bob, facing left, full body",
            ),
        ]
        for name, pose in walk_prompts:
            edit(
                client,
                (
                    f"{CHAR} {BG} Pose: {pose}. "
                    "Keep silhouette readable as walking, not floating or sliding. "
                    "Exact same character as the side/front references."
                ),
                [side, front],
                out_path=OUT / f"raw_{name}.png",
            )

    print("ALL RAW DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
