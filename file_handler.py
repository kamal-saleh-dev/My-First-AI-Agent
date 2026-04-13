# file_handler.py — File attachment handling (PDF, Word, Excel, PPT, images, video, code)
import os, sys, re, io, time, json, subprocess, threading

def get_token_limit(model: str = None) -> int:
    """
    Dynamic context limit based on active model.
    Returns character limit (not tokens — 1 token ≈ 4 chars).

    Cloud models (Claude, GPT, Qwen3 cloud): 150k chars (~37k tokens)
    Mid-size local (14b+):                    32k  chars (~8k tokens)
    Small local (7b):                          8k  chars (~2k tokens)
    """
    m = (model or _model() or "").lower()
    # Cloud / large context models
    if any(x in m for x in ["claude", "gpt-4", "or_free", "qwen3", "gemini", "mistral-large"]):
        return 150_000
    # Mid-size local models (≥14b)
    if any(x in m for x in ["14b", "32b", "70b", "72b", "codestral", "deepseek-v2"]):
        return 32_000
    # Default: small local model (7b)
    return 8_000

def _import_cv2():
    import cv2 as _cv2; return _cv2

def _import_pytesseract():
    """Lazy import pytesseract — auto-detect tesseract binary across platforms."""
    try:
        import pytesseract as _t
        import sys as _sys, os as _os, shutil as _sh
        # Only set on Windows if tesseract is NOT already on PATH
        if _sys.platform == "win32" and not _sh.which("tesseract"):
            candidates = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]
            for path in candidates:
                if _os.path.exists(path):
                    _t.pytesseract.tesseract_cmd = path
                    break
        return _t
    except ImportError:
        safe_print("⚠️ pytesseract not installed — OCR unavailable. Run: pip install pytesseract")
        return None

def _import_pil():
    from PIL import ImageEnhance, ImageFilter; return ImageEnhance, ImageFilter

import llm_client as _llm_client  # for live DEFAULT_MODEL reads

# Globals injected by agent.py via inject_globals()
safe_chat = get_response = log = _state = project_context = safe_print = None
save_project_context = None  # injected from agent.py via inject_globals()

def _model() -> str:
    """Always returns the current DEFAULT_MODEL (reflects /model switches)."""
    return _llm_client.DEFAULT_MODEL

# ── Required globals injected by agent.py at startup ─────────────────────────
_REQUIRED_GLOBALS = {"safe_chat", "get_response", "log", "_state"}

def inject_globals(**kwargs):
    """
    Called once by agent.py after imports.
    Injects shared dependencies: safe_chat, get_response, DEFAULT_MODEL, log, _state
    """
    g = globals()
    for k, v in kwargs.items():
        g[k] = v

def _require_injected():
    """Guard — validates ALL required globals are injected (call inject_globals() first)."""
    missing = [k for k, v in {
        "safe_chat": safe_chat, "get_response": get_response, "log": log
    }.items() if v is None]
    if missing:
        raise RuntimeError(
            f"file_handler globals not injected: {missing} — call inject_globals() first"
        )

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

def detect_intent(text):
    text_lower = text.lower()

    if any(w in text_lower for w in ["summarize", "summary"]): return "summarize"
    if any(w in text_lower for w in ["bug", "issue", "fix", "error"]): return "detect_issues"
    
    # 🔥 1. كبرنا شبكة الدردشة عشان تشمل الهزار والأسئلة العامة
    default_words = [
        "help", "make", "create", "build", "unity", "code", "write", "game", 
        "how", "what", "can you", "project", "budget", "develop",
        "joke", "tell", "say", "yes", "no", "thanks", "who", "why", "where", "when",
        "ازيك", "عامل", "هلو", "اهلا", "مرحبا", "hello", "hi", "hey", "good"
    ]
    if any(w in text_lower for w in default_words):
        return "default"
        
    compare_words = ["فرق", "قارن", "مقارنة", "اختلاف", "compare", "difference"]
    if any(w in text_lower for w in compare_words):
        return "compare"
        
    summarize_words = ["لخص", "الخلاصة", "باختصار", "الملخص", "summarize", "summary"]
    if any(w in text_lower for w in summarize_words):
        return "summarize"
        
    issue_words = ["مشكلة", "غلطة", "خطأ", "ايرور", "bug", "issue", "error", "fix"]
    if any(w in text_lower for w in issue_words):
        return "detect_issues"
        
    describe_words = ["اشرح", "ايه ده", "تفاصيل", "وصف", "فيها ايه", "describe", "explain"]
    if any(w in text_lower for w in describe_words):
        return "describe"
        
    # 🔥 2. قفلنا ثغرة التفكير الغبي للموديل
    try:
        prompt = f"Categorize into ONE: 'compare', 'summarize', 'detect_issues', 'describe', 'default'. RULE: For coding, general questions, or jokes, YOU MUST pick 'default'. User Request: '{text}'. Reply with one word."
        r = safe_chat(model=_model(), messages=[{"role": "user", "content": prompt}])
        ans = get_response(r).strip().lower()
        
        # لو الموديل جاب سيرة default في كلامه، نعتبرها دردشة فوراً ومندورش على الباقي
        if "default" in ans:
            return "default"
            
        for valid in ["compare", "summarize", "detect_issues", "describe"]:
            if valid in ans:
                return valid
    except Exception as e:
        safe_print(f"⚠ intent detection error: {e}")
        
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
        r = safe_chat(model=_model(), messages=[{"role": "user", "content": prompt}])
        ans = get_response(r).strip()
        
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
    _require_injected()

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(4000)

        print("🧠 Analyzing code with AI...")

        r = safe_chat(
            model=_model(),
            messages=[{
                "role":"user",
                "content":f"Explain this code briefly and detect problems:\n\n{content}"
            }]
        )

        print("\n🤖 AI Analysis:")
        print(get_response(r))

    except Exception as e:
        print(f"❌ Code analysis error: {e}")


def handle_image_file(file_path):
    cv2 = _import_cv2()
    try:
        size = os.path.getsize(file_path) / (1024*1024)
        print(f"🖼 Image attached: {os.path.basename(file_path)}")
        print(f"📦 Size: {size:.2f} MB")
        
        # 🔥 التعديل هنا: رسالة توضيحية فقط
        print("⚡ Vision ready: Ask me to describe it!") 

    except Exception as e:
        print(f"❌ Image error: {e}")


def handle_video_file(file_path):
    cv2 = _import_cv2()
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
    from pypdf import PdfReader

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

            # Detect poppler path cross-platform (Windows only needs explicit path)
            import shutil as _sh, sys as _sys
            poppler_path = None
            if _sys.platform == "win32" and not _sh.which("pdftoppm"):
                _win_candidates = [
                    r"C:\poppler\Library\bin",
                    r"C:\poppler\bin",
                    r"C:\Program Files\poppler\Library\bin",
                ]
                import os as _os
                for _p in _win_candidates:
                    if _os.path.isdir(_p):
                        poppler_path = _p
                        break
            images = convert_from_path(
                file_path,
                first_page=1,
                last_page=2,
                poppler_path=poppler_path   # None = use PATH (Linux/Mac/Win with PATH set)
            )

            ImageEnhance, ImageFilter = _import_pil()
            pytesseract = _import_pytesseract()

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

        r = safe_chat(
            model=_model(),
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
                {text[:get_token_limit()]}"""
            }]
        )

        raw = get_response(r)
        print("\n🤖 PDF Summary:")
        print(raw)

        try:

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
    from docx import Document

    try:
        print("📄 Reading Word file...")

        doc = Document(file_path)

        text = ""
        for p in doc.paragraphs:
            text += p.text + "\n"

        text = text[:get_token_limit()]

        print("🧠 Sending Word content to AI...")

        r = safe_chat(
            model=_model(),
            messages=[{
                "role":"user",
                "content":f"Summarize this document:\n\n{text}"
            }]
        )

        print("\n🤖 Word Summary:")
        print(get_response(r))

    except Exception as e:
        print(f"❌ Word error: {e}")


def handle_excel_file(file_path):
    import openpyxl

    try:
        print("📊 Reading Excel file...")

        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet = wb.active

        rows = []

        for row in sheet.iter_rows(values_only=True):
            rows.append(str(row))

        text = "\n".join(rows)[:get_token_limit()]

        print("🧠 Sending Excel content to AI...")

        r = safe_chat(
            model=_model(),
            messages=[{
                "role":"user",
                "content":f"Explain this excel data:\n\n{text}"
            }]
        )

        print("\n🤖 Excel Analysis:")
        print(get_response(r))

    except Exception as e:
        print(f"❌ Excel error: {e}")


def handle_ppt_file(file_path):
    from pptx import Presentation

    try:
        print("📽 Reading PowerPoint...")

        prs = Presentation(file_path)

        text = ""

        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text += shape.text + "\n"

        text = text[:get_token_limit()]

        print("🧠 Sending PowerPoint content to AI...")

        r = safe_chat(
            model=_model(),
            messages=[{
                "role":"user",
                "content":f"Summarize this presentation:\n\n{text}"
            }]
        )

        print("\n🤖 PPT Summary:")
        print(get_response(r))

    except Exception as e:
        print(f"❌ PowerPoint error: {e}")

# ================= ATTACH =================
def attach_tool(file_path):
    global project_context # 🔥 ضفنا دي عشان نقدر نعدل في الذاكرة

    if not os.path.exists(file_path):
        print("❌ File not found.")
        return

    file_type = detect_file_type(file_path)

    # 🔥 السحر هنا: لو دي سكرين شوت لايف، امسح القديمة من الذاكرة الأول!
    if "live_screen" in file_path:
        # ✅ mutate in-place to keep reference valid
        _state.project_context[:] = [item for item in _state.project_context if "live_screen" not in item["path"]]

    already_exists = any(item["path"] == file_path for item in project_context)

    if not already_exists:
        project_context.append({
            "path": file_path,
            "type": file_type
        })
    else:
        print("⚡ File already in context, skipped.")

    save_project_context()
