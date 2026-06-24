# Hand Tracking using MediaPipe

A production-grade hand tracking application that uses **MediaPipe** and your webcam to:

- Track hand landmarks in real-time
- Control the mouse cursor with hand gestures
- Perform left-click via pinch gesture
- Toggle Air Scroll mode for hands-free scrolling
- Run as a background system tray application
- Emergency shutdown via global hotkey (`Ctrl+Alt+Q`)

---

## Platform Support

| Feature | Linux | macOS |
|---------|-------|-------|
| `hand_tracking.py` (basic demo) | ✅ | ✅ |
| `hand_tracking_pro.py` (full app) | ✅ | ✅ |
| `main.py` (Air Scroll) | ✅ | ❌ (no `uinput`) |
| `mirror_desktop.py` | ✅ | ✅ |
| `toggle_scroll.sh` | ✅ | ❌ (Bash script only) |
| System Tray icon | ✅* | ⚠️ Limited |
| Emergency Hotkey (`Ctrl+Alt+Q`) | ✅ | ✅ |

*\* Requires a system tray-compatible desktop environment (GNOME may need an extension like AppIndicator).*

---

## Prerequisites

- **Python 3.7** or higher
- **Webcam** (built-in or USB)
- **pip** package manager

---

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd hand-tracking-using-mediapipe
```

### 2. Create a virtual environment (recommended)

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install required packages

```bash
pip install --upgrade pip
pip install opencv-python mediapipe pyautogui pynput pystray pillow
```

> **Note for macOS (Apple Silicon / M-series):**  
> MediaPipe may not have a pre-built wheel for ARM64 macOS. If you encounter errors:
> ```bash
> pip install mediapipe-silicon  # Community build for Apple Silicon
> ```
> Or use a Conda environment (see below).

### 4. (Alternative) Install with Conda

If you use Miniconda/Anaconda (as on the original development system):

```bash
conda create -n hand_tracking python=3.10 -y
conda activate hand_tracking
pip install opencv-python mediapipe pyautogui pynput pystray pillow
```

### 5. (Linux-only) Additional setup for `main.py`

The `main.py` script uses the Linux `uinput` kernel module to emulate a physical mouse. This requires:
- The `uinput` kernel module loaded
- `sudo` privileges (or udev rules)
- The `evdev` Python package

```bash
# Load the uinput kernel module
sudo modprobe uinput

# Install evdev (if not already installed)
pip install evdev

# Make uinput load on boot (optional)
echo "uinput" | sudo tee /etc/modules-load.d/uinput.conf
```

> **macOS users:** `main.py` will **not** work on macOS because macOS does not have the `uinput` kernel interface. Use `hand_tracking_pro.py` instead, which uses `pyautogui` (cross-platform).

---

## Project Structure

```
hand-tracking-using-mediapipe/
├── config.py              # Camera & screen configuration
├── hand_tracker.py        # HandTracker class (MediaPipe wrapper)
├── hand_tracking.py       # Basic hand tracking demo (simple landmarks)
├── hand_tracking_pro.py   # Full application (mouse control, tray, hotkey)
├── mouse_controller.py    # Virtual mouse via uinput (Linux only)
├── main.py                # Air Scroll application (Linux only, requires sudo)
├── mirror_desktop.py      # Desktop mirroring utility
├── tray_manager.py        # System tray icon manager
├── toggle_scroll.sh       # Bash script to toggle main.py (Linux)
├── error_log.txt          # Runtime error log
├── hand-landmarks.png     # MediaPipe landmark reference
├── Screenshot.png         # Sample output screenshot
└── README.md              # This file
```

---

## Usage

### 🔹 Basic Hand Tracking Demo

**Cross-platform** – Shows hand landmarks and connections on your webcam feed.

```bash
python hand_tracking.py
```

- Displays webcam feed with hand skeleton overlay
- Highlights fingertips with magenta circles
- Shows FPS in top-left corner
- Press **`q`** to exit

---

### 🔹 Full Application with Mouse Control

**Cross-platform** – The main application with cursor control, pinch-to-click, system tray, and hotkey.

```bash
# Default mode (system tray if available)
python hand_tracking_pro.py

# Force console mode (no tray icon)
python hand_tracking_pro.py --no-tray
```

**Features:**
- **Cursor control** – Move your index finger to control the mouse pointer
- **Pinch to click** – Bring thumb and index finger together to left-click
- **System Tray** – Start/Stop/Exit controls (Linux with AppIndicator support)
- **Console mode** – Fallback for environments without system tray
- **Emergency hotkey** – Press `Ctrl+Alt+Q` anywhere to kill the app

**Console mode commands (when `--no-tray` is used):**
| Command | Action |
|---------|--------|
| `q` + Enter | Quit the application |
| `[Enter]` (empty) | Toggle tracking on/off |
| `Ctrl+Alt+Q` | Emergency stop (global hotkey) |

> **Tip:** On macOS, the system tray icon may not work reliably. Use `--no-tray` and the console interface.

---

### 🔹 Air Scroll Application (Linux Only)

**Linux only** – Uses the hardware-emulated virtual mouse (`uinput`) for scrolling and gestures.

```bash
sudo python main.py
```

Or use the toggle script:

```bash
./toggle_scroll.sh
```

**Gesture Controls:**

| Gesture | Action |
|---------|--------|
| **Pinky + Thumb** touch | Toggle Scroll Mode ON/OFF |
| **Index finger** in upper zone | Scroll UP |
| **Index finger** in lower zone | Scroll DOWN |
| **Ring + Thumb** touch | Emergency EXIT (kills the app) |
| **Esc** key | Exit |

**Scroll Zones** (configurable in `main.py`):
- **Upper Zone** (`y < 80`) → Scroll Up
- **Lower Zone** (`y > 140`) → Scroll Down
- **Middle Zone** (`80 ≤ y ≤ 140`) → No scroll

---

### 🔹 Desktop Mirror Utility

**Cross-platform** – Mirrors your desktop in an OpenCV window (for debugging/projection).

```bash
python mirror_desktop.py
```

Press **`q`** to stop.

---

## Configuration

Edit `config.py` to adjust:

```python
CAM_WIDTH = 1920          # Camera capture width
CAM_HEIGHT = 1080         # Camera capture height
SCREEN_WIDTH = 1920        # Your screen width
SCREEN_HEIGHT = 1080       # Your screen height
SMOOTHING = 5              # Smoothing factor for cursor movement
FRAME_MARGIN = 100         # Virtual boundary box margin (pixels)
```

For `hand_tracking_pro.py`, settings are defined as constants at the top of the file:
- `SMOOTHING_ALPHA` – Cursor smoothing (0.0–1.0, lower = smoother)
- `PINCH_DISTANCE_THRESHOLD` – Pinch sensitivity (pixels)
- `CLICK_COOLDOWN` – Debounce time between clicks (seconds)
- `IDLE_TIMEOUT` – Seconds before entering power-saving mode

---

## Troubleshooting

### ❌ Camera not found
```bash
# List available cameras
ls /dev/video*   # Linux
```
If using a virtual machine, ensure the webcam is passed through to the guest OS.

### ❌ `pyautogui` permission issues (macOS)
macOS requires accessibility permissions:
1. Open **System Settings → Privacy & Security → Accessibility**
2. Add your terminal app (or Python) to the allowed list
3. Restart the application

### ❌ `uinput` permission errors (Linux)
```bash
# Either run with sudo:
sudo python main.py

# Or add your user to the 'input' group and set udev rules:
sudo usermod -a -G input $USER
echo 'KERNEL=="uinput", GROUP="input", MODE="0660"' | sudo tee /etc/udev/rules.d/99-uinput.rules
# Reboot or reload udev
```

### ❌ System tray icon missing (Linux GNOME)
GNOME Shell removed AppIndicator support by default. Install an extension:
```bash
# Ubuntu/Debian
sudo apt install gnome-shell-extension-appindicator

# Then restart GNOME Shell (Alt+F2, type 'r', Enter)
```
Or use `--no-tray` to run in console mode.

### ❌ MediaPipe installation fails (macOS Apple Silicon)
```bash
pip install mediapipe-silicon
```
If that doesn't work, use a Conda environment as described in the Installation section.

### ❌ High CPU usage
- The application automatically throttles after **10 seconds** of no hand detected
- For `hand_tracking_pro.py`, the detection confidence is set to `0.7` by default – increase it in the source for more aggressive throttling
- Close other applications using the webcam

---

## License

MIT License – see the [LICENSE](LICENSE) file for details.

---

## Acknowledgements

- [MediaPipe](https://mediapipe.dev/) by Google for hand landmark detection
- [OpenCV](https://opencv.org/) for camera and image processing
- [pyautogui](https://pyautogui.readthedocs.io/) for cross-platform mouse control
- [pynput](https://pynput.readthedocs.io/) for global hotkey support
- [pystray](https://pystray.readthedocs.io/) for system tray integration