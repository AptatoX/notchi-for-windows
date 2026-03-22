from __future__ import annotations

import json
import math
import socketserver
import threading
import time
import ctypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tkinter as tk
from PIL import Image, ImageTk
from tkinter import messagebox


APP_HOST = "127.0.0.1"
APP_PORT = 8765
REFRESH_MS = 500
ANIMATION_MS = 120
MAX_EVENTS = 8
MAX_MESSAGES = 5
EMOTION_DECAY = 0.92
PROMPT_EMOTION_DAMPEN = 0.55
REPLY_EMOTION_DAMPEN = 0.3
HAPPY_THRESHOLD = 0.3
SAD_THRESHOLD = 0.42
SOB_THRESHOLD = 0.8
TRANSPARENT_KEY = "#00ff00"
SESSION_SLEEP_SECONDS = 180


@dataclass
class SessionData:
    session_id: str
    cwd: str
    sprite_x: float = 0.5
    sprite_y_offset: float = 0.0
    started_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    state: str = "idle"
    last_prompt: str = ""
    current_tool: str = ""
    permission_mode: str = "default"
    interactive: bool = True
    emotion: str = "neutral"
    emotion_scores: dict[str, float] = field(default_factory=lambda: {"happy": 0.0, "sad": 0.0})
    last_emotion_update: float = field(default_factory=time.time)
    events: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)

    @property
    def project_name(self) -> str:
        path = Path(self.cwd)
        return path.name or self.cwd or "unknown"

    @property
    def duration(self) -> str:
        total = int(time.time() - self.started_at)
        minutes, seconds = divmod(total, 60)
        return f"{minutes}m {seconds:02d}s"


class ConversationParser:
    def __init__(self) -> None:
        self._offsets: dict[str, int] = {}
        self._seen_ids: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def mark_current_position(self, session_id: str, cwd: str) -> None:
        path = self.session_file_path(session_id, cwd)
        with self._lock:
            if not path.exists():
                self._offsets[session_id] = 0
                self._seen_ids[session_id] = set()
                return
            self._offsets[session_id] = path.stat().st_size
            self._seen_ids[session_id] = set()

    def reset(self, session_id: str) -> None:
        with self._lock:
            self._offsets.pop(session_id, None)
            self._seen_ids.pop(session_id, None)

    def parse_incremental(self, session_id: str, cwd: str) -> list[str]:
        path = self.session_file_path(session_id, cwd)
        if not path.exists():
            return []

        with self._lock:
            offset = self._offsets.get(session_id, 0)
            seen_ids = self._seen_ids.setdefault(session_id, set())
            file_size = path.stat().st_size
            if file_size < offset:
                offset = 0
                seen_ids.clear()

            if file_size == offset:
                return []

            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                handle.seek(offset)
                chunk = handle.read()

            self._offsets[session_id] = file_size

        messages: list[str] = []
        for line in chunk.splitlines():
            line = line.strip()
            if not line:
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            if payload.get("type") != "assistant":
                continue

            message_id = payload.get("uuid")
            if not message_id or message_id in seen_ids:
                continue

            if payload.get("isMeta") is True:
                continue

            message = payload.get("message", {})
            content = message.get("content")
            text = self._extract_text(content)
            if not text:
                continue

            seen_ids.add(message_id)
            messages.append(text)

        return messages

    @staticmethod
    def _extract_text(content: Any) -> str:
        if isinstance(content, str):
            text = content.strip()
            return text if text and not text.startswith("[Request interrupted") else ""

        if not isinstance(content, list):
            return ""

        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "text":
                continue
            text = str(block.get("text", "")).strip()
            if text and not text.startswith("[Request interrupted"):
                parts.append(text)
        return "\n".join(parts).strip()

    @staticmethod
    def session_file_path(session_id: str, cwd: str) -> Path:
        project_dir = cwd.replace("/", "-").replace("\\", "-").replace(".", "-").replace(":", "")
        return Path.home() / ".claude" / "projects" / project_dir / f"{session_id}.jsonl"


class EmotionAnalyzer:
    HAPPY_WORDS = {
        "thanks", "thank you", "great", "awesome", "nice", "perfect", "love", "happy",
        "good", "cool", "excellent", "yay", "success", "worked", "win",
    }
    SAD_WORDS = {
        "error", "fail", "failed", "broken", "bug", "sad", "frustrated", "stuck",
        "annoying", "bad", "issue", "problem", "hate", "wrong", "sob", "can't", "cannot",
    }
    CALM_WORDS = {
        "okay", "ok", "sure", "sounds good", "fixed", "resolved", "done", "complete",
        "completed", "all set", "no worries", "works now",
    }

    @classmethod
    def update_session_emotion(cls, session: SessionData, text: str, source: str) -> None:
        cls.decay_session_emotion(session)
        emotion, intensity = cls.analyze(text)
        dampen = PROMPT_EMOTION_DAMPEN if source == "prompt" else REPLY_EMOTION_DAMPEN
        if emotion == "neutral":
            session.emotion_scores["happy"] *= 0.9
            session.emotion_scores["sad"] *= 0.9
        else:
            session.emotion_scores[emotion] = min(
                1.0,
                session.emotion_scores.get(emotion, 0.0) + intensity * dampen,
            )
            other = "sad" if emotion == "happy" else "happy"
            cross_decay = 0.9 if source == "reply" else 0.85
            session.emotion_scores[other] *= cross_decay

        session.last_emotion_update = time.time()
        cls.resolve_session_emotion(session)

    @classmethod
    def decay_session_emotion(cls, session: SessionData) -> None:
        now = time.time()
        elapsed = max(0.0, now - session.last_emotion_update)
        if elapsed <= 0:
            return

        # Roughly match the macOS app's gradual fade by decaying per minute.
        factor = EMOTION_DECAY ** (elapsed / 60.0)
        for key in list(session.emotion_scores):
            value = session.emotion_scores[key] * factor
            session.emotion_scores[key] = 0.0 if value < 0.01 else value
        session.last_emotion_update = now
        cls.resolve_session_emotion(session)

    @classmethod
    def resolve_session_emotion(cls, session: SessionData) -> None:
        happy = session.emotion_scores.get("happy", 0.0)
        sad = session.emotion_scores.get("sad", 0.0)
        if sad >= SOB_THRESHOLD:
            session.emotion = "sob"
        elif sad >= SAD_THRESHOLD:
            session.emotion = "sad"
        elif happy >= HAPPY_THRESHOLD:
            session.emotion = "happy"
        else:
            session.emotion = "neutral"

    @classmethod
    def analyze(cls, text: str) -> tuple[str, float]:
        lowered = text.lower()
        happy_hits = sum(1 for word in cls.HAPPY_WORDS if word in lowered)
        sad_hits = sum(1 for word in cls.SAD_WORDS if word in lowered)
        calm_hits = sum(1 for word in cls.CALM_WORDS if word in lowered)

        if calm_hits > 0 and happy_hits == sad_hits == 0:
            return "neutral", 0.0
        if happy_hits == sad_hits == 0:
            return "neutral", 0.0
        if sad_hits > happy_hits:
            return "sad", min(1.0, 0.35 + sad_hits * 0.2)
        if happy_hits > sad_hits:
            return "happy", min(1.0, 0.35 + happy_hits * 0.18)
        return "neutral", 0.0


class SessionStore:
    def __init__(self, parser: ConversationParser) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, SessionData] = {}
        self._parser = parser
        self._selected_session_id: str | None = None

    def process(self, payload: dict[str, Any]) -> None:
        session_id = payload.get("session_id") or "unknown"
        cwd = payload.get("cwd") or ""
        event_name = payload.get("event", "")
        status = payload.get("status", "")
        tool = payload.get("tool") or ""
        new_messages: list[str] = []

        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                sprite_x, sprite_y_offset = self._resolve_sprite_position(
                    session_id,
                    [item.sprite_x for item in self._sessions.values()],
                )
                session = SessionData(
                    session_id=session_id,
                    cwd=cwd,
                    sprite_x=sprite_x,
                    sprite_y_offset=sprite_y_offset,
                )
                self._sessions[session_id] = session
                if self._selected_session_id is None:
                    self._selected_session_id = session_id

            session.cwd = cwd or session.cwd
            session.last_activity = time.time()
            session.permission_mode = payload.get("permission_mode", session.permission_mode)
            session.interactive = payload.get("interactive", session.interactive)

            if event_name == "UserPromptSubmit":
                prompt = (payload.get("user_prompt") or "").strip()
                if prompt:
                    session.last_prompt = prompt[:120]
                    EmotionAnalyzer.update_session_emotion(session, prompt, source="prompt")
                session.messages = []
                session.state = "working"
                session.current_tool = ""
                self._parser.mark_current_position(session_id, session.cwd)
            elif event_name == "PreToolUse":
                session.state = "working"
                session.current_tool = tool
            elif event_name == "PermissionRequest":
                session.state = "waiting"
                session.current_tool = tool
            elif event_name == "PreCompact":
                session.state = "compacting"
            elif event_name in {"PostToolUse", "Stop", "SubagentStop"}:
                if event_name in {"Stop", "SubagentStop"} or status == "waiting_for_input":
                    session.state = "idle"
                    session.current_tool = ""
                new_messages = self._parser.parse_incremental(session_id, session.cwd)
            elif event_name == "SessionStart":
                session.state = "working" if status != "waiting_for_input" else "idle"
            elif event_name == "SessionEnd":
                self._sessions.pop(session_id, None)
                self._parser.reset(session_id)
                if self._selected_session_id == session_id:
                    self._selected_session_id = next(iter(self._sessions), None)
                return
            elif status == "waiting_for_input":
                session.state = "idle"

            line = self._format_event_line(event_name, tool, status)
            if line:
                session.events.append(line)
                session.events = session.events[-MAX_EVENTS:]

            if new_messages:
                session.messages.extend(new_messages)
                session.messages = session.messages[-MAX_MESSAGES:]
                for message in new_messages:
                    EmotionAnalyzer.update_session_emotion(session, message, source="reply")
            else:
                EmotionAnalyzer.decay_session_emotion(session)

    def snapshot(self) -> list[SessionData]:
        with self._lock:
            for session in self._sessions.values():
                self._apply_sleep_state_locked(session)
                EmotionAnalyzer.decay_session_emotion(session)
            return sorted(
                [self._copy_session(session) for session in self._sessions.values()],
                key=lambda item: item.last_activity,
                reverse=True,
            )

    def selected_session_id(self) -> str | None:
        with self._lock:
            return self._selected_session_id

    def select_session(self, session_id: str | None) -> None:
        with self._lock:
            if session_id is None or session_id in self._sessions:
                self._selected_session_id = session_id

    def effective_session(self) -> SessionData | None:
        with self._lock:
            for session in self._sessions.values():
                self._apply_sleep_state_locked(session)
            target = self._sessions.get(self._selected_session_id or "")
            if target is not None:
                return self._copy_session(target)
            if not self._sessions:
                return None
            session = max(self._sessions.values(), key=lambda item: item.last_activity)
            return self._copy_session(session)

    @staticmethod
    def _copy_session(session: SessionData) -> SessionData:
        return SessionData(
            session_id=session.session_id,
            cwd=session.cwd,
            sprite_x=session.sprite_x,
            sprite_y_offset=session.sprite_y_offset,
            started_at=session.started_at,
            last_activity=session.last_activity,
            state=session.state,
            last_prompt=session.last_prompt,
            current_tool=session.current_tool,
            permission_mode=session.permission_mode,
            interactive=session.interactive,
            emotion=session.emotion,
            emotion_scores=dict(session.emotion_scores),
            last_emotion_update=session.last_emotion_update,
            events=list(session.events),
            messages=list(session.messages),
        )

    @staticmethod
    def _resolve_sprite_position(session_id: str, existing_positions: list[float]) -> tuple[float, float]:
        x_position_min = 0.08
        x_position_range = 0.82
        x_min_separation = 0.14
        x_nudge_step = 0.23

        hashed = abs(hash(session_id))
        candidate = x_position_min + (hashed % 820) / 1000.0
        for _ in range(10):
            too_close = any(abs(current - candidate) < x_min_separation for current in existing_positions)
            if not too_close:
                break
            candidate = ((candidate - x_position_min + x_nudge_step) % x_position_range) + x_position_min

        y_offset = -float((hashed >> 8) % 18)
        return candidate, y_offset

    @staticmethod
    def _apply_sleep_state_locked(session: SessionData) -> None:
        if time.time() - session.last_activity > SESSION_SLEEP_SECONDS and session.state == "idle":
            session.state = "sleeping"

    @staticmethod
    def _format_event_line(event_name: str, tool: str, status: str) -> str:
        labels = {
            "UserPromptSubmit": "Prompt submitted",
            "SessionStart": "Session started",
            "PreToolUse": f"Running {tool or 'tool'}",
            "PostToolUse": f"Finished {tool or 'tool'}",
            "PermissionRequest": f"Permission requested for {tool or 'tool'}",
            "PreCompact": "Compacting context",
            "Stop": "Claude is waiting",
            "SubagentStop": "Subagent is waiting",
            "SessionEnd": "Session ended",
        }
        suffix = " (error)" if status == "error" else ""
        return labels.get(event_name, event_name) + suffix


class HookInstaller:
    def __init__(self, app_dir: Path) -> None:
        self.app_dir = app_dir
        self.claude_dir = Path.home() / ".claude"
        self.hooks_dir = self.claude_dir / "hooks"
        self.settings_path = self.claude_dir / "settings.json"
        self.installed_hook = self.hooks_dir / "notchi-hook.ps1"

    def install(self) -> tuple[bool, str]:
        if not self.claude_dir.exists():
            return False, f"Claude config directory not found: {self.claude_dir}"

        self.hooks_dir.mkdir(parents=True, exist_ok=True)
        hook_source = self.app_dir / "notchi-hook.ps1"
        self.installed_hook.write_text(hook_source.read_text(encoding="utf-8"), encoding="utf-8")

        data: dict[str, Any] = {}
        if self.settings_path.exists():
            try:
                data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}

        hooks = data.get("hooks", {})
        command = f'powershell -NoProfile -ExecutionPolicy Bypass -File "{self.installed_hook}"'
        entry = [{"type": "command", "command": command}]
        with_matcher = [{"matcher": "*", "hooks": entry}]
        without_matcher = [{"hooks": entry}]
        precompact = [{"matcher": "auto", "hooks": entry}, {"matcher": "manual", "hooks": entry}]

        config_by_event = {
            "UserPromptSubmit": without_matcher,
            "SessionStart": without_matcher,
            "PreToolUse": with_matcher,
            "PostToolUse": with_matcher,
            "PermissionRequest": with_matcher,
            "PreCompact": precompact,
            "Stop": without_matcher,
            "SubagentStop": without_matcher,
            "SessionEnd": without_matcher,
        }

        for event_name, config in config_by_event.items():
            existing = hooks.get(event_name, [])
            if not any(self._contains_notchi_hook(item) for item in existing):
                existing.extend(config)
            hooks[event_name] = existing

        data["hooks"] = hooks
        self.settings_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        return True, f"Installed hook into {self.installed_hook}"

    def is_installed(self) -> bool:
        if not self.settings_path.exists():
            return False
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        hooks = data.get("hooks", {})
        return any(
            self._contains_notchi_hook(item)
            for event_entries in hooks.values()
            for item in event_entries
        )

    @staticmethod
    def _contains_notchi_hook(entry: dict[str, Any]) -> bool:
        for hook in entry.get("hooks", []):
            command = hook.get("command", "")
            if "notchi-hook.ps1" in command:
                return True
        return False


class SpriteRenderer:
    def __init__(self, assets_dir: Path) -> None:
        self.assets_dir = assets_dir
        self._cache: dict[tuple[str, int, int], ImageTk.PhotoImage] = {}
        self._grass_cache: dict[int, ImageTk.PhotoImage] = {}

    def get_frame(self, state: str, emotion: str, frame_index: int, scale: float = 2.0) -> ImageTk.PhotoImage:
        frame_count = 5 if state == "compacting" else 6
        normalized = frame_index % frame_count
        scale_key = int(scale * 100)
        cache_key = (f"{state}:{emotion}", normalized, scale_key)
        if cache_key not in self._cache:
            image = self._load_frame_image(state, emotion, normalized, scale)
            self._cache[cache_key] = ImageTk.PhotoImage(image)
        return self._cache[cache_key]

    def get_grass(self, scale: float = 1.0) -> ImageTk.PhotoImage:
        scale_key = int(scale * 100)
        if scale_key not in self._grass_cache:
            path = self.assets_dir / "GrassIsland.imageset" / "grass.png"
            image = Image.open(path).convert("RGBA")
            width = max(96, int(172 * scale))
            height = max(40, int(70 * scale))
            image = image.resize((width, height), Image.Resampling.NEAREST)
            self._grass_cache[scale_key] = ImageTk.PhotoImage(image)
        return self._grass_cache[scale_key]

    def _load_frame_image(self, state: str, emotion: str, frame_index: int, scale: float) -> Image.Image:
        columns = 5 if state == "compacting" else 6
        sprite_name = self._sprite_name_for(state, emotion)
        path = self.assets_dir / f"{sprite_name}.imageset" / "sprite_sheet.png"
        sheet = Image.open(path).convert("RGBA")
        frame_width = sheet.width // columns
        frame = sheet.crop((frame_index * frame_width, 0, (frame_index + 1) * frame_width, sheet.height))
        alpha_box = frame.getchannel("A").getbbox()
        if alpha_box is not None:
            left, top, right, bottom = alpha_box
            padding = 2
            frame = frame.crop((
                max(0, left - padding),
                max(0, top - padding),
                min(frame.width, right + padding),
                min(frame.height, bottom + padding),
            ))
        scaled_width = max(48, int(frame.width * scale))
        scaled_height = max(48, int(frame.height * scale))
        return frame.resize((scaled_width, scaled_height), Image.Resampling.NEAREST)

    def _sprite_name_for(self, state: str, emotion: str) -> str:
        requested = f"{state}_{emotion}"
        fallback_order = [requested]
        if emotion == "sob":
            fallback_order.append(f"{state}_sad")
        fallback_order.append(f"{state}_neutral")

        for name in fallback_order:
            if (self.assets_dir / f"{name}.imageset" / "sprite_sheet.png").exists():
                return name
        return f"{state}_neutral"


class EventTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


class EventHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        chunks: list[bytes] = []
        while True:
            data = self.request.recv(4096)
            if not data:
                break
            chunks.append(data)

        if not chunks:
            return

        try:
            payload = json.loads(b"".join(chunks).decode("utf-8"))
        except json.JSONDecodeError:
            return

        self.server.app.store.process(payload)


class NotchiWindowsApp:
    def __init__(self) -> None:
        self.base_dir = Path(__file__).resolve().parent
        self.parser = ConversationParser()
        self.store = SessionStore(self.parser)
        self.installer = HookInstaller(self.base_dir)
        self.sprite_renderer = SpriteRenderer(self.base_dir.parent / "notchi" / "notchi" / "Assets.xcassets")
        self.drag_origin: tuple[int, int] | None = None
        self.details_visible = False
        self.animation_phase = 0.0
        self.frame_tick = 0.0
        self.sprite_bounds: dict[str, tuple[float, float, float, float]] = {}

        self.root = tk.Tk()
        self.root.title("Notchi for Windows")
        self.root.geometry("420x180+730+30")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT_KEY)

        self.server = EventTCPServer((APP_HOST, APP_PORT), EventHandler)
        self.server.app = self
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)

        self.status_var = tk.StringVar(value="Starting listener...")
        self.toggle_var = tk.StringVar(value="Details")
        self._build_ui()
        self._auto_install_hook()

    def _build_ui(self) -> None:
        self.frame = tk.Frame(self.root, bg=TRANSPARENT_KEY, bd=0, highlightthickness=0)
        self.frame.pack(fill="both", expand=True, padx=6, pady=6)

        self.header = tk.Frame(self.frame, bg="#111827")
        self.header.pack(fill="x", padx=14, pady=(12, 8))
        self.header.bind("<ButtonPress-1>", self.start_drag)
        self.header.bind("<B1-Motion>", self.do_drag)

        title = tk.Label(self.header, text="Notchi for Windows", fg="#f8fafc", bg="#111827", font=("Microsoft YaHei UI", 14, "bold"))
        title.pack(side="left")
        title.bind("<ButtonPress-1>", self.start_drag)
        title.bind("<B1-Motion>", self.do_drag)

        actions = tk.Frame(self.header, bg="#111827")
        actions.pack(side="right")

        tk.Button(actions, textvariable=self.toggle_var, command=self.toggle_details, bg="#0f172a", fg="#cbd5e1", activebackground="#1e293b", activeforeground="#f8fafc", relief="flat", padx=8, pady=4).pack(side="left", padx=(0, 6))
        tk.Button(actions, text="Install Hook", command=self.install_hook, bg="#2563eb", fg="white", activebackground="#1d4ed8", activeforeground="white", relief="flat", padx=10, pady=4).pack(side="left", padx=(0, 6))
        tk.Button(actions, text="Close", command=self.shutdown, bg="#1f2937", fg="#cbd5e1", activebackground="#374151", activeforeground="#f8fafc", relief="flat", padx=10, pady=4).pack(side="left")

        self.floating_actions = tk.Frame(self.frame, bg="#111827", bd=0, highlightthickness=1, highlightbackground="#334155")
        self.floating_install = tk.Button(
            self.floating_actions,
            text="Install",
            command=self.install_hook,
            bg="#2563eb",
            fg="white",
            activebackground="#1d4ed8",
            activeforeground="white",
            relief="flat",
            padx=8,
            pady=3,
        )
        self.floating_install.pack(side="left", padx=(6, 4), pady=6)
        self.floating_details = tk.Button(
            self.floating_actions,
            textvariable=self.toggle_var,
            command=self.toggle_details,
            bg="#0f172a",
            fg="#cbd5e1",
            activebackground="#1e293b",
            activeforeground="#f8fafc",
            relief="flat",
            padx=8,
            pady=3,
            width=7,
        )
        self.floating_details.pack(side="left", padx=(0, 6), pady=6)

        self.status_label = tk.Label(self.frame, textvariable=self.status_var, fg="#94a3b8", bg="#111827", anchor="w", justify="left", font=("Microsoft YaHei UI", 9))

        self.hero = tk.Canvas(self.frame, width=472, height=110, bg=TRANSPARENT_KEY, highlightthickness=0, relief="flat")
        self.hero.pack(fill="x", padx=14, pady=(10, 8))
        self.hero.bind("<Button-1>", self.on_hero_click)
        self.hero.bind("<Double-Button-1>", self.on_hero_double_click)
        self.hero.bind("<ButtonPress-1>", self.start_drag)
        self.hero.bind("<B1-Motion>", self.do_drag)

        self.body_frame = tk.Frame(self.frame, bg="#111827")
        self.body_scrollbar = tk.Scrollbar(self.body_frame, orient="vertical")
        self.body = tk.Text(
            self.body_frame,
            bg="#0f172a",
            fg="#e2e8f0",
            insertbackground="#e2e8f0",
            relief="flat",
            wrap="word",
            state="disabled",
            font=("Microsoft YaHei UI", 10),
            padx=12,
            pady=10,
            yscrollcommand=self.body_scrollbar.set,
        )
        self.body_scrollbar.configure(command=self.body.yview)
        self.body.pack(side="left", fill="both", expand=True)
        self.body_scrollbar.pack(side="right", fill="y")
        self._configure_transparency()
        self.update_layout()

    def _configure_transparency(self) -> None:
        try:
            self.root.wm_attributes("-transparentcolor", TRANSPARENT_KEY)
        except tk.TclError:
            pass
        self._set_tool_window_style()

    def _auto_install_hook(self) -> None:
        ok, message = self.installer.install()
        self.status_var.set(message if ok else f"Auto-install skipped: {message}")

    def _set_tool_window_style(self) -> None:
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            exstyle = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, exstyle | 0x00000080)
        except Exception:
            pass

    def start_drag(self, event: tk.Event) -> None:
        self.drag_origin = (event.x_root, event.y_root)

    def do_drag(self, event: tk.Event) -> None:
        if self.drag_origin is None:
            return
        dx = event.x_root - self.drag_origin[0]
        dy = event.y_root - self.drag_origin[1]
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")
        self.drag_origin = (event.x_root, event.y_root)

    def toggle_details(self) -> None:
        self.details_visible = not self.details_visible
        self.update_layout()

    def update_layout(self) -> None:
        self.header.pack_forget()
        self.floating_actions.place_forget()
        self.status_label.pack_forget()
        self.body_frame.pack_forget()
        if self.details_visible:
            self.frame.configure(bg="#111827", highlightthickness=1, highlightbackground="#334155")
            self.root.configure(bg="#111827")
            self.hero.configure(bg="#111827")
            self.hero.configure(width=452, height=110)
            self.header.pack(fill="x", padx=14, pady=(12, 8))
            self.status_label.pack(fill="x", padx=14)
            self.body_frame.pack(fill="both", expand=True, padx=14, pady=(8, 12))
            self.root.geometry("520x430")
            self.toggle_var.set("Hide")
        else:
            self.frame.configure(bg=TRANSPARENT_KEY, highlightthickness=0)
            self.root.configure(bg=TRANSPARENT_KEY)
            self.hero.configure(bg=TRANSPARENT_KEY)
            self.hero.configure(width=372, height=110)
            self.root.geometry("420x180")
            self.toggle_var.set("Details")
            self.floating_actions.place(relx=1.0, x=-18, y=10, anchor="ne")
        self._configure_transparency()

    def on_hero_click(self, event: tk.Event) -> None:
        session_id = self._session_id_at_point(event.x, event.y)
        if session_id is not None:
            self.store.select_session(session_id)
            return
        if self.details_visible:
            self.toggle_details()

    def on_hero_double_click(self, event: tk.Event) -> None:
        session_id = self._session_id_at_point(event.x, event.y)
        if session_id is not None:
            self.store.select_session(session_id)
            self.toggle_details()
            return
        if not self.details_visible:
            self.toggle_details()

    def _session_id_at_point(self, x: float, y: float) -> str | None:
        for session_id, bounds in reversed(list(self.sprite_bounds.items())):
            left, top, right, bottom = bounds
            if left <= x <= right and top <= y <= bottom:
                return session_id
        return None

    def install_hook(self) -> None:
        ok, message = self.installer.install()
        self.status_var.set(message)
        if not ok:
            messagebox.showerror("Hook install failed", message)

    def render(self) -> None:
        sessions = self.store.snapshot()
        focused = self.store.effective_session()
        installed = "installed" if self.installer.is_installed() else "not installed"
        self.status_var.set(f"Listening on {APP_HOST}:{APP_PORT} | Claude hook {installed} | Active sessions: {len(sessions)}")
        self.render_mascot(sessions)

        lines: list[str] = []
        if not sessions:
            lines.append("No active Claude Code sessions yet.")
            lines.append("")
            lines.append("1. Start this app.")
            lines.append("2. Click 'Install Hook'.")
            lines.append("3. Open Claude Code and use it normally.")
        elif focused is not None:
            lines.append(f"Selected: {focused.project_name} [{focused.state}]")
            lines.append(f"Duration: {focused.duration}")
            lines.append(f"Emotion: {focused.emotion}")
            if focused.last_prompt:
                lines.append(f"Prompt: {focused.last_prompt}")
            if focused.current_tool:
                lines.append(f"Tool: {focused.current_tool}")
            lines.append(f"Mode: {focused.permission_mode}")
            if focused.messages:
                lines.append("Claude:")
                for message in focused.messages[-2:]:
                    preview = message.replace("\n", " ").strip()
                    if len(preview) > 180:
                        preview = preview[:177] + "..."
                    lines.append(f"  {preview}")
            lines.append("Recent:")
            for entry in focused.events[-4:]:
                lines.append(f"  - {entry}")
            if len(sessions) > 1:
                lines.append("")
                lines.append("Other Sessions:")
                for session in sessions:
                    if session.session_id == focused.session_id:
                        continue
                    lines.append(f"  {session.project_name} [{session.state}] {session.emotion}")

        if self.details_visible:
            self.body.configure(state="normal")
            self.body.delete("1.0", "end")
            self.body.insert("1.0", "\n".join(lines).rstrip())
            self.body.configure(state="disabled")
        self.root.after(REFRESH_MS, self.render)

    def animate(self) -> None:
        sessions = self.store.snapshot()
        active = sessions[0] if sessions else None
        state = active.state if active else "idle"
        emotion = active.emotion if active else "neutral"

        self.animation_phase += self._phase_step_for(state, emotion)
        self.frame_tick += self._frame_step_for(state, emotion)
        self.render_mascot(sessions)
        self.root.after(self._animation_delay_for(state, emotion), self.animate)

    def render_mascot(self, sessions: list[SessionData]) -> None:
        canvas = self.hero
        canvas.delete("all")
        self.sprite_bounds = {}

        width = int(canvas.cget("width"))
        height = int(canvas.cget("height"))
        focused = self.store.effective_session()
        sprite_base_scale = self._base_sprite_scale(len(sessions))

        self._draw_grass_band(canvas, width, height)

        ordered_sessions = sorted(sessions, key=lambda item: item.sprite_x)
        for index, session in enumerate(ordered_sessions):
            state = session.state
            emotion = session.emotion
            bob = self._bob_offset(state, emotion)
            pet_x = self._sprite_canvas_x(index, len(ordered_sessions), width)
            is_selected = focused is not None and focused.session_id == session.session_id
            sprite_scale = sprite_base_scale * (1.04 if is_selected else 1.0)
            sprite = self.sprite_renderer.get_frame(state, emotion, int(self.frame_tick), scale=sprite_scale)
            sprite_width = sprite.width()
            sprite_height = sprite.height()
            sprite_y = 70 + session.sprite_y_offset * 0.22 + bob

            canvas.create_image(pet_x, sprite_y, image=sprite)
            self.sprite_bounds[session.session_id] = (
                pet_x - sprite_width / 2,
                sprite_y - sprite_height / 2,
                pet_x + sprite_width / 2,
                sprite_y + sprite_height / 2,
            )

        focused_state = focused.state if focused is not None else "idle"
        focused_emotion = focused.emotion if focused is not None else "neutral"
        if self.details_visible and focused is None:
            canvas.create_text(156, 60, text="Install the hook and start a session.", anchor="w", fill="#cbd5e1", font=("Segoe UI", 10), width=290)

    @staticmethod
    def _draw_grass_band(canvas: tk.Canvas, width: int, height: int) -> None:
        left = 26
        right = width - 26
        base_y = height - 18

        # Deep shadow to lightly ground the sprites.
        canvas.create_oval(left + 18, base_y - 4, right - 18, base_y + 12, fill="#111827", outline="")
        # Low-saturation grass body.
        canvas.create_oval(left, base_y - 12, right, base_y + 8, fill="#5d7c67", outline="")
        # Slight highlight ridge so it reads as a thin island instead of a block.
        canvas.create_oval(left + 10, base_y - 14, right - 10, base_y - 2, fill="#7f9a86", outline="")

    def _subtitle_for(self, session: SessionData) -> str:
        if session.messages:
            preview = session.messages[-1].replace("\n", " ").strip()
            return preview[:72] + ("..." if len(preview) > 72 else "")
        if session.current_tool:
            return f"Using {session.current_tool}"
        if session.last_prompt:
            return session.last_prompt[:72] + ("..." if len(session.last_prompt) > 72 else "")
        return f"Mode: {session.permission_mode}"

    @staticmethod
    def _sprite_canvas_x(index: int, total: int, width: int) -> float:
        if total <= 1:
            return width * 0.5
        left_margin = 76
        right_margin = 92
        usable_width = max(120, width - left_margin - right_margin)
        step = usable_width / max(1, total - 1)
        return left_margin + (step * index)

    def _bob_offset(self, state: str, emotion: str) -> float:
        amplitudes = {
            "working": 3.5,
            "waiting": 1.5,
            "compacting": 1.0,
            "sleeping": 0.5,
            "idle": 2.0,
        }
        amplitude = amplitudes.get(state, 2.0) * self._emotion_motion_multiplier(emotion)
        return math.sin(self.animation_phase) * amplitude

    @staticmethod
    def _base_sprite_scale(session_count: int) -> float:
        return {
            0: 1.2,
            1: 1.2,
            2: 1.08,
            3: 0.96,
            4: 0.86,
        }.get(session_count, 0.78)

    @staticmethod
    def _base_grass_scale(session_count: int) -> float:
        return {
            0: 0.62,
            1: 0.62,
            2: 0.56,
            3: 0.5,
            4: 0.46,
        }.get(session_count, 0.42)

    @staticmethod
    def _emotion_motion_multiplier(emotion: str) -> float:
        return {
            "happy": 1.35,
            "neutral": 1.0,
            "sad": 0.72,
            "sob": 0.3,
        }.get(emotion, 1.0)

    def _phase_step_for(self, state: str, emotion: str) -> float:
        base = {
            "working": 0.42,
            "waiting": 0.24,
            "compacting": 0.18,
            "sleeping": 0.08,
            "idle": 0.28,
        }.get(state, 0.28)
        return base * self._emotion_motion_multiplier(emotion)

    def _frame_step_for(self, state: str, emotion: str) -> float:
        base = {
            "working": 0.9,
            "waiting": 0.45,
            "compacting": 0.55,
            "sleeping": 0.15,
            "idle": 0.35,
        }.get(state, 0.35)
        return max(0.08, base * self._emotion_motion_multiplier(emotion))

    def _animation_delay_for(self, state: str, emotion: str) -> int:
        base = {
            "working": 95,
            "waiting": 120,
            "compacting": 140,
            "sleeping": 220,
            "idle": 130,
        }.get(state, ANIMATION_MS)
        multiplier = {
            "happy": 0.85,
            "neutral": 1.0,
            "sad": 1.18,
            "sob": 1.45,
        }.get(emotion, 1.0)
        return max(80, int(base * multiplier))

    @staticmethod
    def _state_label(state: str) -> str:
        labels = {
            "working": "working",
            "waiting": "waiting",
            "compacting": "compacting",
            "sleeping": "sleeping",
            "idle": "idle",
        }
        return labels.get(state, state)

    def run(self) -> None:
        self.server_thread.start()
        self.render()
        self.animate()
        self.root.mainloop()

    def shutdown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.root.destroy()


if __name__ == "__main__":
    app = NotchiWindowsApp()
    app.run()
