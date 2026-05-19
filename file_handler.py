# file_handler.py — File attachment handling (PDF, Word, Excel, PPT, images, video, code)
import os
import sys
import re
import io
import time
import json
import subprocess
import threading

import llm_client as _llm_client   # for live DEFAULT_MODEL reads


# ── Dependency container ──────────────────────────────────────────────────────

class _Deps:
    """
    Holds dependencies injected by agent.py at startup.
    Provides fail-fast validation: raises RuntimeError immediately if any
    required dep is missing — errors surface at startup, not at runtime.
    """
    _REQUIRED = ("safe_chat", "get_response", "log", "_state")

    def __init__(self):
        self.safe_chat            = None
        self.get_response         = None
        self.log                  = None
        self._state               = None
        self.project_context      = None
        self.safe_print           = None
        self.save_project_context = None
        self._initialized         = False

    def init(self, **kwargs) -> None:
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
        missing = [k for k in self._REQUIRED if getattr(self, k) is None]
        if missing:
            raise RuntimeError(
                f"file_handler.inject_globals(): missing required deps: {missing}\n"
                f"Pass them as keyword args: inject_globals("
                f"{', '.join(f'{k}=...' for k in missing)})"
            )
        self._initialized = True

    def require(self) -> None:
        if not self._initialized:
            raise RuntimeError(
                "file_handler.inject_globals() was never called. "
                "Call it once at startup before using any file_handler functions."
            )


_deps = _Deps()

# ── Backward-compatible module-level aliases ──────────────────────────────────
# Legacy code that does `from file_handler import safe_chat` keeps working.
# These are updated by inject_globals() each time it is called.
safe_chat            = None
get_response         = None
log                  = None
_state               = None
project_context      = None
safe_print           = None
save_project_context = None


def _model() -> str:
    """Always returns the current DEFAULT_MODEL (reflects /model switches)."""
    return _llm_client.DEFAULT_MODEL


# ── Lazy import helpers ───────────────────────────────────────────────────────

def _import_cv2():
    try:
        import cv2 as _cv2
        return _cv2
    except ImportError:
        (_deps.safe_print or print)(
            "⚠️ opencv-python not installed — image processing unavailable."
            " Run: pip install opencv-python"
        )
        return None


def _import_pytesseract():
    """Lazy import pytesseract — auto-detect tesseract binary across platforms."""
    try:
        import pytesseract as _t
        import shutil as _sh
        if sys.platform == "win32" and not _sh.which("tesseract"):
            candidates = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]
            for path in candidates:
                if os.path.exists(path):
                    _t.pytesseract.tesseract_cmd = path
                    break
        return _t
    except ImportError:
        (_deps.safe_print or print)(
            "⚠️ pytesseract not installed — OCR unavailable. Run: pip install pytesseract"
        )
        return None


def _import_pil():
    from PIL import ImageEnhance, ImageFilter
    return ImageEnhance, ImageFilter


# ── Public injection API ──────────────────────────────────────────────────────

_REQUIRED_GLOBALS = {"safe_chat", "get_response", "log", "_state"}


def inject_globals(**kwargs) -> None:
    """
    Called once by agent.py after all imports.
    Validates ALL required deps are present — fails fast at startup.
    Also keeps module-level aliases in sync for backward compatibility.
    """
    # Initialise the typed container (raises on missing required deps)
    _deps.init(**kwargs)

    # Keep module-level names in sync so existing code still works
    g = globals()
    for k, v in kwargs.items():
        g[k] = v


def _require_injected() -> None:
    """Guard — call before any function that needs injected deps."""
    _deps.require()


# ── File type detection ───────────────────────────────────────────────────────

def detect_file_type(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".py", ".js", ".cs", ".cpp", ".c", ".java",
               ".html", ".css", ".json", ".xml", ".ts"):
        return "code"
    if ext in (".png", ".jpg", ".ico", ".jpeg", ".webp", ".bmp"):
        return "image"
    if ext in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
        return "video"
    if ext == ".pdf":
        return "pdf"
    if ext == ".docx":
        return "word"
    if ext == ".xlsx":
        return "excel"
    if ext == ".pptx":
        return "ppt"
    return "text"


# ── Intent detection ──────────────────────────────────────────────────────────

def detect_intent(text: str) -> str:
    """
    Classify user text into one of: compare | summarize | detect_issues | describe | default.

    BUG FIX: specific intents are checked BEFORE the broad 'default' keyword list,
    so 'compare' and 'summarize' can never be swallowed by the default branch.
    LLM fallback is only reached when no keyword matches.
    """
    text_lower = text.lower()

    # ── 1. Specific intents first (highest priority) ──────────────────────────
    compare_words   = ["فرق", "قارن", "مقارنة", "اختلاف", "compare", "difference"]
    summarize_words = ["لخص", "الخلاصة", "باختصار", "الملخص", "summarize", "summary"]
    issue_words     = ["مشكلة", "غلطة", "خطأ", "ايرور", "bug", "issue", "error", "fix"]
    describe_words  = ["اشرح", "ايه ده", "تفاصيل", "وصف", "فيها ايه", "describe", "explain"]

    if any(w in text_lower for w in compare_words):
        return "compare"
    if any(w in text_lower for w in summarize_words):
        return "summarize"
    if any(w in text_lower for w in issue_words):
        return "detect_issues"
    if any(w in text_lower for w in describe_words):
        return "describe"

    # ── 2. Broad 'default' keyword net (catches greetings, general questions) ─
    default_words = [
        "help", "make", "create", "build", "unity", "code", "write", "game",
        "how", "what", "can you", "project", "budget", "develop",
        "joke", "tell", "say", "yes", "no", "thanks", "who", "why", "where", "when",
        "ازيك", "عامل", "هلو", "اهلا", "مرحبا", "hello", "hi", "hey", "good",
    ]
    if any(w in text_lower for w in default_words):
        return "default"

    # ── 3. LLM fallback for ambiguous inputs ──────────────────────────────────
    try:
        prompt = (
            "Categorize into ONE: 'compare', 'summarize', 'detect_issues', 'describe', 'default'. "
            "RULE: For coding, general questions, or jokes, YOU MUST pick 'default'. "
            f"User Request: '{text}'. Reply with one word."
        )
        r   = _deps.safe_chat(model=_model(), messages=[{"role": "user", "content": prompt}])
        ans = _deps.get_response(r).strip().lower()

        if "default" in ans:
            return "default"
        for valid in ("compare", "summarize", "detect_issues", "describe"):
            if valid in ans:
                return valid
    except Exception as e:
        (_deps.safe_print or print)(f"⚠ intent detection error: {e}")

    return "default"


# ── Context window sizing ─────────────────────────────────────────────────────

def get_token_limit(model: str = None) -> int:
    """
    Dynamic context limit based on active model.
    Returns character limit (not tokens — 1 token ≈ 4 chars).
    """
    m = (model or _model() or "").lower()
    if any(x in m for x in ["claude", "gpt-4", "or_free", "qwen3", "gemini", "mistral-large"]):
        return 150_000
    if any(x in m for x in ["14b", "32b", "70b", "72b", "codestral", "deepseek-v2"]):
        return 32_000
    return 8_000


# ── Relevant-file selector ────────────────────────────────────────────────────

def select_relevant_files(user_text: str, context_list: list) -> list:
    total_files = len(context_list)
    if not user_text or total_files <= 1:
        return context_list

    print("🧠 Context Layer: Selecting the best files for this task...")
    text_lower = user_text.lower()

    if "كل" in text_lower or "all" in text_lower or str(total_files) in text_lower:
        print(f"🎯 Selected ALL {total_files} relevant files (Fast Rule)")
        return context_list

    files_info = "".join(
        f"File {i}: {os.path.basename(item['path'])}\n"
        for i, item in enumerate(context_list, 1)
    )
    prompt = (
        "Extract the requested file numbers from the user's text.\n"
        "The user might use Arabic or English ordinal numbers (e.g., الأولى = 1, الرابعة = 4).\n"
        f"Available Files (Total: {total_files}):\n{files_info}"
        f'User Request: "{user_text}"\n'
        "Reply ONLY with the digits separated by commas (e.g., 1, 4). No text."
    )
    try:
        r   = _deps.safe_chat(model=_model(), messages=[{"role": "user", "content": prompt}])
        ans = _deps.get_response(r).strip()
        selected_ids   = [int(s) - 1 for s in ans.replace(",", " ").split() if s.isdigit()]
        selected_files = [context_list[i] for i in selected_ids if 0 <= i < total_files]
        if selected_files:
            print(f"🎯 Selected {len(selected_files)} relevant files out of {total_files}")
            return selected_files
    except Exception as e:
        print(f"⚠️ Context selection error: {e}")

    return context_list


# ── Brain prompt builder ──────────────────────────────────────────────────────

def brain_prompt(file_type: str, file_name: str, intent: str = "default") -> str:
    file_name = file_name.lower()
    if intent == "compare":      return "Compare this file with other related files and highlight similarities and differences."
    if intent == "detect_issues":return "Analyze this file carefully and detect any problems, inconsistencies, or issues."
    if intent == "summarize":    return "Provide a clear and concise summary of this content."
    if intent == "describe":     return "Describe this content in detail with important observations."
    if file_type == "image":     return "Describe this image in detail. Mention important visual details."
    if file_type == "code":      return "Explain this code briefly. Detect bugs and suggest improvements."
    if file_type == "pdf":
        if "invoice" in file_name or "receipt" in file_name:
            return "Extract invoice information in structured form."
        return "Summarize this PDF clearly."
    if file_type in ("word", "text"):  return "Summarize this document and extract key points."
    if file_type == "excel":           return "Analyze this spreadsheet and explain the data."
    if file_type == "ppt":             return "Summarize this presentation slide by slide."
    return "Analyze this file intelligently."


# ── File handlers ─────────────────────────────────────────────────────────────

def handle_code_file(file_path: str) -> None:
    _require_injected()
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(4000)
        print("🧠 Analyzing code with AI...")
        r = _deps.safe_chat(model=_model(), messages=[{
            "role": "user",
            "content": f"Explain this code briefly and detect problems:\n\n{content}",
        }])
        print("\n🤖 AI Analysis:")
        print(_deps.get_response(r))
    except Exception as e:
        print(f"❌ Code analysis error: {e}")


def handle_image_file(file_path: str) -> None:
    try:
        size = os.path.getsize(file_path) / (1024 * 1024)
        print(f"🖼 Image attached: {os.path.basename(file_path)}")
        print(f"📦 Size: {size:.2f} MB")
        print("⚡ Vision ready: Ask me to describe it!")
    except Exception as e:
        print(f"❌ Image error: {e}")


def handle_video_file(file_path: str) -> None:
    cv2 = _import_cv2()
    if cv2 is None:
        print("❌ opencv not available — cannot process video.")
        return
    print("🎬 Processing video...")
    try:
        vidcap       = cv2.VideoCapture(file_path)
        total_frames = int(vidcap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps          = vidcap.get(cv2.CAP_PROP_FPS)
        duration     = total_frames / fps if fps else 0

        print(f"⏱ Duration: {duration:.1f}s | Total Frames: {total_frames}")
        step = int(fps) if duration < 5 else int(total_frames / 5)
        if step == 0:
            step = 1

        extracted_count = 0
        while extracted_count < 6:
            frame_id = extracted_count * step
            if frame_id >= total_frames:
                break
            vidcap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
            success, image = vidcap.read()
            if not success:
                break
            height, width = image.shape[:2]
            if height > 512:
                scale     = 512 / height
                new_width = int(width * scale)
                image     = cv2.resize(image, (new_width, 512))
            frame_path = f"{file_path}_frame_{extracted_count}.jpg"
            cv2.imwrite(frame_path, image)
            ctx = _deps.project_context if _deps.project_context is not None else project_context
            if ctx is not None and not any(item["path"] == frame_path for item in ctx):
                ctx.append({"path": frame_path, "type": "image"})
            print(f"📸 Frame {extracted_count + 1}: {os.path.basename(frame_path)} (Resized)")
            extracted_count += 1

        if _deps.save_project_context:
            _deps.save_project_context()
        elif save_project_context:
            save_project_context()
        print(f"⚡ Done! {extracted_count} frames ready. Ask: 'Describe video'")
    except Exception as e:
        print(f"❌ Video error: {e}")


def handle_pdf_file(file_path: str) -> None:
    _require_injected()
    from pypdf import PdfReader
    try:
        print("📄 Reading PDF...")
        reader = PdfReader(file_path)
        text   = ""
        for page in reader.pages[:3]:
            text += page.extract_text() or ""

        if not text.strip():
            print("🧠 No text found, using OCR...")
            from pdf2image import convert_from_path
            import shutil as _sh
            poppler_path = None
            if sys.platform == "win32" and not _sh.which("pdftoppm"):
                for _p in [r"C:\poppler\Library\bin", r"C:\poppler\bin",
                            r"C:\Program Files\poppler\Library\bin"]:
                    if os.path.isdir(_p):
                        poppler_path = _p
                        break
            images = convert_from_path(file_path, first_page=1, last_page=2,
                                       poppler_path=poppler_path)
            ImageEnhance, ImageFilter = _import_pil()
            pytesseract = _import_pytesseract()
            for img in images:
                img = img.convert("L")
                img = ImageEnhance.Contrast(img).enhance(2)
                img = img.filter(ImageFilter.SHARPEN)
                text += pytesseract.image_to_string(img, lang="ara+eng", config="--psm 6")

        if not text.strip():
            print("❌ OCR failed.")
            return

        print("🧠 Sending PDF content to AI...")
        r   = _deps.safe_chat(model=_model(), messages=[{
            "role": "user",
            "content": (
                "Extract ONLY real information from this document.\n\n"
                'Return STRICT JSON format only:\n\n'
                '{\n"company": "",\n"date": "",\n"total_amount": "",\n'
                '"invoice_number": "",\n"details": ""\n}\n\n'
                "Do NOT guess. If something missing leave it empty.\n\n"
                f"Document:\n{text[:get_token_limit()]}"
            ),
        }])
        raw = _deps.get_response(r)
        print("\n🤖 PDF Summary:")
        print(raw)
        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                print("✅ JSON Parsed Successfully")
                ctx = _deps.project_context if _deps.project_context is not None else project_context
                if ctx:
                    for item in ctx:
                        if item["path"] == file_path:
                            item["data"] = data
                            break
                if _deps.save_project_context:
                    _deps.save_project_context()
            else:
                print("⚠ No JSON found.")
        except Exception as e:
            print("⚠ JSON parse error:", e)
    except Exception as e:
        print(f"❌ PDF error: {e}")


def handle_word_file(file_path: str) -> None:
    _require_injected()
    from docx import Document
    try:
        print("📄 Reading Word file...")
        doc  = Document(file_path)
        text = "\n".join(p.text for p in doc.paragraphs)[:get_token_limit()]
        print("🧠 Sending Word content to AI...")
        r = _deps.safe_chat(model=_model(), messages=[{
            "role": "user", "content": f"Summarize this document:\n\n{text}",
        }])
        print("\n🤖 Word Summary:")
        print(_deps.get_response(r))
    except Exception as e:
        print(f"❌ Word error: {e}")


def handle_excel_file(file_path: str) -> None:
    _require_injected()
    import openpyxl
    try:
        print("📊 Reading Excel file...")
        wb    = openpyxl.load_workbook(file_path, data_only=True)
        sheet = wb.active
        text  = "\n".join(str(row) for row in sheet.iter_rows(values_only=True))[:get_token_limit()]
        print("🧠 Sending Excel content to AI...")
        r = _deps.safe_chat(model=_model(), messages=[{
            "role": "user", "content": f"Explain this excel data:\n\n{text}",
        }])
        print("\n🤖 Excel Analysis:")
        print(_deps.get_response(r))
    except Exception as e:
        print(f"❌ Excel error: {e}")


def handle_ppt_file(file_path: str) -> None:
    _require_injected()
    from pptx import Presentation
    try:
        print("📽 Reading PowerPoint...")
        prs  = Presentation(file_path)
        text = "\n".join(
            shape.text for slide in prs.slides
            for shape in slide.shapes if hasattr(shape, "text")
        )[:get_token_limit()]
        print("🧠 Sending PowerPoint content to AI...")
        r = _deps.safe_chat(model=_model(), messages=[{
            "role": "user", "content": f"Summarize this presentation:\n\n{text}",
        }])
        print("\n🤖 PPT Summary:")
        print(_deps.get_response(r))
    except Exception as e:
        print(f"❌ PowerPoint error: {e}")


# ── Attach tool ───────────────────────────────────────────────────────────────

def attach_tool(file_path: str) -> None:
    _require_injected()
    if not os.path.exists(file_path):
        print("❌ File not found.")
        return

    file_type = detect_file_type(file_path)

    # Resolve active project_context (prefer injected, fall back to module-level alias)
    ctx = _deps.project_context if _deps.project_context is not None else project_context
    contexts = [ctx] if ctx is not None else []
    try:
        from state_manager import project_context as canonical_context
        if canonical_context is not None and all(c is not canonical_context for c in contexts):
            contexts.append(canonical_context)
    except Exception:
        pass

    # Replace live_screen frames — mutate in-place to keep reference valid
    if "live_screen" in file_path and _deps._state is not None:
        for one_context in contexts:
            one_context[:] = [
                item for item in one_context
                if "live_screen" not in item["path"]
            ]

    already_attached = any(
        item["path"] == file_path
        for one_context in contexts
        for item in one_context
    )
    if contexts and not already_attached:
        entry = {"path": file_path, "type": file_type}
        for one_context in contexts:
            one_context.append(dict(entry))
    else:
        print("⚡ File already in context, skipped.")

    if _deps.save_project_context:
        _deps.save_project_context()
    elif save_project_context:
        save_project_context()
