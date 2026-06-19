"""
Hand Tracking Pro — Production-Grade Modular Hand Tracking Application
======================================================================
Refactored from the original MediaPipe hand tracking prototype into a
modular, reusable, and production-grade codebase.

Features:
    - HandDetector class (reusable module)
    - Real-time hand landmark detection with configurable confidence
    - Screen-space mouse mapping with Exponential Moving Average smoothing
    - Pinch gesture (thumb tip → index tip distance < threshold) → left click
    - Debounce mechanism to prevent rapid-fire clicking
    - System tray icon with Start / Stop / Exit controls
    - Global hotkey (Ctrl+Alt+Q) for emergency graceful shutdown
    - Headless (background) execution — no OpenCV windows
    - Automatic fallback to console-mode when tray is unavailable

Author : Generated from AR_Pick project
License: MIT
"""

from __future__ import annotations

import time
import threading
import os
import signal
import sys
from dataclasses import dataclass, field
from typing import Optional

import cv2
import mediapipe as mp
import pyautogui
from pynput import keyboard as pynput_keyboard

# Optional import — tray icon may fail on some Linux DEs
_has_tray: bool = True
try:
    import pystray
    from pystray import MenuItem as Item
    from PIL import Image, ImageDraw
except Exception:
    _has_tray = False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# --- Detection / Tracking ---------------------------------------------------
DETECTION_CONFIDENCE: float = 0.7
TRACKING_CONFIDENCE: float = 0.5
CAMERA_ID: int = 0
CAMERA_WIDTH: int = 640
CAMERA_HEIGHT: int = 480
MAX_NUM_HANDS: int = 1  # we only need one hand for cursor control

# --- Screen Mapping ---------------------------------------------------------
SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()
# Smoothing factor for Exponential Moving Average (0 < alpha ≤ 1)
# Lower values = smoother but more lag
SMOOTHING_ALPHA: float = 0.3

# --- Pinch Gesture ----------------------------------------------------------
PINCH_THUMB_TIP_ID: int = 4
PINCH_INDEX_TIP_ID: int = 8
PINCH_DISTANCE_THRESHOLD: float = 30.0  # pixels
CLICK_COOLDOWN: float = 0.5  # seconds — debounce window

# --- Throttle (idle power saving) -------------------------------------------
IDLE_THROTTLE_SECONDS: float = 2.0  # run at reduced rate after 10 s of no hand
IDLE_TIMEOUT: float = 10.0

# --- Global Hotkey (Ctrl+Alt+Q) ---------------------------------------------
HOTKEY_CTRL: bool = False
HOTKEY_ALT: bool = False
HOTKEY_Q: bool = False

# --- Mode (console fallback if no tray) -------------------------------------
USE_TRAY: bool = _has_tray and ("--no-tray" not in sys.argv)

# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class Landmark:
    """A single hand landmark with normalized coordinates."""

    id: int
    x: float  # normalized 0 – 1
    y: float  # normalized 0 – 1
    z: float  # depth


@dataclass
class HandData:
    """Holds all landmark positions for one detected hand."""

    landmarks: list[Landmark] = field(default_factory=list)
    pixel_positions: list[tuple[int, int]] = field(default_factory=list)

    def __getitem__(self, lm_id: int) -> Landmark | None:
        for lm in self.landmarks:
            if lm.id == lm_id:
                return lm
        return None


# ---------------------------------------------------------------------------
# HandDetector  (Phase 1 – Refactored reusable class)
# ---------------------------------------------------------------------------


class HandDetector:
    """
    Detects hands in a video frame using MediaPipe Hands.

    Provides two primary methods:
        - findHands(img)     → annotated image
        - findPosition(img)  → list[HandData] with landmark details
    """

    def __init__(
        self,
        detection_confidence: float = DETECTION_CONFIDENCE,
        tracking_confidence: float = TRACKING_CONFIDENCE,
        max_num_hands: int = MAX_NUM_HANDS,
    ) -> None:
        self._mp_hands = mp.solutions.hands
        self._mp_draw = mp.solutions.drawing_utils
        self._hands = self._mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_num_hands,
            min_detection_confidence=detection_confidence,
            min_tracking_confidence=tracking_confidence,
        )

        # Internal state for throttling / performance
        self._last_hand_seen: float = time.time()
        self._idle: bool = False

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def findHands(self, img: cv2.Mat, draw: bool = True) -> cv2.Mat:
        """
        Process an image and optionally draw hand landmarks / connections.

        Args:
            img:   BGR frame from camera.
            draw:  Whether to annotate the frame with landmarks.

        Returns:
            Annotated image (may be the same object if draw=False).
        """
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self._results = self._hands.process(img_rgb)

        if self._results.multi_hand_landmarks:
            self._last_hand_seen = time.time()
            self._idle = False

            if draw:
                for hand_lms in self._results.multi_hand_landmarks:
                    self._mp_draw.draw_landmarks(
                        img, hand_lms, self._mp_hands.HAND_CONNECTIONS
                    )
        else:
            # Check idle timeout
            if time.time() - self._last_hand_seen > IDLE_TIMEOUT:
                self._idle = True

        return img

    def findPosition(self, img: cv2.Mat) -> list[HandData]:
        """
        Extract normalized landmark positions for all detected hands.

        Args:
            img: BGR frame (used only for shape dimensions).

        Returns:
            List of HandData objects, one per detected hand.
        """
        h, w, _ = img.shape
        hands_data: list[HandData] = []

        if not hasattr(self, "_results") or not self._results.multi_hand_landmarks:
            return hands_data

        for hand_lms in self._results.multi_hand_landmarks:
            data = HandData()
            for idx, lm in enumerate(hand_lms.landmark):
                cx, cy = int(lm.x * w), int(lm.y * h)
                data.landmarks.append(Landmark(id=idx, x=lm.x, y=lm.y, z=lm.z))
                data.pixel_positions.append((cx, cy))
            hands_data.append(data)

        return hands_data

    def is_idle(self) -> bool:
        """Return True if no hand detected for longer than IDLE_TIMEOUT."""
        return self._idle


# ---------------------------------------------------------------------------
# MouseController  (Phase 2 – Screen mapping, smoothing, gesture clicks)
# ---------------------------------------------------------------------------


class MouseController:
    """
    Maps hand position from camera coordinates to screen coordinates,
    applies EMA smoothing, and detects pinch gestures for mouse clicks.
    """

    def __init__(
        self,
        smoothing_alpha: float = SMOOTHING_ALPHA,
        pinch_threshold: float = PINCH_DISTANCE_THRESHOLD,
        click_cooldown: float = CLICK_COOLDOWN,
    ) -> None:
        self._alpha = smoothing_alpha
        self._pinch_threshold = pinch_threshold
        self._cooldown = click_cooldown

        # Smoothed cursor position (EMA)
        self._smooth_x: float | None = None
        self._smooth_y: float | None = None

        # Debounce state for pinch click
        self._last_click_time: float = 0.0
        self._was_pinched: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(
        self, hand: HandData, frame_width: int, frame_height: int
    ) -> None:
        """
        Process one hand data sample:
          1. Map hand → screen coordinates.
          2. Apply EMA smoothing.
          3. Move mouse.
          4. Check pinch gesture and trigger click with debounce.
        """
        if not hand.pixel_positions:
            return

        # Use index finger MCP (id=5) as cursor anchor for natural feel
        anchor_id = 5
        if anchor_id >= len(hand.pixel_positions):
            return

        raw_x, raw_y = hand.pixel_positions[anchor_id]

        # --- Map to screen coordinates ---
        screen_x = (raw_x / frame_width) * SCREEN_WIDTH
        screen_y = (raw_y / frame_height) * SCREEN_HEIGHT

        # --- EMA Smoothing ---
        if self._smooth_x is None:
            self._smooth_x = screen_x
            self._smooth_y = screen_y
        else:
            self._smooth_x = (
                self._alpha * screen_x + (1 - self._alpha) * self._smooth_x
            )
            self._smooth_y = (
                self._alpha * screen_y + (1 - self._alpha) * self._smooth_y
            )

        # ------------------------------------------------------------------
        # Move the mouse cursor
        # ------------------------------------------------------------------
        pyautogui.moveTo(int(self._smooth_x), int(self._smooth_y))

        # ------------------------------------------------------------------
        # Pinch gesture detection (thumb tip → index tip distance)
        # ------------------------------------------------------------------
        thumb_pos = (
            hand.pixel_positions[PINCH_THUMB_TIP_ID]
            if len(hand.pixel_positions) > PINCH_THUMB_TIP_ID
            else None
        )
        index_pos = (
            hand.pixel_positions[PINCH_INDEX_TIP_ID]
            if len(hand.pixel_positions) > PINCH_INDEX_TIP_ID
            else None
        )

        if thumb_pos is not None and index_pos is not None:
            dist = self._euclidean(thumb_pos, index_pos)
            is_pinched = dist < self._pinch_threshold

            now = time.time()

            # --- Debounce ---
            if is_pinched:
                if (
                    not self._was_pinched
                    and (now - self._last_click_time) > self._cooldown
                ):
                    pyautogui.click()
                    self._last_click_time = now
                self._was_pinched = True
            else:
                self._was_pinched = False

    def reset_smoothing(self) -> None:
        """Reset EMA state (e.g. on hand loss / re-detect)."""
        self._smooth_x = None
        self._smooth_y = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _euclidean(a: tuple[int, int], b: tuple[int, int]) -> float:
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


# ---------------------------------------------------------------------------
# Shared global state (used by both TrayApp and ConsoleApp)
# ---------------------------------------------------------------------------

_running: bool = False
_tracking: bool = True
_stop_event = threading.Event()
_emergency_flag: bool = False


def emergency_stop() -> None:
    """Emergency stop — called from hotkey or signal handler."""
    global _running, _emergency_flag
    print("\n[Emergency] Ctrl+Alt+Q pressed — shutting down.")
    _running = False
    _emergency_flag = True
    _stop_event.set()
    os._exit(0)


# ---------------------------------------------------------------------------
# Global hotkey listener (shared between tray & console modes)
# ---------------------------------------------------------------------------

_hotkey_listener: pynput_keyboard.Listener | None = None
_pressed_keys: set = set()


def _hotkey_on_press(key) -> None:
    """Detect Ctrl+Alt+Q combination globally."""
    global _pressed_keys
    _pressed_keys.add(key)

    has_ctrl = (
        pynput_keyboard.Key.ctrl_l in _pressed_keys
        or pynput_keyboard.Key.ctrl_r in _pressed_keys
    )
    has_alt = (
        pynput_keyboard.Key.alt_l in _pressed_keys
        or pynput_keyboard.Key.alt_r in _pressed_keys
    )
    has_q = (
        hasattr(key, "char") and key.char is not None and key.char.lower() == "q"
    )

    if has_ctrl and has_alt and has_q:
        emergency_stop()


def _hotkey_on_release(key) -> None:
    _pressed_keys.discard(key)


def _start_hotkey_listener() -> pynput_keyboard.Listener:
    listener = pynput_keyboard.Listener(
        on_press=_hotkey_on_press, on_release=_hotkey_on_release
    )
    listener.daemon = True
    listener.start()
    return listener


# ---------------------------------------------------------------------------
# Core tracking loop (used by both TrayApp and ConsoleApp)
# ---------------------------------------------------------------------------


def _tracking_loop() -> None:
    """Main camera + detection + mouse loop (runs in background thread)."""
    global _running, _tracking

    cap = cv2.VideoCapture(CAMERA_ID)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

    detector = HandDetector()
    mouse = MouseController()
    fps_counter = _FPSCounter()

    while _running and not _stop_event.is_set():
        # --- Throttle if idle to save CPU ---
        if detector.is_idle():
            time.sleep(IDLE_THROTTLE_SECONDS)
            mouse.reset_smoothing()
            continue

        if not _tracking:
            time.sleep(0.1)
            continue

        success, img = cap.read()
        if not success:
            time.sleep(0.05)
            continue

        # Flip horizontally for mirror-like experience
        img = cv2.flip(img, 1)

        # Phase 1: detect (headless — no drawing)
        img = detector.findHands(img, draw=False)

        # Phase 2: get positions & control mouse
        hands = detector.findPosition(img)
        if hands:
            mouse.update(hands[0], CAMERA_WIDTH, CAMERA_HEIGHT)
        else:
            mouse.reset_smoothing()

        # FPS logging
        fps_counter.tick()
        if fps_counter.elapsed >= 2.0:
            fps_counter.reset()

    cap.release()
    cv2.destroyAllWindows()


# ---------------------------------------------------------------------------
# FPS Counter helper
# ---------------------------------------------------------------------------


class _FPSCounter:
    """Simple FPS counter used for internal monitoring."""

    def __init__(self) -> None:
        self._start = time.perf_counter()
        self._frames = 0
        self._last = self._start

    def tick(self) -> None:
        self._frames += 1
        self._last = time.perf_counter()

    @property
    def fps(self) -> float:
        return self._frames / (self._last - self._start + 1e-9)

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self._start

    def reset(self) -> None:
        self._start = time.perf_counter()
        self._frames = 0


# ---------------------------------------------------------------------------
# Mode 1: TrayApp (system tray icon — preferred)
# ---------------------------------------------------------------------------


class TrayApp:
    """System tray icon with Start/Stop/Exit controls."""

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None

    def run(self) -> None:
        """Start the icon (blocks until Exit is chosen)."""
        global _running
        _running = True
        icon = self._build_icon()
        _start_tracking_thread()
        icon.run()
        _cleanup()

    def _start_tracking(self, icon, item) -> None:
        global _tracking
        _tracking = True
        if not self._thread or not self._thread.is_alive():
            _start_tracking_thread()

    def _stop_tracking(self, icon, item) -> None:
        global _tracking
        _tracking = False

    def _exit_app(self, icon, item) -> None:
        global _running
        _running = False
        _stop_event.set()
        icon.stop()

    def _build_icon(self) -> pystray.Icon:
        image = _create_icon_image()
        menu = pystray.Menu(
            Item("Start Tracking", self._start_tracking, default=True),
            Item("Stop Tracking", self._stop_tracking),
            Item("Exit", self._exit_app),
        )
        return pystray.Icon("HandTrackPro", image, "Hand Track Pro", menu)


def _create_icon_image(size: int = 64) -> Image.Image:
    """Generate a simple 64×64 icon with a hand-like symbol."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 8
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(255, 105, 180, 255),
    )
    inner_margin = margin + 10
    draw.ellipse(
        [inner_margin, inner_margin, size - inner_margin, size - inner_margin],
        fill=(255, 255, 255, 255),
    )
    return img


# ---------------------------------------------------------------------------
# Mode 2: ConsoleApp (fallback when system tray is unavailable)
# ---------------------------------------------------------------------------


class ConsoleApp:
    """
    Console-based fallback when system tray is unsupported (e.g. GNOME).

    Runs tracking in the foreground. Type 'q' + Enter to quit,
    or press Ctrl+Alt+Q to emergency stop.
    """

    def run(self) -> None:
        global _running, _tracking
        _running = True

        _start_tracking_thread()

        print()
        print("  Tracking is ACTIVE (console mode)")
        print("  Commands:")
        print("    [Enter] space + Enter = toggle tracking")
        print("    [Enter] q + Enter     = quit")
        print("    [Global] Ctrl+Alt+Q   = emergency stop")
        print()

        try:
            while _running and not _stop_event.is_set():
                cmd = input(">> ").strip().lower()
                if cmd == "q":
                    break
                elif cmd == "":
                    _tracking = not _tracking
                    status = "ACTIVE" if _tracking else "STOPPED"
                    print(f"  Tracking: {status}")
                else:
                    print(f"  Unknown command: {cmd}")
        except (EOFError, KeyboardInterrupt):
            pass
        finally:
            _running = False
            _stop_event.set()
            print("\n  Shutting down...")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _start_tracking_thread() -> None:
    _stop_event.clear()
    thread = threading.Thread(target=_tracking_loop, daemon=True)
    thread.start()


def _cleanup() -> None:
    try:
        if _hotkey_listener is not None:
            _hotkey_listener.stop()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Entry point  (Phase 1 – main() function)
# ---------------------------------------------------------------------------


def main() -> None:
    """
    Application entry point.

    Auto-detects whether a system tray is available:
      - Tray mode: the default, requires an AppIndicator-compatible DE
      - Console mode: fallback for GNOME / Pop!_OS without tray extensions.
        Use ``--no-tray`` flag to force console mode.
    """
    global _hotkey_listener

    # Start the global hotkey listener (works in both modes)
    _hotkey_listener = _start_hotkey_listener()

    print("=" * 50)
    print("  Hand Track Pro")
    print("  Running in background (headless)")
    print("  Emergency hotkey: Ctrl+Alt+Q")
    print(f"  Screen: {SCREEN_WIDTH}x{SCREEN_HEIGHT}")
    print("=" * 50)

    if USE_TRAY:
        print("  Mode: System Tray")
        print("  Use the tray icon to control tracking.")
        print("  (If no icon appears, re-run with --no-tray)")
        print()
        try:
            app = TrayApp()
            app.run()
        except Exception as e:
            print(f"  Tray unavailable ({e}), falling back to console mode...")
            _fallback_console()
    else:
        _fallback_console()


def _fallback_console() -> None:
    """Run in console mode as a fallback."""
    print("  Mode: Console")
    print("  Press Ctrl+Alt+Q to force-quit in an emergency.")
    app = ConsoleApp()
    app.run()


if __name__ == "__main__":
    main()