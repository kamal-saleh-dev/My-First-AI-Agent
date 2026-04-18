# script_generator.py — Single-script generation logic
# Extracted from generation_engine.py
# Responsibility: given a script name/role/engine → produce code string

import re
from llm_client import safe_chat, get_response
import llm_client


def _get_model() -> str:
    return llm_client.DEFAULT_MODEL


# ── Lazy template loaders (no cost at import time) ────────────────────────────

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


# ── Module-level constants ────────────────────────────────────────────────────

WEB_ENGINES = {"dotnet", "react", "angular", "html", "sql", "python"}

BLOCK_MAP = {
    "html": "html", "css": "css", "javascript": "javascript",
    "react": "jsx", "angular": "typescript",
    "sql": "sql", "python": "python", "dotnet": "csharp",
}

_UNITY_SYSTEM = (
    "You are a senior Unity C# developer.\n"
    "RULES:\n"
    "- Use C# with MonoBehaviour.\n"
    "- All variables used must be declared first with appropriate default values.\n"
    "- NO placeholders, NO //TODO, NO empty methods. Implement full logic.\n"
    "- For 2D games, ALWAYS use Rigidbody2D, Collider2D, and 2D physics callbacks.\n"
    "- Use Vector3.Distance() instead of .distanceTo().\n"
    "- Access Singleton managers using .Instance (e.g., GameManager.Instance.AddScore()).\n"
    "- Use GameObject.FindGameObjectsWithTag (include GameObject prefix).\n"
    "- Return ONLY one ```csharp code block."
)


# ── Engine config ─────────────────────────────────────────────────────────────

def _get_engine_cfg(engine: str) -> dict:
    """Return engine config dict, loading templates lazily on demand."""
    if engine == "unity":
        return {"system": _UNITY_SYSTEM, "lang": "Unity C#",
                "block": "csharp", "skip_template": False}
    if engine == "unreal":
        sys_prompt, _, _ = _unreal_tpl()
        return {"system": sys_prompt, "lang": "Unreal C++",
                "block": "cpp", "skip_template": True}
    if engine in ("dotnet", "dotnet_web"):
        sys_prompt, _ = _dotnet_tpl()
        return {"system": sys_prompt, "lang": "ASP.NET Core C#",
                "block": "csharp", "skip_template": False}
    if engine == "react":
        sys_prompt, _ = _react_tpl()
        return {"system": sys_prompt, "lang": "React.js",
                "block": "jsx", "skip_template": False}
    if engine == "angular":
        sys_prompt, _ = _angular_tpl()
        return {"system": sys_prompt, "lang": "Angular TypeScript",
                "block": "typescript", "skip_template": False}
    if engine == "html":
        sys_prompt, _ = _html_tpl()
        return {"system": sys_prompt, "lang": "HTML/CSS/JS",
                "block": "html", "skip_template": False}
    if engine == "sql":
        sys_prompt, _ = _sql_tpl()
        return {"system": sys_prompt, "lang": "SQL",
                "block": "sql", "skip_template": False}
    if engine == "python":
        sys_prompt, _ = _python_tpl()
        return {"system": sys_prompt, "lang": "Python",
                "block": "python", "skip_template": False}
    # Fallback
    return {"system": _UNITY_SYSTEM, "lang": "Unity C#",
            "block": "csharp", "skip_template": False}


class _LazyCfg:
    """Backward-compatible lazy accessor for ENGINE_CFG[engine]."""
    def get(self, k, default=None):
        return _get_engine_cfg(k) if k else default
    def __getitem__(self, k):
        return _get_engine_cfg(k)

ENGINE_CFG = _LazyCfg()


# ── Template router ───────────────────────────────────────────────────────────

def get_template(script_name: str, role: str, engine: str):
    """Return a filled skeleton template string, or None."""
    if engine == "dotnet":
        _, fn = _dotnet_tpl();   return fn(script_name, role)
    if engine == "react":
        _, fn = _react_tpl();    return fn(script_name, role)
    if engine == "angular":
        _, fn = _angular_tpl();  return fn(script_name, role)
    if engine == "html":
        _, fn = _html_tpl();     return fn(script_name, role)
    if engine == "sql":
        _, fn = _sql_tpl();      return fn(script_name, role)
    if engine == "python":
        _, fn = _python_tpl();   return fn(script_name, role)
    if engine == "unreal":
        _, _gut, _ = _unreal_tpl()
        tpl = _gut(script_name, role)
        return tpl if tpl else None
    # Unity / fallback
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
        "fill_update":        "// update logic here",
        "fill_fixed_update":  "// physics here",
        "fill_extra":         "// extra methods",
        "fill_attack":        "// attack logic",
        "fill_collision":     "// collision logic",
        "fill_effect":        "// apply power-up effect",
        "fill_fields":        "// fields here",
        "fill_start":         "// init here",
        "fill_methods":       "// methods here",
    }
    return FILL_TEMPLATES[role].format(name=script_name, **defaults)


# ── Context block builder ─────────────────────────────────────────────────────

def _build_context_block(generated_context: dict) -> str:
    if not generated_context:
        return ""
    parts = []
    for prev_name, prev_code in generated_context.items():
        sig_lines = [
            l.strip() for l in prev_code.split("\n")
            if any(l.strip().startswith(k) for k in [
                "public class", "public enum", "public interface",
                "public void", "public int", "public float",
                "public bool", "public string", "public List",
                "public static", "private void", "    public",
            ])
        ]
        parts.append(f"// {prev_name}.cs signatures:\n" + "\n".join(sig_lines[:15]))
    return "ALREADY GENERATED SCRIPTS (use these exact signatures):\n" + "\n\n".join(parts)


# ── Private generation helpers ────────────────────────────────────────────────

def _generate_with_skeleton(script_name, script_role, task, skeleton,
                             fill_rules, context_block, eng_cfg, model_name, block_type):
    fill_prompt = (
        f"You are a Unity C# developer. Complete this script for the game: {task}\n\n"
        f"SCRIPT NAME: {script_name}\nROLE: {script_role}\n\n"
        f"{context_block}\n\n"
        f"HERE IS THE SKELETON — replace every // FILL: comment with real working code:\n\n"
        f"```csharp\n{skeleton}\n```\n\n"
        f"{fill_rules.format(task=task, name=script_name) if fill_rules else ''}\n\n"
        "RULES:\n"
        "- Keep ALL existing method signatures exactly as they are\n"
        "- Replace EVERY // FILL: ... line with real implementation\n"
        "- Do NOT add new class declarations or enums that exist in other scripts above\n"
        "- Do NOT leave any // FILL: markers in the output\n"
        "- Return ONLY one ```csharp code block"
    )
    r = safe_chat(model=model_name, messages=[
        {"role": "system", "content": eng_cfg["system"]},
        {"role": "user",   "content": fill_prompt},
    ])
    result = get_response(r)
    if "// FILL:" in result or "```" not in result:
        print(f"⚠️ LLM left FILL markers in {script_name} — using skeleton", flush=True)
        result = f"```csharp\n{skeleton}\n```"
    return result


def _generate_fresh(script_name, script_role, task, engine,
                    context_block, eng_cfg, model_name, block_type):
    if engine in WEB_ENGINES:
        prompt = (
            f"Write a {eng_cfg['lang']} file named {script_name} for: {task}\n\n"
            f"ROLE: {script_role}\n\n"
            "RULES:\n"
            f"1. Write complete, production-ready {eng_cfg['lang']} code\n"
            "2. No placeholders, no TODO, no empty functions\n"
            f"3. Return ONLY one ```{eng_cfg['block']} code block"
        )
    else:
        prompt = (
            f"Write a {eng_cfg['lang']} script named {script_name} for this game: {task}\n\n"
            f"ROLE: {script_role}\n\n"
            f"{context_block}\n\n"
            "UNIVERSAL RULES:\n"
            "1. Use correct namespaces\n"
            f"2. Class declaration: public class {script_name} : MonoBehaviour\n"
            "3. Array initialization in Start() or Awake() — NEVER at field declaration\n"
            "4. Do NOT redeclare enums/classes from other scripts above\n"
            "5. Declare ALL variables before using them\n"
            "6. NO empty method bodies, NO placeholders, NO TODO\n"
            f"7. Return ONLY one ```{eng_cfg['block']} code block"
        )

    r = safe_chat(model=model_name, messages=[
        {"role": "system", "content": eng_cfg["system"]},
        {"role": "user",   "content": prompt},
    ])
    result = get_response(r)

    PLACEHOLDER_SIGNS = [
        "// add", "// todo", "// replace", "/* ", "your logic",
        "your code", "implement here", "add logic", "assuming",
    ]
    if any(p in result.lower() for p in PLACEHOLDER_SIGNS):
        print(f"⚠️ Placeholder in {script_name}, regenerating...", flush=True)
        r2 = safe_chat(model=model_name, messages=[
            {"role": "system", "content": eng_cfg["system"]},
            {"role": "user",   "content": (
                f"Rewrite {script_name} with NO placeholders and NO empty methods."
                f" Real code only.\nPrevious:\n{result}"
            )},
        ])
        result = get_response(r2)
    return result


# ── Public API ────────────────────────────────────────────────────────────────

def generate_single(script_name: str, script_role: str, engine: str,
                    task: str, script_pairs: list, eng_cfg: dict,
                    generated_context: dict, model_name: str) -> tuple[str, bool]:
    """
    Generate code for one script.
    Returns (code_response, used_template).
    """
    template      = None if eng_cfg["skip_template"] else get_template(script_name, script_role, engine)
    used_template = False
    block_type    = BLOCK_MAP.get(engine, "csharp")

    # ── Template path ──────────────────────────────────────────────────────────
    if template:
        print(f"📐 Using template [{script_role}] for {script_name}", flush=True)

        if engine in WEB_ENGINES:
            sibling_pages = [
                f"{n}.html" for n, r in script_pairs
                if r in ("page", "component", "layout") and n != script_name
            ]
            siblings_hint = f"\nOTHER PAGES: {', '.join(sibling_pages)}" if sibling_pages else ""

            customize_prompt = (
                f"You are a senior {engine} developer.\n"
                f"Customize this template for: {task}\n"
                f"File: {script_name} (role: {script_role}){siblings_hint}\n\n"
                f"SKELETON:\n{template}\n\n"
                f"RULES:\n"
                f"- Replace ALL generic content with real content for: {task}\n"
                f"- Return ONLY one ```{block_type} code block\n"
                "- No explanations outside the code block"
            )
            r = safe_chat(model=_get_model(), messages=[
                {"role": "system", "content": eng_cfg["system"]},
                {"role": "user",   "content": customize_prompt},
            ])
            code_response = get_response(r)
        else:
            code_response = f"```{block_type}\n{template}\n```"
            used_template = True

        generated_context[script_name] = template

    # ── LLM generation path ────────────────────────────────────────────────────
    else:
        context_block = _build_context_block(generated_context)
        skeleton      = get_fill_template(script_name, script_role)
        _, _, _, ROLE_FILL_RULES = _unity_tpl()
        fill_rules    = ROLE_FILL_RULES.get(script_role, "")

        if skeleton and engine == "unity":
            code_response = _generate_with_skeleton(
                script_name, script_role, task, skeleton,
                fill_rules, context_block, eng_cfg, model_name, block_type,
            )
        else:
            code_response = _generate_fresh(
                script_name, script_role, task, engine,
                context_block, eng_cfg, model_name, block_type,
            )

    # ── Model Advisor: escalate if quality is low ────────────────────────────
    # Only escalate LLM-generated scripts (not verbatim templates).
    if not used_template:
        try:
            from model_advisor import assess_quality, escalate, _ESCALATE_THRESHOLD
            score, issues = assess_quality(
                code_response, engine, script_name,
                generated_context, [p[0] for p in script_pairs],
            )
            if score < (100 - _ESCALATE_THRESHOLD):
                code_response, _ = escalate(
                    task, script_name, script_role, engine,
                    model_name, code_response, eng_cfg,
                    script_pairs, generated_context, model_name,
                )
        except Exception as _adv_err:
            pass   # advisor failure never blocks generation

    return code_response, used_template
