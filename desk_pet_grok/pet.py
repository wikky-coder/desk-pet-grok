"""Pet widget: sprites + turn transitions + walk cycle + soft idle breath."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QRect, QTimer, Qt
from PySide6.QtGui import QBitmap, QColor, QImage, QPainter, QPixmap, QRegion
from PySide6.QtWidgets import QWidget

from desk_pet_grok.anim import ProceduralAnim
from desk_pet_grok.state import PetState

DEFAULT_ASSETS_ROOT = Path(__file__).resolve().parents[1] / "assets"

_FRAME_GLOBS = ("*.webp", "*.png")
_FPS_MS = {
    "idle": 120,
    "think": 110,
    "work": 90,
    "wait": 110,
    "done": 100,
    "error": 100,
    "sleep": 180,
}
_DEFAULT_FPS_MS = 120
_ANIM_INTERVAL_MS = 16  # ~60 fps procedural layer
_WALK_FRAME_MS = 90  # walk cycle cadence
_TURN_FRAME_MS = 56  # front↔side turn (~0.3s for 5 clean keys)
_MOVE_SPEED_MIN = 2.0


def assets_root_default() -> Path:
    """Project-root ``assets/`` (sibling of the ``desk_pet_grok`` package)."""
    return DEFAULT_ASSETS_ROOT


def sprites_dir(root: Path | None = None) -> Path:
    return (root or DEFAULT_ASSETS_ROOT) / "sprites"


def list_sprite_paths(root: Path | None = None) -> dict[str, Path]:
    """Return available named sprites under ``assets/sprites/``."""
    folder = sprites_dir(root)
    out: dict[str, Path] = {}
    if not folder.is_dir():
        return out
    for name in ("front", "quarter", "side", "back"):
        for ext in (".png", ".webp"):
            path = folder / f"{name}{ext}"
            if path.is_file():
                out[name] = path
                break
    return out


def list_walk_frame_paths(root: Path | None = None) -> list[Path]:
    """Sorted walk-cycle frames under ``assets/sprites/walk/`` (01.png …)."""
    folder = sprites_dir(root) / "walk"
    if not folder.is_dir():
        return []
    frames: list[Path] = []
    for pattern in _FRAME_GLOBS:
        frames.extend(folder.glob(pattern))
    return sorted(frames, key=lambda p: p.name.lower())


def list_turn_frame_paths(root: Path | None = None) -> list[Path]:
    """Sorted turn-sequence frames under ``assets/sprites/turn/`` (front→side)."""
    folder = sprites_dir(root) / "turn"
    if not folder.is_dir():
        return []
    frames: list[Path] = []
    for pattern in _FRAME_GLOBS:
        frames.extend(folder.glob(pattern))
    return sorted(frames, key=lambda p: p.name.lower())


def list_frame_paths(state: PetState, root: Path | None = None) -> list[Path]:
    """Return sorted webp/png paths under ``root/<state.value>/``."""
    folder = (root or DEFAULT_ASSETS_ROOT) / state.value
    if not folder.is_dir():
        return []
    frames: list[Path] = []
    for pattern in _FRAME_GLOBS:
        frames.extend(folder.glob(pattern))
    return sorted(frames, key=lambda p: p.name.lower())


def _load_pixmap(path: Path) -> QPixmap | None:
    pix = QPixmap(str(path))
    return None if pix.isNull() else pix


def _load_pixmaps(paths: list[Path]) -> list[QPixmap]:
    out: list[QPixmap] = []
    for path in paths:
        pix = _load_pixmap(path)
        if pix is not None:
            out.append(pix)
    return out


def _scrub_alpha_dust(img: QImage, *, alpha_cut: int = 12) -> QImage:
    """Zero premultiplied pixels whose alpha is below ``alpha_cut``.

    Smooth downscales leave a 1–2 px halo of near-transparent dust that can
    look like a hard outline on a translucent desktop window. Removing only
    that dust keeps visible antialiased edges intact.
    """
    if img.isNull() or alpha_cut <= 0:
        return img
    out = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    w, h = out.width(), out.height()
    nbytes = out.sizeInBytes()
    try:
        ptr = out.bits()
        ptr.setsize(nbytes)
        buf = memoryview(ptr).cast("B")
        # Premultiplied ARGB32 little-endian byte order: B, G, R, A.
        for i in range(3, len(buf), 4):
            if buf[i] < alpha_cut:
                j = i - 3
                buf[j] = 0
                buf[j + 1] = 0
                buf[j + 2] = 0
                buf[i] = 0
        return out
    except Exception:
        for y in range(h):
            for x in range(w):
                c = out.pixelColor(x, y)
                if c.alpha() < alpha_cut:
                    out.setPixelColor(x, y, QColor(0, 0, 0, 0))
        return out


class PetWidget(QWidget):
    """Shows pet art: turn transitions, walk frames while moving, front idle."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        assets_root: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._assets_root = Path(assets_root) if assets_root else DEFAULT_ASSETS_ROOT
        self._state = PetState.idle
        self._frames: list[QPixmap] = []
        self._frame_index = 0
        self._frame_dir = 1
        self._missing = True
        self._using_fallback = False
        self._facing = 1  # 1 = right, -1 = left (horizontal mirror)
        self._moving = False
        self._speed = 0.0
        self._use_sprites = False
        self._sprites: dict[str, QPixmap] = {}
        self._walk_frames: list[QPixmap] = []
        self._walk_index = 0
        self._turn_frames: list[QPixmap] = []
        self._turn_index = 0
        self._turn_dir = 0  # +1 front→side, -1 side→front, 0 idle
        self._sprite_mode = "front"  # front | quarter | side | back | walk | turn
        self._anim = ProceduralAnim()
        self._anim_clock = QElapsedTimer()
        self._anim_clock.start()

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        # Force full-widget paints; partial updates leave pose ghosts on macOS.
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setMinimumSize(80, 80)
        self._mask_key: tuple | None = None
        self._scaled_cache: dict[tuple[int, int], QPixmap] = {}

        self._frame_timer = QTimer(self)
        self._frame_timer.timeout.connect(self._advance_frame)

        self._walk_timer = QTimer(self)
        self._walk_timer.setInterval(_WALK_FRAME_MS)
        self._walk_timer.timeout.connect(self._advance_walk)

        self._turn_timer = QTimer(self)
        self._turn_timer.setInterval(_TURN_FRAME_MS)
        self._turn_timer.timeout.connect(self._advance_turn)

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(_ANIM_INTERVAL_MS)
        self._anim_timer.timeout.connect(self._tick_anim)
        self._anim_timer.start()

        self._reload_sprites()
        self.set_state(PetState.idle)

    @property
    def state(self) -> PetState:
        return self._state

    @property
    def missing_assets(self) -> bool:
        """True when neither sprites nor the requested state's frames are usable."""
        return self._missing

    @property
    def using_idle_fallback(self) -> bool:
        """True when playing idle frames because the requested state folder was empty."""
        return self._using_fallback

    @property
    def using_sprites(self) -> bool:
        return self._use_sprites

    @property
    def has_walk_frames(self) -> bool:
        return len(self._walk_frames) > 0

    @property
    def has_turn_frames(self) -> bool:
        return len(self._turn_frames) > 1

    @property
    def assets_root(self) -> Path:
        return self._assets_root

    @property
    def facing(self) -> int:
        """1 = facing right (default art), -1 = mirrored left."""
        return self._facing

    @property
    def anim(self) -> ProceduralAnim:
        return self._anim

    @property
    def sprite_mode(self) -> str:
        return self._sprite_mode

    @property
    def turning(self) -> bool:
        return self._turn_dir != 0 and self._sprite_mode == "turn"

    def set_facing(self, facing: int) -> None:
        """Mirror the sprite when ``facing < 0`` (look-at / wander facing)."""
        new = 1 if int(facing) >= 0 else -1
        if new != self._facing:
            self._facing = new
            # Look-at / facing flip does not hard-cut view; keep current pose.
            self.update()

    def set_motion(self, moving: bool, speed: float = 0.0) -> None:
        """Drive turn → walk cycle / settle from window motion."""
        prev_mode = self._sprite_mode
        self._moving = bool(moving)
        self._speed = max(0.0, float(speed))
        self._anim.set_moving(self._moving, self._speed, self._facing)
        self._refresh_sprite_mode()
        if self._sprite_mode != prev_mode:
            # Pose change must repaint immediately; otherwise macOS keeps the
            # previous (wider) opaque region as a white silhouette for a frame.
            self._mask_key = None
            self.update()
            win = self.window()
            if win is not None and win is not self:
                win.update()

    def play_jump(self) -> None:
        """Procedural jump impulse (local paint offset)."""
        self._anim.trigger_jump()

    def _reload_sprites(self) -> None:
        self._sprites.clear()
        self._scaled_cache.clear()
        for name, path in list_sprite_paths(self._assets_root).items():
            pix = _load_pixmap(path)
            if pix is not None:
                self._sprites[name] = pix
        self._walk_frames = _load_pixmaps(list_walk_frame_paths(self._assets_root))
        self._turn_frames = _load_pixmaps(list_turn_frame_paths(self._assets_root))
        self._use_sprites = "front" in self._sprites or "side" in self._sprites

    def _want_walk(self) -> bool:
        return self._moving and self._speed > _MOVE_SPEED_MIN

    def _start_turn(self, direction: int) -> None:
        """Begin front↔side turn. direction +1 = to side, -1 = to front."""
        if not self._turn_frames:
            return
        self._turn_dir = 1 if direction >= 0 else -1
        if self._turn_dir > 0:
            # Resume from current index if mid-turn reverse, else from start.
            if self._sprite_mode != "turn":
                self._turn_index = 0
        else:
            if self._sprite_mode != "turn":
                self._turn_index = len(self._turn_frames) - 1
        self._sprite_mode = "turn"
        self._anim.set_walk_frames_active(False)
        self._walk_timer.stop()
        if not self._turn_timer.isActive():
            self._turn_timer.start()
        self.update()

    def _finish_turn(self) -> None:
        finished_dir = self._turn_dir
        self._turn_dir = 0
        self._turn_timer.stop()
        if finished_dir > 0:
            # Arrived at side → walk or hold side
            if self._want_walk() and self._walk_frames:
                self._sprite_mode = "walk"
                self._anim.set_walk_frames_active(True)
                self._walk_index = 0
                if not self._walk_timer.isActive():
                    self._walk_timer.start()
            elif "side" in self._sprites:
                self._sprite_mode = "side"
                self._anim.set_walk_frames_active(False)
            else:
                self._sprite_mode = "front"
                self._anim.set_walk_frames_active(False)
        else:
            # Settled front
            self._sprite_mode = "front" if "front" in self._sprites else next(iter(self._sprites), "front")
            self._anim.set_walk_frames_active(False)
            self._walk_timer.stop()
        self.update()

    def _refresh_sprite_mode(self) -> None:
        if not self._use_sprites:
            self._anim.set_walk_frames_active(False)
            self._walk_timer.stop()
            self._turn_timer.stop()
            self._turn_dir = 0
            return

        want = self._want_walk()

        # Mid-turn: reverse direction if intent flipped.
        if self._sprite_mode == "turn" and self._turn_frames:
            desired = 1 if want else -1
            if desired != self._turn_dir:
                self._turn_dir = desired
            return

        if want:
            # Already walking — keep cycling.
            if self._sprite_mode == "walk" and self._walk_frames:
                self._anim.set_walk_frames_active(True)
                if not self._walk_timer.isActive():
                    self._walk_timer.start()
                return
            # From front / quarter / idle → turn out then walk.
            if self.has_turn_frames and self._sprite_mode in ("front", "quarter", "back"):
                self._start_turn(+1)
                return
            # Already on side (no turn assets, or turn skipped): walk or side.
            if self._walk_frames:
                self._sprite_mode = "walk"
                self._anim.set_walk_frames_active(True)
                if not self._walk_timer.isActive():
                    self._walk_timer.start()
            elif "side" in self._sprites:
                self._sprite_mode = "side"
                self._anim.set_walk_frames_active(False)
                self._walk_timer.stop()
            return

        # Want idle / settle
        self._anim.set_walk_frames_active(False)
        self._walk_timer.stop()
        if self._sprite_mode in ("walk", "side") and self.has_turn_frames:
            self._start_turn(-1)
            return
        if "front" in self._sprites:
            self._sprite_mode = "front"
        elif "side" in self._sprites:
            self._sprite_mode = "side"
        else:
            self._sprite_mode = next(iter(self._sprites), "front")

    def set_state(self, state: PetState) -> None:
        """Load art for ``state``; sprites preferred; else frames / idle / placeholder."""
        self._state = state
        self._using_fallback = False

        if self._use_sprites:
            self._missing = False
            self._frames = []
            self._frame_index = 0
            self._frame_dir = 1
            self._frame_timer.stop()
            self._refresh_sprite_mode()
            self.update()
            return

        requested = list_frame_paths(state, self._assets_root)
        self._missing = len(requested) == 0

        paths = requested
        if not paths and state is not PetState.idle:
            idle_paths = list_frame_paths(PetState.idle, self._assets_root)
            if idle_paths:
                paths = idle_paths
                self._using_fallback = True

        self._frames = _load_pixmaps(paths)
        if paths and not self._frames:
            self._missing = True
            self._using_fallback = False

        self._frame_index = 0
        self._frame_dir = 1
        self._restart_frame_timer()
        self.update()

    def _interval_ms(self) -> int:
        return int(_FPS_MS.get(self._state.value, _DEFAULT_FPS_MS))

    def _restart_frame_timer(self) -> None:
        self._frame_timer.stop()
        if len(self._frames) > 1:
            self._frame_timer.start(self._interval_ms())

    def _advance_frame(self) -> None:
        n = len(self._frames)
        if n <= 1:
            return
        if n == 2:
            self._frame_index = 1 - self._frame_index
            self.update()
            return
        nxt = self._frame_index + self._frame_dir
        if nxt <= 0:
            self._frame_index = 0
            self._frame_dir = 1
        elif nxt >= n - 1:
            self._frame_index = n - 1
            self._frame_dir = -1
        else:
            self._frame_index = nxt
        self.update()

    def _advance_walk(self) -> None:
        n = len(self._walk_frames)
        if n <= 1:
            return
        self._walk_index = (self._walk_index + 1) % n
        self.update()

    def _advance_turn(self) -> None:
        if not self._turn_frames or self._turn_dir == 0:
            self._turn_timer.stop()
            return
        nxt = self._turn_index + self._turn_dir
        if nxt < 0:
            self._turn_index = 0
            self._finish_turn()
            return
        if nxt >= len(self._turn_frames):
            self._turn_index = len(self._turn_frames) - 1
            self._finish_turn()
            return
        self._turn_index = nxt
        self.update()

    def _tick_anim(self) -> None:
        elapsed_ms = self._anim_clock.restart()
        dt = max(0.001, min(elapsed_ms / 1000.0, 0.1))
        self._anim.tick(dt)
        self.update()

    def _current_pixmap(self) -> QPixmap | None:
        if self._use_sprites:
            if self._sprite_mode == "turn" and self._turn_frames:
                return self._turn_frames[self._turn_index % len(self._turn_frames)]
            if self._sprite_mode == "walk" and self._walk_frames:
                return self._walk_frames[self._walk_index % len(self._walk_frames)]
            pix = self._sprites.get(self._sprite_mode)
            if pix is None:
                pix = self._sprites.get("front") or next(iter(self._sprites.values()), None)
            return pix
        if self._frames:
            return self._frames[self._frame_index]
        return None

    def _needs_side_flip_convention(self) -> bool:
        """Side/walk/turn art faces LEFT; facing=1 (right) → flip."""
        if self._sprite_mode in ("side", "walk"):
            return True
        if self._sprite_mode == "turn":
            # Later turn frames approach side; use flip once past midpoint.
            n = max(1, len(self._turn_frames) - 1)
            return self._turn_index >= n * 0.35
        return False

    def paintEvent(self, event) -> None:  # noqa: N802
        """Draw exactly one pose into a fresh buffer, then Source-blit it.

        macOS Cocoa often ignores CompositionMode_Clear on nested translucent
        widgets, so the wider front silhouette stays as an opaque white ghost
        behind the narrower walk sprite. Replacing the full widget with an
        offscreen ARGB buffer (CompositionMode_Source) and clipping the
        top-level window mask to this frame's alpha removes that ghost.
        """
        del event
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return

        buf = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        buf.fill(0)  # transparent — reliable erase (unlike Clear on Cocoa)

        ip = QPainter(buf)
        # Smooth scale + AA for soft edges; Source-blit + window mask still kill pose ghosts.
        ip.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        ip.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        pix = self._current_pixmap()
        if pix is not None:
            scaled = self._scaled_to_height(pix)
            need_flip = self._facing < 0
            if self._use_sprites and self._needs_side_flip_convention():
                need_flip = self._facing > 0

            tf = self._anim.transform()
            if tf.use_layers and self._sprite_mode == "side":
                self._paint_layered(ip, scaled, tf, need_flip=need_flip)
            else:
                cx = w / 2.0 + tf.offset_x
                cy = h / 2.0 + tf.offset_y
                ip.translate(cx, cy)
                ip.rotate(tf.rotation_deg)
                # Mirror via painter (avoid QPixmap.transformed baking opaque mats).
                flip = -1.0 if need_flip else 1.0
                ip.scale(tf.scale_x * flip, tf.scale_y)
                ip.drawPixmap(
                    int(-scaled.width() / 2),
                    int(-scaled.height() / 2),
                    scaled,
                )
        else:
            side = max(8, min(w, h) - 8)
            x = (w - side) // 2
            y = (h - side) // 2
            ip.setBrush(QColor("#5B8DEF"))
            ip.setPen(Qt.PenStyle.NoPen)
            ip.drawEllipse(x, y, side, side)
        ip.end()

        painter = QPainter(self)
        # Source replaces every destination pixel (RGB+A); Clear is flaky on macOS.
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.drawImage(0, 0, buf)
        painter.end()

        self._sync_window_mask(buf)

    def _sync_window_mask(self, buf: QImage) -> None:
        """Clip the frameless top-level window to this frame's opaque pixels."""
        key = (
            self._sprite_mode,
            self._walk_index,
            self._turn_index,
            self._facing,
            buf.width(),
            buf.height(),
        )
        # Breath scale is absorbed by pad below; refresh when pose/frame/size changes.
        if key == self._mask_key:
            return
        self._mask_key = key

        win = self.window()
        if win is None:
            return
        bitmap = QBitmap.fromImage(buf.createAlphaMask())
        region = QRegion(bitmap)
        # Dilate a few px so idle breath scale does not clip the silhouette.
        pad = 5
        dilated = QRegion()
        for dx in (-pad, 0, pad):
            for dy in (-pad, 0, pad):
                dilated = dilated.united(region.translated(dx, dy))
        region = dilated
        # Map pet-local region into the top-level window if we are a child.
        if win is not self:
            origin = self.mapTo(win, self.rect().topLeft())
            region.translate(origin)
        win.setMask(region)

    def _paint_layered(
        self,
        painter: QPainter,
        scaled: QPixmap,
        tf,
        *,
        need_flip: bool = False,
    ) -> None:
        """Two-layer fake walk fallback when no walk frames."""
        sw, sh = scaled.width(), scaled.height()
        split_y = max(1, min(sh - 1, int(sh * tf.split_frac)))
        overlap = max(2, sh // 40)
        upper_h = min(sh, split_y + overlap)
        lower_y = max(0, split_y - overlap)

        upper = scaled.copy(QRect(0, 0, sw, upper_h))
        lower = scaled.copy(QRect(0, lower_y, sw, sh - lower_y))

        cx = self.width() / 2.0 + tf.offset_x
        cy = self.height() / 2.0 + tf.offset_y
        painter.save()
        painter.translate(cx, cy)
        flip = -1.0 if need_flip else 1.0
        painter.scale(tf.scale_x * flip, tf.scale_y)

        painter.save()
        painter.translate(tf.lower_ox, tf.lower_oy + lower_y - sh / 2.0)
        painter.drawPixmap(int(-sw / 2), 0, lower)
        painter.restore()

        painter.save()
        painter.translate(tf.upper_ox, tf.upper_oy - sh / 2.0)
        painter.rotate(tf.upper_rot)
        painter.drawPixmap(int(-sw / 2), 0, upper)
        painter.restore()

        painter.restore()

    def _scaled_to_height(self, pix: QPixmap) -> QPixmap:
        """Smooth scale on premultiplied ARGB; strip near-zero alpha fringes.

        Premultiplied source keeps bilinear samples from inventing white RGB in
        transparent texels. Tiny-alpha leftovers (AA dust) are zeroed so they
        do not read as a paper outline against the desktop; the Source-blit
        and window mask still erase previous poses. Results are cached per
        source pixmap identity and target height.
        """
        if pix.isNull() or self.height() <= 0:
            return pix
        key = (id(pix), self.height())
        cached = self._scaled_cache.get(key)
        if cached is not None and not cached.isNull():
            return cached
        img = pix.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        scaled = img.scaledToHeight(
            self.height(),
            Qt.TransformationMode.SmoothTransformation,
        )
        out = QPixmap.fromImage(_scrub_alpha_dust(scaled))
        self._scaled_cache[key] = out
        return out
