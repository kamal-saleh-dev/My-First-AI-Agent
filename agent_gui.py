import sys, os, subprocess, math, json, datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QFrame, QLabel, QScrollArea,
    QFileDialog, QMenu, QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QThread, Signal, QTimer, QPoint
from PySide6.QtGui import QColor, QTextCursor, QPainter


class HologramCore(QWidget):
    def __init__(self):
        super().__init__()
        self.angle_y = 0.0; self.angle_x = 0.0
        self.speed_mult = 1.0; self.color = QColor(30, 136, 229); self.pulse = 0.0
        self.setMinimumHeight(200); self.setMaximumHeight(240)
        self.nodes = []
        for i in range(0,360,15):
            for j in range(-90,90,15):
                ri,rj=math.radians(i),math.radians(j)
                self.nodes.append([math.cos(rj)*math.cos(ri),math.sin(rj),math.cos(rj)*math.sin(ri)])
        t=QTimer(self); t.timeout.connect(self._tick); t.start(16)
    def set_state(self,s):
        if s=="typing": self.speed_mult=4.0; self.color=QColor(0,220,130)
        else:           self.speed_mult=1.0; self.color=QColor(30,136,229)
    def _tick(self):
        self.angle_y+=0.008*self.speed_mult; self.angle_x+=0.004*self.speed_mult
        self.pulse=(math.sin(self.angle_y*2)+1)/2; self.update()
    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(),QColor("#070710"))
        cx,cy=self.width()/2,self.height()/2; sb=min(self.width(),self.height())*0.38
        for node in self.nodes:
            x,y,z=node
            nx=x*math.cos(self.angle_y)-z*math.sin(self.angle_y); nz=x*math.sin(self.angle_y)+z*math.cos(self.angle_y); x,z=nx,nz
            ny=y*math.cos(self.angle_x)-z*math.sin(self.angle_x); nz=y*math.sin(self.angle_x)+z*math.cos(self.angle_x); y,z=ny,nz
            sc=sb/(z+3); sz=max(1.0,(z+2.5)*1.8); alp=int(max(15,min(230,(z+2)*55+self.pulse*25)))
            c=QColor(self.color); c.setAlpha(alp); p.setBrush(c); p.setPen(Qt.NoPen)
            p.drawEllipse(cx+x*sc-sz/2,cy+y*sc-sz/2,sz,sz)


class AgentStreamer(QThread):
    new_char=Signal(str); error_sig=Signal(str)
    def __init__(self,proc): super().__init__(); self.process=proc; self.is_running=True
    def run(self):
        try:
            while self.is_running and self.process and self.process.poll() is None:
                try:
                    ch=self.process.stdout.read(1)
                    if ch: self.new_char.emit(ch)
                    else: break
                except OSError: break
                except Exception as e: self.error_sig.emit(f"Stream error: {e}"); break
        except Exception as e: self.error_sig.emit(f"Streamer crashed: {e}")
    def stop(self): self.is_running=False


class SessionRow(QFrame):
    clicked_sig=Signal(str); rename_sig=Signal(str)
    delete_sig=Signal(str);  pin_sig=Signal(str); export_sig=Signal(str)

    _M = ("QMenu{background:#12122a;border:1px solid #22224a;border-radius:8px;"
          "color:#d0d0f0;font-size:13px;padding:4px;}"
          "QMenu::item{padding:7px 18px;border-radius:5px;}"
          "QMenu::item:selected{background:#1e1e3a;color:#aabbff;}"
          "QMenu::separator{height:1px;background:#22224a;margin:3px 8px;}")

    def __init__(self,sid,title,ts,pinned=False,active=False):
        super().__init__(); self.sid=sid
        self.setCursor(Qt.PointingHandCursor); self.setFixedHeight(54)
        self._set_style(active,pinned)
        row=QHBoxLayout(self); row.setContentsMargins(12,4,6,4); row.setSpacing(4)
        txt=QWidget(); txt.setAttribute(Qt.WA_TransparentForMouseEvents)
        tl=QVBoxLayout(txt); tl.setContentsMargins(0,0,0,0); tl.setSpacing(1)
        pre="📌 " if pinned else ""
        self._lbl=QLabel(pre+title[:36]+("…" if len(title)>36 else ""))
        self._lbl.setStyleSheet("color:#d0d0f0;font-size:12px;font-weight:600;background:transparent;")
        tsl=QLabel(ts); tsl.setStyleSheet("color:#44446a;font-size:10px;background:transparent;")
        tl.addWidget(self._lbl); tl.addWidget(tsl); row.addWidget(txt,1)
        self._btn=QPushButton("⋯"); self._btn.setFixedSize(26,26)
        self._btn.setStyleSheet("QPushButton{background:transparent;color:#555577;border:none;font-size:16px;padding:0 4px;border-radius:4px;}QPushButton:hover{color:#aabbff;background:#1e1e3a;}")
        self._btn.setCursor(Qt.PointingHandCursor); self._btn.clicked.connect(self._menu)
        self._btn.hide(); row.addWidget(self._btn)

    def _set_style(self,active,pinned=False):
        brd="#4466ff" if active else ("#ffaa33" if pinned else "transparent")
        bg="#1a1a3a" if active else "#111120"
        self.setStyleSheet(f"QFrame{{background:{bg};border-radius:8px;border-left:3px solid {brd};margin:2px 8px;}}QFrame:hover{{background:#161630;}}")

    def _menu(self):
        m=QMenu(self); m.setStyleSheet(self._M)
        m.addAction("✏️  Rename",     lambda: self.rename_sig.emit(self.sid))
        m.addAction("📌  Pin / Unpin",lambda: self.pin_sig.emit(self.sid))
        m.addAction("📤  Export",     lambda: self.export_sig.emit(self.sid))
        m.addSeparator()
        m.addAction("🗑️  Delete",     lambda: self.delete_sig.emit(self.sid))
        m.exec(self._btn.mapToGlobal(QPoint(0,self._btn.height())))

    def enterEvent(self,_): self._btn.show()
    def leaveEvent(self,_): self._btn.hide()
    def mousePressEvent(self,e):
        if not self._btn.underMouse(): self.clicked_sig.emit(self.sid)


class ModernAgentGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Agent — 3D Core Edition")
        self.resize(1340,860); self.setMinimumSize(900,600)
        self.setStyleSheet("background:#07070f;color:#e0e0f0;font-family:'Segoe UI';")
        self.setWindowOpacity(0.0)
        a=QPropertyAnimation(self,b"windowOpacity",self); a.setDuration(900)
        a.setStartValue(0.0); a.setEndValue(1.0); a.setEasingCurve(QEasingCurve.OutCubic)
        a.start(); self._anim=a

        self._sessions={}; self._active_id=""; self._pending_id=""
        self._agent_buf=""; self._in_agent_turn=False; self._attached=[]
        self._sess_file=os.path.join(os.path.dirname(os.path.abspath(__file__)),"gui_sessions.json")
        self._load_sessions()
        self.process=None; self.streamer=None
        self._build_ui()
        self._typing_timer=QTimer(self); self._typing_timer.timeout.connect(self._agent_turn_ended)
        self._create_pending(); QTimer.singleShot(900,self._start_agent)

    def _build_ui(self):
        root=QWidget(); self.setCentralWidget(root)
        rl=QHBoxLayout(root); rl.setContentsMargins(0,0,0,0); rl.setSpacing(0)

        # Sidebar
        sb=QFrame(); sb.setFixedWidth(240)
        sb.setStyleSheet("background:#0a0a18;border-right:1px solid #14142a;")
        sbl=QVBoxLayout(sb); sbl.setContentsMargins(0,14,0,14); sbl.setSpacing(0)
        logo=QLabel("🤖  AI Agent"); logo.setStyleSheet("color:#5588ff;font-size:15px;font-weight:700;padding:0 16px 12px;")
        sbl.addWidget(logo)
        nb=QPushButton("＋  New Chat"); nb.setCursor(Qt.PointingHandCursor); nb.setFixedHeight(36)
        nb.setStyleSheet("QPushButton{background:#151530;color:#6688ff;border:1px solid #22224a;border-radius:8px;font-size:13px;font-weight:600;margin:0 10px 10px;}QPushButton:hover{background:#1c1c40;color:#aabbff;}")
        nb.clicked.connect(self._new_chat); sbl.addWidget(nb)
        sep=QFrame(); sep.setFrameShape(QFrame.HLine); sep.setStyleSheet("color:#14142a;"); sbl.addWidget(sep)
        hl=QLabel("CONVERSATIONS"); hl.setStyleSheet("color:#2a2a55;font-size:10px;font-weight:700;padding:10px 16px 4px;letter-spacing:1px;"); sbl.addWidget(hl)
        self._sess_scroll=QScrollArea(); self._sess_scroll.setWidgetResizable(True)
        self._sess_scroll.setStyleSheet("border:none;background:transparent;")
        self._sess_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._sess_cont=QWidget(); self._sess_lay=QVBoxLayout(self._sess_cont)
        self._sess_lay.setContentsMargins(0,0,0,0); self._sess_lay.setSpacing(0); self._sess_lay.addStretch()
        self._sess_scroll.setWidget(self._sess_cont); sbl.addWidget(self._sess_scroll,1)
        self._att_lbl=QLabel("No files attached"); self._att_lbl.setWordWrap(True)
        self._att_lbl.setStyleSheet("color:#334455;font-size:10px;padding:6px 14px;font-style:italic;"); sbl.addWidget(self._att_lbl)
        rl.addWidget(sb)

        # Content
        ct=QWidget(); cl=QVBoxLayout(ct); cl.setContentsMargins(18,14,18,14); cl.setSpacing(10)
        self.hologram=HologramCore(); cl.addWidget(self.hologram)
        self.chat_display=QTextEdit(); self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("QTextEdit{background:#07070f;border:none;font-size:14px;color:#d0d0e8;padding:8px;}QScrollBar:vertical{background:#0a0a18;width:6px;border-radius:3px;}QScrollBar::handle:vertical{background:#22224a;border-radius:3px;}")
        cl.addWidget(self.chat_display,1)
        bs="QPushButton{background:#10102a;color:#7788bb;border:1px solid #1e1e3a;border-radius:8px;font-size:13px;padding:6px 14px;}QPushButton:hover{background:#181838;color:#aabbff;}QPushButton:disabled{color:#333355;border-color:#111122;}"
        tb=QHBoxLayout(); tb.setSpacing(8)
        self._ab=QPushButton("📎 Attach File"); self._ab.setCursor(Qt.PointingHandCursor); self._ab.setStyleSheet(bs); self._ab.clicked.connect(self._attach_file)
        self._sb2=QPushButton("📸 Screenshot"); self._sb2.setCursor(Qt.PointingHandCursor); self._sb2.setStyleSheet(bs); self._sb2.clicked.connect(self._take_screenshot)
        cb=QPushButton("🗑 Clear"); cb.setCursor(Qt.PointingHandCursor); cb.setStyleSheet(bs); cb.clicked.connect(self._clear_display)
        tb.addWidget(self._ab); tb.addWidget(self._sb2); tb.addWidget(cb); tb.addStretch(); cl.addLayout(tb)
        ir=QHBoxLayout(); ir.setSpacing(10)
        self.input_box=QLineEdit(); self.input_box.setPlaceholderText("Ask the Agent anything…"); self.input_box.setFixedHeight(48)
        self.input_box.setStyleSheet("QLineEdit{background:#10102a;border:1px solid #1e1e3a;border-radius:24px;padding-left:20px;font-size:14px;color:#e0e0f0;}QLineEdit:focus{border:1px solid #4466ff;}QLineEdit:disabled{color:#334455;}")
        self.send_btn=QPushButton("➤"); self.send_btn.setFixedSize(48,48); self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet("QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #3355ff,stop:1 #1133cc);border-radius:24px;font-size:18px;color:white;font-weight:bold;}QPushButton:hover{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #4466ff,stop:1 #2244ee);}QPushButton:pressed{background:#1122aa;}QPushButton:disabled{background:#1a1a2a;color:#333355;}")
        self.send_btn.clicked.connect(self.send_msg); self.input_box.returnPressed.connect(self.send_msg)
        ir.addWidget(self.input_box); ir.addWidget(self.send_btn); cl.addLayout(ir)
        rl.addWidget(ct,1)

    # Sessions
    def _mk_sid(self):
        import uuid; return str(uuid.uuid4())[:8]

    def _create_pending(self):
        sid=self._mk_sid(); ts=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        self._sessions[sid]={"title":"New Chat","ts":ts,"messages":[],"pinned":False}
        self._active_id=sid; self._pending_id=sid; self._render(sid)

    def _new_chat(self):
        self._flush_agent_turn()
        if not self._sessions.get(self._active_id,{}).get("messages"):
            self._render(self._active_id); return
        self._create_pending(); self._attached.clear(); self._upd_att()
        if self.process:
            try: self.process.stdin.write("new_chat\n"); self.process.stdin.flush()
            except Exception: pass

    def _commit_pending(self):
        if self._pending_id==self._active_id:
            self._pending_id=""; self._refresh_sb()

    def _load_session(self,sid):
        if sid==self._active_id: return
        self._flush_agent_turn()
        if self._pending_id and not self._sessions.get(self._pending_id,{}).get("messages"):
            del self._sessions[self._pending_id]; self._pending_id=""
        self._active_id=sid; self._refresh_sb(); self._render(sid)

    def _render(self,sid):
        self.chat_display.clear()
        msgs=self._sessions.get(sid,{}).get("messages",[])
        if not msgs:
            self.chat_display.append("<span style='color:#334466;font-size:13px;'>✨ New conversation — ask anything.</span><br>"); return
        for m in msgs: self._bubble(m["role"],m["html"])

    def _bubble(self,role,html):
        if role=="user":
            self.chat_display.append(f"<br><span style='color:#4477ff;font-weight:bold;'>👤 YOU:</span> <span style='color:#e0e0f0;'>{html}</span><br>")
        else:
            self.chat_display.append(f"<span style='color:#d0d0e8;'>{html}</span>")
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())

    def _save_msg(self,role,text,html):
        if self._active_id not in self._sessions: return
        sess=self._sessions[self._active_id]
        sess["messages"].append({"role":role,"text":text,"html":html})
        if role=="user" and sess["title"]=="New Chat":
            sess["title"]=text[:55]+("…" if len(text)>55 else "")
        if role=="user" and self._pending_id==self._active_id: self._commit_pending()
        else: self._refresh_sb()
        self._save_sess()

    def _flush_agent_turn(self):
        if self._agent_buf.strip(): self._save_msg("agent",self._agent_buf,self._agent_buf)
        self._agent_buf=""; self._in_agent_turn=False

    def _refresh_sb(self):
        while self._sess_lay.count()>1:
            item=self._sess_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        pinned=[(s,v) for s,v in self._sessions.items() if v.get("pinned") and v.get("messages") and s!=self._pending_id]
        unpinned=[(s,v) for s,v in reversed(list(self._sessions.items())) if not v.get("pinned") and v.get("messages") and s!=self._pending_id]
        for sid,sess in pinned+unpinned:
            row=SessionRow(sid,sess["title"],sess["ts"],pinned=sess.get("pinned",False),active=(sid==self._active_id))
            row.clicked_sig.connect(self._load_session); row.rename_sig.connect(self._rename)
            row.delete_sig.connect(self._delete); row.pin_sig.connect(self._pin); row.export_sig.connect(self._export)
            self._sess_lay.insertWidget(0,row)

    # Context menu actions
    def _rename(self,sid):
        sess=self._sessions.get(sid)
        if not sess: return
        t,ok=QInputDialog.getText(self,"Rename","New name:",text=sess["title"])
        if ok and t.strip(): sess["title"]=t.strip()[:60]; self._refresh_sb(); self._save_sess()

    def _delete(self,sid):
        t=self._sessions.get(sid,{}).get("title","this conversation")
        if QMessageBox.question(self,"Delete",f'Delete "{t}"?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes: return
        del self._sessions[sid]; self._save_sess()
        if self._active_id==sid:
            self._create_pending()
            if self.process:
                try: self.process.stdin.write("new_chat\n"); self.process.stdin.flush()
                except Exception: pass
        self._refresh_sb()

    def _pin(self,sid):
        sess=self._sessions.get(sid)
        if sess: sess["pinned"]=not sess.get("pinned",False); self._refresh_sb(); self._save_sess()

    def _export(self,sid):
        sess=self._sessions.get(sid)
        if not sess: return
        path,_=QFileDialog.getSaveFileName(self,"Export",f"{sess['title'][:40]}.txt","Text Files (*.txt)")
        if not path: return
        try:
            with open(path,"w",encoding="utf-8") as f:
                f.write(f"Conversation: {sess['title']}\nDate: {sess['ts']}\n{'─'*60}\n\n")
                for m in sess.get("messages",[]):
                    f.write(f"[{'YOU' if m['role']=='user' else 'AGENT'}]\n{m['text']}\n\n")
            self.chat_display.append(f"<span style='color:#00cc88;'>📤 Exported to {os.path.basename(path)}</span>")
        except Exception as e: self.chat_display.append(f"<span style='color:red;'>❌ {e}</span>")

    # Messaging
    def send_msg(self):
        msg=self.input_box.text().strip()
        if not msg or not self.process: return
        self.input_box.clear(); self._flush_agent_turn()
        self._bubble("user",msg); self._save_msg("user",msg,msg)
        try: self.process.stdin.write(msg+"\n"); self.process.stdin.flush()
        except Exception as e: self.chat_display.append(f"<span style='color:red;'>❌ {e}</span>")

    # Streaming
    def _on_char(self,ch):
        self.hologram.set_state("typing"); self._typing_timer.start(1800)
        self._in_agent_turn=True; self._agent_buf+=ch
        c=self.chat_display.textCursor(); c.movePosition(QTextCursor.End)
        self.chat_display.setTextCursor(c); self.chat_display.insertPlainText(ch)
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())
    def _agent_turn_ended(self): self._typing_timer.stop(); self.hologram.set_state("idle"); self._flush_agent_turn()
    def _on_stream_error(self,msg): self.hologram.set_state("idle"); self._flush_agent_turn(); self.chat_display.append(f"<span style='color:orange;'>⚠️ {msg}</span>")

    # Attach/Screenshot
    def _lock(self,ph):
        for w in (self.input_box,self.send_btn,self._ab,self._sb2): w.setEnabled(False)
        self.input_box.setPlaceholderText(ph)
    def _unlock(self):
        for w in (self.input_box,self.send_btn,self._ab,self._sb2): w.setEnabled(True)
        self.input_box.setPlaceholderText("Ask the Agent anything…"); self.input_box.setFocus()
    def _attach_file(self):
        paths,_=QFileDialog.getOpenFileNames(self,"Attach Files","","All Files (*);; Images (*.png *.jpg *.jpeg *.webp *.bmp);; Documents (*.pdf *.docx *.xlsx *.pptx *.txt);; Code (*.py *.cs *.cpp *.js *.ts *.html *.css *.json)")
        if not paths: return
        self._lock("⏳ Attaching…")
        for path in paths:
            self._attached.append(path)
            self.chat_display.append(f"<span style='color:#ffaa44;'>📎 Attaching: {os.path.basename(path)}</span>")
            if self.process:
                try: self.process.stdin.write(f"attach {path}\n"); self.process.stdin.flush()
                except Exception as e: self.chat_display.append(f"<span style='color:red;'>❌ {e}</span>")
        self._upd_att(); QTimer.singleShot(1500,self._att_ready)
    def _take_screenshot(self):
        base=os.path.dirname(sys.executable) if getattr(sys,"frozen",False) else os.path.dirname(os.path.abspath(__file__))
        path=os.path.join(base,"live_screen.png"); screen=QApplication.primaryScreen()
        if not screen: self.chat_display.append("<span style='color:red;'>❌ No screen.</span>"); return
        self.hide(); QTimer.singleShot(250,lambda: self._capture(screen,path))
    def _capture(self,screen,path):
        screen.grabWindow(0).save(path,"PNG"); self.show()
        self.chat_display.append("<span style='color:#00ccff;'>📸 Screenshot captured — attaching…</span>")
        self._lock("⏳ Attaching screenshot…")
        if self.process:
            try: self.process.stdin.write(f"attach {path}\n"); self.process.stdin.flush()
            except Exception as e: self.chat_display.append(f"<span style='color:red;'>❌ {e}</span>")
        self._attached.append(path); self._upd_att(); QTimer.singleShot(1500,self._att_ready)
    def _att_ready(self):
        self._unlock(); self.chat_display.append("<span style='color:#00cc88;'>✅ File ready — ask about it now</span><br>")
    def _upd_att(self):
        if not self._attached: self._att_lbl.setText("No files attached"); return
        names=[os.path.basename(p) for p in self._attached[-4:]]; extra=len(self._attached)-4
        self._att_lbl.setText("📎 "+"\n".join(names)+(f"\n+{extra} more" if extra>0 else ""))
    def _clear_display(self): self.chat_display.clear()

    # Persistence
    def _load_sessions(self):
        try:
            if os.path.exists(self._sess_file):
                with open(self._sess_file,encoding="utf-8") as f: self._sessions=json.load(f)
                for s in self._sessions.values(): s.setdefault("pinned",False)
        except Exception: self._sessions={}
    def _save_sess(self):
        try:
            saved={k:v for k,v in self._sessions.items() if v.get("messages")}
            if len(saved)>60:
                np=[k for k,v in saved.items() if not v.get("pinned")]
                for k in np[:-60]: del saved[k]
            with open(self._sess_file,"w",encoding="utf-8") as f: json.dump(saved,f,ensure_ascii=False,indent=2)
        except Exception: pass

    # Agent
    def _start_agent(self):
        base=os.path.dirname(sys.executable) if getattr(sys,"frozen",False) else os.path.dirname(os.path.abspath(__file__))
        ap=os.path.join(base,"agent.py")
        if not os.path.exists(ap): self.chat_display.append(f"<span style='color:red;'>❌ agent.py not found</span>"); return
        si=None
        if sys.platform=="win32": si=subprocess.STARTUPINFO(); si.dwFlags|=subprocess.STARTF_USESHOWWINDOW
        env=os.environ.copy(); env["PYTHONUNBUFFERED"]="1"
        try:
            self.process=subprocess.Popen([sys.executable,ap],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="ignore",bufsize=1,cwd=base,startupinfo=si,env=env)
            self.streamer=AgentStreamer(self.process); self.streamer.new_char.connect(self._on_char); self.streamer.error_sig.connect(self._on_stream_error); self.streamer.start()
        except Exception as e: self.chat_display.append(f"<span style='color:red;'>❌ {e}</span>")

    def closeEvent(self,event):
        self._flush_agent_turn(); self._save_sess()
        if self.streamer: self.streamer.stop()
        if self.process:  self.process.terminate()
        event.accept()


if __name__=="__main__":
    app=QApplication(sys.argv); app.setStyle("Fusion")
    win=ModernAgentGUI(); win.show(); sys.exit(app.exec())
