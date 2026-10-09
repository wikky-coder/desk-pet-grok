# 桌宠grok assets

## Primary look (recommended)

`sprites/` — consistent static views used with **procedural animation** (breath / sway / walk bob / jump):

- `front.png` — idle / facing camera
- `side.png` — walking (left profile; mirrored in code by facing)
- `back.png` — optional rear view

When `sprites/front.png` (or `side.png`) exists, the pet prefers these over per-state frame folders.

## Fallback sequences

`idle/`, `think/`, `work/`, `wait/`, `done/`, `error/`, `sleep/` — optional multi-frame loops (`01.png`…).
Used only when `sprites/` is missing.
