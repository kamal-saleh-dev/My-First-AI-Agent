import ollama
import os
import subprocess
import shutil
from duckduckgo_search import DDGS
import sys
import io
from pypdf import PdfReader
from docx import Document
import openpyxl
from pptx import Presentation
import pytesseract
from PIL import ImageEnhance, ImageFilter
import json
import re
import cv2
import math

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.stdin.reconfigure(encoding="utf-8") # 🔥 السطر ده هو اللي هيحل مشكلة الرموز الغريبة في الإدخال!

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, "agent_memory.txt")
CONTEXT_FILE = os.path.join(BASE_DIR, "project_context.json")

# ================= PROJECT CONTEXT =================
project_context = []

last_user_input = ""

active_intent = "default"

# ================= MODE =================

def detect_mode(user):
    t = user.lower()
    if t.startswith("build"):
        return "PROJECT"
    if t == "run":
        return "RUN"
    if t.startswith("delete") or t.startswith("remove"):
        return "DELETE"
    if "job" in t:
        return "JOB"
    if t.startswith("attach"):
        return "ATTACH"
    if "clear" in t:
        return "CLEAR"
    return "CHAT"


# ================= MEMORY =================

def save_last_project(path):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        f.write(path)

def load_last_project():
    if not os.path.exists(MEMORY_FILE):
        return None
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()

# ================= CONTEXT MEMORY =================

def save_project_context():
    try:
        with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
            json.dump(project_context, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("⚠ Context save error:", e)


def load_project_context():
    global project_context

    if not os.path.exists(CONTEXT_FILE):
        return

    try:
        with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
            project_context = json.load(f)

        print(f"🧠 Loaded project context ({len(project_context)} files)")

    except Exception as e:
        print("⚠ Context load error:", e)

# ================= HELPERS =================

def is_valid_path(name):
    invalid = ["*", "?", "<", ">", "|", "\""]
    for c in invalid:
        if c in name:
            return False
    return True

def clean_line(line):
    line = line.strip()
    if not line: return None
    if "```" in line: return None
    if ":" in line: return None
    if line.startswith("-") or line.startswith("*"): return None
    if "Here is" in line or "structure" in line: return None # فلترة إضافية
    if not is_valid_path(line): return None
    return line


# ================= BUILD =================

def build_structure(task):
    print("🔨 Designing structure...")
    r = ollama.chat(
        model="llama3",
        messages=[{
            "role":"user",
            "content":f"Return ONLY python project structure for {task}. List files and folders line by line. NO explanation."
        }]
    )

    lines = r["message"]["content"].split("\n")
    files = []

    for raw in lines:
        line = clean_line(raw)
        if not line: continue

        try:
            if line.endswith("/") or line.endswith("\\"):
                os.makedirs(line, exist_ok=True)
                print("📁 Folder:", line)
            else:
                folder = os.path.dirname(line)
                if folder:
                    os.makedirs(folder, exist_ok=True)
                
                # إنشاء ملف فارغ
                with open(line, "w", encoding="utf-8") as f:
                    f.write("")
                
                files.append(line)
                print("📄 File:", line)

        except Exception as e:
            print(f"⚠ Skipped bad path: {line} ({e})")

    # لو مفيش ملفات اتعملت، نعمل ملف رئيسي اجباري
    if len(files) == 0:
        with open("main.py", "w", encoding="utf-8") as f:
            f.write("")
        files.append("main.py")

    return files


# ================= GENERATE =================

def generate_code(files, task):
    for file in files:
        print(f"⚙ Generating code for: {file}...")
        
        prompt = f"Write ONLY python code for {file} in {task}. NO markdown blocks. NO explanation."
        
        r = ollama.chat(
            model="llama3",
            messages=[{"role":"user", "content": prompt}]
        )

        code = r["message"]["content"]
        # تنظيف إضافي للكود
        code = code.replace("```python", "").replace("```", "")
        if code.strip().startswith("Here is"): # لو الذكاء الاصطناعي رغي
            code = "# Generated code\n" + code.split("\n", 1)[1]

        with open(file, "w", encoding="utf-8") as f:
            f.write(code)
        
        print(f"✅ Written: {file}")


# ================= RUN =================

def run_python(file_path):
    print(f"\n🚀 Running: {file_path}")
    folder = os.path.dirname(file_path)
    script = os.path.basename(file_path)

    try:
        subprocess.run(
            [sys.executable, script], # استخدام بايثون الحالي
            timeout=15, # وقت أطول للمدخلات
            cwd=folder
        )
    except subprocess.TimeoutExpired:
        print("⚠ Program timed out (loop or waiting for input).")
    except Exception as e:
        print(f"❌ Run Error: {e}")


# ================= DELETE =================

def delete_tool(task):
    name = task.replace("delete", "").replace("remove", "").strip()
    
    # محاولة الحذف من المسار الحالي
    target = os.path.abspath(name)
    
    if os.path.exists(target):
        try:
            shutil.rmtree(target)
            print(f"🗑️ Deleted: {target}")
            
            # تنظيف الذاكرة
            last = load_last_project()
            if last and name in last:
                if os.path.exists(MEMORY_FILE):
                    os.remove(MEMORY_FILE)
        except Exception as e:
            print(f"❌ Error deleting: {e}")
    else:
        print(f"❌ Folder '{name}' not found.")


# ================= PROJECT =================

def project_tool(task):
    folder_name = task.replace("build", "").strip().replace(" ", "_").lower()
    if not folder_name: folder_name = "project"

    # إنشاء المشروع في المكان الحالي اللي اليوزر واقف فيه
    project_path = os.path.join(os.getcwd(), folder_name)
    
    if os.path.exists(project_path):
        print(f"⚠ Folder '{folder_name}' already exists. Updating inside it.")
    
    os.makedirs(project_path, exist_ok=True)
    print(f"📁 Project Path: {project_path}")

    cwd = os.getcwd()
    os.chdir(project_path)

    files = build_structure(task)
    generate_code(files, task)

    # اختيار ملف التشغيل بذكاء
    chosen = None
    priority = ["main.py", "app.py", "run.py", f"{folder_name}.py"]
    
    for p in priority:
        if p in files:
            chosen = p
            break
            
    if not chosen and files:
        chosen = files[0]

    if chosen:
        abs_path = os.path.abspath(chosen)
        save_last_project(abs_path)
        
        # العودة للمسار الأصلي قبل التشغيل لتجنب الأخطاء
        os.chdir(cwd)
        run_python(abs_path)
        print("🔥 Project completed.")
    else:
        print("❌ No files generated to run.")
        os.chdir(cwd)

# ================= JOB =================

def job_tool(task):
    print(f"🔎 Searching jobs for: {task}...")
    try:
        results = DDGS().text(f"{task} jobs", max_results=3)
        if not results:
            print("No jobs found.")
        for r in results:
            print(f"\n📌 {r['title']}")
            print(f"🔗 {r['href']}")
    except Exception as e:
        print(f"Error searching jobs: {e}")

# ================= CHAT (FULLY AUTONOMOUS) =================

def self_correct(draft_response, user_query):
    print("🧠 Reflection Layer: Reviewing and polishing the response...")
    
    # رسالة تظهر وقت الـ (Idle) عشان تفهم إن التأخير ده بسبب تحميل الموديل
    print("⏳ Swapping models in memory (Loading Llama 3)...", flush=True) 
    
    prompt = f"""You are a professional Content Editor. You are reviewing a draft analysis of multiple images.
    
    USER QUERY: "{user_query}"
    DRAFT ANALYSIS: "{draft_response}"

    YOUR STRICT MISSION:
    1. Clean up the language and make it professional.
    2. Keep the comparison between images as provided in the draft.
    3. If the draft contains descriptions of images, DO NOT say you cannot see them. Trust the draft.
    4. NEVER apologize or say "I am an AI" or "I have limitations". 
    5. Just return the polished, final version of the analysis.

    FINAL OUTPUT ONLY. NO INTRODUCTIONS."""
    
    try:
        # 🔥 تفعيل خاصية الـ Streaming
        stream = ollama.chat(model="llama3", messages=[{"role": "user", "content": prompt}], stream=True)
        
        # بنطبع البداية ونجبر الشاشة تطلعها فوراً
        sys.stdout.write("\n🤖 Agent: ")
        sys.stdout.flush()
        
        final_reply = ""
        for chunk in stream:
            word = chunk['message']['content']
            # بنكتب الكلمة ونجبر الشاشة تعرضها في نفس اللحظة (غصب عن التيرمنال)
            sys.stdout.write(word)
            sys.stdout.flush()
            final_reply += word
            
        sys.stdout.write("\n\n")
        sys.stdout.flush()
        
        return final_reply
        
    except Exception as e:
        print(f"\n⚠️ Reflection failed: {e}")
        return draft_response

def chat_tool(task):
    global active_intent
    
    if task:
        task = task.strip()
    
    # تحويل رسالة النظام الافتراضية لطلب فارغ
    if task == "Analyze and describe the attached files in detail.":
        task = ""

    # =========================================================
    # 🧠 NO AUTO-ANALYZE (وضع الانتظار والرسالة المجمعة)
    # =========================================================
    if not task:
        count = len(project_context)
        file_word = "file" if count == 1 else "files"
        
        # 🔥 السطر ده هيطبع مرة واحدة بس بعد ما كل الملفات تترفع
        print(f"📎 Successfully attached {count} {file_word} to project context!")
        
        if count >= 2:
            print("Tell me what you want to do with them (e.g., compare, summarize).")
        else:
            print("Ask a specific question about this file.")
            
        active_intent = "default"
        return

    # =========================================================
    # 🤖 AUTONOMOUS EXECUTION (التنفيذ المستقل)
    # =========================================================
    
    # 1. تشغيل طبقة اتخاذ القرار (المرحلة 1)
    intent = active_intent
    
    # 2. تشغيل طبقة اختيار الملفات (المرحلة 2)
    working_context = select_relevant_files(task, project_context)
    
    # فصل الصور والفيديوهات والنصوص من الملفات (اللي اتفلترت بس)
    images = [item["path"] for item in working_context if item["type"] == "image"]
    videos = [item["path"] for item in working_context if item["type"] == "video"] # 🔥 السطر الجديد أهو
    text_context = ""
    
    for item in working_context:
        if item["type"] not in ["image", "video"]: # 🔥 الشرط الجديد أهو
            text_context += f"\n--- File: {os.path.basename(item['path'])} ---\n"
            if "data" in item:
                text_context += json.dumps(item["data"])
            else:
                try:
                    with open(item["path"], "r", encoding="utf-8", errors="ignore") as f:
                        text_context += f.read(1500)
                except:
                    pass

    # تحديد الموديل بناءً على الملفات المطلوبة
    model_name = "llava" if images else "llama3"
    
    # تجهيز تقرير سريع عن اللي الموديل بيفكر فيه حالياً
    status_parts = []
    if images: status_parts.append(f"{len(images)} images")
    if videos: status_parts.append(f"{len(videos)} videos")
    
    # حساب الملفات اللي مش صور ولا فيديوهات (زي الورد والأكسيل والكود)
    other_files_count = len(working_context) - len(images) - len(videos)
    if other_files_count > 0:
        status_parts.append(f"{other_files_count} text/data files")

    # لو فيه أي حاجة، يطبعهم في سطر واحد شيك
    if status_parts:
        report = " and ".join(status_parts)
        print(f"🤔 Thinking about {report}...")

    # 3. توجيه الذكاء الاصطناعي بناءً على النية اللي اكتشفها
    if intent == "compare":
        if videos:
            # لو الملفات فيها فيديوهات
            final_prompt = """You are an expert video analyst. I have attached MULTIPLE videos (or extracted video frames). 
                            You MUST look at ALL of them. Do NOT ignore any video.
                            Please structure your response exactly like this:
                            - Video 1: [Brief description of the first video's content and action]
                            - Video 2: [Brief description of the second video's content and action]
                            - Differences & Similarities: [Explicitly compare their events, subjects, or visuals]"""

        elif images:
                    # 🔥 بناء هيكل الوصف ديناميكياً على حسب عدد الصور
            image_descriptions = "\n".join([f"- Image {i+1}: [Brief description of image {i+1}]" for i in range(len(images))])
            
            final_prompt = f"""You are an expert visual analyst. I have attached {len(images)} images. 
                            You MUST look at ALL {len(images)} of them. Do NOT ignore any image.
                            Please structure your response exactly like this:
                            {image_descriptions}
                            - Differences & Similarities: [Explicitly compare all {len(images)} images in detail]"""

        else:
                                        # لو الملفات نصوص/أكواد بس
            final_prompt = """You are an expert data analyst. I have attached MULTIPLE text/code files. 
                            You MUST read ALL of them. Do NOT ignore any file.
                            Please structure your response exactly like this:
                            - File 1: [Brief summary of the first file's content/purpose]
                            - File 2: [Brief summary of the second file's content/purpose]
                            - Differences & Similarities: [Explicitly compare their contents, logic, or structure]"""

    elif intent == "summarize":
        final_prompt = "You are an expert summarizer. Provide a concise, highly accurate summary of the provided files."
    elif intent == "detect_issues":
        final_prompt = "You are an expert debugger and reviewer. Analyze the provided files to find any bugs, errors, or issues."
    else:
        # لو سؤال محدد، هنضطر نبعت كلام المستخدم
        final_prompt = f"You are a helpful AI assistant. Answer the user's question accurately based on the provided files.\n\nUser Question: {task}"

    # دمج النصوص (لو فيه ملفات نصية) مع الأمر النهائي
    if text_context:
        final_prompt = f"Context from text files:\n{text_context}\n\n{final_prompt}"

    try:
        r = ollama.chat(
            model=model_name,
            messages=[{"role": "user", "content": final_prompt, "images": images if images else None}]
        )
        result = r["message"]["content"]
        
        # 🔥 تشغيل طبقة المراجعة الذاتية (بتاخد الإجابة المبدئية وسؤال المستخدم)
        final_result = self_correct(result, task)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
    active_intent = "default"

# ================= FILE TYPE DETECTOR =================

def detect_file_type(file_path):

    ext = os.path.splitext(file_path)[1].lower()

    code_ext = [
        ".py",".js",".cs",".cpp",".c",".java",
        ".html",".css",".json",".xml",".ts"
    ]

    image_ext = [".png",".jpg",".ico",".jpeg",".webp",".bmp"]
    video_ext = [".mp4",".avi",".mov",".mkv",".webm"]
    pdf_ext = [".pdf"]
    word_ext = [".docx"]
    excel_ext = [".xlsx"]
    ppt_ext = [".pptx"]

    if ext in code_ext:
        return "code"

    if ext in image_ext:
        return "image"

    if ext in video_ext:
        return "video"
    
    if ext in pdf_ext:
        return "pdf"
    
    if ext in word_ext:
        return "word"

    if ext in excel_ext:
        return "excel"

    if ext in ppt_ext:
        return "ppt"

    return "text"

# ================= SMART HANDLERS =================

def detect_intent(user_text):
    if not user_text: return "default"
    
    # لو الأمر مجرد إرفاق ملف، اخرج فوراً
    if user_text.strip().lower().startswith("attach"):
        return "default"
        
    # 🔥 كاميرا المراقبة: خلينا نشوف التيرمنال بيبعت العربي سليم ولا متكسر!
    print(f"👀 DEBUG - Python read this: '{user_text}'")
    
    print("🧠 Decision Layer: Analyzing user intent...")
    text_lower = user_text.lower()
    
    # 🔥 فلترة بايثون السريعة (شاملة كل الأخطاء الإملائية والاحتمالات)
    compare_words = ["فرق", "الفرق", "قارن", "مقارنة", "مقارنه", "اختلاف", "compare", "combare"]
    if any(w in text_lower for w in compare_words):
        print("🎯 Intent Detected (Fast Rule): compare")
        return "compare"
        
    summarize_words = ["لخص", "الخلاصة", "باختصار", "الملخص", "summarize"]
    if any(w in text_lower for w in summarize_words):
        print("🎯 Intent Detected (Fast Rule): summarize")
        return "summarize"
        
    issue_words = ["مشكلة", "غلطة", "خطأ", "ايرور", "bug", "issues"]
    if any(w in text_lower for w in issue_words):
        print("🎯 Intent Detected (Fast Rule): detect_issues")
        return "detect_issues"
        
    describe_words = ["اشرح", "ايه ده", "تفاصيل", "وصف", "فيها ايه", "describe"]
    if any(w in text_lower for w in describe_words):
        print("🎯 Intent Detected (Fast Rule): describe")
        return "describe"
        
    # 2. لو بايثون مفهمش، نسأل الذكاء الاصطناعي كحل أخير
    try:
        prompt = f"Categorize into exactly ONE: 'compare', 'summarize', 'detect_issues', 'describe', 'default'. User Request: '{user_text}'. Reply with one word only."
        r = ollama.chat(model="llama3", messages=[{"role": "user", "content": prompt}])
        ans = r["message"]["content"].strip().lower()
        for valid in ["compare", "summarize", "detect_issues", "describe"]:
            if valid in ans:
                print(f"🎯 Intent Detected (AI): {valid}")
                return valid
    except:
        pass
        
    print("🎯 Intent Detected: default")
    return "default"

def select_relevant_files(user_text, context_list):
    total_files = len(context_list)
    if not user_text or total_files <= 1:
        return context_list
        
    print("🧠 Context Layer: Selecting the best files for this task...")
    text_lower = user_text.lower()
    
    # 🔥 فلترة بايثون السريعة: لو طلب "كل" الصور أو كتب رقم بيساوي عدد الملفات
    if "كل" in text_lower or "all" in text_lower or str(total_files) in text_lower:
        print(f"🎯 Selected ALL {total_files} relevant files (Fast Rule)")
        return context_list
        
    files_info = ""
    for i, item in enumerate(context_list, 1): 
        files_info += f"File {i}: {os.path.basename(item['path'])}\n"
        
    prompt = f"""Extract the requested file numbers from the user's text. 
    The user might use Arabic or English ordinal numbers (e.g., الأولى = 1, الرابعة = 4).
    Available Files (Total: {total_files}):
    {files_info}
    User Request: "{user_text}"
    Reply ONLY with the digits separated by commas (e.g., 1, 4). No text."""
    
    try:
        r = ollama.chat(model="llama3", messages=[{"role": "user", "content": prompt}])
        ans = r["message"]["content"].strip()
        
        selected_ids = [int(s) - 1 for s in ans.replace(',', ' ').split() if s.isdigit()]
        selected_files = [context_list[i] for i in selected_ids if 0 <= i < total_files]
        
        if selected_files:
            print(f"🎯 Selected {len(selected_files)} relevant files out of {total_files}")
            return selected_files
            
    except Exception as e:
        print(f"⚠️ Context selection error: {e}")
        
    return context_list

def brain_prompt(file_type, file_name, intent="default"):

    file_name = file_name.lower()

    # 🎯 Intent-based override
    if intent == "compare":
        return "Compare this file with other related files and highlight similarities and differences."

    if intent == "detect_issues":
        return "Analyze this file carefully and detect any problems, inconsistencies, or issues."

    if intent == "summarize":
        return "Provide a clear and concise summary of this content."

    if intent == "describe":
        return "Describe this content in detail with important observations."
    
    # صور
    if file_type == "image":
        return "Describe this image in detail. Mention important visual details."

    # كود
    if file_type == "code":
        return "Explain this code briefly. Detect bugs and suggest improvements."

    # PDF
    if file_type == "pdf":
        if "invoice" in file_name or "receipt" in file_name:
            return "Extract invoice information in structured form."
        return "Summarize this PDF clearly."

    # Word / Text
    if file_type in ["word", "text"]:
        return "Summarize this document and extract key points."

    # Excel
    if file_type == "excel":
        return "Analyze this spreadsheet and explain the data."

    # PowerPoint
    if file_type == "ppt":
        return "Summarize this presentation slide by slide."

    return "Analyze this file intelligently."

def handle_code_file(file_path):

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(4000)

        print("🧠 Analyzing code with AI...")

        r = ollama.chat(
            model="llama3",
            messages=[{
                "role":"user",
                "content":f"Explain this code briefly and detect problems:\n\n{content}"
            }]
        )

        print("\n🤖 AI Analysis:")
        print(r["message"]["content"])

    except Exception as e:
        print(f"❌ Code analysis error: {e}")


def handle_image_file(file_path):
    try:
        size = os.path.getsize(file_path) / (1024*1024)
        print(f"🖼 Image attached: {os.path.basename(file_path)}")
        print(f"📦 Size: {size:.2f} MB")
        
        # 🔥 التعديل هنا: رسالة توضيحية فقط
        print("⚡ Vision ready: Ask me to describe it!") 

    except Exception as e:
        print(f"❌ Image error: {e}")


def handle_video_file(file_path):
    print("🎬 Processing video for RTX 3060 Ti...")
    
    try:
        vidcap = cv2.VideoCapture(file_path)
        
        # معلومات الفيديو
        total_frames = int(vidcap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = vidcap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps
        
        print(f"⏱ Duration: {duration:.1f}s | Total Frames: {total_frames}")

        # ✅ استراتيجية 3060 Ti:
        # هناخد 5 لقطات موزعة بالتساوي على الفيديو كله
        # ده أفضل من أخذ لقطة كل ثانية عشان الذاكرة متتخنقش
        target_frame_count = 5 
        
        # لو الفيديو قصير جدا (أقل من 5 ثواني) هناخد لقطة كل ثانية
        if duration < 5:
            step = int(fps) # كل ثانية
        else:
            step = int(total_frames / target_frame_count)

        if step == 0: step = 1

        count = 0
        extracted_count = 0
        
        while True:
            # نقفز للفريم المطلوب مباشرة لتوفير المعالجة
            # (بدل ما نقرأ فريم فريم)
            frame_id = extracted_count * step
            if frame_id >= total_frames:
                break
                
            vidcap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
            success, image = vidcap.read()
            
            if not success: break
            
            # 🔥 أهم خطوة للـ 8GB VRAM: تصغير الصورة
            # بنخلي الارتفاع 512 بيكسل بس، والعرض يتضبط أوتوماتيك
            # ده بيخلي الصورة خفيفة جداً على الموديل
            height, width = image.shape[:2]
            max_height = 512
            if height > max_height:
                scale = max_height / height
                new_width = int(width * scale)
                image = cv2.resize(image, (new_width, max_height))

            # الحفظ والإضافة
            frame_path = f"{file_path}_frame_{extracted_count}.jpg"
            cv2.imwrite(frame_path, image)
            
            if not any(item["path"] == frame_path for item in project_context):
                project_context.append({
                    "path": frame_path,
                    "type": "image"
                })

            
            print(f"📸 Frame {extracted_count+1}: {os.path.basename(frame_path)} (Resized)")
            extracted_count += 1
            
            # أمان أخير
            if extracted_count >= 6:
                break
        
        save_project_context()
        print(f"⚡ Done! {extracted_count} frames ready. Ask: 'Describe video'")
        
    except Exception as e:
        print(f"❌ Video error: {e}")

def handle_pdf_file(file_path):

    try:
        print("📄 Reading PDF...")

        # نحاول نقرأه كنص عادي الأول
        reader = PdfReader(file_path)

        text = ""

        for page in reader.pages[:3]:
            text += page.extract_text() or ""

        # لو مفيش نص → نستخدم OCR
        if not text.strip():

            print("🧠 No text found, using OCR...")

            from pdf2image import convert_from_path

            images = convert_from_path(
                file_path,
                first_page=1,
                last_page=2,
                poppler_path=r"C:\poppler\Library\bin"
            )

            for img in images:

                # تحويل رمادي
                img = img.convert("L")

                # زيادة التباين
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(2)

                # شوية sharpen
                img = img.filter(ImageFilter.SHARPEN)

                text += pytesseract.image_to_string(
                    img,
                    lang="ara+eng",
                    config="--psm 6"
                )

        if not text.strip():
            print("❌ OCR failed.")
            return

        print("🧠 Sending PDF content to AI...")

        r = ollama.chat(
            model="llama3",
            messages=[{
                "role":"user",
                "content": f"""
                Extract ONLY real information from this document.

                Return STRICT JSON format only:

                {{
                "company": "",
                "date": "",
                "total_amount": "",
                "invoice_number": "",
                "details": ""
                }}

                Do NOT guess.
                If something missing leave it empty.

                Document:
                {text[:4000]}"""
            }]
        )

        print("\n🤖 PDF Summary:")
        print(r["message"]["content"])

        try:
            raw = r["message"]["content"]

            # استخراج JSON من أي كلام حوالينه
            match = re.search(r"\{.*\}", raw, re.DOTALL)

            if match:
                json_text = match.group(0)
                data = json.loads(json_text)

                print("✅ JSON Parsed Successfully")
                print(data)

                # حفظ البيانات داخل project context
                for item in project_context:
                    if item["path"] == file_path:
                        item["data"] = data
                        break

                save_project_context()

            else:
                print("⚠ No JSON found.")

        except Exception as e:
            print("⚠ JSON parse error:", e)

    except Exception as e:
        print(f"❌ PDF error: {e}")

def handle_word_file(file_path):

    try:
        print("📄 Reading Word file...")

        doc = Document(file_path)

        text = ""
        for p in doc.paragraphs:
            text += p.text + "\n"

        text = text[:4000]

        print("🧠 Sending Word content to AI...")

        r = ollama.chat(
            model="llama3",
            messages=[{
                "role":"user",
                "content":f"Summarize this document:\n\n{text}"
            }]
        )

        print("\n🤖 Word Summary:")
        print(r["message"]["content"])

    except Exception as e:
        print(f"❌ Word error: {e}")


def handle_excel_file(file_path):

    try:
        print("📊 Reading Excel file...")

        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet = wb.active

        rows = []

        for row in sheet.iter_rows(values_only=True):
            rows.append(str(row))

        text = "\n".join(rows)[:4000]

        print("🧠 Sending Excel content to AI...")

        r = ollama.chat(
            model="llama3",
            messages=[{
                "role":"user",
                "content":f"Explain this excel data:\n\n{text}"
            }]
        )

        print("\n🤖 Excel Analysis:")
        print(r["message"]["content"])

    except Exception as e:
        print(f"❌ Excel error: {e}")


def handle_ppt_file(file_path):

    try:
        print("📽 Reading PowerPoint...")

        prs = Presentation(file_path)

        text = ""

        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text += shape.text + "\n"

        text = text[:4000]

        print("🧠 Sending PowerPoint content to AI...")

        r = ollama.chat(
            model="llama3",
            messages=[{
                "role":"user",
                "content":f"Summarize this presentation:\n\n{text}"
            }]
        )

        print("\n🤖 PPT Summary:")
        print(r["message"]["content"])

    except Exception as e:
        print(f"❌ PowerPoint error: {e}")

# ================= ATTACH =================

def attach_tool(file_path):

    if not os.path.exists(file_path):
        print("❌ File not found.")
        return

    file_type = detect_file_type(file_path)

    # print(f"📎 Detected type: {file_type}")

    # منع التكرار في الذاكرة
    already_exists = any(
        item["path"] == file_path
        for item in project_context
    )

    if not already_exists:
        project_context.append({
            "path": file_path,
            "type": file_type
        })
        # print(f"🧠 Added to project context ({len(project_context)} files)")
    else:
        print("⚡ File already in context, skipped.")

    save_project_context()

# ================= LOOP =================

load_project_context()

print("\n🤖 AGENT READY (Commands: build, run, delete, job, or chat)")

while True:
    try:
        user = input().strip()
        last_user_input = user

        intent = detect_intent(user)
        if intent != "default":
            active_intent = intent
        
        if user.lower() == "exit": break
        if not user: continue

        mode = detect_mode(user)
        if mode != "ATTACH":
            print(f"Mode: {mode}")

        if mode == "RUN":
            last = load_last_project()
            if last and os.path.exists(last):
                run_python(last)
            else:
                print("❌ No valid project history found.")

        elif mode == "DELETE":
            delete_tool(user)

        elif mode == "PROJECT":
            project_tool(user)

        elif mode == "JOB":
            job_tool(user)
        
        elif mode == "ATTACH":
            file_path = user.replace("attach", "", 1).strip()
            # print(f"📎 File attached: {file_path}")
            attach_tool(file_path)
        
        elif mode == "CLEAR":
            project_context.clear()

            if os.path.exists(CONTEXT_FILE):
                os.remove(CONTEXT_FILE)
            print("🧹 Project context cleared.")

        else:
            chat_tool(user)
            
    except KeyboardInterrupt:
        print("\nExiting...")
        break
    except Exception as e:
        print(f"❌ Critical Error: {e}")
