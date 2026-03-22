from __future__ import annotations

import time
from pathlib import Path
import sys

import tkinter as tk
from PIL import Image, ImageGrab

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from windows import app as notchi_app


ASSETS_DIR = ROOT / "assets"
HIDE_SCREENSHOT = ASSETS_DIR / "windows-hide-preview.png"
DETAIL_SCREENSHOT = ASSETS_DIR / "windows-detail-preview.png"
GIF_OUTPUT = ASSETS_DIR / "windows-mascots.gif"


def _sample_payloads() -> list[dict[str, str]]:
    cwd_root = ROOT.parent
    return [
        {
            "session_id": "session-alpha",
            "cwd": str(cwd_root / "notchi"),
            "event": "UserPromptSubmit",
            "user_prompt": "thanks this is awesome, ship it",
            "status": "",
        },
        {
            "session_id": "session-alpha",
            "cwd": str(cwd_root / "notchi"),
            "event": "PreToolUse",
            "tool": "Edit",
            "status": "",
        },
        {
            "session_id": "session-beta",
            "cwd": str(cwd_root / "demo-api"),
            "event": "PermissionRequest",
            "tool": "Bash",
            "status": "",
        },
        {
            "session_id": "session-gamma",
            "cwd": str(cwd_root / "broken-build"),
            "event": "UserPromptSubmit",
            "user_prompt": "error bug fail cannot work",
            "status": "",
        },
        {
            "session_id": "session-gamma",
            "cwd": str(cwd_root / "broken-build"),
            "event": "Stop",
            "status": "waiting_for_input",
        },
    ]


def _populate_demo_state(app: notchi_app.NotchiWindowsApp) -> None:
    for payload in _sample_payloads():
        app.store.process(payload)

    with app.store._lock:
        alpha = app.store._sessions["session-alpha"]
        beta = app.store._sessions["session-beta"]
        gamma = app.store._sessions["session-gamma"]

        alpha.messages = [
            "Claude is updating the hook flow and polishing the desktop overlay.",
            "The Windows port is ready to publish with sprites and detail mode.",
        ]
        alpha.events = [
            "Prompt submitted",
            "Running Edit",
            "Finished Edit",
            "Claude is waiting",
        ]
        alpha.current_tool = "Edit"
        alpha.state = "working"
        alpha.started_at = time.time() - 420

        beta.messages = ["Claude needs approval before running a shell command."]
        beta.events = ["Permission requested for Bash", "Claude is waiting"]
        beta.state = "waiting"
        beta.emotion = "neutral"
        beta.started_at = time.time() - 175

        gamma.messages = ["The failing build looks reproducible, and the stack trace is isolated."]
        gamma.events = ["Prompt submitted", "Claude is waiting"]
        gamma.state = "idle"
        gamma.started_at = time.time() - 980
        gamma.last_activity = time.time() - 20

        app.store._selected_session_id = "session-alpha"


def _create_backdrop(root: tk.Tk, width: int, height: int, x: int, y: int) -> tk.Toplevel:
    backdrop = tk.Toplevel(root)
    backdrop.overrideredirect(True)
    backdrop.geometry(f"{width}x{height}+{x}+{y}")
    backdrop.configure(bg="#09111f")
    backdrop.attributes("-topmost", True)
    canvas = tk.Canvas(backdrop, width=width, height=height, bg="#09111f", highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    canvas.create_rectangle(0, 0, width, height, fill="#09111f", outline="")
    canvas.create_oval(-120, -80, 220, 180, fill="#12314d", outline="")
    canvas.create_oval(width - 250, 20, width + 40, 240, fill="#163b33", outline="")
    canvas.create_text(
        42,
        28,
        anchor="nw",
        text="Notchi for Windows",
        fill="#dbeafe",
        font=("Segoe UI", 20, "bold"),
    )
    canvas.create_text(
        42,
        62,
        anchor="nw",
        text="Desktop companion for Claude Code",
        fill="#93c5fd",
        font=("Segoe UI", 11),
    )
    backdrop.update_idletasks()
    return backdrop


def _sync_ui(app: notchi_app.NotchiWindowsApp, cycles: int = 4) -> None:
    for _ in range(cycles):
        app.root.update_idletasks()
        app.root.update()
        time.sleep(0.05)


def _grab_bbox(path: Path, bbox: tuple[int, int, int, int]) -> None:
    image = ImageGrab.grab(bbox=bbox, all_screens=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _window_bbox(window: tk.Misc) -> tuple[int, int, int, int]:
    return (
        window.winfo_rootx(),
        window.winfo_rooty(),
        window.winfo_rootx() + window.winfo_width(),
        window.winfo_rooty() + window.winfo_height(),
    )


def _hero_bbox(app: notchi_app.NotchiWindowsApp, padding: int = 10) -> tuple[int, int, int, int]:
    widget = app.hero
    return (
        widget.winfo_rootx() - padding,
        widget.winfo_rooty() - padding,
        widget.winfo_rootx() + widget.winfo_width() + padding,
        widget.winfo_rooty() + widget.winfo_height() + padding,
    )


def _generate_gif(app: notchi_app.NotchiWindowsApp) -> None:
    frames: list[Image.Image] = []
    app.details_visible = False
    app.update_layout()
    _sync_ui(app)
    for _ in range(10):
        app.animation_phase += 0.35
        app.frame_tick += 0.7
        app.render_mascot(app.store.snapshot())
        _sync_ui(app, cycles=1)
        frame = ImageGrab.grab(bbox=_hero_bbox(app), all_screens=True).convert("P", palette=Image.ADAPTIVE)
        frames.append(frame)

    frames[0].save(
        GIF_OUTPUT,
        save_all=True,
        append_images=frames[1:],
        duration=120,
        loop=0,
        disposal=2,
    )


def main() -> None:
    notchi_app.APP_PORT = 0
    original_auto_install = notchi_app.NotchiWindowsApp._auto_install_hook
    notchi_app.NotchiWindowsApp._auto_install_hook = lambda self: self.status_var.set("Preview mode")
    app = notchi_app.NotchiWindowsApp()

    try:
        app.root.geometry("520x430+160+120")
        _populate_demo_state(app)

        backdrop = _create_backdrop(app.root, 860, 560, 40, 60)

        app.details_visible = False
        app.update_layout()
        app.render()
        _sync_ui(app)
        _grab_bbox(HIDE_SCREENSHOT, _window_bbox(app.root))

        app.details_visible = True
        app.update_layout()
        app.render()
        _sync_ui(app)
        _grab_bbox(DETAIL_SCREENSHOT, _window_bbox(app.root))

        _generate_gif(app)
        backdrop.destroy()
    finally:
        try:
            app.server.server_close()
            app.root.destroy()
        except Exception:
            pass
        notchi_app.NotchiWindowsApp._auto_install_hook = original_auto_install


if __name__ == "__main__":
    main()
