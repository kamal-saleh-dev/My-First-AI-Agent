import sys, os, subprocess, math, json, datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QFrame, QLabel, QScrollArea,
    QFileDialog, QMenu, QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QThread, Signal, QTimer, QPoint, QPointF
from PySide6.QtGui import QColor, QTextCursor, QPainter, QRadialGradient, QPen

# ============================================================
#  THEMES  —  edit / add your own palettes here
# ============================================================
THEMES = {
    "Soft Dark": {
        "base": (18, 20, 27),
        "accent": "#5fa8bf", "accent2": "#8a86b8", "accent3": "#bd86a6",
        "accent_soft": "rgba(95,168,191,0.12)", "accent2_soft": "rgba(138,134,184,0.16)",
        "panel": "rgba(24,27,36,0.85)", "card": "rgba(255,255,255,0.035)", "field": "rgba(255,255,255,0.04)",
        "border": "rgba(255,255,255,0.07)",
        "txt": "#d7dae2", "txt2": "#969cab", "txt3": "#6b7180",
        "ok": "#5fb89a", "warn": "#d6a45e", "err": "#d98a93",
        "menu_bg": "#1a1d27",
        "session_bg": "rgba(255,255,255,0.025)", "session_hover": "rgba(255,255,255,0.06)",
        "confirm_bg": "rgba(50,20,22,0.6)", "confirm_fg": "#e8c4ca",
        "blob_alpha": 34,
    },
    "Neon Night": {
        "base": (7, 8, 16),
        "accent": "#22d3ee", "accent2": "#8b5cf6", "accent3": "#ec4899",
        "accent_soft": "rgba(34,211,238,0.12)", "accent2_soft": "rgba(139,92,246,0.18)",
        "panel": "rgba(10,12,24,0.55)", "card": "rgba(255,255,255,0.05)", "field": "rgba(255,255,255,0.05)",
        "border": "rgba(255,255,255,0.09)",
        "txt": "#eaecf5", "txt2": "#8b90a8", "txt3": "#5f6b9a",
        "ok": "#34d399", "warn": "#fbbf24", "err": "#fb7185",
        "menu_bg": "#101226",
        "session_bg": "rgba(255,255,255,0.03)", "session_hover": "rgba(255,255,255,0.07)",
        "confirm_bg": "rgba(60,10,10,0.55)", "confirm_fg": "#ffd5db",
        "blob_alpha": 80,
    },
    "Calm Slate": {
        "base": (26, 28, 33),
        "accent": "#8b94a6", "accent2": "#9aa0b0", "accent3": "#a98b9c",
        "accent_soft": "rgba(139,148,166,0.12)", "accent2_soft": "rgba(154,160,176,0.14)",
        "panel": "rgba(32,35,42,0.9)", "card": "rgba(255,255,255,0.03)", "field": "rgba(255,255,255,0.035)",
        "border": "rgba(255,255,255,0.06)",
        "txt": "#cfd3db", "txt2": "#929aa8", "txt3": "#6d7480",
        "ok": "#7fae93", "warn": "#c2a06a", "err": "#c98f97",
        "menu_bg": "#20232a",
        "session_bg": "rgba(255,255,255,0.025)", "session_hover": "rgba(255,255,255,0.05)",
        "confirm_bg": "rgba(48,26,28,0.6)", "confirm_fg": "#e3c9ce",
        "blob_alpha": 22,
    },
    "Daylight": {
        "base": (234, 237, 243),
        "accent": "#2b8aa8", "accent2": "#6d54c4", "accent3": "#c13d86",
        "accent_soft": "rgba(43,138,168,0.12)", "accent2_soft": "rgba(109,84,196,0.12)",
        "panel": "rgba(255,255,255,0.75)", "card": "rgba(255,255,255,0.72)", "field": "rgba(255,255,255,0.85)",
        "border": "rgba(0,0,0,0.10)",
        "txt": "#202533", "txt2": "#5a6273", "txt3": "#8a91a0",
        "ok": "#0f9d6b", "warn": "#c77a0c", "err": "#d33b52",
        "menu_bg": "#ffffff",
        "session_bg": "rgba(0,0,0,0.03)", "session_hover": "rgba(0,0,0,0.06)",
        "confirm_bg": "rgba(253,232,234,0.9)", "confirm_fg": "#9a2230",
        "blob_alpha": 24,
    },
}
DEFAULT_THEME = "Soft Dark"

# Active palette (mutated in place so all widgets see updates)
P = {}
def apply_palette(name):
    P.clear(); P.update(THEMES.get(name, THEMES[DEFAULT_THEME]))

def _rgb(h):
    h = h.lstrip("#"); return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
def _grad(a, b, c):
    return "qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 " + a + ",stop:0.5 " + b + ",stop:1 " + c + ")"
def _grad2(a, b):
    return "qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 " + a + ",stop:1 " + b + ")"

# ── QSS builders (no f-strings: literal CSS braces stay single) ──
def q_sidebar():   return "background:" + P["panel"] + ";border-right:1px solid " + P["border"] + ";"
def q_logo():      return "color:" + P["accent2"] + ";font-size:15px;font-weight:800;padding:0 16px 12px;background:transparent;"
def q_dimlabel():  return "color:" + P["txt3"] + ";font-size:10px;font-weight:700;padding:10px 16px 4px;letter-spacing:1px;background:transparent;"
def q_attlabel():  return "color:" + P["txt3"] + ";font-size:10px;padding:6px 14px;font-style:italic;background:transparent;"
def q_newchat():
    return ("QPushButton{background:" + P["card"] + ";color:" + P["accent2"] + ";border:1px solid " + P["border"] + ";border-radius:10px;font-size:13px;font-weight:600;margin:0 10px 10px;}"
            "QPushButton:hover{background:" + P["accent2_soft"] + ";color:" + P["txt"] + ";border:1px solid " + P["accent2"] + ";}")
def q_chat():
    return ("QTextEdit{background:" + P["card"] + ";border:1px solid " + P["border"] + ";border-radius:14px;font-size:14px;color:" + P["txt"] + ";padding:10px;}"
            "QScrollBar:vertical{background:transparent;width:8px;border-radius:4px;}"
            "QScrollBar::handle:vertical{background:" + P["border"] + ";border-radius:4px;}"
            "QScrollBar::add-line,QScrollBar::sub-line{height:0;}")
def q_toolbtn():
    return ("QPushButton{background:" + P["card"] + ";color:" + P["txt2"] + ";border:1px solid " + P["border"] + ";border-radius:12px;font-size:13px;padding:6px 14px;}"
            "QPushButton:hover{background:" + P["accent_soft"] + ";color:" + P["txt"] + ";border:1px solid " + P["accent"] + ";}"
            "QPushButton:disabled{color:" + P["txt3"] + ";border-color:" + P["border"] + ";}")
def q_cmdbtn():
    return ("QPushButton{background:" + P["accent2_soft"] + ";color:" + P["accent2"] + ";border:1px solid " + P["accent2"] + ";border-radius:12px;font-size:13px;padding:6px 14px;}"
            "QPushButton:hover{background:" + P["accent2_soft"] + ";color:" + P["txt"] + ";}")
def q_input_normal():
    return ("QLineEdit{background:" + P["field"] + ";border:1px solid " + P["border"] + ";border-radius:24px;padding-left:20px;font-size:14px;color:" + P["txt"] + ";}"
            "QLineEdit:focus{border:1px solid " + P["accent"] + ";}"
            "QLineEdit:disabled{color:" + P["txt3"] + ";}")
def q_input_confirm():
    return ("QLineEdit{background:" + P["confirm_bg"] + ";border:2px solid " + P["err"] + ";border-radius:24px;padding-left:20px;font-size:14px;color:" + P["confirm_fg"] + ";}"
            "QLineEdit:focus{border:2px solid " + P["accent3"] + ";}")
def q_send():
    g = _grad(P["accent"], P["accent2"], P["accent3"])
    return ("QPushButton{background:" + g + ";border-radius:24px;font-size:18px;color:white;font-weight:bold;}"
            "QPushButton:hover{background:" + g + ";}"
            "QPushButton:pressed{background:" + P["accent2"] + ";}"
            "QPushButton:disabled{background:" + P["card"] + ";color:" + P["txt3"] + ";}")
def q_send_confirm():
    g = _grad2(P["err"], P["accent3"])
    return ("QPushButton{background:" + g + ";border-radius:24px;font-size:18px;color:white;font-weight:bold;}"
            "QPushButton:hover{background:" + P["accent3"] + ";}")
def q_stop():
    g = _grad2(P["err"], P["accent3"])
    return ("QPushButton{background:" + g + ";border-radius:24px;font-size:18px;color:white;font-weight:bold;}"
            "QPushButton:hover{background:" + g + ";}"
            "QPushButton:pressed{background:" + P["err"] + ";}")
def q_menu():
    return ("QMenu{background:" + P["menu_bg"] + ";border:1px solid " + P["border"] + ";border-radius:8px;color:" + P["txt"] + ";font-size:13px;padding:4px;}"
            "QMenu::item{padding:7px 18px;border-radius:5px;}"
            "QMenu::item:selected{background:" + P["accent_soft"] + ";color:" + P["txt"] + ";}"
            "QMenu::separator{height:1px;background:" + P["border"] + ";margin:3px 8px;}")

# ── Commands reference data ─────────────────────────────────
COMMANDS = [
    ("GENERATION", [
        ("make a <type> game",        "Generate a Unity / Unreal game project"),
        ("build a <type> website",    "Generate React / Angular / HTML / .NET project"),
        ("/resume <project>",         "Resume an interrupted project generation"),
    ]),
    ("SELF-MODIFICATION", [
        ("add <feature> to yourself", "Add a new capability to the agent"),
        ("edit yourself",             "Ask agent to modify its own source code"),
        ("/scan",                     "List all project .py files with status"),
        ("/read <file>",              "Read a source file (smart summary for large files)"),
        ("/read <file> full",         "Read entire source file without truncation"),
        ("/diff <file>",              "Show diff between current file and last backup"),
    ]),
    ("FILES & CONTEXT", [
        ("attach <path>",             "Attach a file to the conversation context"),
        ("clear",                     "Clear all attached files from context"),
    ]),
    ("MODEL SWITCHING", [
        ("/model local",              "Use local Ollama model (always free)"),
        ("/model or_free",            "Use OpenRouter auto free model"),
        ("/model or_deepseek",        "Use DeepSeek R1 free"),
        ("/model or_llama",           "Use Llama 3.3 70B free"),
        ("/model or_qwen",            "Use Qwen3 Coder 480B free"),
        ("/model or_gptoss",          "Use gpt-oss 120B free"),
        ("/model or_dsflash",         "Use DeepSeek V4 Flash free"),
    ]),
    ("SYSTEM", [
        ("/status",                   "Show current model, memory and context info"),
        ("/time",                     "Show the current date and time"),
        ("/help",                     "Print all commands in the terminal"),
        ("checkpoints",               "List resumable interrupted generations"),
        ("metrics",                   "Show performance stats dashboard"),
        ("health",                    "Show domain health report"),
        ("new_chat",                  "Start a fresh conversation"),
        ("/date",                     "Show today's date"),
        ("/weather <city>",           "Show current weather for a city"),
        ("exit",                      "Exit the agent"),
    ]),
]

def _load_commands_manifest() -> list:
    """Load extra commands added by self_mod from commands_manifest.json."""
    import json, os as _os
    path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "commands_manifest.json")
    try:
        if _os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def _get_all_commands() -> list:
    """Merge hardcoded COMMANDS with dynamic manifest entries."""
    result = [list(section) for section in COMMANDS]  # deep copy
    extras = _load_commands_manifest()
    if not extras:
        return result
    sections: dict = {}
    for e in extras:
        sec = e.get("section", "AGENT COMMANDS")
        sections.setdefault(sec, []).append((e["cmd"], e["desc"]))
    for sec_name, cmds in sections.items():
        result.append((sec_name, cmds))
    return result

# ── Animated aurora background ────────────────────────────────
# (Animated aurora background removed — user preferred a clean, static backdrop.)

# ── Commands floating panel ───────────────────────────────
class CommandsPanel(QFrame):
    """Floating commands reference — toggled by the ⌘ Commands button."""
    send_command = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint)
        self.setFixedWidth(540)
        self.hide()
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 10, 0, 10)
        self._outer.setSpacing(0)
        self.rebuild()

    def rebuild(self):
        while self._outer.count():
            it = self._outer.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        self.setStyleSheet("QFrame{background:" + P["menu_bg"] + ";border:1px solid " + P["border"] + ";border-radius:14px;}")
        head = QWidget(); hl = QHBoxLayout(head); hl.setContentsMargins(16, 0, 10, 8)
        title = QLabel("⌘  Commands Reference")
        title.setStyleSheet("color:" + P["accent2"] + ";font-size:13px;font-weight:700;background:transparent;")
        close_btn = QPushButton("✕"); close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet("QPushButton{background:transparent;color:" + P["txt3"] + ";border:none;font-size:13px;}QPushButton:hover{color:" + P["accent3"] + ";}")
        close_btn.clicked.connect(self.hide)
        hl.addWidget(title); hl.addStretch(); hl.addWidget(close_btn)
        self._outer.addWidget(head)
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background:" + P["border"] + ";max-height:1px;")
        self._outer.addWidget(sep)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none;background:transparent;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        il = QVBoxLayout(inner); il.setContentsMargins(0, 6, 0, 10); il.setSpacing(0)
        for section, cmds in _get_all_commands():
            sec_lbl = QLabel(section)
            sec_lbl.setStyleSheet("color:" + P["txt3"] + ";font-size:10px;font-weight:700;letter-spacing:1px;padding:10px 16px 3px;background:transparent;")
            il.addWidget(sec_lbl)
            for cmd, desc in cmds:
                row = QWidget(); rl = QHBoxLayout(row)
                rl.setContentsMargins(10, 1, 14, 1); rl.setSpacing(10)
                btn = QPushButton(cmd); btn.setFixedWidth(220)
                btn.setStyleSheet("QPushButton{background:transparent;color:" + P["accent"] + ";font-size:11px;font-weight:600;font-family:Consolas,monospace;text-align:left;border:none;padding:4px 8px;border-radius:5px;}QPushButton:hover{background:" + P["accent_soft"] + ";color:" + P["txt"] + ";}")
                btn.setCursor(Qt.PointingHandCursor)
                _cmd = cmd.split("<")[0].strip()
                btn.clicked.connect(lambda _, c=_cmd: self._on_cmd(c))
                desc_lbl = QLabel(desc)
                desc_lbl.setStyleSheet("color:" + P["txt2"] + ";font-size:11px;background:transparent;")
                desc_lbl.setWordWrap(True)
                rl.addWidget(btn); rl.addWidget(desc_lbl, 1)
                il.addWidget(row)
            il.addSpacing(2)
        il.addStretch()
        scroll.setWidget(inner)
        self._outer.addWidget(scroll)

    def _on_cmd(self, cmd: str):
        self.send_command.emit(cmd)
        self.hide()

    def toggle(self, anchor_widget):
        if self.isVisible():
            self.hide(); return
        ag = anchor_widget.mapToGlobal(QPoint(0, 0))
        self.move(ag.x() - self.width() + anchor_widget.width(), ag.y() - self.height() - 6)
        self.show(); self.raise_()

# ── Settings (theme) floating panel ───────────────────────
class SettingsPanel(QFrame):
    """Floating appearance settings — pick a color theme."""
    theme_chosen = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint)
        self.setFixedWidth(300)
        self.current = DEFAULT_THEME
        self.hide()
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 10, 0, 12)
        self._outer.setSpacing(0)
        self.rebuild(self.current)

    def rebuild(self, current=None):
        if current:
            self.current = current
        while self._outer.count():
            it = self._outer.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        self.setStyleSheet("QFrame{background:" + P["menu_bg"] + ";border:1px solid " + P["border"] + ";border-radius:14px;}")
        head = QWidget(); hl = QHBoxLayout(head); hl.setContentsMargins(16, 0, 10, 8)
        title = QLabel("⚙  Appearance")
        title.setStyleSheet("color:" + P["accent2"] + ";font-size:13px;font-weight:700;background:transparent;")
        close_btn = QPushButton("✕"); close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet("QPushButton{background:transparent;color:" + P["txt3"] + ";border:none;font-size:13px;}QPushButton:hover{color:" + P["accent3"] + ";}")
        close_btn.clicked.connect(self.hide)
        hl.addWidget(title); hl.addStretch(); hl.addWidget(close_btn)
        self._outer.addWidget(head)
        lbl = QLabel("THEME")
        lbl.setStyleSheet("color:" + P["txt3"] + ";font-size:10px;font-weight:700;letter-spacing:1px;padding:2px 16px 6px;background:transparent;")
        self._outer.addWidget(lbl)
        for name in THEMES.keys():
            sel = (name == self.current)
            b = QPushButton(("●  " if sel else "○  ") + name)
            b.setCursor(Qt.PointingHandCursor); b.setFixedHeight(38)
            fg = P["accent"] if sel else P["txt2"]
            b.setStyleSheet("QPushButton{background:transparent;color:" + fg + ";text-align:left;border:none;font-size:13px;font-weight:600;padding:4px 16px;border-radius:8px;margin:1px 8px;}QPushButton:hover{background:" + P["accent_soft"] + ";color:" + P["txt"] + ";}")
            b.clicked.connect(lambda _, n=name: self._pick(n))
            self._outer.addWidget(b)

    def _pick(self, name):
        self.theme_chosen.emit(name)
        self.hide()

    def toggle(self, anchor_widget):
        if self.isVisible():
            self.hide(); return
        ag = anchor_widget.mapToGlobal(QPoint(0, 0))
        self.move(ag.x() - self.width() + anchor_widget.width(), ag.y() - self.height() - 6)
        self.show(); self.raise_()

class RobotAvatar(QWidget):
    """Friendly robot head with 3 distinct states: idle / thinking / talking.
    Pure QPainter, theme-aware. talk energy decays so streaming = talking, a pause = thinking."""
    def __init__(self):
        super().__init__()
        self.mode = "idle"      # "idle" or "active"
        self.t = 0.0
        self.talk = 0.0         # talk energy 0..1, bumped on each streamed char
        self.blink = 0.0        # 1 = eyes closed
        self._blink_t = 0.0
        self.setMinimumHeight(195); self.setMaximumHeight(225)
        tm = QTimer(self); tm.timeout.connect(self._tick); tm.start(33)  # ~30 fps
    def set_state(self, s):
        if s == "idle":
            self.mode = "idle"
        elif s == "thinking":
            self.mode = "active"
        elif s == "talking":
            self.mode = "active"; self.talk = 1.0
    def _tick(self):
        self.t += 0.06
        self.talk = max(0.0, self.talk - 0.045)      # decays -> pause becomes "thinking"
        self._blink_t += 0.033
        period = 3.2 if self.mode == "idle" else 4.8
        if self._blink_t > period:
            self._blink_t = 0.0
        self.blink = 1.0 if self._blink_t < 0.15 else 0.0
        self.update()
    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        bc = P["base"]; p.fillRect(self.rect(), QColor(bc[0], bc[1], bc[2]))  # solid calm background
        accent = QColor(*_rgb(P["accent"])); accent2 = QColor(*_rgb(P["accent2"])); accent3 = QColor(*_rgb(P["accent3"])); txt = QColor(*_rgb(P["txt"]))
        active = (self.mode == "active"); talking = active and self.talk > 0.05; thinking = active and not talking
        glow_c = accent3 if talking else (accent2 if thinking else accent)
        bob = math.sin(self.t * (2.2 if active else 1.1)) * (3 if active else 5)
        cx = W / 2.0; cy = H / 2.0 + bob + 6
        head_w, head_h = 108, 88
        hx, hy = cx - head_w/2, cy - head_h/2
        # soft halo behind head
        halo = QRadialGradient(QPointF(cx, cy), head_w)
        g0 = QColor(glow_c); g0.setAlpha(75 if active else 42); halo.setColorAt(0.0, g0)
        g1 = QColor(glow_c); g1.setAlpha(0); halo.setColorAt(1.0, g1)
        p.setBrush(halo); p.setPen(Qt.NoPen); p.drawEllipse(QPointF(cx, cy), head_w, head_w)
        # antenna + bulb
        atop = hy - 24
        pen = QPen(QColor(txt)); pen.setWidth(3); pen.setCapStyle(Qt.RoundCap); p.setPen(pen)
        p.drawLine(QPointF(cx, hy), QPointF(cx, atop + 7))
        pulse = (math.sin(self.t * (9 if talking else (4.5 if thinking else 2.2))) * 0.5 + 0.5)
        br = 6 + pulse * (5 if active else 2)
        bg = QRadialGradient(QPointF(cx, atop), br * 2.6)
        bgc = QColor(glow_c); bgc.setAlpha(170); bg.setColorAt(0.0, bgc)
        bgc2 = QColor(glow_c); bgc2.setAlpha(0); bg.setColorAt(1.0, bgc2)
        p.setBrush(bg); p.setPen(Qt.NoPen); p.drawEllipse(QPointF(cx, atop), br * 2.6, br * 2.6)
        p.setBrush(QColor(glow_c)); p.drawEllipse(QPointF(cx, atop), br, br)
        # head body
        p.setPen(QPen(QColor(glow_c), 2))
        face = QColor(255, 255, 255, 16) if bc[0] < 128 else QColor(0, 0, 0, 16)
        p.setBrush(face); p.drawRoundedRect(hx, hy, head_w, head_h, 28, 28)
        # eyes (look up while thinking, blink while idle/thinking)
        eye_dy = -8 if thinking else 0
        eye_open = 1.0 - self.blink
        eye_w = 16; eye_h = 24 * max(0.12, eye_open)
        ey = cy - 8 + eye_dy - eye_h / 2
        eye_c = accent3 if talking else accent
        p.setPen(Qt.NoPen); p.setBrush(eye_c)
        for sgn in (-1, 1):
            p.drawRoundedRect(cx + sgn * 23 - eye_w/2, ey, eye_w, eye_h, 6, 6)
        # mouth
        my = cy + 27
        if talking:
            bars = 5; bw = 8; gap = 6; total = bars * bw + (bars - 1) * gap; x0 = cx - total / 2
            p.setBrush(accent2); p.setPen(Qt.NoPen)
            for i in range(bars):
                lvl = (math.sin(self.t * 7 + i * 1.25) * 0.5 + 0.5)
                bh = 5 + lvl * 22 * max(0.25, self.talk)
                p.drawRoundedRect(x0 + i * (bw + gap), my - bh/2, bw, bh, 3, 3)
        else:
            pen2 = QPen(QColor(txt)); pen2.setWidth(3); pen2.setCapStyle(Qt.RoundCap); p.setPen(pen2)
            p.drawLine(QPointF(cx - 16, my), QPointF(cx + 16, my))
        # floating thought dots while thinking
        if thinking:
            p.setPen(Qt.NoPen)
            for i in range(3):
                a = (math.sin(self.t * 3 - i * 0.6) * 0.5 + 0.5)
                dc = QColor(accent2); dc.setAlpha(int(70 + a * 185)); p.setBrush(dc)
                p.drawEllipse(QPointF(cx + 26 + i * 14, hy - 12 - i * 9 - a * 4), 4 + a * 1.6, 4 + a * 1.6)
        p.end()

class AgentStreamer(QThread):
    new_char = Signal(str); error_sig = Signal(str)
    def __init__(self, proc): super().__init__(); self.process = proc; self.is_running = True
    def run(self):
        try:
            while self.is_running and self.process and self.process.poll() is None:
                try:
                    ch = self.process.stdout.read(1)
                    if ch:
                        self.new_char.emit(ch)
                    else: break
                except OSError: break
                except Exception as e: self.error_sig.emit("Stream error: " + str(e)); break
        except Exception as e: self.error_sig.emit("Streamer crashed: " + str(e))
    def stop(self): self.is_running = False

class SessionRow(QFrame):
    clicked_sig = Signal(str); rename_sig = Signal(str)
    delete_sig = Signal(str);  pin_sig = Signal(str); export_sig = Signal(str)
    def __init__(self, sid, title, ts, pinned=False, active=False):
        super().__init__(); self.sid = sid
        self.setCursor(Qt.PointingHandCursor); self.setFixedHeight(54)
        self._set_style(active, pinned)
        row = QHBoxLayout(self); row.setContentsMargins(12, 4, 6, 4); row.setSpacing(4)
        txt = QWidget(); txt.setAttribute(Qt.WA_TransparentForMouseEvents)
        tl = QVBoxLayout(txt); tl.setContentsMargins(0, 0, 0, 0); tl.setSpacing(1)
        self._pre = "📌 " if pinned else ""
        self._title = title
        self._lbl = QLabel(self._pre + title[:36] + ("…" if len(title) > 36 else ""))
        self._lbl.setStyleSheet("color:" + P["txt"] + ";font-size:12px;font-weight:600;background:transparent;")
        tsl = QLabel(ts); tsl.setStyleSheet("color:" + P["txt3"] + ";font-size:10px;background:transparent;")
        tl.addWidget(self._lbl); tl.addWidget(tsl); row.addWidget(txt, 1)
        self._btn = QPushButton("⋯"); self._btn.setFixedSize(26, 26)
        self._btn.setStyleSheet("QPushButton{background:transparent;color:" + P["txt2"] + ";border:none;font-size:16px;padding:0 4px;border-radius:4px;}QPushButton:hover{color:" + P["txt"] + ";background:" + P["accent_soft"] + ";}")
        self._btn.setCursor(Qt.PointingHandCursor); self._btn.clicked.connect(self._menu)
        self._btn.hide(); row.addWidget(self._btn)
    def _set_style(self, active, pinned=False):
        brd = P["accent"] if active else (P["accent2"] if pinned else "transparent")
        bg = P["accent_soft"] if active else P["session_bg"]
        self.setStyleSheet("QFrame{background:" + bg + ";border-radius:10px;border-left:3px solid " + brd + ";margin:2px 8px;}QFrame:hover{background:" + P["session_hover"] + ";}")
    def _menu(self):
        m = QMenu(self); m.setStyleSheet(q_menu())
        m.addAction("✏️  Rename",      lambda: self.rename_sig.emit(self.sid))
        m.addAction("📌  Pin / Unpin", lambda: self.pin_sig.emit(self.sid))
        m.addAction("📤  Export",      lambda: self.export_sig.emit(self.sid))
        m.addSeparator()
        m.addAction("🗑️  Delete",      lambda: self.delete_sig.emit(self.sid))
        m.exec(self._btn.mapToGlobal(QPoint(0, self._btn.height())))
    def enterEvent(self, _):
        self._btn.show()
        short = self._pre + self._title[:22] + ("…" if len(self._title) > 22 else "")
        self._lbl.setText(short)
    def leaveEvent(self, _):
        self._btn.hide()
        full = self._pre + self._title[:36] + ("…" if len(self._title) > 36 else "")
        self._lbl.setText(full)
    def mousePressEvent(self, e):
        if not self._btn.underMouse(): self.clicked_sig.emit(self.sid)

class ModernAgentGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Agent — 3D Core Edition")
        self.resize(1340, 860); self.setMinimumSize(900, 600)
        self._theme_name = self._load_settings()
        apply_palette(self._theme_name)
        self.setWindowOpacity(0.0)
        a = QPropertyAnimation(self, b"windowOpacity", self); a.setDuration(900)
        a.setStartValue(0.0); a.setEndValue(1.0); a.setEasingCurve(QEasingCurve.OutCubic)
        a.start(); self._anim = a
        self._sessions = {}; self._active_id = ""; self._pending_id = ""
        self._agent_buf = ""; self._in_agent_turn = False; self._attached = []
        self._manually_busy = False
        self._confirm_mode = False
        self._sess_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui_sessions.json")
        self._load_sessions()
        self.process = None; self.streamer = None
        self._cmd_panel = CommandsPanel(); self._cmd_panel.send_command.connect(self._send_command_from_panel)
        self._settings_panel = SettingsPanel(); self._settings_panel.theme_chosen.connect(self._apply_theme)
        self._build_ui()
        self._typing_timer = QTimer(self); self._typing_timer.timeout.connect(self._agent_turn_ended)
        self._create_pending(); QTimer.singleShot(900, self._start_agent)
        self._refresh_sb()
    # ── Theme persistence ──
    def _settings_path(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui_settings.json")
    def _load_settings(self):
        try:
            p = self._settings_path()
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f: d = json.load(f)
                t = d.get("theme")
                if t in THEMES: return t
        except Exception: pass
        return DEFAULT_THEME
    def _save_settings(self):
        try:
            with open(self._settings_path(), "w", encoding="utf-8") as f:
                json.dump({"theme": self._theme_name}, f, ensure_ascii=False, indent=2)
        except Exception: pass
    def _apply_theme(self, name):
        if name not in THEMES: return
        self._theme_name = name; apply_palette(name); self._save_settings()
        busy = self._manually_busy; confirm = self._confirm_mode
        self._build_ui()
        self._cmd_panel.rebuild(); self._settings_panel.rebuild(self._theme_name)
        self._refresh_sb(); self._render(self._active_id)
        if busy: self._set_busy(True)
        if confirm: self._set_confirm_mode(True)
        self.chat_display.append("<span style='color:" + P["txt3"] + ";font-size:12px;'>🎨 Theme: " + name + "</span>")
    def resizeEvent(self, e):
        super().resizeEvent(e)
    def _build_ui(self):
        self.setStyleSheet("color:" + P["txt"] + ";font-family:'Segoe UI';")
        root = QWidget(); root.setObjectName("root"); self.setCentralWidget(root)
        _bc = P["base"]
        root.setStyleSheet("QWidget#root{background:rgb(" + str(_bc[0]) + "," + str(_bc[1]) + "," + str(_bc[2]) + ");}")
        rl = QHBoxLayout(root); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(0)
        sb = QFrame(); sb.setFixedWidth(240); sb.setStyleSheet(q_sidebar())
        sbl = QVBoxLayout(sb); sbl.setContentsMargins(0, 14, 0, 14); sbl.setSpacing(0)
        logo = QLabel("🤖  AI Agent"); logo.setStyleSheet(q_logo()); sbl.addWidget(logo)
        nb = QPushButton("＋  New Chat"); nb.setCursor(Qt.PointingHandCursor); nb.setFixedHeight(36); nb.setStyleSheet(q_newchat())
        nb.clicked.connect(self._new_chat); sbl.addWidget(nb)
        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setStyleSheet("color:" + P["border"] + ";"); sbl.addWidget(sep)
        hl = QLabel("CONVERSATIONS"); hl.setStyleSheet(q_dimlabel()); sbl.addWidget(hl)
        self._sess_scroll = QScrollArea(); self._sess_scroll.setWidgetResizable(True)
        self._sess_scroll.setStyleSheet("border:none;background:transparent;")
        self._sess_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._sess_cont = QWidget(); self._sess_cont.setStyleSheet("background:transparent;"); self._sess_lay = QVBoxLayout(self._sess_cont)
        self._sess_lay.setContentsMargins(0, 0, 0, 0); self._sess_lay.setSpacing(0); self._sess_lay.addStretch()
        self._sess_scroll.setWidget(self._sess_cont); sbl.addWidget(self._sess_scroll, 1)
        self._att_lbl = QLabel("No files attached"); self._att_lbl.setWordWrap(True); self._att_lbl.setStyleSheet(q_attlabel()); sbl.addWidget(self._att_lbl)
        rl.addWidget(sb)
        ct = QWidget(); ct.setStyleSheet("background:transparent;"); cl = QVBoxLayout(ct); cl.setContentsMargins(18, 14, 18, 14); cl.setSpacing(10)
        self.hologram = RobotAvatar(); cl.addWidget(self.hologram)
        self.chat_display = QTextEdit(); self.chat_display.setReadOnly(True); self.chat_display.setStyleSheet(q_chat())
        cl.addWidget(self.chat_display, 1)
        tb = QHBoxLayout(); tb.setSpacing(8)
        self._ab = QPushButton("📎 Attach File"); self._ab.setCursor(Qt.PointingHandCursor); self._ab.setStyleSheet(q_toolbtn()); self._ab.clicked.connect(self._attach_file)
        self._sb2 = QPushButton("📸 Screenshot"); self._sb2.setCursor(Qt.PointingHandCursor); self._sb2.setStyleSheet(q_toolbtn()); self._sb2.clicked.connect(self._take_screenshot)
        cb = QPushButton("🗑 Clear"); cb.setCursor(Qt.PointingHandCursor); cb.setStyleSheet(q_toolbtn()); cb.clicked.connect(self._clear_display)
        cmd_btn = QPushButton("⌘ Commands"); cmd_btn.setCursor(Qt.PointingHandCursor); cmd_btn.setStyleSheet(q_cmdbtn()); cmd_btn.clicked.connect(lambda: self._toggle_commands(cmd_btn))
        set_btn = QPushButton("⚙ Settings"); set_btn.setCursor(Qt.PointingHandCursor); set_btn.setStyleSheet(q_toolbtn()); set_btn.clicked.connect(lambda: self._toggle_settings(set_btn))
        tb.addWidget(self._ab); tb.addWidget(self._sb2); tb.addWidget(cb); tb.addWidget(cmd_btn); tb.addWidget(set_btn); tb.addStretch(); cl.addLayout(tb)
        ir = QHBoxLayout(); ir.setSpacing(10)
        self.input_box = QLineEdit(); self.input_box.setPlaceholderText("Ask the Agent anything…"); self.input_box.setFixedHeight(48); self.input_box.setStyleSheet(q_input_normal())
        self.send_btn = QPushButton("➤"); self.send_btn.setFixedSize(48, 48); self.send_btn.setCursor(Qt.PointingHandCursor); self.send_btn.setStyleSheet(q_send())
        self.send_btn.clicked.connect(self.send_msg); self.input_box.returnPressed.connect(self.send_msg)
        self.stop_btn = QPushButton("⏹"); self.stop_btn.setFixedSize(48, 48); self.stop_btn.setCursor(Qt.PointingHandCursor); self.stop_btn.setStyleSheet(q_stop()); self.stop_btn.clicked.connect(self._stop_agent); self.stop_btn.hide()
        ir.addWidget(self.input_box); ir.addWidget(self.send_btn); ir.addWidget(self.stop_btn); cl.addLayout(ir)
        rl.addWidget(ct, 1)
    # ── Sessions ──
    def _mk_sid(self):
        import uuid; return str(uuid.uuid4())[:8]
    def _create_pending(self):
        sid = self._mk_sid(); ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        self._sessions[sid] = {"title": "New Chat", "ts": ts, "messages": [], "pinned": False}
        self._active_id = sid; self._pending_id = sid; self._render(sid)
    def _new_chat(self):
        self._flush_agent_turn()
        if not self._sessions.get(self._active_id, {}).get("messages"):
            self._render(self._active_id); return
        self._create_pending(); self._attached.clear(); self._upd_att()
        if self.process:
            try: self.process.stdin.write("new_chat\n"); self.process.stdin.flush()
            except Exception: pass
    def _commit_pending(self):
        if self._pending_id == self._active_id:
            self._pending_id = ""; self._refresh_sb()
    def _load_session(self, sid):
        if sid == self._active_id: return
        self._flush_agent_turn()
        if self._pending_id and not self._sessions.get(self._pending_id, {}).get("messages"):
            del self._sessions[self._pending_id]; self._pending_id = ""
        self._active_id = sid; self._refresh_sb(); self._render(sid)
    def _render(self, sid):
        self.chat_display.clear()
        msgs = self._sessions.get(sid, {}).get("messages", [])
        if not msgs:
            self.chat_display.append("<span style='color:" + P["txt3"] + ";font-size:13px;'>✨ New conversation — ask anything.</span><br>"); return
        for m in msgs: self._bubble(m["role"], m["html"])
    def _bubble(self, role, html):
        if role == "user":
            self.chat_display.append("<br><span style='color:" + P["accent"] + ";font-weight:bold;'>👤 YOU:</span> <span style='color:" + P["txt"] + ";'>" + html + "</span><br>")
        else:
            self.chat_display.append("<span style='color:" + P["txt"] + ";'>" + html + "</span>")
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())
    def _save_msg(self, role, text, html):
        if self._active_id not in self._sessions: return
        sess = self._sessions[self._active_id]
        sess["messages"].append({"role": role, "text": text, "html": html})
        if role == "user" and sess["title"] == "New Chat":
            sess["title"] = text[:55] + ("…" if len(text) > 55 else "")
        if role == "user" and self._pending_id == self._active_id: self._commit_pending()
        else: self._refresh_sb()
        self._save_sess()
    def _flush_agent_turn(self):
        text = self._agent_buf.strip()
        _NOISE = (
            "✅ AGENT READY", "✅ I'm READY", "ℹ️", "⏱", "📋 Scripts",
            "⚙️ Writing", "💾 Script saved", "🎮 Planning",
        )
        if text and not any(text.startswith(n) for n in _NOISE):
            self._save_msg("agent", text, text)
        self._agent_buf = ""; self._in_agent_turn = False
    def _refresh_sb(self):
        while self._sess_lay.count() > 1:
            item = self._sess_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        pinned = [(s, v) for s, v in self._sessions.items() if v.get("pinned") and v.get("messages") and s != self._pending_id]
        unpinned = [(s, v) for s, v in reversed(list(self._sessions.items())) if not v.get("pinned") and v.get("messages") and s != self._pending_id]
        for sid, sess in pinned + unpinned:
            row = SessionRow(sid, sess["title"], sess["ts"], pinned=sess.get("pinned", False), active=(sid == self._active_id))
            row.clicked_sig.connect(self._load_session); row.rename_sig.connect(self._rename)
            row.delete_sig.connect(self._delete); row.pin_sig.connect(self._pin); row.export_sig.connect(self._export)
            self._sess_lay.insertWidget(0, row)
    # ── Context menu actions ──
    def _rename(self, sid):
        sess = self._sessions.get(sid)
        if not sess: return
        t, ok = QInputDialog.getText(self, "Rename", "New name:", text=sess["title"])
        if ok and t.strip(): sess["title"] = t.strip()[:60]; self._refresh_sb(); self._save_sess()
    def _delete(self, sid):
        t = self._sessions.get(sid, {}).get("title", "this conversation")
        if QMessageBox.question(self, "Delete", 'Delete "' + t + '"?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
        del self._sessions[sid]; self._save_sess()
        if self._active_id == sid:
            self._create_pending()
            if self.process:
                try: self.process.stdin.write("new_chat\n"); self.process.stdin.flush()
                except Exception: pass
        self._refresh_sb()
    def _pin(self, sid):
        sess = self._sessions.get(sid)
        if sess: sess["pinned"] = not sess.get("pinned", False); self._refresh_sb(); self._save_sess()
    def _export(self, sid):
        sess = self._sessions.get(sid)
        if not sess: return
        path, _ = QFileDialog.getSaveFileName(self, "Export", sess["title"][:40] + ".txt", "Text Files (*.txt)")
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("Conversation: " + sess["title"] + "\nDate: " + sess["ts"] + "\n" + ("─"*60) + "\n\n")
                for m in sess.get("messages", []):
                    f.write("[" + ("YOU" if m["role"] == "user" else "AGENT") + "]\n" + m["text"] + "\n\n")
            self.chat_display.append("<span style='color:" + P["ok"] + ";'>📤 Exported to " + os.path.basename(path) + "</span>")
        except Exception as e: self.chat_display.append("<span style='color:" + P["err"] + ";'>❌ " + str(e) + "</span>")
    # ── Messaging ──
    def _set_busy(self, busy):
        self._manually_busy = busy
        if busy:
            self.send_btn.hide(); self.stop_btn.show(); self.hologram.set_state("thinking")
        else:
            self.stop_btn.hide(); self.send_btn.show(); self.hologram.set_state("idle")
    def _stop_agent(self):
        if self.process:
            try:
                self.process.stdin.write("STOP_AGENT\n"); self.process.stdin.flush()
            except Exception:
                pass
        self._set_busy(False)
        self.chat_display.append("<span style='color:" + P["err"] + ";'>⛔ Stopped.</span>")
    def send_msg(self):
        msg = self.input_box.text().strip()
        if not msg or not self.process: return
        self.input_box.clear()
        if self._confirm_mode:
            self._exit_confirm_mode()
        self._flush_agent_turn()
        self._bubble("user", msg); self._save_msg("user", msg, msg)
        try:
            self.process.stdin.write(msg + "\n"); self.process.stdin.flush()
            self._set_busy(True)
        except Exception as e: self.chat_display.append("<span style='color:" + P["err"] + ";'>❌ " + str(e) + "</span>")
    # ── Streaming ──
    def _on_char(self, ch):
        self.hologram.set_state("talking"); self._typing_timer.start(8000)  # long safety net only; true end = AGENT_IDLE marker
        self._in_agent_turn = True; self._agent_buf += ch
        if "⚡AGENT_IDLE" in self._agent_buf[-20:]:
            self._agent_buf = self._agent_buf.replace("⚡AGENT_IDLE", "")
            self._typing_timer.stop()
            self._set_busy(False)          # agent explicitly signalled it is done -> bring Send back exactly now
        c = self.chat_display.textCursor(); c.movePosition(QTextCursor.End)
        self.chat_display.setTextCursor(c); self.chat_display.insertPlainText(ch)
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())
        if "Type  YES  to apply" in self._agent_buf or "Type YES to confirm" in self._agent_buf:
            self._set_confirm_mode(True)
        elif "✅ Confirmed" in self._agent_buf or "❌ Cancelled" in self._agent_buf or "❌ Timed out" in self._agent_buf:
            self._set_confirm_mode(False)
        if "Type  YES  to apply" in self._agent_buf and not self._confirm_mode:
            self._enter_confirm_mode()
    def _agent_turn_ended(self):
        self._typing_timer.stop(); self._flush_agent_turn()
        self._set_busy(False)                       # always restore the Send button once the agent goes quiet
        if self._confirm_mode:
            self._set_confirm_mode(False)
    def _set_confirm_mode(self, active):
        self._confirm_mode = active
        if active:
            self.input_box.setPlaceholderText("⚠️  Type  YES  to confirm or  NO  to cancel")
            self.input_box.setStyleSheet(q_input_confirm())
            self.send_btn.setStyleSheet(q_send_confirm())
        else:
            self.input_box.setPlaceholderText("Ask the Agent anything…")
            self.input_box.setStyleSheet(q_input_normal())
            self.send_btn.setStyleSheet(q_send())
    def _on_stream_error(self, msg):
        self._set_busy(False); self._flush_agent_turn()
        self.chat_display.append("<span style='color:" + P["warn"] + ";'>⚠️ " + msg + "</span>")
    # ── Attach / Screenshot ──
    def _lock(self, ph):
        for w in (self.input_box, self.send_btn, self._ab, self._sb2): w.setEnabled(False)
        self.input_box.setPlaceholderText(ph)
    def _unlock(self):
        for w in (self.input_box, self.send_btn, self._ab, self._sb2): w.setEnabled(True)
        self.input_box.setPlaceholderText("Ask the Agent anything…"); self.input_box.setFocus()
    def _attach_file(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Attach Files", "", "All Files (*);; Images (*.png *.jpg *.jpeg *.webp *.bmp);; Documents (*.pdf *.docx *.xlsx *.pptx *.txt);; Code (*.py *.cs *.cpp *.js *.ts *.html *.css *.json)")
        if not paths: return
        self._lock("⏳ Attaching…")
        for path in paths:
            self._attached.append(path)
            self.chat_display.append("<span style='color:" + P["warn"] + ";'>📎 Attaching: " + os.path.basename(path) + "</span>")
            if self.process:
                try: self.process.stdin.write("attach " + path + "\n"); self.process.stdin.flush()
                except Exception as e: self.chat_display.append("<span style='color:" + P["err"] + ";'>❌ " + str(e) + "</span>")
        self._upd_att(); QTimer.singleShot(1500, self._att_ready)
    def _take_screenshot(self):
        base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base, "live_screen.png"); screen = QApplication.primaryScreen()
        if not screen: self.chat_display.append("<span style='color:" + P["err"] + ";'>❌ No screen.</span>"); return
        self.hide(); QTimer.singleShot(250, lambda: self._capture(screen, path))
    def _capture(self, screen, path):
        screen.grabWindow(0).save(path, "PNG"); self.show()
        self.chat_display.append("<span style='color:" + P["accent"] + ";'>📸 Screenshot captured — attaching…</span>")
        self._lock("⏳ Attaching screenshot…")
        if self.process:
            try: self.process.stdin.write("attach " + path + "\n"); self.process.stdin.flush()
            except Exception as e: self.chat_display.append("<span style='color:" + P["err"] + ";'>❌ " + str(e) + "</span>")
        self._attached.append(path); self._upd_att(); QTimer.singleShot(1500, self._att_ready)
    def _att_ready(self):
        self._unlock(); self.chat_display.append("<span style='color:" + P["ok"] + ";'>✅ File ready — ask about it now</span><br>")
    def _upd_att(self):
        if not self._attached: self._att_lbl.setText("No files attached"); return
        names = [os.path.basename(p) for p in self._attached[-4:]]; extra = len(self._attached)-4
        self._att_lbl.setText("📎 " + "\n".join(names) + (("\n+" + str(extra) + " more") if extra > 0 else ""))
    def _clear_display(self): self.chat_display.clear()
    # ── Confirmation mode ──
    def _enter_confirm_mode(self):
        self._confirm_mode = True
        self.input_box.setText("")
        self.input_box.setPlaceholderText("Type YES to apply changes, or NO to cancel")
        self.input_box.setStyleSheet(q_input_confirm())
        self.send_btn.setStyleSheet(q_send_confirm())
        self.chat_display.append("<br><span style='color:" + P["err"] + ";font-weight:bold;font-size:13px;'>⚠️  Waiting for confirmation — type YES or NO in the input box below</span><br>")
    def _exit_confirm_mode(self):
        self._confirm_mode = False
        self.input_box.setPlaceholderText("Ask the Agent anything…")
        self.input_box.setStyleSheet(q_input_normal())
        self.send_btn.setStyleSheet(q_send())
    def _toggle_commands(self, anchor_widget):
        self._cmd_panel.toggle(anchor_widget)
    def _toggle_settings(self, anchor_widget):
        if self._settings_panel.isVisible():
            self._settings_panel.hide(); return
        self._settings_panel.rebuild(self._theme_name)
        self._settings_panel.toggle(anchor_widget)
    def _send_command_from_panel(self, cmd):
        self.input_box.setText(cmd)
        self.input_box.setFocus()
    # ── Persistence ──
    def _load_sessions(self):
        try:
            if os.path.exists(self._sess_file):
                with open(self._sess_file, encoding="utf-8") as f: self._sessions = json.load(f)
                for s in self._sessions.values(): s.setdefault("pinned", False)
        except Exception: self._sessions = {}
    def _save_sess(self):
        try:
            saved = {k: v for k, v in self._sessions.items() if v.get("messages")}
            if len(saved) > 60:
                np = [k for k, v in saved.items() if not v.get("pinned")]
                for k in np[:-60]: del saved[k]
            with open(self._sess_file, "w", encoding="utf-8") as f: json.dump(saved, f, ensure_ascii=False, indent=2)
        except Exception: pass
    # ── Agent ──
    def _start_agent(self):
        base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        ap = os.path.join(base, "agent.py")
        if not os.path.exists(ap): self.chat_display.append("<span style='color:" + P["err"] + ";'>❌ agent.py not found</span>"); return
        si = None
        if sys.platform == "win32": si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        env = os.environ.copy(); env["PYTHONUNBUFFERED"] = "1"
        try:
            self.process = subprocess.Popen([sys.executable, ap], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="ignore", bufsize=1, cwd=base, startupinfo=si, env=env)
            self.streamer = AgentStreamer(self.process); self.streamer.new_char.connect(self._on_char); self.streamer.error_sig.connect(self._on_stream_error); self.streamer.start()
        except Exception as e: self.chat_display.append("<span style='color:" + P["err"] + ";'>❌ " + str(e) + "</span>")
    def closeEvent(self, event):
        self._flush_agent_turn(); self._save_sess()
        if self.streamer: self.streamer.stop()
        if self.process:  self.process.terminate()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setStyle("Fusion")
    win = ModernAgentGUI(); win.show(); sys.exit(app.exec())
