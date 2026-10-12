# Slim pass notes (2026-10-12)

Pre-slim backup tarball kept outside the repo (not committed).

## Phase A — clutter
- Removed all root `_bak_*` directories and scattered `*.bak*` files (incl. `assets/rig25d.bak`).
- Left `_archives/`, active `assets/`, and `_gen*` trees on disk; gitignore now ignores regenerable gen dirs and bak patterns.
- Cleared project `__pycache__` trees (not under `.venv`).

## Phase B — classic PetWidget path
**Keep for now (deprecated fallback).**

Reasons:
- `PetWindow` still swaps to `PetWidget` when `puppet25d` is False or 25d assets unavailable (`window.py`).
- Tests still cover classic path: `tests/test_pet_assets.py`, `tests/test_pet_sprites.py`, `tests/test_puppet_window.py` (`puppet25d=False`).
- `assets/sprites` (~31MB) remains the classic sheet set.

Default runtime is already `Pet25D` when available. Removing classic path needs a dedicated test migration; deferred.

## Phase C — code slim (this pass)
- Extracted `_paint_holiday` / `_paint_work` / `_paint_cling` / `_paint_sulk` / `_paint_lounge_art` into `desk_pet_grok/pet25d_paint.py`.
- `Pet25D` keeps thin wrappers; loaders (`_hol_images`, `_work_art_load`, `_cling_art_load`, `_sulk_sprite`) stay on the widget (also used by setters / `cling_cut_x`).

## Deferred
- Drop classic `PetWidget` + `assets/sprites` after test migration.
- Thin `interaction.py` mixin further.
- Merge screen probe family (`screen_*` + `ax_probe` / `focus_probe`) — no clear dead duplicates yet.

## Verify (2026-10-12)
- Freed ~37 MB on disk (bak dirs/files + `__pycache__` + `assets/rig25d.bak`).
- `pet25d.py` 1124 → 992 lines; new `pet25d_paint.py` 166 lines.
- Tests: **708 passed** (ignored numpy-only: fallfix*, happyface, workhands, edgefit, tail).
- Pre-slim backup tarball kept outside the repo (~220MB, not committed).
