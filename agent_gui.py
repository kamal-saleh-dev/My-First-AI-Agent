import sys
import os
from tkinter import filedialog
import time
from PIL import ImageGrab
import glob

# ===========================================
# 🔥 FIX EXE LOOP
# ===========================================

import customtkinter as ctk
import subprocess
import threading
import tkinter as tk

# ===========================================
# ⚙️ MODERN & OLED SETTINGS
# ===========================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ألوان احترافية (Deep Black Style)
BG_COLOR = "#0b0b0b"        # أسود ملكي للخلفية الأساسية
CHAT_BG_COLOR = "#121212"   # رمادي غامق جداً لمنطقة الشات
USER_BUBBLE = "#1e88e5"     # أزرق زاهي لفقاعات المستخدم
BOT_BUBBLE = "#262626"      # رمادي متوسط لفقاعات الـ Agent
ACCENT_COLOR = "#00e676"    # أخضر نيون للحالة (Status)
BORDER_COLOR = "#333333"    # لون الحدود (Borders)

process = None
current_status = "Idle"
anim_step = 0
full_chat_history = ""
pending_attachments = [] 
is_screen_share_on = False  # حالة الشير سكرين

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

# 5. THE CAPSULE INPUT BAR
input_container = ctk.CTkFrame(
    footer, 
    fg_color="#1e1e1e",      # أفتح قليلاً من الخلفية عشان تبرز
    corner_radius=25,
    border_width=1, 
    border_color=BORDER_COLOR
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

is_screen_share_on = False

def toggle_screen_share():
    global is_screen_share_on
    is_screen_share_on = not is_screen_share_on
    
    if is_screen_share_on:
        screen_btn.configure(text="💻 (ON)", text_color="#00ff00") # أخضر شغال
        set_status("Screen Share Active")
    else:
        screen_btn.configure(text="💻 (OFF)", text_color="#aaaaaa") # رمادي مقفول
        set_status("Idle")

# زرار الشير سكرين
screen_btn = ctk.CTkButton(
    input_container, 
    text="💻 (OFF)", 
    width=60, 
    height=40, 
    fg_color="transparent", 
    hover_color="#404040", 
    text_color="#aaaaaa",
    font=("Segoe UI", 13, "bold"),
    corner_radius=20,
    command=toggle_screen_share
)
screen_btn.pack(side="left", padx=(5, 0))

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

# 2. زرار الإرسال ➢
send_btn = ctk.CTkButton(
    input_container, 
    text="➢", 
    width=40, 
    height=40, 
    fg_color=USER_BUBBLE, 
    text_color="white", 
    hover_color="#005f99", 
    corner_radius=20, 
    font=("Arial", 20, "bold"), 
    command=lambda: send_command()
)

# 🔥 السطر السحري اللي هيظهر الزرار
send_btn.pack(side="right", padx=(5, 10))

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
# STATUS LOGIC
# ===========================================

def set_status(s):
    global current_status, idle_timer
    current_status = s
    
    # لو دخل في التفكير، نلغي أي تايمر قديم عشان ميفصلش في النص
    if s == "Thinking" and idle_timer is not None:
        app.after_cancel(idle_timer)
        idle_timer = None

    if s == "Idle":
        status_label.configure(text_color="#00ff00")
    else:
        status_label.configure(text_color="#ffcc00")
    app.update_idletasks()

def animate_status():
    global anim_step
    anim_step += 1
    if current_status == "Idle":
        status_label.configure(text=f"● Idle{' .'*(anim_step%3)}")
    elif current_status == "Running":
        frames=["Running ◐","Running ◓","Running ◑","Running ◒"]
        status_label.configure(text=frames[anim_step%4])
    elif current_status == "Thinking":
        status_label.configure(text=f"● Thinking{' .'*(anim_step%4)}")
    app.after(400, animate_status)

# ===========================================
# 🚦 QUEUE & ANIMATION SYSTEM (نظام الطابور والكتابة)
# ===========================================
msg_queue = []
is_typing = False

def process_queue():
    global is_typing, msg_queue
    # لو فيه رسايل مستنية ومفيش حاجة بتكتب دلوقتي، ابدأ اللي عليها الدور
    if msg_queue and not is_typing:
        next_msg = msg_queue.pop(0)
        show_bubble_sequentially(next_msg['text'], next_msg['is_user'])

def show_bubble_sequentially(text, is_user):
    global is_typing, full_chat_history
    is_typing = True
    
    sender = "YOU" if is_user else "AGENT"
    icon = "👤" if is_user else "🤖"
    full_chat_history += f"[{sender}]: {text}\n"

    color = USER_BUBBLE if is_user else BOT_BUBBLE
    align = "e" if is_user else "w"

    wrapper = ctk.CTkFrame(chat_area, fg_color="transparent")
    wrapper.pack(fill="x", pady=6, padx=15)

    # تعديل شكل الفقاعات لتكون أنعم
    bubble = ctk.CTkFrame(wrapper, fg_color=color, corner_radius=15) # تدويرة أقل شوية بتبان احترافية أكتر
    bubble.pack(anchor=align)
    # إضافة حدود خفيفة لفقاعة الـ Agent عشان تبان على الخلفية السودة
    if not is_user:
        bubble.configure(border_width=1, border_color="#333")

    ctk.CTkLabel(bubble, text=icon).pack(side="left", padx=(12,5), pady=8)
    ctk.CTkLabel(bubble, text=f"{sender}:", font=("Segoe UI", 13, "bold")).pack(side="left", pady=8)
    
    msg_label = ctk.CTkLabel(bubble, text="", wraplength=500, justify="left", font=("Segoe UI", 14))
    msg_label.pack(side="left", padx=(8,15), pady=8)

    # تشغيل تأثير الكتابة
    type_text_effect(msg_label, text, 0)

def type_text_effect(label, text, index=0):
    global is_typing
    if index < len(text):
        current_text = label.cget("text")
        label.configure(text=current_text + text[index])
        
        # سرعة الكتابة (20 مللي ثانية)
        app.after(20, type_text_effect, label, text, index + 1)
        
        if text[index] == " " or index == len(text)-1:
            chat_area._parent_canvas.yview_moveto(1)
    else:
        # 🔥 هنا السر: بنقول للسيستم أنا خلصت كتابة البالونة دي
        is_typing = False
        chat_area._parent_canvas.yview_moveto(1)
        # استدعاء الرسالة اللي بعدها من الطابور بعد 100 مللي ثانية
        app.after(100, process_queue)

def add_bubble(text, is_user=False):
    global msg_queue
    # بنضيف الرسالة للطابور بدل ما نعرضها فوراً
    msg_queue.append({'text': text, 'is_user': is_user})
    process_queue()

def add_bot_message(t):
    clean=t.replace("Agent:","").strip()
    if clean: add_bubble(clean,False)

def add_user_message(t):
    add_bubble(t,True)

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

idle_timer = None

def make_idle():
    global active_bot_label
    set_status("Idle")
    
    # 🔥 أول ما يخلص تفكير وكتابة، نقص أي سطور فاضية (Enters) في آخر البالونة
    if active_bot_label:
        clean_text = active_bot_label.cget("text").strip()
        active_bot_label.configure(text=clean_text)

# ===========================================
# 🔥 STREAMING ENGINE (محرك الكتابة الحية)
# ===========================================
is_streaming_mode = False
active_bot_label = None

def start_new_bot_bubble():
    global active_bot_label, full_chat_history
    wrapper = ctk.CTkFrame(chat_area, fg_color="transparent")
    wrapper.pack(fill="x", pady=6, padx=15)

    bubble = ctk.CTkFrame(wrapper, fg_color=BOT_BUBBLE, corner_radius=20)
    bubble.pack(anchor="w")

    ctk.CTkLabel(bubble, text="🤖").pack(side="left", padx=(12,5), pady=8)
    ctk.CTkLabel(bubble, text="AGENT:", font=("Segoe UI", 13, "bold")).pack(side="left", pady=8)
    
    active_bot_label = ctk.CTkLabel(bubble, text="", wraplength=500, justify="left", font=("Segoe UI", 14))
    active_bot_label.pack(side="left", padx=(8,15), pady=8)
    
    full_chat_history += "[AGENT]: "

def stream_to_bubble(text_chunk):
    global active_bot_label, full_chat_history
    if active_bot_label:
        current = active_bot_label.cget("text")
        active_bot_label.configure(text=current + text_chunk)
        full_chat_history += text_chunk
        
        if text_chunk in [" ", "\n"]:
            chat_area._parent_canvas.yview_moveto(1)

def reset_idle_timer():
    global idle_timer
    # 🔥 أول ما الموديل يبدأ ينطق حرف، نكسر التفكير ونقلبه Running فوراً
    set_status("Running")
    
    # ونجدد التايمر، بحيث أول ما يسكت ثانيتين يرجع Idle
    if idle_timer is not None:
        app.after_cancel(idle_timer)
    idle_timer = app.after(2000, make_idle)

def process_line(line):
    clean_lower = line.lower()
    
    # لو لقى كلمات التفكير، يقلب الشريط Thinking
    if any(word in clean_lower for word in ["analyzing", "comparing", "thinking", "reading", "processing", "swapping", "loading"]):
        set_status("Thinking")
        
    update_context_counter(line)
    
    # إخفاء رسايل الكواليس من الشات
    if not any(icon in line for icon in ["💭", "🧠", "👀", "⏳", "🤖"]):
        add_bot_message(line)
    
    # جوا دالة قراءة السطور في agent_gui.py
    if "🏁 Done." in line:
        app.after(100, make_idle)
        return # 🔥 الـ return دي هي اللي هتمنع الكلمة إنها تنزل في الشات

def read_output():
    global process, is_streaming_mode, is_typing, msg_queue
    
    buffer = ""
    try:
        while True:
            if process is None: break
            
            char = process.stdout.read(1)
            if not char: break
            
            buffer += char
            
            if not is_streaming_mode:
                if char == '\n':
                    line = buffer.strip()
                    buffer = ""
                    if line:
                        app.after(0, lambda l=line: process_line(l))
                else:
                    if "🤖 Agent:" in buffer:
                        # 🔥 الانتظار لحد ما كل بالونات النظام تخلص كتابة حرف حرف
                        while is_typing or msg_queue:
                            time.sleep(0.1) 
                        
                        is_streaming_mode = True
                        buffer = buffer.split("🤖 Agent:")[1]
                        app.after(0, start_new_bot_bubble)
                        if buffer:
                            app.after(0, lambda c=buffer: stream_to_bubble(c))
                        buffer = ""
            else:
                app.after(0, lambda c=char: stream_to_bubble(c))
                buffer = ""
                app.after(0, reset_idle_timer)
                
                # سرعة الـ Streaming للإجابة النهائية
                time.sleep(0.02)
                
    except Exception as e:
        print("Read output error:", e)

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
        add_bot_message("Hello! I'm ready.")

        # 🔥 Sync context counter on startup
        try:
            import json
            context_file = os.path.join(base_dir, "project_context.json")
            if os.path.exists(context_file):
                with open(context_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    context_label.configure(text=f"🧠 Context: {len(data)} files")
        except:
            pass

        threading.Thread(target=read_output,daemon=True).start()
    except Exception as e:
        add_bot_message(f"Error starting agent: {e}")

# ===========================================
# SEND LOGIC (UPDATED)
# ===========================================

def _send_to_agent(cmd, files):
    global pending_attachments

    if process:
        try:
            # attach files first
            for fp in files:
                process.stdin.write(f"attach {fp}\n")

            # send command
            if cmd:
                process.stdin.write(cmd + "\n")
            else:
                process.stdin.write("Analyze and describe the attached files in detail.\n")

            process.stdin.flush()

        except Exception as e:
            print("Error sending:", e)

def send_command(event=None):
    global pending_attachments, is_streaming_mode, is_screen_share_on
    cmd = input_box.get().strip()

    if not cmd and not pending_attachments and not is_screen_share_on:
        return

    is_streaming_mode = False 

    if cmd:
        add_user_message(cmd)
    elif pending_attachments:
        count = len(pending_attachments)
        add_user_message(f"📂 Auto-Analyze Request ({count} files)")

    set_status("Thinking") 
    input_box.delete(0, "end")
    app.update_idletasks()

    files_copy = pending_attachments.copy()

    ## 🔥 لو الشير سكرين شغال، صور الشاشة باسم جديد وابعتها!
    if is_screen_share_on:
        app.iconify() 
        app.update()
        time.sleep(0.2) 
        
        # مسح أي سكرين شوت قديمة من الهارد عشان منسحمش مساحتك
        for old_file in glob.glob("live_screen_*.jpg"):
            try: os.remove(old_file)
            except: pass
            
        screen = ImageGrab.grab()
        # 🔥 اسم جديد بالثانية عشان نكسر الـ Cache بتاع الموديل
        save_path = os.path.join(os.getcwd(), f"live_screen_{int(time.time())}.jpg")
        screen.save(save_path, quality=100)
        
        app.deiconify() 
        files_copy.append(save_path)

    threading.Thread(
        target=_send_to_agent,
        args=(cmd, files_copy),
        daemon=True
    ).start()

    pending_attachments.clear()
    refresh_file_chips()

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
# ربط زرار Enter بالإرسال
input_box.bind("<Return>", send_command)
app.mainloop()
