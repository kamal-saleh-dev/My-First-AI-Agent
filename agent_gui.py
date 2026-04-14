import sys
import os
import subprocess
import math
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QTextEdit, QLineEdit, QPushButton, QFrame)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QThread, Signal, QTimer
from PySide6.QtGui import QColor, QTextCursor, QPainter

# ==========================================
# 🌌 The 3D Hologram Core
# ==========================================
class HologramCore(QWidget):
    def __init__(self):
        super().__init__()
        self.angle_y = 0.0
        self.angle_x = 0.0
        self.speed_multiplier = 1.0
        self.color = QColor(30, 136, 229)

        self.nodes = []
        for i in range(0, 360, 15):
            for j in range(-90, 90, 15):
                rad_i = math.radians(i)
                rad_j = math.radians(j)
                x = math.cos(rad_j) * math.cos(rad_i)
                y = math.sin(rad_j)
                z = math.cos(rad_j) * math.sin(rad_i)
                self.nodes.append([x, y, z])

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)

    def set_state(self, state):
        if state == "typing":
            self.speed_multiplier = 4.0
            self.color = QColor(0, 230, 118)
        else:
            self.speed_multiplier = 1.0
            self.color = QColor(30, 136, 229)

    def update_animation(self):
        self.angle_y += 0.01 * self.speed_multiplier
        self.angle_x += 0.005 * self.speed_multiplier
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#050505"))

        cx = self.width() / 2
        cy = self.height() / 2

        for node in self.nodes:
            x, y, z = node
            new_x = x * math.cos(self.angle_y) - z * math.sin(self.angle_y)
            new_z = x * math.sin(self.angle_y) + z * math.cos(self.angle_y)
            x, z = new_x, new_z
            new_y = y * math.cos(self.angle_x) - z * math.sin(self.angle_x)
            new_z = y * math.sin(self.angle_x) + z * math.cos(self.angle_x)
            y, z = new_y, new_z

            scale = 250 / (z + 3)
            px = cx + x * scale
            py = cy + y * scale
            size = max(1.0, (z + 2.5) * 2.0)
            alpha = int(max(20, min(255, (z + 2) * 60)))
            
            c = QColor(self.color)
            c.setAlpha(alpha)
            painter.setBrush(c)
            painter.setPen(QColor(0, 0, 0, 0))
            painter.drawEllipse(px, py, size, size)

# ==========================================
# 🧠 The Brain (Safely streams the terminal)
# ==========================================
class AgentStreamer(QThread):
    new_char  = Signal(str)
    error_sig = Signal(str)   # emitted on any unhandled exception

    def __init__(self, process):
        super().__init__()
        self.process    = process
        self.is_running = True

    def run(self):
        """Stream stdout char-by-char. Any exception emits error_sig instead of crashing the GUI."""
        try:
            while self.is_running and self.process and self.process.poll() is None:
                try:
                    char = self.process.stdout.read(1)
                    if char:
                        self.new_char.emit(char)
                    else:
                        break
                except OSError:
                    break  # pipe closed — normal on agent exit
                except Exception as e:
                    self.error_sig.emit(f"Stream error: {e}")
                    break
        except Exception as e:
            # Outer safety net — never let an unhandled exception silently kill the thread
            self.error_sig.emit(f"Streamer crashed: {e}")

    def stop(self):
        self.is_running = False

# ==========================================
# 🎨 The GUI
# ==========================================
class ModernAgentGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Agent - 3D Core Edition")
        self.resize(1200, 800)
        self.setStyleSheet("background-color: #0b0b0b; color: white; font-family: 'Segoe UI';")

        self.setWindowOpacity(0.0)
        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setDuration(1200)
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.fade_anim.start()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(250)
        self.sidebar.setStyleSheet("background-color: #121212; border-right: 1px solid #1e1e1e;")
        main_layout.addWidget(self.sidebar)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.addWidget(content_widget)

        self.hologram_core = HologramCore()
        self.hologram_core.setMinimumHeight(350)
        content_layout.addWidget(self.hologram_core)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("background-color: #0b0b0b; border: none; font-size: 15px; padding: 10px;")
        self.chat_display.append("<span style='color:#00ff00;'>🤖 System: GUI Initialized. 3D Core Online. Starting Agent...</span><br>")
        content_layout.addWidget(self.chat_display)

        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)
        
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Ask the Agent anything...")
        self.input_box.setFixedHeight(50)
        self.input_box.setStyleSheet("QLineEdit { background-color: #1e1e1e; border: 1px solid #333333; border-radius: 25px; padding-left: 20px; font-size: 15px; } QLineEdit:focus { border: 1px solid #1e88e5; }")
        
        self.send_btn = QPushButton("➢")
        self.send_btn.setFixedSize(50, 50)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet("QPushButton { background-color: #1e88e5; border-radius: 25px; font-weight: bold; font-size: 20px; color: white; } QPushButton:hover { background-color: #1565c0; }")

        input_layout.addWidget(self.input_box)
        input_layout.addWidget(self.send_btn)
        content_layout.addLayout(input_layout)

        self.process = None
        self.streamer = None
        self.typing_timer = QTimer()
        self.typing_timer.timeout.connect(self.stop_typing_anim)
        
        self.send_btn.clicked.connect(self.send_msg)
        self.input_box.returnPressed.connect(self.send_msg)

        # 🔥 التعديل السحري: نأخر التشغيل ثانية واحدة لحد ما الواجهة تترسم وتستقر
        QTimer.singleShot(1000, self.start_agent)

    def start_agent(self):
        # 1. تحديد مسار الملف صح (حتى لو حولته EXE بعدين)
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        agent_path = os.path.join(base_dir, "agent.py")

        if not os.path.exists(agent_path):
            self.chat_display.append(
                f"<span style='color:red;'>❌ agent.py not found in: {base_dir}</span>"
            )
            return
        
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        # 2. إجبار البايثون يبعت الرسايل فوراً بدون تأخير
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        try:
            self.process = subprocess.Popen(
                [sys.executable, agent_path],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="ignore", bufsize=1,
                cwd=base_dir, startupinfo=startupinfo, env=env
            )
            
            self.streamer = AgentStreamer(self.process)
            self.streamer.new_char.connect(self.append_char)
            self.streamer.error_sig.connect(self._on_stream_error)
            self.streamer.start()
        except Exception as e:
            self.chat_display.append(f"<span style='color:red;'>❌ Error: {e}</span>")

    def send_msg(self):
        msg = self.input_box.text().strip()
        if not msg or not self.process: return
        
        self.input_box.clear()
        self.chat_display.append(f"<br><span style='color:#1e88e5; font-weight:bold;'>👤 YOU:</span> <span style='color:white;'>{msg}</span><br>")
        
        try:
            self.process.stdin.write(msg + "\n")
            self.process.stdin.flush()
        except Exception as e:
            self.chat_display.append(f"<span style='color:red;'>❌ Send Error: {e}</span>")

    def append_char(self, char):
        self.hologram_core.set_state("typing")
        self.typing_timer.start(1000)

        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.insertPlainText(char)
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())

    def stop_typing_anim(self):
        self.hologram_core.set_state("idle")
        self.typing_timer.stop()

    def _on_stream_error(self, msg: str):
        """Called when the streamer thread encounters an error."""
        self.hologram_core.set_state("idle")
        self.chat_display.append(f"<span style='color:orange;'>⚠️ {msg}</span>")

    def closeEvent(self, event):
        if self.streamer: self.streamer.stop()
        if self.process: self.process.terminate()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ModernAgentGUI()
    window.show()
    sys.exit(app.exec())