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
pending_attachments = [] # قائمة الملفات المعلقة

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
# 🎨 GUI LAYOUT & STYLING (MODERN CHATGPT STYLE)
# ===========================================

# 1. Main Chat Area (منطقة الشات)
# وضعناها هنا لأنها يجب أن تكون قبل الـ Footer
chat_area = ctk.CTkScrollableFrame(
    app,
    width=900,
    corner_radius=15,
    fg_color=CHAT_BG_COLOR
)
chat_area.pack(pady=10, padx=20, fill="both", expand=True)

# 2. Main Footer Container
# ده الفريم الكبير اللي شايل كل حاجة تحت
footer = ctk.CTkFrame(app, fg_color="transparent")
footer.pack(side="bottom", fill="x", padx=40, pady=(0, 25))

# 3. Status Bar (شريط الحالة صغير فوق)
status_frame = ctk.CTkFrame(footer, fg_color="transparent", height=20)
status_frame.pack(fill="x", pady=(0, 5))

# أيقونة الحالة (نقطة خضراء + كلمة Idle)
status_label = ctk.CTkLabel(
    status_frame, 
    text="● Idle", 
    font=("Segoe UI", 12, "bold"), 
    text_color="#00ff00"
)
status_label.pack(side="top", anchor="center")

# عدد ملفات الذاكرة (Context)
context_label = ctk.CTkLabel(
    footer, 
    text="Context: 0 files", 
    font=("Segoe UI", 10), 
    text_color="gray"
)
context_label.pack(pady=(0, 5))

# 4. Pending Files Area (شريط الملفات المرفقة)
# ده مخفي دلوقتي، هيظهر بس لما تختار ملفات
pending_frame = ctk.CTkScrollableFrame(
    footer, 
    fg_color="transparent", 
    orientation="horizontal", 
    height=45 # ارتفاع مناسب للـ Chips
)
# (سيتم عمل Pack له داخل دالة التحديث)

# 5. THE CAPSULE INPUT BAR (الكبسولة)
input_container = ctk.CTkFrame(
    footer, 
    fg_color="#2f2f2f",      # لون رمادي غامق زي ChatGPT
    corner_radius=25,        # تدويرة كبيرة
    border_width=1, 
    border_color="#444"      # حدود خفيفة
)
input_container.pack(fill="x", ipady=5)

# تعريف دالة Attach (نحتاجها قبل الزرار)
def attach_file():
    global pending_attachments
    file_paths = filedialog.askopenfilenames(title="Select files")
    if not file_paths: return

    for fp in file_paths:
        if fp not in pending_attachments:
            pending_attachments.append(fp)
    
    refresh_file_chips()

# زرار الإضافة (+)
attach_btn = ctk.CTkButton(
    input_container, 
    text="+", 
    width=40, 
    height=40, 
    fg_color="transparent", 
    hover_color="#404040", 
    text_color="#aaaaaa",
    font=("Arial", 24),
    corner_radius=20,
    command=attach_file
)
attach_btn.pack(side="left", padx=(10, 0))

# خانة الكتابة
input_box = ctk.CTkEntry(
    input_container, 
    placeholder_text="Ask anything...", 
    placeholder_text_color="#888",
    height=45, 
    font=("Segoe UI", 15),
    fg_color="transparent", 
    border_width=0, 
    text_color="white"
)
input_box.pack(side="left", fill="x", expand=True, padx=10)
# (سيتم ربط زر Enter لاحقًا بعد تعريف دالة send_command)

# زرار الإرسال (سهم)
send_btn = ctk.CTkButton(
    input_container, 
    text="➤", 
    width=40, 
    height=40, 
    fg_color="white",        # لون أبيض
    text_color="black",      # سهم أسود
    hover_color="#dddddd",
    corner_radius=20,        # دائري بالكامل
    font=("Segoe UI", 16, "bold"),
    # (سيتم وضع الأمر command لاحقًا)
)
send_btn.pack(side="right", padx=(0, 10))

# ===========================================
# 🔄 UI HELPER FUNCTIONS
# ===========================================

def remove_attachment(path):
    if path in pending_attachments:
        pending_attachments.remove(path)
        refresh_file_chips()

def refresh_file_chips():
    # 1. تنظيف القديم
    for widget in pending_frame.winfo_children():
        widget.destroy()

    # 2. إظهار/إخفاء الشريط
    if not pending_attachments:
        pending_frame.pack_forget()
    else:
        # يظهر فوق الكبسولة (Input Container)
        pending_frame.pack(fill="x", pady=(0, 10), before=input_container)

    # 3. رسم الزراير (Chips)
    for file_path in pending_attachments:
        name = os.path.basename(file_path)
        if len(name) > 20: name = name[:17] + "..."
        
        # كبسولة للملف
        chip = ctk.CTkFrame(pending_frame, fg_color="#3a3a3a", corner_radius=15)
        chip.pack(side="left", padx=5)
        
        # أيقونة + اسم
        icon = "🖼" if name.lower().endswith(('.png','.jpg','.jpeg')) else "📄"
        lbl = ctk.CTkLabel(chip, text=f"{icon} {name}", font=("Segoe UI", 11), text_color="#ddd")
        lbl.pack(side="left", padx=(10, 5), pady=5)
        
        # زرار حذف (x)
        btn = ctk.CTkButton(
            chip, 
            text="×", 
            width=20, 
            height=20, 
            fg_color="transparent", 
            hover_color="#555", 
            text_color="#ff5555",
            font=("Arial", 12, "bold"),
            command=lambda p=file_path: remove_attachment(p)
        )
        btn.pack(side="right", padx=(0, 5))

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
    ctk.CTkLabel(bubble,text=f"{sender}:",font=("Segoe UI",13,"bold")).pack(side="left",pady=8)
    ctk.CTkLabel(bubble,text=text,wraplength=500,justify="left",font=("Segoe UI",14)).pack(side="left",padx=(8,15),pady=8)

    app.update_idletasks()
    chat_area._parent_canvas.yview_moveto(1)

def add_bot_message(t):
    clean=t.replace("Agent:","").strip()
    if clean: add_bubble(clean,False)

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
# ATTACH LOGIC (UPDATED)
# ===========================================
def attach_file():
    global pending_attachments
    file_paths = filedialog.askopenfilenames(title="Select files")
    if not file_paths: return

    for fp in file_paths:
        if fp not in pending_attachments:
            pending_attachments.append(fp)
    
    refresh_file_chips() # تحديث واجهة الملفات

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
# SEND LOGIC (UPDATED)
# ===========================================

def send_command(event=None):
    global pending_attachments
    cmd = input_box.get().strip()

    # لو مفيش نص ومفيش ملفات، متبعتش حاجة
    if not cmd and not pending_attachments:
        return

    # 1. إظهار رسالة للمستخدم في الشات
    if cmd:
        add_user_message(cmd)
    elif pending_attachments:
        # لو باعت ملفات بس من غير كلام، بنكتب رسالة تلقائية إننا طلبنا تحليل
        count = len(pending_attachments)
        add_user_message(f"📂 Auto-Analyze Request ({count} files)")

    set_status("Thinking")
    input_box.delete(0, "end")

    if process:
        try:
            # 2. ابعت أوامر الـ attach لكل الملفات الأول
            # الـ Agent هيستقبلهم ويخزنهم في الذاكرة (Context)
            for fp in pending_attachments:
                process.stdin.write(f"attach {fp}\n")
            
            # 3. المنطق الذكي (Smart Trigger)
            if cmd:
                # الحالة الأولى: المستخدم كاتب أمر محدد
                process.stdin.write(cmd + "\n")
            else:
                # الحالة الثانية: المستخدم مبعتش كلام (سايبها فاضية)
                # بنبعت أمر عام "Analyze" والـ Agent هو اللي بيحدد الطريقة
                # سواء كان صورة (Vision) أو ملف نصي (Summarize/Explain)
                process.stdin.write("Analyze and describe the attached files in detail.\n")
            
            process.stdin.flush()
            
            # تنظيف القائمة والواجهة
            pending_attachments.clear()
            refresh_file_chips()
            
        except Exception as e:
            print(f"Error sending: {e}")

# تأكد من ربط زرار الإنتر
input_box.bind("<Return>", send_command)

# ربط زرار الإرسال والإنتر بدالة الإرسال
input_box.bind("<Return>", send_command)
send_btn.configure(command=send_command)

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