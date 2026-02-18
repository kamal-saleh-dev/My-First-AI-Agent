import sys
import os
from tkinter import filedialog

# ===========================================
# 🔥 FIX EXE LOOP
# ===========================================
if len(sys.argv) > 1 and sys.argv[1] == "--worker":
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    import agent 
    sys.exit()

import customtkinter as ctk
import subprocess
import threading
import tkinter as tk

# ===========================================
# ⚙️ SETTINGS
# ===========================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG_COLOR = "#1e1e1e"
CHAT_BG_COLOR = "#121212"
USER_BUBBLE = "#007acc"
BOT_BUBBLE = "#2d2d2d"

process = None
current_status = "Idle"
anim_step = 0
full_chat_history = ""
pending_attachments = []

# ===========================================
# WINDOW SETUP
# ===========================================

app = ctk.CTk(fg_color=BG_COLOR)
app.geometry("950x700")
app.title("AI Agent")

# 1. HEADER (TOP)
header = ctk.CTkFrame(app, fg_color="transparent")
header.pack(pady=(15,10), fill="x", padx=20, side="top")

title = ctk.CTkLabel(
    header,
    text="🤖 AI Agent",
    font=("Segoe UI",22,"bold")
)
title.pack(side="left")

# ===========================================
# COPY HISTORY
# ===========================================

def copy_to_clipboard(text):
    app.clipboard_clear()
    app.clipboard_append(text)
    app.update()

def copy_all_history():
    copy_to_clipboard(full_chat_history)
    copy_btn.configure(text="Copied! ✅", fg_color="green")
    app.after(2000, lambda:
        copy_btn.configure(text="Copy History 📋",
                           fg_color=["#3B8ED0","#1F6AA5"])
    )

copy_btn = ctk.CTkButton(
    header,
    text="Copy History 📋",
    width=120,
    height=30,
    command=copy_all_history
)
copy_btn.pack(side="right")

# ===========================================
# FOOTER CONTAINER (BOTTOM)
# ===========================================
# ده حاوية لكل حاجة تحت (الحالة + الملفات + الكتابة)
footer = ctk.CTkFrame(app, fg_color="transparent")
footer.pack(side="bottom", fill="x", padx=20, pady=(0,20))

# ===========================================
# CHAT AREA (MIDDLE)
# ===========================================
# الشات بياخد كل المساحة المتاحة بين الهيدر والفوتر
chat_area = ctk.CTkScrollableFrame(
    app,
    width=900,
    corner_radius=15,
    fg_color=CHAT_BG_COLOR
)
chat_area.pack(pady=10, padx=20, fill="both", expand=True)

# ===========================================
# STATUS & CONTEXT (INSIDE FOOTER - TOP)
# ===========================================

status_frame = ctk.CTkFrame(footer, fg_color="transparent")
status_frame.pack(fill="x", pady=(5,5))

status_label = ctk.CTkLabel(
    status_frame,
    text="● Idle",
    font=("Segoe UI",12,"bold"),
    text_color="#00ff00"
)
status_label.pack(side="top")

context_label = ctk.CTkLabel(
    status_frame,
    text="🧠 Context: 0 files",
    font=("Segoe UI",11),
    text_color="gray"
)
context_label.pack(side="top")

pending_label = ctk.CTkLabel(
    status_frame,
    text="", # فاضي في البداية
    font=("Segoe UI",11),
    text_color="#ffaa00"
)
pending_label.pack(side="top")

# ===========================================
# INPUT AREA (INSIDE FOOTER - BOTTOM)
# ===========================================

input_frame = ctk.CTkFrame(footer, fg_color="transparent")
input_frame.pack(fill="x", pady=(5,0))

input_box = ctk.CTkEntry(
    input_frame,
    placeholder_text="Type command...",
    height=45,
    font=("Segoe UI",14),
    corner_radius=22
)
input_box.pack(side="left", fill="x", expand=True, padx=(0,10))

attach_btn = ctk.CTkButton(
    input_frame,
    text="📎",
    width=50,
    height=45,
    fg_color="#444",
    command=lambda: attach_file() # Placeholder function call
)
attach_btn.pack(side="right", padx=(0,5))

send_btn = ctk.CTkButton(
    input_frame,
    text="Send",
    width=80,
    height=45,
    fg_color=USER_BUBBLE,
    command=lambda: send_command()
)
send_btn.pack(side="right")

# ===========================================
# STATUS LOGIC
# ===========================================

def set_status(s):
    global current_status
    current_status = s
    if s=="Idle":
        status_label.configure(text_color="#00ff00")
    else:
        status_label.configure(text_color="#ffcc00")

def animate_status():
    global anim_step
    anim_step += 1

    if current_status=="Idle":
        status_label.configure(text=f"● Idle{' .'*(anim_step%3)}")
    elif current_status=="Running":
        frames=["Running ◐","Running ◓","Running ◑","Running ◒"]
        status_label.configure(text=frames[anim_step%4])
    elif current_status=="Thinking":
        status_label.configure(text=f"● Thinking{' .'*(anim_step%4)}")

    app.after(400,animate_status)

# ===========================================
# BUBBLES
# ===========================================

def add_bubble(text,is_user=False):

    global full_chat_history

    sender = "YOU" if is_user else "AGENT"
    icon = "👤" if is_user else "🤖"

    full_chat_history += f"[{sender}]: {text}\n"

    color = USER_BUBBLE if is_user else BOT_BUBBLE
    align = "e" if is_user else "w"

    wrapper = ctk.CTkFrame(chat_area, fg_color="transparent")
    wrapper.pack(fill="x", pady=6, padx=15)

    bubble = ctk.CTkFrame(wrapper, fg_color=color, corner_radius=20)
    bubble.pack(anchor=align)

    ctk.CTkLabel(bubble,text=icon).pack(side="left",padx=(12,5),pady=8)

    ctk.CTkLabel(
        bubble,
        text=f"{sender}:",
        font=("Segoe UI",13,"bold")
    ).pack(side="left",pady=8)

    ctk.CTkLabel(
        bubble,
        text=text,
        wraplength=500,
        justify="left",
        font=("Segoe UI",14)
    ).pack(side="left",padx=(8,15),pady=8)

    app.update_idletasks()
    # Scroll to bottom
    chat_area._parent_canvas.yview_moveto(1)

def add_bot_message(t):
    clean=t.replace("Agent:","").strip()
    if clean:
        add_bubble(clean,False)

def add_user_message(t):
    add_bubble(t,True)

def update_context_counter(text):
    if "Loaded project context" in text:
        try:
            num = text.split("(")[1].split("files")[0].strip()
            context_label.configure(text=f"🧠 Context: {num} files")
        except: pass

    if "Added to project context" in text:
        try:
            num = text.split("(")[1].split("files")[0].strip()
            context_label.configure(text=f"🧠 Context: {num} files")
        except: pass

    if "Project context cleared" in text:
        context_label.configure(text="🧠 Context: 0 files")

# ===========================================
# ATTACH LOGIC
# ===========================================
def attach_file():
    global pending_attachments
    file_paths = filedialog.askopenfilenames(title="Select files")
    if not file_paths: return

    for fp in file_paths:
        if fp not in pending_attachments:
            pending_attachments.append(fp)
    
    pending_label.configure(text=f"📎 Pending: {len(pending_attachments)} files")

# ===========================================
# AGENT LOGIC
# ===========================================

def read_output():
    while True:
        if process is None: break
        try:
            line=process.stdout.readline()
            if not line: break
            clean=line.strip()
            if clean:
                app.after(0,lambda t=clean:add_bot_message(t))
                app.after(0,lambda t=clean:update_context_counter(t))
                app.after(0,lambda:set_status("Running"))
                app.after(2000,lambda:set_status("Idle"))
        except: break

def start_agent():
    global process
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    if getattr(sys, 'frozen', False):
        cmd = [sys.executable, "--worker"]
    else:
        agent_path = os.path.join(base_dir, "agent.py")
        cmd = [sys.executable, agent_path]

    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="ignore",
            bufsize=1,
            cwd=base_dir,
            startupinfo=startupinfo
        )
        add_bot_message("Hello! System ready.")
        threading.Thread(target=read_output,daemon=True).start()
    except Exception as e:
        add_bot_message(f"Error starting agent: {e}")

# ===========================================
# SEND LOGIC
# ===========================================

def send_command(event=None):
    global pending_attachments
    cmd=input_box.get().strip()

    if not cmd and not pending_attachments:
        return

    if cmd: add_user_message(cmd)
    set_status("Thinking")
    input_box.delete(0,"end")

    if process:
        try:
            if cmd: process.stdin.write(cmd+"\n")
            for fp in pending_attachments:
                process.stdin.write(f"attach {fp}\n")
            
            process.stdin.flush()
            pending_attachments.clear()
            pending_label.configure(text="") # Clear pending label
        except: pass

input_box.bind("<Return>",send_command)

# ===========================================
# SHORTCUT FIX
# ===========================================

real_entry = input_box._entry

def perform_select_all(event=None):
    real_entry.select_range(0,"end")
    real_entry.icursor("end")
def perform_copy(event=None): real_entry.event_generate("<<Copy>>")
def perform_paste(event=None): real_entry.event_generate("<<Paste>>")
def perform_cut(event=None): real_entry.event_generate("<<Cut>>")

def key_handler(event):
    if not (event.state & 0x4): return
    code = event.keycode
    if code == 65: perform_select_all(); return "break"
    elif code == 67: perform_copy(); return "break"
    elif code == 86: perform_paste(); return "break"
    elif code == 88: perform_cut(); return "break"

real_entry.bind("<Key>", key_handler)

def show_input_menu(event):
    menu=tk.Menu(app,tearoff=0)
    menu.add_command(label="Cut",command=perform_cut)
    menu.add_command(label="Copy",command=perform_copy)
    menu.add_command(label="Paste",command=perform_paste)
    menu.add_command(label="Select All",command=perform_select_all)
    menu.tk_popup(event.x_root,event.y_root)

real_entry.bind("<Button-3>",show_input_menu)

# ===========================================
# STARTUP
# ===========================================

def on_closing():
    if process: process.terminate()
    app.destroy()

app.protocol("WM_DELETE_WINDOW",on_closing)
app.after(1000,start_agent)
animate_status()
app.mainloop()