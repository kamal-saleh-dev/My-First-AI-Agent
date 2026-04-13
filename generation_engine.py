# generation_tool.py — Full project/game generation pipeline
# Extracted from agent.py chat_tool() — handles planning → generation → review → save

import os
import re
import sys
import time
import shutil

from logger        import log, safe_print
from llm_client    import safe_chat, get_response
import llm_client
import config as _cfg
from errors        import GenerationError, CompileError, ValidationError, TemplateError
from profiler      import profiler
from domain_sandbox import get_sandbox
from recovery      import RecoveryContext, get_checkpoint_manager

from compiler_tools   import (compile_check_csharp, llm_fix_compile_errors,
                               detect_programming_domain, validate_code, LANGUAGE_RULES)
from unity_pipeline   import auto_fix_unity_code
from unreal_templates import save_unreal_scripts
from launcher         import launch_website
from metrics          import metrics
from model_router     import DOMAIN_REGISTRY

from planner import (
    plan_scripts, apply_role_fixes, normalize_script_pairs,
    get_fallback_plan, get_unreal_fallback,
    get_cached_plan, set_cached_plan,
)

# ── Template imports are LAZY — not loaded at module import time ─────────────
# This keeps agent startup fast. Each function below imports only when called.

def _unity_tpl():
    from template_cache import get_unity_templates
    return get_unity_templates()

def _unreal_tpl():
    from template_cache import get_unreal_templates
    return get_unreal_templates()

def _dotnet_tpl():
    from dotnet_templates import DOTNET_SYSTEM_PROMPT, get_dotnet_template
    return DOTNET_SYSTEM_PROMPT, get_dotnet_template

def _react_tpl():
    from react_templates import REACT_SYSTEM_PROMPT, get_react_template
    return REACT_SYSTEM_PROMPT, get_react_template

def _angular_tpl():
    from angular_templates import ANGULAR_SYSTEM_PROMPT, get_angular_template
    return ANGULAR_SYSTEM_PROMPT, get_angular_template

def _html_tpl():
    from html_templates import HTML_SYSTEM_PROMPT, get_html_template
    return HTML_SYSTEM_PROMPT, get_html_template

def _sql_tpl():
    from sql_templates import SQL_SYSTEM_PROMPT, get_sql_template
    return SQL_SYSTEM_PROMPT, get_sql_template

def _python_tpl():
    from python_templates import PYTHON_SYSTEM_PROMPT, get_python_template
    return PYTHON_SYSTEM_PROMPT, get_python_template


def _get_model() -> str:
    return llm_client.DEFAULT_MODEL


# ═══════════════════════════════════════════════════════════
# ENGINE DETECTION
# ═══════════════════════════════════════════════════════════

def detect_engine(task: str, hint_domain: str = "general") -> str:
    """Detect target engine/framework from task text."""
    EXPLICIT = {
        "unity":  ["unity", "يونتي"],
        "unreal": ["unreal", "c++", "أنريل", "ue4", "ue5"],
    }
    t = task.lower()
    for eng, kws in EXPLICIT.items():
        if any(kw in t for kw in kws):
            return eng

    if hint_domain in ("unity", "unreal", "dotnet", "react", "angular", "html", "sql", "python"):
        return hint_domain

    # Default game engine
    return "unity" if "unreal" not in t else "unreal"


# ═══════════════════════════════════════════════════════════
# PROJECT NAME EXTRACTION
# ═══════════════════════════════════════════════════════════

_STOP_WORDS = {
    "make","create","build","a","an","the","with","using","in","for",
    "website","site","app","api","web","game","full","complete","simple",
    "server","database","project","script","unity","unreal","python",
    "react","angular","html","sql","fastapi","flask","dotnet","asp",
}

def extract_project_name(task: str, engine: str) -> str:
    """Extract a clean project name from the task description."""
    model = _get_model()
    r = safe_chat(model=model, messages=[{
        "role": "user",
        "content": f"Extract the game or project name from this text. If none, reply ONLY with 'NONE'. Text: '{task}'"
    }])
    extracted = get_response(r).strip()

    if "NONE" in extracted.upper() or len(extracted) >= 30:
        words = [w for w in re.sub(r"[^a-z0-9 ]", "", task.lower()).split()
                 if w not in _STOP_WORDS and len(w) > 2]
        default = "MyGame" if engine in ("unity", "unreal") else "MyProject"
        return "_".join(words[:3]).title() if words else default

    engine_words = {"unity","unreal","godot","pygame","monogame","gamemaker","cocos"}
    proj_words = [w for w in extracted.strip().lower().split() if w not in engine_words]
    if not proj_words:
        proj_words = [w for w in task.lower().replace("make","").replace("create","").replace("build","").split()
                      if len(w) > 3 and w not in engine_words]
    return "_".join(w.capitalize() for w in proj_words[:4])[:40] or "MyGame"


# ═══════════════════════════════════════════════════════════
# TEMPLATE ROUTER
# ═══════════════════════════════════════════════════════════

def get_template(script_name: str, role: str, engine: str):
    """Return a skeleton template for the given script/role/engine, or None."""
    if engine == "dotnet":
        _, fn = _dotnet_tpl();  return fn(script_name, role)
    if engine == "react":
        _, fn = _react_tpl();   return fn(script_name, role)
    if engine == "angular":
        _, fn = _angular_tpl(); return fn(script_name, role)
    if engine == "html":
        _, fn = _html_tpl();    return fn(script_name, role)
    if engine == "sql":
        _, fn = _sql_tpl();     return fn(script_name, role)
    if engine == "python":
        _, fn = _python_tpl();  return fn(script_name, role)
    if engine == "unreal":
        _, _gut, _ = _unreal_tpl()
        tpl = _gut(script_name, role)
        return tpl if tpl else None
    # Unity / fallback — use UNIVERSAL_TEMPLATES
    UNIVERSAL_TEMPLATES, TEMPLATED_ROLES, _, _ = _unity_tpl()
    if role in TEMPLATED_ROLES:
        tpl = UNIVERSAL_TEMPLATES.get(role)
        return tpl.format(name=script_name) if tpl else None
    return None


def get_fill_template(script_name: str, role: str):
    """Return a fill-skeleton for Unity scripts, or None."""
    _, _, FILL_TEMPLATES, _ = _unity_tpl()
    if role not in FILL_TEMPLATES:
        return None
    defaults = {
        "fill_update": "// update logic here",
        "fill_fixed_update": "// physics here",
        "fill_extra": "// extra methods",
        "fill_attack": "// attack logic",
        "fill_collision": "// collision logic",
        "fill_effect": "// apply power-up effect",
        "fill_fields": "// fields here",
        "fill_start": "// init here",
        "fill_methods": "// methods here",
    }
    return FILL_TEMPLATES[role].format(name=script_name, **defaults)


# ═══════════════════════════════════════════════════════════
# ENGINE CONFIG
# ═══════════════════════════════════════════════════════════

_UNITY_SYSTEM = """You are a senior Unity C# developer.
RULES:
- Use C# with MonoBehaviour.
- All variables used must be declared first with appropriate default values.
- NO placeholders, NO //TODO, NO empty methods. Implement full logic.
- For 2D games, ALWAYS use Rigidbody2D, Collider2D, and 2D physics callbacks.
- Use Vector3.Distance() instead of .distanceTo().
- Access Singleton managers using .Instance (e.g., GameManager.Instance.AddScore()).
- Use GameObject.FindGameObjectsWithTag (include GameObject prefix).
- Return ONLY one ```csharp code block."""

def _get_engine_cfg(engine: str) -> dict:
    """Return engine config, resolving lazy template imports on demand."""
    if engine == "unity":
        return {"system": _UNITY_SYSTEM, "lang": "Unity C#", "block": "csharp", "skip_template": False}
    if engine == "unreal":
        sys_prompt, _, _ = _unreal_tpl()
        return {"system": sys_prompt, "lang": "Unreal C++", "block": "cpp", "skip_template": True}
    if engine in ("dotnet", "dotnet_web"):
        sys_prompt, _ = _dotnet_tpl()
        return {"system": sys_prompt, "lang": "ASP.NET Core C#", "block": "csharp", "skip_template": False}
    if engine == "react":
        sys_prompt, _ = _react_tpl()
        return {"system": sys_prompt, "lang": "React.js", "block": "jsx", "skip_template": False}
    if engine == "angular":
        sys_prompt, _ = _angular_tpl()
        return {"system": sys_prompt, "lang": "Angular TypeScript", "block": "typescript", "skip_template": False}
    if engine == "html":
        sys_prompt, _ = _html_tpl()
        return {"system": sys_prompt, "lang": "HTML/CSS/JS", "block": "html", "skip_template": False}
    if engine == "sql":
        sys_prompt, _ = _sql_tpl()
        return {"system": sys_prompt, "lang": "SQL", "block": "sql", "skip_template": False}
    if engine == "python":
        sys_prompt, _ = _python_tpl()
        return {"system": sys_prompt, "lang": "Python", "block": "python", "skip_template": False}
    return {"system": _UNITY_SYSTEM, "lang": "Unity C#", "block": "csharp", "skip_template": False}

# Keep ENGINE_CFG as a compatibility alias (lazy — built on first access)
class _LazyCfg:
    def get(self, k, default=None):
        return _get_engine_cfg(k) if k else default
    def __getitem__(self, k):
        return _get_engine_cfg(k)

ENGINE_CFG = _LazyCfg()

WEB_ENGINES = {"dotnet", "react", "angular", "html", "sql", "python"}
BLOCK_MAP   = {"html":"html","css":"css","javascript":"javascript","react":"jsx",
               "angular":"typescript","sql":"sql","python":"python","dotnet":"csharp"}


# ═══════════════════════════════════════════════════════════
# SINGLE SCRIPT GENERATION
# ═══════════════════════════════════════════════════════════

def _generate_single(script_name: str, script_role: str, engine: str,
                     task: str, script_pairs: list, eng_cfg: dict,
                     generated_context: dict, model_name: str) -> tuple[str, bool]:
    """
    Generate code for one script.
    Returns (code_response, used_template).
    """
    template    = None if eng_cfg["skip_template"] else get_template(script_name, script_role, engine)
    used_template = False
    block_type  = BLOCK_MAP.get(engine, "csharp")

    # ── Template path ─────────────────────────────────────────
    if template:
        print(f"📐 Using template [{script_role}] for {script_name}", flush=True)

        if engine in WEB_ENGINES:
            sibling_pages = [f"{n}.html" for n, r in script_pairs
                             if r in ("page","component","layout") and n != script_name]
            siblings_hint = f"\nOTHER PAGES: {', '.join(sibling_pages)}" if sibling_pages else ""

            customize_prompt = f"""You are a senior {engine} developer.
Customize this template for: {task}
File: {script_name} (role: {script_role}){siblings_hint}

SKELETON:
{template}

RULES:
- Replace ALL generic content with real content for: {task}
- Return ONLY one ```{block_type} code block
- No explanations outside the code block"""

            r = safe_chat(model=_get_model(), messages=[
                {"role": "system", "content": eng_cfg["system"]},
                {"role": "user",   "content": customize_prompt}
            ])
            code_response = get_response(r)
        else:
            code_response = f"```{block_type}\n{template}\n```"
            used_template = True

        generated_context[script_name] = template

    # ── LLM generation path ───────────────────────────────────
    else:
        context_block = _build_context_block(generated_context)
        skeleton      = get_fill_template(script_name, script_role)
        _, _, _, ROLE_FILL_RULES = _unity_tpl()
        fill_rules    = ROLE_FILL_RULES.get(script_role, "")

        if skeleton and engine == "unity":
            code_response = _generate_with_skeleton(
                script_name, script_role, task, skeleton,
                fill_rules, context_block, eng_cfg, model_name, block_type
            )
        else:
            code_response = _generate_fresh(
                script_name, script_role, task, engine,
                context_block, eng_cfg, model_name, block_type
            )

    return code_response, used_template


def _build_context_block(generated_context: dict) -> str:
    if not generated_context:
        return ""
    parts = []
    for prev_name, prev_code in generated_context.items():
        sig_lines = [l.strip() for l in prev_code.split('\n')
                     if any(l.strip().startswith(k) for k in
                            ['public class','public enum','public interface',
                             'public void','public int','public float',
                             'public bool','public string','public List',
                             'public static','private void','    public'])]
        parts.append(f"// {prev_name}.cs signatures:\n" + '\n'.join(sig_lines[:15]))
    return "ALREADY GENERATED SCRIPTS (use these exact signatures):\n" + '\n\n'.join(parts)


def _generate_with_skeleton(script_name, script_role, task, skeleton,
                             fill_rules, context_block, eng_cfg, model_name, block_type):
    fill_prompt = f"""You are a Unity C# developer. Complete this script for the game: {task}

SCRIPT NAME: {script_name}
ROLE: {script_role}

{context_block}

HERE IS THE SKELETON — replace every // FILL: comment with real working code:

```csharp
{skeleton}
```

{fill_rules.format(task=task, name=script_name) if fill_rules else ""}

RULES:
- Keep ALL existing method signatures exactly as they are
- Replace EVERY // FILL: ... line with real implementation
- Do NOT add new class declarations or enums that exist in other scripts above
- Do NOT leave any // FILL: markers in the output
- Return ONLY one ```csharp code block"""

    r = safe_chat(model=model_name, messages=[
        {"role": "system", "content": eng_cfg["system"]},
        {"role": "user",   "content": fill_prompt}
    ])
    result = get_response(r)

    if "// FILL:" in result or "```" not in result:
        print(f"⚠️ LLM left FILL markers in {script_name} — using skeleton", flush=True)
        result = f"```csharp\n{skeleton}\n```"
    return result


def _generate_fresh(script_name, script_role, task, engine,
                    context_block, eng_cfg, model_name, block_type):
    if engine in WEB_ENGINES:
        prompt = f"""Write a {eng_cfg['lang']} file named {script_name} for: {task}

ROLE: {script_role}

RULES:
1. Write complete, production-ready {eng_cfg['lang']} code
2. No placeholders, no TODO, no empty functions
3. Return ONLY one ```{eng_cfg['block']} code block"""
    else:
        prompt = f"""Write a {eng_cfg['lang']} script named {script_name} for this game: {task}

ROLE: {script_role}

{context_block}

UNIVERSAL RULES:
1. Use correct namespaces
2. Class declaration: public class {script_name} : MonoBehaviour
3. Array initialization in Start() or Awake() — NEVER at field declaration
4. Do NOT redeclare enums/classes from other scripts above
5. Declare ALL variables before using them
6. NO empty method bodies, NO placeholders, NO TODO
7. Return ONLY one ```{eng_cfg['block']} code block"""

    r = safe_chat(model=model_name, messages=[
        {"role": "system", "content": eng_cfg["system"]},
        {"role": "user",   "content": prompt}
    ])
    result = get_response(r)

    # Regenerate if placeholders detected
    PLACEHOLDER_SIGNS = ["// add","// todo","// replace","/* ","your logic",
                         "your code","implement here","add logic","assuming"]
    if any(p in result.lower() for p in PLACEHOLDER_SIGNS):
        print(f"⚠️ Placeholder in {script_name}, regenerating...", flush=True)
        r2 = safe_chat(model=model_name, messages=[
            {"role": "system", "content": eng_cfg["system"]},
            {"role": "user",   "content": f"Rewrite {script_name} with NO placeholders and NO empty methods. Real code only.\nPrevious:\n{result}"}
        ])
        result = get_response(r2)
    return result


# ═══════════════════════════════════════════════════════════
# REVIEW PASS
# ═══════════════════════════════════════════════════════════

_ROLE_RULES = {
    "player":      "- Player moves with WASD/arrows using Rigidbody2D.velocity — do NOT use transform.Translate",
    "enemy":       "- Asteroid enemies move DOWNWARD (Vector3.down) — do NOT chase player",
    "powerup":     "- PowerUps FALL DOWN (Vector3.down) — NEVER move up",
    "background":  "- Background scrolls LEFT (negative X direction)",
    "spawner":     "- Use spawnPoints array for spawn positions",
    "projectile":  "- Bullet moves in transform.up direction — Destroy after 3 seconds",
    "collectible": "- Collectible stays STILL — Use OnTriggerEnter2D to detect player",
}

_WEB_REVIEW_RULES = {
    "html":       "- Replace generic placeholders with real content\n- Ensure all href links point to actual sibling files\n- Keep Bootstrap structure intact",
    "css":        "- Remove any non-CSS lines\n- Keep all :root variables\n- No placeholders",
    "javascript": "- Replace placeholder API endpoints with realistic ones\n- No TODO comments or empty functions",
    "react":      "- Replace all placeholder text with real content\n- Ensure imports are correct",
    "angular":    "- Replace all placeholder text with real content\n- Ensure @Component selector is correct",
    "sql":        "- Replace generic table/column names with domain-appropriate names\n- Ensure all FK references are valid",
    "python":     "- Replace placeholder functions with real implementations\n- No TODO or pass-only functions",
    "dotnet":     "- Replace placeholder controller actions with real implementations\n- No TODO comments",
}


def _review_script(script_name: str, script_role: str, engine: str,
                   code_response: str, model_name: str) -> str:
    """Run one review/fix pass on a generated script. Returns improved code."""
    block_type = BLOCK_MAP.get(engine, "csharp")

    if engine == "unreal":
        return _review_unreal(script_name, script_role, code_response, model_name)

    if engine in WEB_ENGINES:
        return _review_web(script_name, engine, code_response, model_name, block_type)

    # Unity review
    extra_rule = _ROLE_RULES.get(script_role, "")
    review_prompt = f"""Fix ALL bugs in this Unity C# script named {script_name} (role: {script_role}):

ROLE-SPECIFIC RULES (CRITICAL):
{extra_rule}

GENERAL BUGS TO FIX:
1. Variables used but never declared → declare them
2. FindGameObjectsWithTag without GameObject. prefix → fix it
3. Null check WRONG: if (x != null) x = GetComponent → RIGHT: if (x == null) x = GetComponent
4. Empty method bodies → implement real logic
5. Class name MUST stay exactly: {script_name}

Return the FIXED script as ONE ```csharp block.

Script to fix:
{code_response}"""

    r = safe_chat(model=model_name, messages=[
        {"role": "system", "content": "Unity C# bug fixer. Return ONLY one ```csharp block."},
        {"role": "user",   "content": review_prompt}
    ])
    reviewed = get_response(r)
    if "```" not in reviewed:
        return code_response
    result = auto_fix_unity_code(reviewed)
    # Enforce class name
    result = re.sub(
        r'(public\s+class\s+)\w+(\s*:\s*MonoBehaviour)',
        rf'\g<1>{script_name}\2',
        result
    )
    return result


def _review_unreal(script_name, script_role, code_response, model_name):
    blocks = re.findall(r"```[a-zA-Z]*\n?(.*?)```", code_response, re.DOTALL)
    if len(blocks) < 2:
        print(f"⚠ Only {len(blocks)} block — forcing header+cpp for {script_name}...", flush=True)
        fp = f"""Write EXACTLY TWO ```cpp blocks for Unreal class {script_name}.
Block 1 = HEADER (.h): #pragma once, #include "CoreMinimal.h", {script_name}.generated.h, UCLASS, GENERATED_BODY(), declarations
Block 2 = CPP (.cpp): #include "{script_name}.h", ALL function implementations

Output ONLY two code blocks, nothing else."""
        r2 = safe_chat(model=model_name, messages=[
            {"role": "system", "content": UNREAL_SYSTEM_PROMPT},
            {"role": "user",   "content": fp}
        ])
        code_response = get_response(r2)

    _, _, _guct = _unreal_tpl()
    ref_cpp  = _guct(script_name, script_role)
    ref_note = f"\n\nREFERENCE IMPLEMENTATION (adapt to {script_name}):\n```cpp\n{ref_cpp[:600]}\n```" if ref_cpp else ""
    review_prompt = f"""Fix this Unreal C++ file: {script_name}

MANDATORY FIXES:
1. #pragma once at top of header
2. GENERATED_BODY() in class body
3. .generated.h MUST match class name
4. ALL float/int UPROPERTY must have REAL C++ = defaults
5. EVERY function in CPP must be declared in header
6. REPLACE ALL placeholders with REAL code
7. Die(): AActor subclass → Destroy(); UActorComponent → GetOwner()->Destroy();
8. IsValid: if (IsValid(MyVar)) — NEVER "if (MyVar IsValid())"
9. UFUNCTION() macro belongs in HEADER only
10. ALL floats initialized with = not Meta=(DefaultValue)

Return ONLY the fixed ```cpp blocks (header first, then cpp).
{ref_note}

{code_response}"""

    r_rev = safe_chat(model=model_name, messages=[
        {"role": "system", "content": UNREAL_SYSTEM_PROMPT},
        {"role": "user",   "content": review_prompt}
    ])
    reviewed = get_response(r_rev)
    return reviewed if "```" in reviewed else code_response


def _review_web(script_name, engine, code_response, model_name, block_type):
    rules = _WEB_REVIEW_RULES.get(engine, "- Fix any placeholders or generic content")
    review_prompt = f"""Review and fix this {engine} file named {script_name}:

RULES TO ENFORCE:
{rules}

Return ONLY one ```{block_type} code block. No explanations.

File to fix:
{code_response}"""

    r = safe_chat(model=model_name, messages=[
        {"role": "system", "content": f"You are a senior {engine} developer. Fix code issues and return only a code block."},
        {"role": "user",   "content": review_prompt}
    ])
    reviewed = get_response(r)
    return reviewed if "```" in reviewed else code_response


# ═══════════════════════════════════════════════════════════
# COMPILE FIX LOOP (Unity only)
# ═══════════════════════════════════════════════════════════

def _compile_fix_loop(script_name: str, code_response: str,
                      generated_context: dict, script_names: list,
                      model_name: str,
                      max_attempts: int = None) -> str:
    if max_attempts is None: max_attempts = _cfg.COMPILE_FIX_ATTEMPTS
    for attempt in range(max_attempts):
        errors = compile_check_csharp(script_name, code_response,
                                      generated_context, planned_scripts=script_names)
        if not errors:
            return code_response

        print(f"🔧 Compile errors ({len(errors)}) — fixing attempt {attempt+1}/{max_attempts}...", flush=True)
        for e in errors[:5]:
            print(f"   {e}", flush=True)

        ctx = ""
        if generated_context:
            ctx_parts = []
            for pn, pc in generated_context.items():
                sigs = [l.strip() for l in pc.split('\n')
                        if any(l.strip().startswith(k)
                               for k in ['public class','public enum','public void',
                                         'public int','public float','public bool','public static'])]
                ctx_parts.append(f"// {pn}.cs:\n" + '\n'.join(f"  {s}" for s in sigs[:10]))
            ctx = "CONTEXT (existing scripts):\n" + '\n\n'.join(ctx_parts)

        fixed = llm_fix_compile_errors(script_name, code_response, errors, model_name, ctx)
        if "```" in fixed:
            code_response = auto_fix_unity_code(fixed)
            code_response = re.sub(
                r'(public\s+class\s+)\w+(\s*:\s*MonoBehaviour)',
                rf'\g<1>{script_name}\2',
                code_response
            )

    remaining = compile_check_csharp(script_name, code_response,
                                     generated_context, planned_scripts=script_names)
    if remaining:
        print(f"⚠️ {script_name} still has {len(remaining)} error(s) after {max_attempts} attempts", flush=True)
    return code_response


# ═══════════════════════════════════════════════════════════
# DOTNET POST-PROCESSING
# ═══════════════════════════════════════════════════════════

def _post_process_dotnet(project_name: str):
    """Create missing .csproj, Program.cs, Views scaffold for dotnet projects."""
    proj_folder = os.path.join("Generated_Scripts", project_name.replace(" ", "_"))
    if not os.path.exists(proj_folder):
        return

    # Remove duplicate Program.* files
    for fn in list(os.listdir(proj_folder)):
        if fn.lower().startswith("program.") and fn.lower() != "program.cs":
            os.remove(os.path.join(proj_folder, fn))
            print(f"🗑 Removed duplicate: {fn}", flush=True)

    # Auto-create AppDbContext if missing
    db_path = os.path.join(proj_folder, "AppDbContext.cs")
    if not os.path.exists(db_path):
        entity_names = []
        for fn in os.listdir(proj_folder):
            if not fn.endswith(".cs"): continue
            if fn in ("AppDbContext.cs", "Program.cs"): continue
            if fn.endswith(("Controller.cs","Service.cs","Repository.cs","Dto.cs","Middleware.cs")): continue
            base = fn[:-3]
            if base.endswith("ViewModel") or base.startswith("I"): continue
            entity_names.append(base)
        dbsets = "\n".join(
            f"    public DbSet<{e}> {e if e.endswith('s') else e + 's'} {{ get; set; }} = null!;"
            for e in sorted(dict.fromkeys(entity_names))
        )
        with open(db_path, "w", encoding="utf-8") as f:
            f.write(f"""using Microsoft.EntityFrameworkCore;
public class AppDbContext : DbContext
{{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) {{ }}
{chr(10) + dbsets + chr(10) if dbsets else ""}
}}
""")
        print("📄 Auto-created: AppDbContext.cs", flush=True)

    # Move loose .cshtml files into Views/<Controller>/<Action>.cshtml
    ctrl_map = {}
    for fn in os.listdir(proj_folder):
        if fn.endswith("Controller.cs"):
            cname = fn.replace("Controller.cs", "")
            ctrl_map[cname.lower()] = cname
    default_ctrl = list(ctrl_map.values())[0] if ctrl_map else "Home"

    for fn in list(os.listdir(proj_folder)):
        if not fn.endswith(".cshtml") or fn.startswith("_"): continue
        src       = os.path.join(proj_folder, fn)
        dest_ctrl = default_ctrl
        fn_lower  = fn.lower().replace(".cshtml", "")
        for ck, cv in ctrl_map.items():
            if ck in fn_lower:
                dest_ctrl = cv; break
        action = "Index"
        for act in ["index","form","create","edit","details","delete","list"]:
            if act in fn_lower:
                action = "Create" if act == "form" else act.capitalize()
                break
        views_dir = os.path.join(proj_folder, "Views", dest_ctrl)
        os.makedirs(views_dir, exist_ok=True)
        dest = os.path.join(views_dir, f"{action}.cshtml")
        if not os.path.exists(dest):
            shutil.move(src, dest)
            print(f"📁 Moved {fn} → Views/{dest_ctrl}/{action}.cshtml", flush=True)
        else:
            os.remove(src)

    # Create .csproj + Program.cs + Views scaffold if missing
    csproj_path = os.path.join(proj_folder, f"{project_name}.csproj")
    if os.path.exists(csproj_path):
        return

    csproj = """<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.EntityFrameworkCore" Version="8.0.0" />
    <PackageReference Include="Microsoft.EntityFrameworkCore.Sqlite" Version="8.0.0" />
    <PackageReference Include="Microsoft.EntityFrameworkCore.Design" Version="8.0.0">
      <PrivateAssets>all</PrivateAssets>
      <IncludeAssets>runtime; build; native; contentfiles; analyzers</IncludeAssets>
    </PackageReference>
    <PackageReference Include="Microsoft.AspNetCore.Mvc.NewtonsoftJson" Version="8.0.0" />
  </ItemGroup>
</Project>
"""
    program_cs = """using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddControllersWithViews();
builder.Services.AddDbContext<AppDbContext>(opt =>
    opt.UseSqlite("Data Source=app.db"));

var app = builder.Build();
if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Home/Error");
    app.UseHsts();
}
app.UseHttpsRedirection();
app.UseStaticFiles();
app.UseRouting();
app.UseAuthorization();

using (var scope = app.Services.CreateScope())
{
    try {
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        db.Database.EnsureCreated();
    } catch { }
}

app.MapControllerRoute(name: "default", pattern: "{controller=Home}/{action=Index}/{id?}");
app.Run();
"""
    layout_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>@ViewData["Title"] - MyApp</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" />
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container"><a class="navbar-brand" href="/">MyApp</a></div>
    </nav>
    <main class="container mt-4">@RenderBody()</main>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    @await RenderSectionAsync("Scripts", required: false)
</body>
</html>
"""
    try:
        with open(csproj_path, "w", encoding="utf-8") as f: f.write(csproj)
        prog = os.path.join(proj_folder, "Program.cs")
        if not os.path.exists(prog):
            with open(prog, "w", encoding="utf-8") as f: f.write(program_cs)
        shared_dir = os.path.join(proj_folder, "Views", "Shared")
        os.makedirs(shared_dir, exist_ok=True)
        os.makedirs(os.path.join(proj_folder, "Views", "Home"), exist_ok=True)
        os.makedirs(os.path.join(proj_folder, "Controllers"), exist_ok=True)
        home_ctrl = os.path.join(proj_folder, "Controllers", "HomeController.cs")
        if not os.path.exists(home_ctrl):
            with open(home_ctrl, "w", encoding="utf-8") as f:
                f.write("using Microsoft.AspNetCore.Mvc;\npublic class HomeController : Controller\n{\n    public IActionResult Index() { return View(); }\n}\n")
        layout_path = os.path.join(shared_dir, "_Layout.cshtml")
        if not os.path.exists(layout_path):
            with open(layout_path, "w", encoding="utf-8") as f: f.write(layout_html)
        viewstart = os.path.join(proj_folder, "Views", "_ViewStart.cshtml")
        if not os.path.exists(viewstart):
            with open(viewstart, "w", encoding="utf-8") as f: f.write('@{ Layout = "_Layout"; }\n')
        viewimports = os.path.join(proj_folder, "Views", "_ViewImports.cshtml")
        if not os.path.exists(viewimports):
            with open(viewimports, "w", encoding="utf-8") as f:
                f.write("@using Microsoft.AspNetCore.Mvc.Razor\n@addTagHelper *, Microsoft.AspNetCore.Mvc.TagHelpers\n")
        print(f"📄 Created {project_name}.csproj + Views scaffold", flush=True)
    except Exception as e:
        print(f"⚠ csproj error: {e}", flush=True)


# ═══════════════════════════════════════════════════════════
# SCRIPT SAVING
# ═══════════════════════════════════════════════════════════

def extract_and_save_scripts(text: str, project_name: str,
                              forced_name: str = None,
                              forced_ext: str = None) -> bool:
    """
    Extract code blocks from LLM response and save to Generated_Scripts/<project>.
    Returns True if at least one file saved successfully.
    """
    pattern = r"```(?:[a-zA-Z0-9+#]*)\n?(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    if not matches:
        return False

    safe_name   = re.sub(r'[\\/*?:"<>|]', "", project_name).strip().replace(" ", "_")
    folder_name = os.path.join("Generated_Scripts", safe_name)
    os.makedirs(folder_name, exist_ok=True)

    # Unreal multi-file (header + cpp) — delegate
    first_domain = detect_programming_domain(matches[0])
    if first_domain in LANGUAGE_RULES and LANGUAGE_RULES[first_domain].get("type") == "multi":
        return save_unreal_scripts(matches, folder_name)

    all_valid = True
    for i, code in enumerate(matches):
        code = code.strip()
        code = re.sub(r'^```[a-zA-Z]*\n?', '', code).strip().rstrip('`').strip()
        code = (code.replace('\u2014', '--').replace('\u2013', '-')
                    .replace('\u2018', "'").replace('\u2019', "'")
                    .replace('\u201c', '"').replace('\u201d', '"'))

        domain_check = detect_programming_domain(code)
        if domain_check == "unity":
            code = auto_fix_unity_code(code)

        is_valid, result = validate_code(code, project_name)
        if not is_valid:
            _non_critical = ("test","config","schema","util","db","handler","settings","spec")
            if domain_check == "python" and any(w in project_name.lower() for w in _non_critical):
                print(f"⚠️ Validation warning: {result} — saving anyway", flush=True)
                result = code
            else:
                print(f"\n❌ Validation Failed: {result}")
                all_valid = False
                continue

        if isinstance(result, str) and len(result) > 50 and (
            "using " in result or "class " in result or "def " in result
            or "#include" in result or "<" in result
        ):
            code = result

        domain    = detect_programming_domain(code)
        extension = (forced_ext if forced_ext
                     else (LANGUAGE_RULES[domain]["extensions"][0]
                           if domain in LANGUAGE_RULES else ".txt"))

        if forced_name:
            class_name = forced_name
        else:
            m = re.search(r"class\s+(?:[A-Za-z0-9_]+\s+)?([A-Za-z_][A-Za-z0-9_]*)", code)
            class_name = m.group(1) if m else f"Script_{i}"

        if forced_name and class_name.lower().endswith(extension.lower()):
            file_name = class_name
        else:
            file_name = f"{class_name}{extension}"

        file_path = os.path.join(folder_name, file_name)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)
        log.save(f"Script saved: {file_path}")

    return all_valid


# ═══════════════════════════════════════════════════════════
# PYTHON PROJECT BUILDER HELPERS (used by project_tools.py)
# ═══════════════════════════════════════════════════════════

def build_structure(task: str, cwd: str = None) -> list:
    """
    Ask LLM for a Python project file structure and create empty files.
    cwd: base directory for all created files (no os.chdir needed).
    """
    base = cwd or os.getcwd()
    print("🔨 Designing structure...")
    r = safe_chat(model=_get_model(), messages=[{
        "role": "user",
        "content": (f"Return ONLY python project structure for {task}. "
                    "List files and folders line by line. NO explanation.")
    }])
    lines = get_response(r).split("\n")
    files = []
    for raw in lines:
        line = raw.strip()
        if not line or "```" in line or ":" in line: continue
        if line.startswith(("-","*")) or "Here is" in line or "structure" in line: continue
        if any(c in line for c in ["*","?","<",">","|",'"']): continue
        try:
            full_path = os.path.join(base, line)
            if line.endswith("/") or line.endswith("\\"):
                os.makedirs(full_path, exist_ok=True)
                print("📁 Folder:", line)
            else:
                folder = os.path.dirname(full_path)
                if folder:
                    os.makedirs(folder, exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write("")
                files.append(line)   # keep relative names for run_python lookup
                print("📄 File:", line)
        except Exception as e:
            print(f"⚠ Skipped bad path: {line} ({e})")

    if not files:
        main_path = os.path.join(base, "main.py")
        with open(main_path, "w", encoding="utf-8") as f:
            f.write("")
        files.append("main.py")
    return files


def generate_code(files: list, task: str, cwd: str = None) -> None:
    """
    Generate Python code for each file in the project.
    cwd: base directory where files live (no os.chdir needed).
    """
    base = cwd or os.getcwd()
    for file in files:
        print(f"⚙ Generating code for: {file}...")
        r = safe_chat(model=_get_model(), messages=[{
            "role": "user",
            "content": f"Write ONLY python code for {file} in {task}. NO markdown blocks. NO explanation."
        }])
        code = get_response(r).replace("```python", "").replace("```", "")
        if code.strip().startswith("Here is"):
            code = "# Generated code\n" + code.split("\n", 1)[1]
        full_path = os.path.join(base, file)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(code)
        print(f"✅ Written: {file}")


def auto_run_and_fix(task_description: str, initial_code: str,
                     max_attempts: int = 3) -> tuple:
    """
    Run Python code in a sandbox, auto-fix errors up to max_attempts.
    Returns (final_code, output_or_error_message).
    """
    import subprocess as _sp
    temp_file = "sandbox_test.py"
    current_code = initial_code

    for attempt in range(1, max_attempts + 1):
        print(f"🧪 Testing code (Attempt {attempt})...")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(current_code)
        try:
            result = _sp.run(
                [sys.executable, temp_file],
                capture_output=True, text=True, timeout=_cfg.PYTHON_SANDBOX_TIMEOUT
            )
            if result.returncode == 0:
                print(f"✅ Success on attempt {attempt}!")
                return current_code, result.stdout

            print(f"❌ Attempt {attempt} failed. Refactoring...")
            fix_prompt = (f"FIX THIS PYTHON CODE.\nTASK: {task_description}\n"
                          f"ERROR: {result.stderr}\nCODE TO FIX:\n{current_code}\n\n"
                          "RULES: Return ONLY the raw code. No markdown, no explanations.")
            r = safe_chat(model=_get_model(), messages=[{"role":"user","content":fix_prompt}])
            raw = get_response(r).replace("```python","").replace("```","").strip()
            # Safety: only accept if response looks like real Python code
            # Previous check was too weak ("import"/"print" alone not sufficient)
            has_code_structure = (
                ("def " in raw or "class " in raw or "import " in raw)
                and len(raw.splitlines()) >= 2  # at least 2 lines
            )
            if has_code_structure:
                current_code = raw
            # else: keep current_code, let next attempt try again

        except _sp.TimeoutExpired:
            return current_code, "❌ Execution timed out (Possible infinite loop)."
        except Exception as e:
            return current_code, f"❌ System Error: {str(e)}"

    return current_code, "⚠️ Could not fix code after max attempts."


# ═══════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════

def run_generation(task: str, engine: str, model_name: str,
                   project_name: str, save_session_fn=None) -> str:
    """
    Full generation pipeline: plan → generate → review → save → launch.
    Returns summary string.
    """
    IS_WEB  = engine in WEB_ENGINES
    icon    = "🌐" if IS_WEB else "🎮"
    label   = {"dotnet":"موقع","react":"موقع","angular":"موقع","html":"موقع",
               "sql":"قاعدة بيانات","python":"مشروع"}.get(engine, "لعبة")
    sandbox = get_sandbox(engine)

    print(f"\n{icon} Planning {engine.capitalize()} files...", flush=True)

    # ── Plan (timed) ───────────────────────────────────────────
    with profiler.track("planning", engine=engine):
        from dotnet_templates import DOTNET_PLANNING_PROMPT, DOTNET_FULLSTACK_PLANNING_PROMPT
        script_pairs = plan_scripts(
        task, engine, safe_chat, get_response,
        _get_model(), DOMAIN_REGISTRY,
        DOTNET_PLANNING_PROMPT, DOTNET_FULLSTACK_PLANNING_PROMPT
    )

    # Remove scripts named same as project
    project_key = re.sub(r"[^a-z0-9]", "", project_name.lower())
    script_pairs = [(n, r) for n, r in script_pairs
                    if re.sub(r"[^a-z0-9]", "", n.lower()) != project_key]
    script_pairs = script_pairs[:8]
    script_names = [p[0] for p in script_pairs]

    eng_cfg = _get_engine_cfg(engine)
    print(f"📋 Scripts to generate: {', '.join(script_names)}", flush=True)

    saved              = []
    failed             = []
    generated_context  = {}
    gen_start          = time.time()

    # ── Generate each script (with recovery checkpoint) ───────
    resume = get_checkpoint_manager().load(project_name) is not None
    with RecoveryContext(task, engine, project_name,
                         script_pairs, model_name, resume=resume) as ctx:
      script_pairs = ctx.remaining  # skip already-completed on resume

    for script_name, script_role in script_pairs:
        print(f"\n⚙️ Writing {script_name} ({engine}) ...", flush=True)

        # 1. Generate
        code_response, used_template = _generate_single(
            script_name, script_role, engine, task,
            script_pairs, eng_cfg, generated_context, model_name
        )

        # 2. Auto-fix Unity syntax
        if engine == "unity":
            code_response = auto_fix_unity_code(code_response)

        # 3. Review pass (skip if template was used as-is)
        if not used_template:
            print(f"🔍 Reviewing {script_name} ...", flush=True)
            code_response = _review_script(
                script_name, script_role, engine, code_response, model_name
            )

        # 4. Compile-fix loop (Unity only)
        if engine == "unity" and not used_template:
            code_response = _compile_fix_loop(
                script_name, code_response,
                generated_context, script_names, model_name
            )

        # 5. Save
        forced_ext = (DOMAIN_REGISTRY[engine]["get_ext"](script_name, script_role)
                      if engine in DOMAIN_REGISTRY and engine not in ("unity","unreal")
                      else None)
        success = extract_and_save_scripts(
            code_response, project_name,
            forced_name=script_name,
            forced_ext=forced_ext
        )

        if success:
            profiler.record(f"script_saved[{engine}]", time.time() - gen_start)
            ext = (DOMAIN_REGISTRY[engine]["get_ext"](script_name, script_role)
                   if engine in DOMAIN_REGISTRY and engine not in ("unity","unreal")
                   else ".cs" if engine == "unity" else "")
            saved.append(script_name + ext)
            # Store signatures for context
            m = re.search(r'```(?:csharp|cs)?\n(.*?)```', code_response, re.DOTALL)
            if m:
                full = m.group(1)
                sigs = [l for l in full.split("\n")
                        if re.match(r"\s*(public|private|void|float|int|bool|string|class|using)", l)]
                generated_context[script_name] = "\n".join(sigs[:20])
        else:
            failed.append(script_name)

    # ── Post-processing ───────────────────────────────────────
    if engine == "dotnet":
        _post_process_dotnet(project_name)

    # ── Metrics ───────────────────────────────────────────────
    gen_time = round(time.time() - gen_start, 1)
    log.info(f"⏱ Generation done in {gen_time}s — saved={len(saved)}")
    metrics.record_generation(bool(saved), engine, gen_time)
    metrics.save()

    # ── Summary ───────────────────────────────────────────────
    summary = f"{icon} تم إنشاء {label} {project_name}!\n\n"
    for s in saved:
        summary += f"   ✅ {s}\n"
    for s in failed:
        summary += f"   ❌ {s} فشل\n"
    summary += f"\n[ 💾 الملفات في: Generated_Scripts/{project_name.replace(' ', '_')} ]"

    print(f"\n🤖 Agent: {summary}\n\n", flush=True)

    # ── Launch browser (web engines) ──────────────────────────
    if engine in ("html", "react", "angular", "dotnet"):
        print("🌐 فاتح الـ website في الـ browser...", flush=True)
        launch_website(project_name, engine)

    if save_session_fn:
        save_session_fn()

    return summary
