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

# 🔥 FIX WINDOWS ENCODING
sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, "agent_memory.txt")
CONTEXT_FILE = os.path.join(BASE_DIR, "project_context.json")

# ================= PROJECT CONTEXT =================
project_context = []


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


# ================= CHAT =================

def chat_tool(task):
    # Normalize task string
    if task:
        task = task.strip()
    
    # 🚨 KEY FIX: Treat the auto-message as "No Task" to trigger the loop
    if task == "Analyze and describe the attached files in detail.":
        # 🧠 Auto Brain already handled analysis
        if len(project_context) > 0:
            print("⚡ Auto Brain already analyzed attached files.")
            return
        task = ""

    # ---------------------------------------------------------
    # MODE A: Auto-Analyze (Loop through files)
    # ---------------------------------------------------------
    if not task:
        print(f"🚀 Auto-Analyzing {len(project_context)} items separately...")
        
        for i, item in enumerate(project_context, 1):
            file_path = item["path"]
            file_type = item["type"]
            file_name = os.path.basename(file_path)
            
            print(f"\n[{i}/{len(project_context)}] 🔍 Analyzing: {file_name}...")
            
            try:
                # 1. Image Analysis
                if file_type == "image":
                    r = ollama.chat(
                        model="llava",
                        messages=[{
                            "role": "user",
                            "content": "Describe this image in detail.",
                            "images": [file_path] # Send ONLY this image
                        }]
                    )
                    print(f"🖼 Report for {file_name}:")
                    print(f"🤖 Agent: {r['message']['content']}")
                
                # 2. Text/Data Analysis
                else:
                    content_to_analyze = ""
                    if "data" in item:
                        content_to_analyze = json.dumps(item["data"], indent=2)
                    else:
                        try:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                content_to_analyze = f.read(2000)
                        except:
                            content_to_analyze = "Could not read file content."

                    r = ollama.chat(
                        model="llama3",
                        messages=[{
                            "role": "user",
                            "content": f"Summarize this file:\n\n{content_to_analyze}"
                        }]
                    )
                    print(f"📄 Report for {file_name}:")
                    print(f"🤖 Agent: {r['message']['content']}")

                print("-" * 40) 

            except Exception as e:
                print(f"❌ Error analyzing {file_name}: {e}")

    # ---------------------------------------------------------
    # MODE B: Specific Question (Group Analysis)
    # ---------------------------------------------------------
    else:
        # Collect all images
        images = [item["path"] for item in project_context if item["type"] == "image"]
        
        # Collect all text context
        text_context = ""
        keywords = task.lower().split()

        for item in project_context:

            if item["type"] == "image":
                continue

            file_name = os.path.basename(item["path"]).lower()

            # Smart filtering
            relevant = any(k in file_name for k in keywords)

            # لو مفيش match ناخد أول ملفين بس كـ fallback
            if not relevant and len(text_context) > 2000:
                continue

            text_context += f"\n--- File: {os.path.basename(item['path'])} ---\n"

            if "data" in item:
                text_context += json.dumps(item["data"])
            elif "cached_text" in item:
                text_context += item["cached_text"]

                text_context += f"\n--- File: {os.path.basename(item['path'])} ---\n"
                if "data" in item:
                    text_context += json.dumps(item['data'])
                else:
                    try:
                        if "cached_text" in item:
                            text_context += item["cached_text"]
                        else:
                            try:
                                with open(item["path"], "r", encoding="utf-8", errors="ignore") as f:
                                    content = f.read(1000)

                                item["cached_text"] = content
                                text_context += content

                            except:
                                pass

                    except: pass

        model_name = "llava" if images else "llama3"
        print(f"🤔 Thinking about {len(images)} images and text files...")

        prompt = task
        if text_context:
            prompt = f"Context from files:\n{text_context}\n\nQuestion: {task}"

        try:
            r = ollama.chat(
                model=model_name,
                messages=[{
                    "role": "user",
                    "content": prompt,
                    "images": images if images else None
                }]
            )
            print(f"\n🤖 Agent: {r['message']['content']}")
        except Exception as e:
            print(f"❌ Error: {e}")

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

def brain_prompt(file_type, file_name):

    file_name = file_name.lower()

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

def self_correct(text):

    try:
        r = ollama.chat(
            model="llama3",
            messages=[{
                "role": "user",
                "content": f"""
                    Rewrite this response so it sounds natural, clear and smart.

                    Return ONLY the final improved response.
                    Do NOT explain changes.
                    Do NOT add notes.
                    Do NOT add headings.

                    Response:
                    {text}
                    """
                }]
            )

        return r["message"]["content"]

    except:
        return text

def attach_tool(file_path):

    if not os.path.exists(file_path):
        print("❌ File not found.")
        return

    file_type = detect_file_type(file_path)

    print(f"📎 Detected type: {file_type}")

    already_exists = any(
    item["path"] == file_path
    for item in project_context
    )

    if not already_exists:
        project_context.append({
            "path": file_path,
            "type": file_type
        })
        print(f"🧠 Added to project context ({len(project_context)} files)")
    else:
        print("⚡ File already in context, skipped.")

    save_project_context()

    try:
        print("🧠 Auto Brain analyzing...")

        previous_memory = None

        for item in project_context:
            if item["path"] == file_path:
                previous_memory = item.get("brain_memory")
                break

        prompt = brain_prompt(file_type, os.path.basename(file_path))

        if previous_memory:
            prompt += f"\n\nPrevious analysis:\n{previous_memory}\n\nUpdate or improve the analysis."

        # الصور تستخدم llava
        if file_type == "image":

            r = ollama.chat(
                model="llava",
                messages=[{
                    "role": "user",
                    "content": prompt,
                    "images": [file_path]
                }]
            )

        else:
            # باقي الملفات
            content = ""

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(3000)
            except:
                content = "Could not read file."

            r = ollama.chat(
                model="llama3",
                messages=[{
                    "role": "user",
                    "content": f"{prompt}\n\n{content}"
                }]
            )

        result = r["message"]["content"]

        # 🧠 Self Correction
        result = self_correct(result)

        print("🤖 Brain Result:")
        print(result)

        # 🧠 حفظ نتيجة التحليل في الذاكرة
        for item in project_context:
            if item["path"] == file_path:
                item["brain_memory"] = result
                break

        save_project_context()

    except Exception as e:
        print(f"❌ Brain error: {e}")

# ================= LOOP =================

load_project_context()

print("\n🤖 AGENT READY (Commands: build, run, delete, job, or chat)")

while True:
    try:
        user = input("\nYou: ").strip()
        if user.lower() == "exit": break
        if not user: continue

        mode = detect_mode(user)
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
            print(f"📎 File attached: {file_path}")
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
