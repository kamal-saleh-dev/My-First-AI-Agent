import sys
import os
import subprocess
import math
import json
import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QFrame, QLabel, QScrollArea,
    QFileDialog
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QThread, Signal, QTimer
from PySide6.QtGui import QColor, QTextCursor, QPainter, QScreen


class HologramCore(QWidget):
    def __init__(self):
        super().__init__()
        self.angle_y    = 0.0
        self.angle_x    = 0.0
        self.speed_mult = 1.0
        self.color      = QColor(30, 136, 229)
        self.pulse      = 0.0
        self.setMinimumHeight(200)
        self.setMaximumHeight(240)
        self.nodes = []
        for i in range(0, 360, 15):
            for j in range(-90, 90, 15):
                ri, rj = math.radians(i), math.radians(j)
                self.nodes.append([math.cos(rj)*math.cos(ri), math.sin(rj), math.cos(rj)*math.sin(ri)])
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_state(self, state):
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
        cx, cy     = self.width() / 2, self.height() / 2
        scale_base = min(self.width(), self.height()) * 0.38
        for node in self.nodes:
            x, y, z = node
            nx = x*math.cos(self.angle_y) - z*math.sin(self.angle_y)
            nz = x*math.sin(self.angle_y) + z*math.cos(self.angle_y)
            x, z = nx, nz
            ny = y*math.cos(self.angle_x) - z*math.sin(self.angle_x)
            nz = y*math.sin(self.angle_x) + z*math.cos(self.angle_x)
            y, z = ny, nz
            sc  = scale_base / (z + 3)
            sz  = max(1.0, (z + 2.5) * 1.8)
            alp = int(max(15, min(230, (z+2)*55 + self.pulse*25)))
            c   = QColor(self.color); c.setAlpha(alp)
            p.setBrush(c); p.setPen(Qt.NoPen)
            p.drawEllipse(cx+x*sc - sz/2, cy+y*sc - sz/2, sz, sz)


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
                    if ch: self.new_char.emit(ch)
                    else:  break
                except OSError: break
                except Exception as e:
                    self.error_sig.emit(f"Stream error: {e}"); break
        except Exception as e:
            self.error_sig.emit(f"Streamer crashed: {e}")

    def stop(self): self.is_running = False


class SessionButton(QFrame):
    clicked_sig = Signal(str)

    def __init__(self, title, ts, session_id, active=False):
        super().__init__()
        self.session_id = session_id
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(54)
        self._set_style(active)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 4)
        lay.setSpacing(1)
        t = QLabel(title[:40] + ("…" if len(title) > 40 else ""))
        t.setStyleSheet("color:#d0d0f0;font-size:12px;font-weight:600;background:transparent;")
        ts_l = QLabel(ts)
        ts_l.setStyleSheet("color:#44446a;font-size:10px;background:transparent;")
        lay.addWidget(t); lay.addWidget(ts_l)

    def _set_style(self, active):
        if active:
            self.setStyleSheet("QFrame{background:#1a1a3a;border-radius:8px;border-left:3px solid #4466ff;margin:2px 8px;}")
        else:
            self.setStyleSheet("QFrame{background:#111120;border-radius:8px;border-left:3px solid transparent;margin:2px 8px;}QFrame:hover{background:#161630;}")

    def set_active(self, active): self._set_style(active)
    def mousePressEvent(self, event): self.clicked_sig.emit(self.session_id)


class ModernAgentGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Agent — 3D Core Edition")
        self.resize(1340, 860)
        self.setMinimumSize(900, 600)
        self.setStyleSheet("background:#07070f;color:#e0e0f0;font-family:'Segoe UI';")

        self.setWindowOpacity(0.0)
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(900); anim.setStartValue(0.0); anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic); anim.start()
        self._anim = anim

        self._sessions      = {}
        self._active_id     = ""
        self._agent_buf     = ""
        self._in_agent_turn = False
        self._attached      = []
        self._sess_file     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui_sessions.json")
        self._load_sessions()

        self.process  = None
        self.streamer = None

        self._build_ui()

        self._typing_timer = QTimer(self)
        self._typing_timer.timeout.connect(self._agent_turn_ended)

        self._new_session(silent=True)
        QTimer.singleShot(900, self._start_agent)

    def _build_ui(self):
        root = QWidget(); self.setCentralWidget(root)
        root_lay = QHBoxLayout(root)
        root_lay.setContentsMargins(0,0,0,0); root_lay.setSpacing(0)

        # ── Sidebar
        sidebar = QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("background:#0a0a18;border-right:1px solid #14142a;")
        sb_lay = QVBoxLayout(sidebar)
        sb_lay.setContentsMargins(0,14,0,14); sb_lay.setSpacing(0)

        logo = QLabel("🤖  AI Agent")
        logo.setStyleSheet("color:#5588ff;font-size:15px;font-weight:700;padding:0 16px 12px;")
        sb_lay.addWidget(logo)

        new_btn = QPushButton("＋  New Chat")
        new_btn.setCursor(Qt.PointingHandCursor); new_btn.setFixedHeight(36)
        new_btn.setStyleSheet("QPushButton{background:#151530;color:#6688ff;border:1px solid #22224a;border-radius:8px;font-size:13px;font-weight:600;margin:0 10px 10px;}QPushButton:hover{background:#1c1c40;color:#aabbff;}")
        new_btn.clicked.connect(self._new_session)
        sb_lay.addWidget(new_btn)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setStyleSheet("color:#14142a;")
        sb_lay.addWidget(sep)

        hist_lbl = QLabel("CONVERSATIONS")
        hist_lbl.setStyleSheet("color:#2a2a55;font-size:10px;font-weight:700;padding:10px 16px 4px;letter-spacing:1px;")
        sb_lay.addWidget(hist_lbl)

        self._sess_scroll = QScrollArea()
        self._sess_scroll.setWidgetResizable(True)
        self._sess_scroll.setStyleSheet("border:none;background:transparent;")
        self._sess_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._sess_container = QWidget()
        self._sess_lay = QVBoxLayout(self._sess_container)
        self._sess_lay.setContentsMargins(0,0,0,0); self._sess_lay.setSpacing(0)
        self._sess_lay.addStretch()
        self._sess_scroll.setWidget(self._sess_container)
        sb_lay.addWidget(self._sess_scroll, 1)

        self._attach_lbl = QLabel("No files attached")
        self._attach_lbl.setWordWrap(True)
        self._attach_lbl.setStyleSheet("color:#334455;font-size:10px;padding:6px 14px;font-style:italic;")
        sb_lay.addWidget(self._attach_lbl)

        root_lay.addWidget(sidebar)

        # ── Content
        content = QWidget()
        c_lay   = QVBoxLayout(content)
        c_lay.setContentsMargins(18,14,18,14); c_lay.setSpacing(10)

        self.hologram = HologramCore()
        c_lay.addWidget(self.hologram)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("QTextEdit{background:#07070f;border:none;font-size:14px;color:#d0d0e8;padding:8px;}QScrollBar:vertical{background:#0a0a18;width:6px;border-radius:3px;}QScrollBar::handle:vertical{background:#22224a;border-radius:3px;}")
        c_lay.addWidget(self.chat_display, 1)

        btn_style = "QPushButton{background:#10102a;color:#7788bb;border:1px solid #1e1e3a;border-radius:8px;font-size:13px;padding:6px 14px;}QPushButton:hover{background:#181838;color:#aabbff;}QPushButton:disabled{color:#333355;border-color:#111122;}"
        tb = QHBoxLayout(); tb.setSpacing(8)
        self._attach_btn = QPushButton("📎 Attach File"); self._attach_btn.setCursor(Qt.PointingHandCursor)
        self._attach_btn.setStyleSheet(btn_style); self._attach_btn.clicked.connect(self._attach_file)
        self._shot_btn   = QPushButton("📸 Screenshot");  self._shot_btn.setCursor(Qt.PointingHandCursor)
        self._shot_btn.setStyleSheet(btn_style);   self._shot_btn.clicked.connect(self._take_screenshot)
        clear_btn        = QPushButton("🗑 Clear");        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet(btn_style);        clear_btn.clicked.connect(self._clear_display)
        tb.addWidget(self._attach_btn); tb.addWidget(self._shot_btn); tb.addWidget(clear_btn); tb.addStretch()
        c_lay.addLayout(tb)

        inp_row = QHBoxLayout(); inp_row.setSpacing(10)
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Ask the Agent anything…"); self.input_box.setFixedHeight(48)
        self.input_box.setStyleSheet("QLineEdit{background:#10102a;border:1px solid #1e1e3a;border-radius:24px;padding-left:20px;font-size:14px;color:#e0e0f0;}QLineEdit:focus{border:1px solid #4466ff;}QLineEdit:disabled{color:#334455;}")
        self.send_btn = QPushButton("➤"); self.send_btn.setFixedSize(48,48); self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet("QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #3355ff,stop:1 #1133cc);border-radius:24px;font-size:18px;color:white;font-weight:bold;}QPushButton:hover{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #4466ff,stop:1 #2244ee);}QPushButton:pressed{background:#1122aa;}QPushButton:disabled{background:#1a1a2a;color:#333355;}")
        self.send_btn.clicked.connect(self.send_msg); self.input_box.returnPressed.connect(self.send_msg)
        inp_row.addWidget(self.input_box); inp_row.addWidget(self.send_btn)
        c_lay.addLayout(inp_row)

        root_lay.addWidget(content, 1)

    # ── Sessions ──────────────────────────────
    def _new_session(self, silent=False):
        import uuid
        sid = str(uuid.uuid4())[:8]
        ts  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        self._sessions[sid] = {"title": "New Chat", "ts": ts, "messages": []}
        self._active_id = sid
        self._attached.clear(); self._update_attach_label()
        self._refresh_sidebar(); self._render_session(sid)
        if not silent and self.process:
            try: self.process.stdin.write("new_chat\n"); self.process.stdin.flush()
            except Exception: pass

    def _load_session(self, sid):
        if sid == self._active_id: return
        self._flush_agent_turn()
        self._active_id = sid
        self._refresh_sidebar(); self._render_session(sid)

    def _render_session(self, sid):
        self.chat_display.clear()
        msgs = self._sessions.get(sid, {}).get("messages", [])
        if not msgs:
            self.chat_display.append("<span style='color:#00cc88;'>✨ New conversation — ask anything.</span><br>")
            return
        for m in msgs:
            self._display_bubble(m["role"], m["html"])

    def _display_bubble(self, role, html):
        if role == "user":
            self.chat_display.append(
                f"<br><span style='color:#4477ff;font-weight:bold;'>👤 YOU:</span> "
                f"<span style='color:#e0e0f0;'>{html}</span><br>"
            )
        else:
            self.chat_display.append(f"<span style='color:#d0d0e8;'>{html}</span>")
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())

    def _save_message(self, role, text, html):
        if self._active_id not in self._sessions: return
        sess = self._sessions[self._active_id]
        sess["messages"].append({"role": role, "text": text, "html": html})
        if role == "user" and sess["title"] == "New Chat":
            sess["title"] = text[:55] + ("…" if len(text) > 55 else "")
            self._refresh_sidebar()
        self._save_sessions()

    def _flush_agent_turn(self):
        if self._agent_buf.strip():
            self._save_message("agent", self._agent_buf, self._agent_buf)
        self._agent_buf = ""; self._in_agent_turn = False

    def _refresh_sidebar(self):
        while self._sess_lay.count() > 1:
            item = self._sess_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for sid, sess in reversed(list(self._sessions.items())):
            btn = SessionButton(sess["title"], sess["ts"], sid, active=(sid == self._active_id))
            btn.clicked_sig.connect(self._load_session)
            self._sess_lay.insertWidget(0, btn)

    # ── Messaging ─────────────────────────────
    def send_msg(self):
        msg = self.input_box.text().strip()
        if not msg or not self.process: return
        self.input_box.clear()
        self._flush_agent_turn()
        self._display_bubble("user", msg)
        self._save_message("user", msg, msg)
        try:
            self.process.stdin.write(msg + "\n"); self.process.stdin.flush()
        except Exception as e:
            self.chat_display.append(f"<span style='color:red;'>❌ Send Error: {e}</span>")

    # ── Streaming ─────────────────────────────
    def _on_char(self, ch):
        self.hologram.set_state("typing")
        self._typing_timer.start(1800)
        self._in_agent_turn = True
        self._agent_buf    += ch
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.insertPlainText(ch)
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())

    def _agent_turn_ended(self):
        self._typing_timer.stop()
        self.hologram.set_state("idle")
        self._flush_agent_turn()

    def _on_stream_error(self, msg):
        self.hologram.set_state("idle"); self._flush_agent_turn()
        self.chat_display.append(f"<span style='color:orange;'>⚠️ {msg}</span>")

    # ── Attach / Screenshot ───────────────────
    def _lock_input(self, ph):
        self.input_box.setEnabled(False); self.send_btn.setEnabled(False)
        self._attach_btn.setEnabled(False); self._shot_btn.setEnabled(False)
        self.input_box.setPlaceholderText(ph)

    def _unlock_input(self):
        self.input_box.setEnabled(True); self.send_btn.setEnabled(True)
        self._attach_btn.setEnabled(True); self._shot_btn.setEnabled(True)
        self.input_box.setPlaceholderText("Ask the Agent anything…"); self.input_box.setFocus()

    def _attach_file(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Attach Files", "",
            "All Files (*);; Images (*.png *.jpg *.jpeg *.webp *.bmp);; "
            "Documents (*.pdf *.docx *.xlsx *.pptx *.txt);; Code (*.py *.cs *.cpp *.js *.ts *.html *.css *.json)")
        if not paths: return
        self._lock_input("⏳ Attaching file… wait a moment")
        for path in paths:
            self._attached.append(path)
            fname = os.path.basename(path)
            self.chat_display.append(f"<span style='color:#ffaa44;'>📎 Attaching: {fname}</span>")
            if self.process:
                try: self.process.stdin.write(f"attach {path}\n"); self.process.stdin.flush()
                except Exception as e: self.chat_display.append(f"<span style='color:red;'>❌ {e}</span>")
        self._update_attach_label()
        QTimer.singleShot(1500, self._on_attach_ready)

    def _take_screenshot(self):
        base_dir  = (os.path.dirname(sys.executable) if getattr(sys,"frozen",False)
                     else os.path.dirname(os.path.abspath(__file__)))
        save_path = os.path.join(base_dir, "live_screen.png")
        screen    = QApplication.primaryScreen()
        if not screen:
            self.chat_display.append("<span style='color:red;'>❌ No screen.</span>"); return
        self.hide()
        QTimer.singleShot(250, lambda: self._capture(screen, save_path))

    def _capture(self, screen, save_path):
        screen.grabWindow(0).save(save_path, "PNG")
        self.show()
        self.chat_display.append("<span style='color:#00ccff;'>📸 Screenshot captured — attaching…</span>")
        self._lock_input("⏳ Attaching screenshot… wait a moment")
        if self.process:
            try: self.process.stdin.write(f"attach {save_path}\n"); self.process.stdin.flush()
            except Exception as e: self.chat_display.append(f"<span style='color:red;'>❌ {e}</span>")
        self._attached.append(save_path); self._update_attach_label()
        QTimer.singleShot(1500, self._on_attach_ready)

    def _on_attach_ready(self):
        self._unlock_input()
        self.chat_display.append("<span style='color:#00cc88;'>✅ File ready — ask about it now</span><br>")

    def _update_attach_label(self):
        if not self._attached: self._attach_lbl.setText("No files attached"); return
        names = [os.path.basename(p) for p in self._attached[-4:]]
        extra = len(self._attached) - 4
        self._attach_lbl.setText("📎 " + "\n".join(names) + (f"\n+{extra} more" if extra > 0 else ""))

    def _clear_display(self): self.chat_display.clear()

    # ── Persistence ───────────────────────────
    def _load_sessions(self):
        try:
            if os.path.exists(self._sess_file):
                with open(self._sess_file, encoding="utf-8") as f:
                    self._sessions = json.load(f)
        except Exception: self._sessions = {}

    def _save_sessions(self):
        try:
            if len(self._sessions) > 60:
                for k in list(self._sessions.keys())[:-60]: del self._sessions[k]
            with open(self._sess_file, "w", encoding="utf-8") as f:
                json.dump(self._sessions, f, ensure_ascii=False, indent=2)
        except Exception: pass

    # ── Agent process ─────────────────────────
    def _start_agent(self):
        base_dir   = (os.path.dirname(sys.executable) if getattr(sys,"frozen",False)
                      else os.path.dirname(os.path.abspath(__file__)))
        agent_path = os.path.join(base_dir, "agent.py")
        if not os.path.exists(agent_path):
            self.chat_display.append(f"<span style='color:red;'>❌ agent.py not found in {base_dir}</span>"); return
        si = None
        if sys.platform == "win32":
            si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        env = os.environ.copy(); env["PYTHONUNBUFFERED"] = "1"
        try:
            self.process = subprocess.Popen(
                [sys.executable, agent_path],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="ignore", bufsize=1,
                cwd=base_dir, startupinfo=si, env=env)
            self.streamer = AgentStreamer(self.process)
            self.streamer.new_char.connect(self._on_char)
            self.streamer.error_sig.connect(self._on_stream_error)
            self.streamer.start()
        except Exception as e:
            self.chat_display.append(f"<span style='color:red;'>❌ Error: {e}</span>")

    def closeEvent(self, event):
        self._flush_agent_turn(); self._save_sessions()
        if self.streamer: self.streamer.stop()
        if self.process:  self.process.terminate()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = ModernAgentGUI()
    win.show()
    sys.exit(app.exec())
