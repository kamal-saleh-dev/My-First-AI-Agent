import sys
import os
import subprocess
import math
import json
import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QFrame, QLabel, QScrollArea,
    QFileDialog, QSplitter, QSizePolicy
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QThread, Signal, QTimer, QSize
from PySide6.QtGui import QColor, QTextCursor, QPainter, QFont, QIcon, QPixmap, QScreen


# ─────────────────────────────────────────────
# 🌌  3-D Hologram Core
# ─────────────────────────────────────────────
class HologramCore(QWidget):
    def __init__(self):
        super().__init__()
        self.angle_y        = 0.0
        self.angle_x        = 0.0
        self.speed_mult     = 1.0
        self.color          = QColor(30, 136, 229)
        self.pulse          = 0.0          # 0-1, used for breathing glow
        self.setMinimumHeight(220)
        self.setMaximumHeight(260)

        self.nodes = []
        for i in range(0, 360, 15):
            for j in range(-90, 90, 15):
                ri, rj = math.radians(i), math.radians(j)
                self.nodes.append([
                    math.cos(rj) * math.cos(ri),
                    math.sin(rj),
                    math.cos(rj) * math.sin(ri),
                ])

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_state(self, state: str):
        if state == "typing":
            self.speed_mult = 4.0
            self.color      = QColor(0, 220, 130)
        else:
            self.speed_mult = 1.0
            self.color      = QColor(30, 136, 229)

    def _tick(self):
        self.angle_y += 0.008 * self.speed_mult
        self.angle_x += 0.004 * self.speed_mult
        self.pulse     = (math.sin(self.angle_y * 2) + 1) / 2
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#070710"))

        cx, cy = self.width() / 2, self.height() / 2
        scale_base = min(self.width(), self.height()) * 0.38

        for node in self.nodes:
            x, y, z = node
            # Y-axis rotation
            nx = x * math.cos(self.angle_y) - z * math.sin(self.angle_y)
            nz = x * math.sin(self.angle_y) + z * math.cos(self.angle_y)
            x, z = nx, nz
            # X-axis rotation
            ny = y * math.cos(self.angle_x) - z * math.sin(self.angle_x)
            nz = y * math.sin(self.angle_x) + z * math.cos(self.angle_x)
            y, z = ny, nz

            sc  = scale_base / (z + 3)
            px  = cx + x * sc
            py  = cy + y * sc
            sz  = max(1.0, (z + 2.5) * 1.8)
            alp = int(max(15, min(230, (z + 2) * 55 + self.pulse * 25)))

            c = QColor(self.color)
            c.setAlpha(alp)
            p.setBrush(c)
            p.setPen(Qt.NoPen)
            p.drawEllipse(px - sz / 2, py - sz / 2, sz, sz)


# ─────────────────────────────────────────────
# 🧠  Agent process streamer
# ─────────────────────────────────────────────
class AgentStreamer(QThread):
    new_char  = Signal(str)
    error_sig = Signal(str)

    def __init__(self, process):
        super().__init__()
        self.process    = process
        self.is_running = True

    def run(self):
        try:
            while self.is_running and self.process and self.process.poll() is None:
                try:
                    ch = self.process.stdout.read(1)
                    if ch:
                        self.new_char.emit(ch)
                    else:
                        break
                except OSError:
                    break
                except Exception as e:
                    self.error_sig.emit(f"Stream error: {e}")
                    break
        except Exception as e:
            self.error_sig.emit(f"Streamer crashed: {e}")

    def stop(self):
        self.is_running = False


# ─────────────────────────────────────────────
# 📜  Chat history item widget
# ─────────────────────────────────────────────
class HistoryItem(QFrame):
    clicked_sig = Signal(str)   # emits the session task text

    def __init__(self, title: str, timestamp: str, task: str):
        super().__init__()
        self.task = task
        self.setFixedHeight(56)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QFrame {
                background: #161620;
                border-radius: 8px;
                margin: 2px 6px;
            }
            QFrame:hover { background: #1e1e2e; }
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 4)
        lay.setSpacing(2)

        title_lbl = QLabel(title[:38] + ("…" if len(title) > 38 else ""))
        title_lbl.setStyleSheet("color: #e0e0f0; font-size: 12px; font-weight: 600;")
        ts_lbl    = QLabel(timestamp)
        ts_lbl.setStyleSheet("color: #555577; font-size: 10px;")

        lay.addWidget(title_lbl)
        lay.addWidget(ts_lbl)

    def mousePressEvent(self, event):
        self.clicked_sig.emit(self.task)


# ─────────────────────────────────────────────
# 🖼  Main window
# ─────────────────────────────────────────────
class ModernAgentGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Agent — 3D Core Edition")
        self.resize(1340, 860)
        self.setMinimumSize(900, 600)
        self.setStyleSheet("background:#07070f; color:#e0e0f0; font-family:'Segoe UI';")

        # Fade-in
        self.setWindowOpacity(0.0)
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(900)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        self._anim = anim   # keep alive

        # State
        self.process       = None
        self.streamer      = None
        self._buf          = ""        # accumulates chars into lines
        self._history      = []        # [{title, ts, task}]
        self._attached     = []        # list of attached file paths
        self._history_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "gui_history.json"
        )
        self._load_history()

        self._build_ui()

        self._typing_timer = QTimer(self)
        self._typing_timer.timeout.connect(self._stop_typing)

        QTimer.singleShot(900, self._start_agent)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root_lay = QHBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # ── Left sidebar ───────────────────────────────────────────────────
        sidebar = QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("background:#0d0d1a; border-right:1px solid #1a1a2e;")
        sb_lay = QVBoxLayout(sidebar)
        sb_lay.setContentsMargins(0, 12, 0, 12)
        sb_lay.setSpacing(0)

        # Logo / title
        logo = QLabel("🤖  AI Agent")
        logo.setStyleSheet("color:#5588ff; font-size:15px; font-weight:700; padding:0 14px 10px;")
        sb_lay.addWidget(logo)

        # New chat button
        new_btn = QPushButton("＋  New Chat")
        new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.setFixedHeight(36)
        new_btn.setStyleSheet("""
            QPushButton {
                background:#1a1a2e; color:#8899ff;
                border:1px solid #2a2a4a; border-radius:8px;
                font-size:13px; font-weight:600; margin:0 10px 10px;
            }
            QPushButton:hover { background:#22224a; }
        """)
        new_btn.clicked.connect(self._new_chat)
        sb_lay.addWidget(new_btn)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#1a1a2e; margin:0;")
        sb_lay.addWidget(sep)

        hist_lbl = QLabel("CHAT HISTORY")
        hist_lbl.setStyleSheet("color:#333355; font-size:10px; font-weight:700; padding:10px 14px 4px;")
        sb_lay.addWidget(hist_lbl)

        # Scrollable history list
        self._hist_scroll = QScrollArea()
        self._hist_scroll.setWidgetResizable(True)
        self._hist_scroll.setStyleSheet("border:none; background:transparent;")
        self._hist_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._hist_container = QWidget()
        self._hist_lay = QVBoxLayout(self._hist_container)
        self._hist_lay.setContentsMargins(0, 0, 0, 0)
        self._hist_lay.setSpacing(0)
        self._hist_lay.addStretch()
        self._hist_scroll.setWidget(self._hist_container)
        sb_lay.addWidget(self._hist_scroll, 1)

        # File attach list label
        self._attach_lbl = QLabel("No files attached")
        self._attach_lbl.setStyleSheet(
            "color:#445566; font-size:10px; padding:6px 14px; font-style:italic;"
        )
        self._attach_lbl.setWordWrap(True)
        sb_lay.addWidget(self._attach_lbl)

        root_lay.addWidget(sidebar)

        # ── Right content area ─────────────────────────────────────────────
        content = QWidget()
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(18, 14, 18, 14)
        content_lay.setSpacing(10)

        # Hologram
        self.hologram = HologramCore()
        content_lay.addWidget(self.hologram)

        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background:#07070f; border:none;
                font-size:14px; color:#d0d0e8;
                padding:8px; line-height:1.5;
            }
            QScrollBar:vertical { background:#0d0d1a; width:6px; border-radius:3px; }
            QScrollBar::handle:vertical { background:#2a2a4a; border-radius:3px; }
        """)
        self.chat_display.append(
            "<span style='color:#00cc88;'>🤖 System: GUI Initialized — 3D Core Online. Starting Agent…</span><br>"
        )
        content_lay.addWidget(self.chat_display, 1)

        # ── Bottom toolbar (attach + screenshot + clear) ───────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        btn_style = """
            QPushButton {
                background:#12122a; color:#8899cc;
                border:1px solid #22224a; border-radius:8px;
                font-size:13px; padding:6px 14px;
            }
            QPushButton:hover { background:#1a1a3a; color:#aabbff; }
        """

        attach_btn = QPushButton("📎 Attach File")
        attach_btn.setCursor(Qt.PointingHandCursor)
        attach_btn.setStyleSheet(btn_style)
        attach_btn.clicked.connect(self._attach_file)
        toolbar.addWidget(attach_btn)

        screenshot_btn = QPushButton("📸 Screenshot")
        screenshot_btn.setCursor(Qt.PointingHandCursor)
        screenshot_btn.setStyleSheet(btn_style)
        screenshot_btn.clicked.connect(self._take_screenshot)
        toolbar.addWidget(screenshot_btn)

        clear_btn = QPushButton("🗑 Clear Chat")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet(btn_style)
        clear_btn.clicked.connect(self._clear_chat)
        toolbar.addWidget(clear_btn)

        toolbar.addStretch()
        content_lay.addLayout(toolbar)

        # ── Input row ──────────────────────────────────────────────────────
        input_row = QHBoxLayout()
        input_row.setSpacing(10)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Ask the Agent anything…")
        self.input_box.setFixedHeight(48)
        self.input_box.setStyleSheet("""
            QLineEdit {
                background:#12122a; border:1px solid #2a2a4a;
                border-radius:24px; padding-left:20px;
                font-size:14px; color:#e0e0f0;
            }
            QLineEdit:focus { border:1px solid #4466ff; }
        """)

        self.send_btn = QPushButton("➤")
        self.send_btn.setFixedSize(48, 48)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #3355ff, stop:1 #1133cc);
                border-radius:24px; font-size:18px; color:white;
                font-weight:bold;
            }
            QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 #4466ff, stop:1 #2244ee); }
            QPushButton:pressed { background:#1122aa; }
        """)

        self.send_btn.clicked.connect(self.send_msg)
        self.input_box.returnPressed.connect(self.send_msg)

        input_row.addWidget(self.input_box)
        input_row.addWidget(self.send_btn)
        content_lay.addLayout(input_row)

        root_lay.addWidget(content, 1)

        # Populate history sidebar
        self._refresh_history_ui()

    # ── Agent process ─────────────────────────────────────────────────────────

    def _start_agent(self):
        base_dir   = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
                      else os.path.dirname(os.path.abspath(__file__)))
        agent_path = os.path.join(base_dir, "agent.py")

        if not os.path.exists(agent_path):
            self.chat_display.append(
                f"<span style='color:red;'>❌ agent.py not found in: {base_dir}</span>"
            )
            return

        si = None
        if sys.platform == "win32":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        try:
            self.process = subprocess.Popen(
                [sys.executable, agent_path],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="ignore", bufsize=1,
                cwd=base_dir, startupinfo=si, env=env,
            )
            self.streamer = AgentStreamer(self.process)
            self.streamer.new_char.connect(self._on_char)
            self.streamer.error_sig.connect(self._on_stream_error)
            self.streamer.start()
        except Exception as e:
            self.chat_display.append(f"<span style='color:red;'>❌ Error: {e}</span>")

    # ── Messaging ─────────────────────────────────────────────────────────────

    def send_msg(self):
        msg = self.input_box.text().strip()
        if not msg or not self.process:
            return
        self.input_box.clear()

        # Show in chat
        self.chat_display.append(
            f"<br><span style='color:#4477ff; font-weight:bold;'>👤 YOU:</span> "
            f"<span style='color:#e0e0f0;'>{msg}</span><br>"
        )

        # Save to history — skip very short or trivial inputs
        if len(msg.strip()) >= 3:
            self._add_history(msg)

        try:
            self.process.stdin.write(msg + "\n")
            self.process.stdin.flush()
        except Exception as e:
            self.chat_display.append(f"<span style='color:red;'>❌ Send Error: {e}</span>")

    def _new_chat(self):
        """Send new_chat command to agent and clear display."""
        self.chat_display.clear()
        self.chat_display.append(
            "<span style='color:#00cc88;'>✨ New conversation started.</span><br>"
        )
        self._attached.clear()
        self._update_attach_label()
        if self.process:
            try:
                self.process.stdin.write("new_chat\n")
                self.process.stdin.flush()
            except Exception:
                pass

    def _clear_chat(self):
        self.chat_display.clear()
        self.chat_display.append(
            "<span style='color:#555577;'>— Chat cleared —</span><br>"
        )

    # ── File attachment ───────────────────────────────────────────────────────

    def _attach_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Attach Files", "",
            "All Files (*);;"
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;"
            "Documents (*.pdf *.docx *.xlsx *.pptx *.txt);;"
            "Code (*.py *.cs *.cpp *.js *.ts *.html *.css *.json)"
        )
        if not paths:
            return

        # Disable input during attach
        self.input_box.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.input_box.setPlaceholderText("⏳ Attaching file… wait a moment")

        for path in paths:
            self._attached.append(path)
            fname = os.path.basename(path)
            self.chat_display.append(
                f"<span style='color:#ffaa44;'>📎 Attaching: {fname}</span>"
            )
            if self.process:
                try:
                    self.process.stdin.write(f"attach {path}\n")
                    self.process.stdin.flush()
                except Exception as e:
                    self.chat_display.append(
                        f"<span style='color:red;'>❌ Attach error: {e}</span>"
                    )
        self._update_attach_label()
        QTimer.singleShot(1500, self._on_attach_ready)

    def _update_attach_label(self):
        if not self._attached:
            self._attach_lbl.setText("No files attached")
        else:
            names = [os.path.basename(p) for p in self._attached[-4:]]
            extra = len(self._attached) - 4
            text  = "\n".join(names)
            if extra > 0:
                text += f"\n+{extra} more"
            self._attach_lbl.setText(f"📎 {text}")

    # ── Screenshot ────────────────────────────────────────────────────────────

    def _take_screenshot(self):
        """Capture the primary screen and send it to the agent as an attached file."""
        base_dir   = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
                      else os.path.dirname(os.path.abspath(__file__)))
        save_path  = os.path.join(base_dir, "live_screen.png")

        screen: QScreen = QApplication.primaryScreen()
        if screen is None:
            self.chat_display.append(
                "<span style='color:red;'>❌ No screen detected.</span>"
            )
            return

        # Hide window briefly so screenshot doesn't include this GUI
        self.hide()
        QTimer.singleShot(250, lambda: self._capture(screen, save_path))

    def _capture(self, screen: QScreen, save_path: str):
        pix = screen.grabWindow(0)
        pix.save(save_path, "PNG")
        self.show()

        self.chat_display.append(
            "<span style='color:#00ccff;'>📸 Screenshot captured — attaching…</span>"
        )

        # Disable input while attach is being processed
        self.input_box.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.input_box.setPlaceholderText("⏳ Attaching screenshot… wait a moment")

        if self.process:
            try:
                self.process.stdin.write(f"attach {save_path}\n")
                self.process.stdin.flush()
            except Exception as e:
                self.chat_display.append(
                    f"<span style='color:red;'>❌ Screenshot attach error: {e}</span>"
                )

        self._attached.append(save_path)
        self._update_attach_label()

        # Re-enable after 1.5s — enough time for agent to register the file
        QTimer.singleShot(1500, self._on_attach_ready)

    def _on_attach_ready(self):
        self.input_box.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.input_box.setPlaceholderText("Ask the Agent anything…")
        self.input_box.setFocus()
        self.chat_display.append(
            "<span style='color:#00cc88;'>✅ Screenshot ready — you can now ask about it</span><br>"
        )

    # ── Char streaming ────────────────────────────────────────────────────────

    def _on_char(self, ch: str):
        self.hologram.set_state("typing")
        self._typing_timer.start(1200)

        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.insertPlainText(ch)
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )

    def _stop_typing(self):
        self.hologram.set_state("idle")
        self._typing_timer.stop()

    def _on_stream_error(self, msg: str):
        self.hologram.set_state("idle")
        self.chat_display.append(f"<span style='color:orange;'>⚠️ {msg}</span>")

    # ── Chat history persistence ──────────────────────────────────────────────

    def _load_history(self):
        try:
            if os.path.exists(self._history_file):
                with open(self._history_file, encoding="utf-8") as f:
                    self._history = json.load(f)
        except Exception:
            self._history = []

    def _save_history(self):
        try:
            # Keep last 50 entries
            self._history = self._history[-50:]
            with open(self._history_file, "w", encoding="utf-8") as f:
                json.dump(self._history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _add_history(self, task: str):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = {"title": task[:60], "ts": ts, "task": task}
        self._history.append(entry)
        self._save_history()
        self._refresh_history_ui()

    def _refresh_history_ui(self):
        # Clear existing items (keep stretch at end)
        while self._hist_lay.count() > 1:
            item = self._hist_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add newest first
        for entry in reversed(self._history[-30:]):
            item = HistoryItem(entry["title"], entry["ts"], entry["task"])
            item.clicked_sig.connect(self._replay_from_history)
            self._hist_lay.insertWidget(0, item)

    def _replay_from_history(self, task: str):
        """Put the old task text into the input box so user can re-send."""
        self.input_box.setText(task)
        self.input_box.setFocus()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        if self.streamer:
            self.streamer.stop()
        if self.process:
            self.process.terminate()
        event.accept()


# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = ModernAgentGUI()
    win.show()
    sys.exit(app.exec())