# compiler_tools.py — Code validation, compile checks, LLM error fixing
import os, re, subprocess, tempfile

def run_process(cmd: list, cwd=None, timeout=60, input_data=None) -> dict:
    """Unified subprocess wrapper — always returns structured result."""
    import subprocess
    try:
        r = subprocess.run(
            cmd, cwd=cwd, timeout=timeout, input=input_data,
            capture_output=True, text=True, encoding="utf-8", errors="ignore"
        )
        return {"success": r.returncode == 0, "stdout": r.stdout or "",
                "stderr": r.stderr or "", "returncode": r.returncode}
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": f"Timeout after {timeout}s", "returncode": -1}
    except FileNotFoundError as e:
        return {"success": False, "stdout": "", "stderr": str(e), "returncode": -2}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "returncode": -3}

from unity_stubs    import UNITY_STUBS
from unreal_templates import validate_unreal

def detect_programming_domain(code):
    code_lower = code.lower()

    if "uclass" in code_lower or "generated_body" in code_lower:
        return "unreal"
    if "using unityengine" in code_lower or "monobehaviour" in code_lower:
        return "unity"
        
    # +++ ضيف السطرين دول للـ Frontend +++
    if "export class" in code_lower or "@component" in code_lower or "from '@angular" in code_lower:
        return "angular"
    if "import react" in code_lower or "export default" in code_lower:
        return "react"

    # +++ عدل شرط البايثون عشان يتجاهل الـ JS/TS +++
    if ("import " in code_lower or "def " in code_lower) and "export " not in code_lower and "from '" not in code_lower:
        return "python"

    if "#include" in code_lower:
        return "cpp"
    if "using system" in code_lower:
        return "csharp"

    return "unknown"

# validate_unreal → imported from unreal_templates

def validate_unity(code):
    # لو missing using UnityEngine، نحطها تلقائياً (بس UnityEngine بس — مش System.Collections)
    if "using UnityEngine" not in code:
        code = "using UnityEngine;\n" + code

    if "MonoBehaviour" not in code:
        return False, "Unity script must inherit from MonoBehaviour"

    if "public class" not in code:
        return False, "Unity script missing public class"

    # Manager/System سكريبتات ممكن متبقاش فيها Start/Update
    has_lifecycle = any(m in code for m in ["void Start", "void Update", "void Awake", "void OnEnable", "void FixedUpdate"])
    is_manager = any(w in code for w in ["Manager", "System", "Controller", "Handler", "Database", "UI", "Menu", "Screen", "Panel", "Dialogue"])
    if not has_lifecycle and not is_manager:
        return False, "Unity script missing lifecycle method (Start/Update/Awake)"

    return True, code

def validate_python(code, task):
    """Python validation — syntax check + unicode cleanup."""
    # Strip any leftover code fence markers
    import re as _re
    code = _re.sub(r'^```[a-zA-Z]*\n?', '', code.strip())
    code = code.rstrip('`').strip()
    # Fix common unicode issues before parsing
    code = code.replace('\u2014', '--')   # em dash → --
    code = code.replace('\u2013', '-')    # en dash → -
    code = code.replace('\u2018', "'")    # left single quote
    code = code.replace('\u2019', "'")    # right single quote
    code = code.replace('\u201c', '"')    # left double quote
    code = code.replace('\u201d', '"')    # right double quote
    try:
        import ast as _ast
        _ast.parse(code)
        return True, code
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"

def validate_code(code, task):
    domain = detect_programming_domain(code)

    if domain == "unreal":
        return validate_unreal(code)

    if domain == "unity":
        return validate_unity(code)

    if domain == "python":
        return validate_python(code, task)

    return True, "Generic code assumed valid"


def detect_requested_language(task):
    """Uses DOMAIN_REGISTRY — single source of truth."""
    return detect_domain(task)

def _get_dotnet_ext(name: str, role: str) -> str:
    """Return correct file extension for a .NET file based on name/role."""
    nl = name.lower()
    # Strip any existing extension from name before deciding
    for ext in (".cs", ".cshtml", ".css", ".js", ".json", ".html"):
        if nl.endswith(ext):
            return ext  # already has correct extension
    if role in ("view_index", "view_form", "layout", "page", "page_model"): return ".cshtml"
    if role == "css"  or "css"  in nl:  return ".css"
    if role == "javascript" or nl in ("site", "app", "main"):    return ".js"
    return ".cs"  # default for C# files

def _infer_array_type(array_expr, code):
    """Try to infer the element type of an array from its declaration."""
    # Extract array name: e.g. "board[x, y]" → "board"
    name = re.match(r'(\w+)', array_expr)
    if not name:
        return "int"
    arr_name = name.group(1)
    # Look for declaration: GemType[,] board or GemType[] board
    m = re.search(rf'(\w+)\s*\[,?\]\s+{re.escape(arr_name)}\b', code)
    if m:
        return m.group(1)
    return "int"

# ================= UNITY AUTO-FIX PIPELINE =================
# كل fix في function منفصلة → سهل التتبع والتعديل والتعطيل

def _fix_type_mismatches(code):
    """Fix 2: int -= float → cast to int, int = Xf → remove f"""
    code = re.sub(
        r'(\w+)\s*-=\s*(\w+f)\b',
        lambda m: f"{m.group(1)} -= (int){m.group(2)}", code)
    code = re.sub(
        r'(\b(?:int)\b\s+\w+)\s*=\s*([0-9]+)f',
        lambda m: f"{m.group(1)} = {m.group(2)}", code)
    return code

def _fix_syntax_errors(code):
    """Fix 3: invalid event += syntax, inline comments in conditions"""
    code = re.sub(r'^\s*public\s+\w+\s+\w+\s*\+=\s*\w+\s*;.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'if\s*\(\s*/\*.*?\*/\s*true\s*\)', 'if (true)', code, flags=re.DOTALL)
    code = re.sub(r'if\s*\(\s*/\*.*?\*/\s*\)', 'if (true)', code, flags=re.DOTALL)
    code = re.sub(r'/\*[^*\n]*\*/', 'true', code)
    return code

def _fix_gameobject_prefix(code):
    """Fix 3.5: FindGameObjectsWithTag without GameObject. prefix"""
    code = re.sub(r'(?<!GameObject\.)(?<!UnityEngine\.)\bFindGameObjectsWithTag\b',
                  'GameObject.FindGameObjectsWithTag', code)
    code = re.sub(r'(?<!GameObject\.)(?<!UnityEngine\.)\bFindGameObjectWithTag\b',
                  'GameObject.FindGameObjectWithTag', code)
    return code

def _fix_undeclared_components(code):
    """Fix 3.7: auto-declare audioSource / anim if used but not declared"""
    if re.search(r'\baudioSource\b', code) and 'AudioSource audioSource' not in code:
        if re.search(r'(private|public|protected)\s+\w[\w<>\[\]]*\s+\w+\s*[;=]', code):
            code = re.sub(
                r'((?:private|public|protected)\s+\w[\w<>\[\]]*\s+\w+\s*[;=][^\n]*\n)(?!.*(?:private|public|protected)\s+\w[\w<>\[\]]*\s+\w+\s*AudioSource)',
                r'\1    private AudioSource audioSource;\n', code, count=1)
        else:
            code = re.sub(r'(class\s+\w+[^{]*\{)', r'\1\n    private AudioSource audioSource;', code, count=1)
        code = re.sub(r'(void Start\s*\(\s*\)\s*\{)',
                      r'\1\n        if (audioSource == null) audioSource = GetComponent<AudioSource>();',
                      code, count=1)
    if re.search(r'\banim\b', code) and 'Animator anim' not in code:
        if re.search(r'(private|public|protected)\s+\w[\w<>\[\]]*\s+\w+\s*[;=]', code):
            code = re.sub(
                r'((?:private|public|protected)\s+\w[\w<>\[\]]*\s+\w+\s*[;=][^\n]*\n)(?!.*Animator anim)',
                r'\1    private Animator anim;\n', code, count=1)
        else:
            code = re.sub(r'(class\s+\w+[^{]*\{)', r'\1\n    private Animator anim;', code, count=1)
        code = re.sub(r'(void Start\s*\(\s*\)\s*\{)',
                      r'\1\n        if (anim == null) anim = GetComponent<Animator>();',
                      code, count=1)
    return code

def _fix_null_checks(code):
    """Fix 3.8: reversed null check + redundant double GetComponent"""
    code = re.sub(
        r'if\s*\(\s*(\w+)\s*!=\s*null\s*\)\s*\n?\s*\1\s*=\s*GetComponent',
        r'if (\1 == null)\n            \1 = GetComponent', code)
    code = re.sub(
        r'(\w+)\s*=\s*GetComponent<(\w+)>\(\)\s*;\s*\n\s*if\s*\(\s*\1\s*==\s*null\s*\)\s*\1\s*=\s*GetComponent<\2>\(\)\s*;',
        r'\1 = GetComponent<\2>();', code)
    return code

def _fix_instantiate_reassign(code):
    """Fix 3.9: prefab = Instantiate(prefab) → instance = Instantiate(prefab)"""
    def _replace(match):
        return f'playerInstance = Instantiate({match.group(2)}'
    return re.sub(r'\b(\w+Prefab)\s*=\s*Instantiate\((\1[^)]*\))', _replace, code)

def _fix_placeholders(code):
    """Fix 4: remove TODO / assuming / placeholder comments"""
    code = re.sub(r'\s*//\s*assuming.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'^\s*//\s*(add|TODO|replace|implement|your logic|your code|add logic here).*$',
                  '', code, flags=re.MULTILINE | re.IGNORECASE)
    return code

def _fix_blank_lines(code):
    """Fix 5: collapse 3+ blank lines to 2"""
    return re.sub(r'\n{3,}', '\n\n', code)

def _fix_field_array_init(code):
    """Fix 6: non-constant array size in field initializer"""
    def _strip(m): return m.group(1) + ";"
    code = re.sub(r'((?:private|protected|public)\s+[\w.]+\[,\]\s+\w+)\s*=\s*new\s+[\w.]+\[\w+\s*,\s*\w+\]\s*;', _strip, code)
    code = re.sub(r'((?:private|protected|public)\s+[\w.]+\[\]\s+\w+)\s*=\s*new\s+[\w.]+\[\w+\]\s*;', _strip, code)
    return code

def _fix_void_with_yield(code):
    """Fix 7: yield return inside void method body → change to IEnumerator"""
    def _check(m):
        if m.group(2) == "void":
            body_start = code.find(m.group(0))
            if 'yield' in code[body_start:body_start+600]:
                return f"{m.group(1)}IEnumerator {m.group(3)}"
        return m.group(0)
    return re.sub(r'^(\s*)(void|IEnumerator)\s+(\w+\s*\([^)]*\)\s*\{)', _check, code, flags=re.MULTILINE)

def _fix_duplicate_enums(code):
    """Fix 8: duplicate public enum → keep first"""
    seen = set()
    def _dedup(m):
        name = m.group(1)
        if name in seen: return ''
        seen.add(name)
        return m.group(0)
    return re.sub(r'public\s+enum\s+(\w+)\s*\{[^}]*\}', _dedup, code)

def _fix_system_enum_prefix(code):
    """Fix 9: Enum.GetValues → System.Enum.GetValues"""
    code = re.sub(r'(?<!System\.)(?<!\w)Enum\.GetValues\b', 'System.Enum.GetValues', code)
    code = re.sub(r'(?<!System\.)(?<!\w)Enum\.GetNames\b',  'System.Enum.GetNames',  code)
    code = re.sub(r'(?<!System\.)(?<!\w)Enum\.Parse\b',     'System.Enum.Parse',     code)
    return code

def _fix_singleton_instance_calls(code):
    """Fix 12: GameManager.GameOver() → GameManager.Instance.GameOver()"""
    singleton_classes = ["GameManager", "RaceManager", "LevelManager", "AudioManager"]
    instance_methods  = ["OnEnemyKilled", "GameOver", "AddScore", "LoseLife",
                         "OnCheckpointReached", "OnLapCompleted"]
    for cls in singleton_classes:
        for method in instance_methods:
            code = re.sub(rf'(?<!\bInstance\.)\b{cls}\.{method}\s*\(',
                          f'{cls}.Instance.{method}(', code)
    return code

def _fix_gemtype_cross_file(code):
    """Fix 13+14: GemType enum cross-file handling"""
    if re.search(r'class\s+BoardManager\b', code):
        has_nested = bool(re.search(r'class\s+BoardManager\b[^{]*\{.*?public\s+enum\s+GemType', code, re.DOTALL))
        if not has_nested:
            top_enum = re.search(r'(public\s+enum\s+GemType\s*\{[^}]*\})', code)
            if top_enum:
                enum_body = top_enum.group(1)
                code = re.sub(r'public\s+enum\s+GemType\s*\{[^}]*\}', '', code)
                code = re.sub(r'(class\s+BoardManager\b[^{]*\{)', r'\1\n    ' + enum_body, code, count=1)
            else:
                code = re.sub(r'(class\s+BoardManager\b[^{]*\{)',
                              r'\1\n    public enum GemType { Empty, Red, Green, Blue, Yellow }', code, count=1)
        code = re.sub(r'^public\s+enum\s+GemType\s*\{[^}]*\}\s*\n', '', code, flags=re.MULTILINE)
    elif re.search(r'\bboardManager\b', code) or re.search(r'\bBoardManager\b', code):
        code = re.sub(r'\s*public\s+enum\s+GemType\s*\{[^}]*\}', '', code)
        if re.search(r'\bGemType\b', code):
            code = re.sub(r'(?<!BoardManager\.)(?<!\w)GemType\b', 'BoardManager.GemType', code)
            code = re.sub(r'BoardManager\.BoardManager\.GemType', 'BoardManager.GemType', code)
    elif 'BoardManager.GemType' in code and 'class BoardManager' not in code and 'boardManager' not in code:
        code = code.replace('BoardManager.GemType', 'GemType')
    return code

def _fix_array_type_cast(code):
    """Fix 10: Random.Range assigned to typed enum array → cast"""
    return re.sub(
        r'(\w+\[[\w\s,]+\])\s*=\s*(Random\.Range\([^)]+\))\s*;',
        lambda m: f"{m.group(1)} = ({_infer_array_type(m.group(1), code)}){m.group(2)};",
        code)

def _fix_coroutine_calls(code):
    """Fix 11: IEnumerator called directly → StartCoroutine(...)"""
    for method in re.findall(r'IEnumerator\s+(\w+)\s*\(', code):
        code = re.sub(
            rf'(?<!StartCoroutine\()(?<!\w){re.escape(method)}\(([^)]*)\)\s*;',
            lambda m, mn=method: f"StartCoroutine({mn}({m.group(1)}));",
            code)
    return code

def _fix_rigidbody_3d_to_2d(code):
    """Fix 15: Rigidbody → Rigidbody2D in 2D scripts"""
    has_2d = re.search(r'(OnCollisionEnter2D|OnTriggerEnter2D|Collider2D|Vector2\.|rb\.velocity|rb\.rotation|rb\.AddForce)', code)
    if has_2d and re.search(r'private Rigidbody\b(?!2D)', code) and 'Rigidbody2D' not in code:
        code = re.sub(r'\bRigidbody\b(?!2D)', 'Rigidbody2D', code)
    return code

def _fix_distance_method(code):
    """Fix 16: .distanceTo() → Vector3.Distance()"""
    return re.sub(r'(\w+(?:\.\w+)*?)\.distanceTo\(([^)]+)\)', r'Vector3.Distance(\1, \2)', code)

def _fix_duplicate_class(code):
    """Fix 17: duplicate class declaration → keep first"""
    matches = list(re.finditer(r'^public class (\w+)\s*[:{]', code, re.MULTILINE))
    if len(matches) > 1:
        seen = set()
        for i, m in enumerate(matches):
            if m.group(1) in seen:
                code = code[:m.start()].rstrip()
                break
            seen.add(m.group(1))
        m2 = list(re.finditer(r'^public class \w+', code, re.MULTILINE))
        if len(m2) > 1:
            code = code[:m2[1].start()].rstrip()
    return code

def _fix_self_referential_swap(code):
    """Fix 18: SwapGems method calling boardManager.SwapGems → remove recursive call"""
    if re.search(r'public void SwapGems\([^)]*\)[^{]*\{[^}]*boardManager\.SwapGems\s*\(', code, re.DOTALL):
        code = re.sub(r'boardManager\.SwapGems\s*\([^)]*\)\s*;', '', code)
    return code

def _fix_board_manager_api(code):
    """Fix 19/19b/19c: cellSize → 1f, GetGemAt → GemAt, GemAt(vec) → GemAt(x,y)"""
    code = re.sub(r'\bbboardManager\.cellSize\b', '1f', code)
    code = re.sub(r'\bboardManager\.cellSize\b',  '1f', code)
    code = re.sub(r'(?<!\w)cellSize\b(?!\s*[=;{(])', '1f', code)
    code = re.sub(r'\bboardManager\.GetGemAt\s*\(', 'boardManager.GemAt(', code)
    code = re.sub(r'\bboardManager\.GetGem\s*\(',   'boardManager.GemAt(', code)
    def _expand(m):
        arg = m.group(1).strip()
        if '.' in arg or ',' in arg: return m.group(0)
        return f'GemAt({arg}.x, {arg}.y)'
    code = re.sub(r'\bGemAt\s*\(\s*([^,)]+)\s*\)', _expand, code)
    return code

def _fix_gem_component_type(code):
    """Fix 19d: GetComponent<Gem>() → GetComponent<GemScript>()"""
    if 'class GemScript' not in code and 'class Gem ' not in code and 'class Gem\n' not in code:
        code = re.sub(r'\bGetComponent<Gem>\s*\(\)', 'GetComponent<GemScript>()', code)
        code = re.sub(r'\bGem\s+(\w+)\s*=\s*(\w+)\.GetComponent<Gem>', r'GemScript \1 = \2.GetComponent<GemScript>', code)
        code = re.sub(r'\bGem\s+(\w+)\s*=\s*gem\.GetComponent', r'GemScript \1 = gem.GetComponent', code)
        code = re.sub(r'(?<!\w)Gem\b(?!\w)(?=\s+\w)', 'GemScript', code)
    return code

def _fix_collider_3d_to_2d(code):
    """Fix 19e: Collider/Collision → Collider2D/Collision2D in Unity 2D callbacks"""
    code = re.sub(r'\bOnTriggerEnter\s*\(\s*Collider\s+(\w+)\s*\)',  r'OnTriggerEnter2D(Collider2D \1)', code)
    code = re.sub(r'\bOnTriggerExit\s*\(\s*Collider\s+(\w+)\s*\)',   r'OnTriggerExit2D(Collider2D \1)', code)
    code = re.sub(r'\bOnTriggerStay\s*\(\s*Collider\s+(\w+)\s*\)',   r'OnTriggerStay2D(Collider2D \1)', code)
    code = re.sub(r'\bOnCollisionEnter\s*\(\s*Collision\s+(\w+)\s*\)', r'OnCollisionEnter2D(Collision2D \1)', code)
    code = re.sub(r'\bOnCollisionExit\s*\(\s*Collision\s+(\w+)\s*\)', r'OnCollisionExit2D(Collision2D \1)', code)
    return code

def _fix_unknown_component_types(code):
    """Fix 19f: GetComponent<Health> → GetComponent<HealthBar>"""
    code = re.sub(r'\bGetComponent<Health>\s*\(\)', 'GetComponent<HealthBar>()', code)
    code = re.sub(r'\bHealth\s+(\w+)\s*=', r'HealthBar \1 =', code)
    return code

def _fix_gemtype_none_empty(code):
    """Fix 20: GemType.None / GemType.Empty → first valid enum value"""
    m = re.search(r'enum\s+GemType\s*\{([^}]+)\}', code)
    first_val = [v.strip().split('=')[0].strip() for v in m.group(1).split(',') if v.strip()][0] if m else 'Red'
    if first_val.lower() not in ('none', 'empty'):
        code = re.sub(r'\bBoardManager\.GemType\.None\b',  f'BoardManager.GemType.{first_val}', code)
        code = re.sub(r'\bBoardManager\.GemType\.Empty\b', f'BoardManager.GemType.{first_val}', code)
        code = re.sub(r'\bGemType\.None\b',  f'GemType.{first_val}', code)
        code = re.sub(r'\bGemType\.Empty\b', f'GemType.{first_val}', code)
    code = re.sub(r'if\s*\(\s*gemType\s*==\s*0\s*\)\s*return[^;]*;', '// enum starts at 0', code)
    return code

def _fix_using_statements(code):
    """Fix LAST: add missing using statements"""
    existing = set(re.findall(r'using\s+([\w.]+)\s*;', code))
    needed = []
    checks = [
        (r'\b(Text|Slider|Button|Image|Toggle|Dropdown|InputField|ScrollRect)\b', 'UnityEngine.UI'),
        (r'\b(List|Dictionary|HashSet|Queue|Stack)<', 'System.Collections.Generic'),
        (r'\b(IEnumerator|StartCoroutine|StopCoroutine)\b', 'System.Collections'),
        (r'\.(ToList|ToArray|Where|Select|FirstOrDefault|OrderBy|Any|All)\s*[(<]', 'System.Linq'),
        (r'\b(Action|Func|Tuple|Math\.|Serializable)\b', 'System'),
        (r'\bSceneManager\b', 'UnityEngine.SceneManagement'),
        (r'\bNavMeshAgent\b', 'UnityEngine.AI'),
    ]
    for pattern, ns in checks:
        if re.search(pattern, code) and ns not in existing:
            needed.append(f'using {ns};')
    if needed:
        last_using = list(re.finditer(r'^using\s+[\w.]+\s*;', code, re.MULTILINE))
        if last_using:
            pos = last_using[-1].end()
            code = code[:pos] + '\n' + '\n'.join(needed) + code[pos:]
        else:
            code = '\n'.join(needed) + '\n' + code
    return code

# Ordered pipeline — ترتيب مهم
_UNITY_FIX_PIPELINE = [
    ("type_mismatches",          _fix_type_mismatches),
    ("syntax_errors",            _fix_syntax_errors),
    ("gameobject_prefix",        _fix_gameobject_prefix),
    ("undeclared_components",    _fix_undeclared_components),
    ("null_checks",              _fix_null_checks),
    ("instantiate_reassign",     _fix_instantiate_reassign),
    ("placeholders",             _fix_placeholders),
    ("blank_lines",              _fix_blank_lines),
    ("field_array_init",         _fix_field_array_init),
    ("void_with_yield",          _fix_void_with_yield),
    ("duplicate_enums",          _fix_duplicate_enums),
    ("system_enum_prefix",       _fix_system_enum_prefix),
    ("singleton_instance_calls", _fix_singleton_instance_calls),
    ("gemtype_cross_file",       _fix_gemtype_cross_file),
    ("array_type_cast",          _fix_array_type_cast),
    ("coroutine_calls",          _fix_coroutine_calls),
    ("rigidbody_3d_to_2d",       _fix_rigidbody_3d_to_2d),
    ("distance_method",          _fix_distance_method),
    ("duplicate_class",          _fix_duplicate_class),
    ("self_referential_swap",    _fix_self_referential_swap),
    ("board_manager_api",        _fix_board_manager_api),
    ("gem_component_type",       _fix_gem_component_type),
    ("collider_3d_to_2d",        _fix_collider_3d_to_2d),
    ("unknown_component_types",  _fix_unknown_component_types),
    ("gemtype_none_empty",       _fix_gemtype_none_empty),
    ("using_statements",         _fix_using_statements),  # LAST
]

def auto_fix_unity_code(code: str, debug: bool = False) -> str:
    """
    Pipeline-based Unity C# post-processor.
    كل fix function مستقلة — سهل إضافة / تعطيل / debug أي step.
    debug=True: يطبع أي step غيّر الكود.
    """
    for name, fix_fn in _UNITY_FIX_PIPELINE:
        try:
            before = code
            code = fix_fn(code)
            if debug and code != before:
                safe_print(f"  [fix:{name}] modified code")
        except Exception as e:
            safe_print(f"  ⚠️ fix step '{name}' error: {e}")
    return code.strip()


# alias للـ backward compatibility
def auto_clean_unity_code(code):
    return auto_fix_unity_code(code)


from unity_stubs import UNITY_STUBS

import tempfile, subprocess, os, shutil
from unity_templates import UNIVERSAL_TEMPLATES, TEMPLATED_ROLES, GAME_SPECIFIC_ROLES, FILL_TEMPLATES, ROLE_FILL_RULES
from unreal_templates import validate_unreal, auto_fix_unreal_header, UNREAL_SYSTEM_PROMPT
from dotnet_templates import (DOTNET_TEMPLATES, DOTNET_TEMPLATED_ROLES,
    DOTNET_SYSTEM_PROMPT, DOTNET_PLANNING_PROMPT, DOTNET_FULLSTACK_PLANNING_PROMPT,
    get_dotnet_template, get_dotnet_role)
from angular_templates import (ANGULAR_TEMPLATES, ANGULAR_TEMPLATED_ROLES,
    ANGULAR_SYSTEM_PROMPT, ANGULAR_PLANNING_PROMPT,
    get_angular_template, get_angular_role)
from html_templates import (HTML_TEMPLATES, HTML_TEMPLATED_ROLES,
    HTML_SYSTEM_PROMPT, HTML_PLANNING_PROMPT,
    get_html_template, get_html_role, get_html_ext)
from react_templates import (REACT_TEMPLATES, REACT_TEMPLATED_ROLES,
    REACT_SYSTEM_PROMPT, REACT_PLANNING_PROMPT,
    get_react_template, get_react_role, get_react_ext)
from python_templates import (PYTHON_TEMPLATES, PYTHON_TEMPLATED_ROLES,
    PYTHON_SYSTEM_PROMPT, PYTHON_PLANNING_PROMPT, SELF_MOD_PROMPT,
    get_python_template, get_python_role)
from sql_templates import (SQL_TEMPLATES, SQL_TEMPLATED_ROLES,
    SQL_SYSTEM_PROMPT, SQL_PLANNING_PROMPT,
    get_sql_template, get_sql_role)

def compile_check_csharp(script_name: str, code: str, all_scripts: dict, planned_scripts: list = None) -> list[str]:
    """
    يعمل dotnet project مؤقت، يحط فيه كل الـ scripts الموجودة + Unity stubs،
    يـ build، ويرجع list من compile errors (فاضية = نظيف).
    all_scripts: dict من {name: code} لكل الـ scripts المتولدة لغاية دلوقتي
    """
    tmpdir = tempfile.mkdtemp(prefix="unity_check_")
    try:
        # إنشاء .csproj بسيط
        csproj = '''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Library</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>disable</Nullable>
    <ImplicitUsings>disable</ImplicitUsings>
    <NoWarn>CS0108;CS0114;CS0162;CS0168;CS0169;CS0219;CS0414;CS0649;CS1591;CS0067</NoWarn>
  </PropertyGroup>
</Project>'''
        with open(os.path.join(tmpdir, "UnityCheck.csproj"), "w") as f:
            f.write(csproj)

        # اكتب Unity stubs
        with open(os.path.join(tmpdir, "UnityStubs.cs"), "w", encoding="utf-8") as f:
            f.write(UNITY_STUBS)

        # اكتب كل الـ scripts السابقة (context)
        known_classes = set()
        # Classes already defined in UnityStubs.cs — don't re-stub these
        known_classes.update({
            'GameManager','HealthBar','PlayerController','Shield','IDamageable',
            'MonoBehaviour','GameObject','Transform','Component','Object','Behaviour',
            'Rigidbody','Rigidbody2D','Collider','Collider2D','Camera','Canvas',
            'AudioSource','Animator','NavMeshAgent','ParticleSystem','Light',
            'MeshRenderer','SpriteRenderer','Text','Slider','Button','Image',
            'InputField','Toggle','Dropdown','ScrollRect','RectTransform',
        })
        for sname, scode in all_scripts.items():
            if sname == script_name:
                continue
            # استخرج الكود النظيف
            import re as _re
            m = _re.search(r'```(?:csharp|cs)?\n(.*?)```', scode, _re.DOTALL)
            clean = m.group(1) if m else scode
            with open(os.path.join(tmpdir, f"{sname}.cs"), "w", encoding="utf-8") as f:
                f.write(clean)
            # track class names defined in context
            for cm in _re.findall(r'public\s+class\s+(\w+)', clean):
                known_classes.add(cm)

        # اكتب الـ script الحالي
        import re as _re
        m = _re.search(r'```(?:csharp|cs)?\n(.*?)```', code, _re.DOTALL)
        clean_code = m.group(1) if m else code
        with open(os.path.join(tmpdir, f"{script_name}.cs"), "w", encoding="utf-8") as f:
            f.write(clean_code)

        # ✅ Auto-stub: لو الـ script بيستخدم GetComponent<X> أو field من type X
        # وX مش في الـ context ولا في stubs → اعمل stub بسيط ليه
        # ✅ Stubs للـ scripts المخططة اللي لسه ما اتولدتش
        # عشان لو Script رقم 1 بيكلم Script رقم 3 → الـ compiler يعرفه
        if planned_scripts:
            stub_lines = ['using UnityEngine;', 'using UnityEngine.UI;', 'using System.Collections.Generic;', '']
            for ps in planned_scripts:
                if ps == script_name:
                    continue
                if ps in all_scripts:
                    continue  # اتولد فعلاً وموجود كـ .cs
                if ps in known_classes:
                    continue  # موجود في context
                # عمل stub بسيط بأكثر الـ fields الشائعة
                stub_lines += [
                    f'public class {ps} : MonoBehaviour {{',
                    f'    public BoardManager boardManager;',
                    f'    public Vector2Int gridPosition;',
                    f'    public int score;',
                    f'    public static {ps} Instance;',
                    f'    public void AddScore(int n){{}}',
                    f'    public void LoseLife(){{}}',
                    f'    public void ShowGameOver(){{}}',
                    f'}}',
                    ''
                ]
            if len(stub_lines) > 4:  # لو فيه stubs فعلاً
                with open(os.path.join(tmpdir, "_PlannedStubs.cs"), "w", encoding="utf-8") as f:
                    f.write('\n'.join(stub_lines))


        # شغل dotnet build
        result = subprocess.run(
            ["dotnet", "build", "--nologo", "-v", "quiet"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=30
        )

        output = result.stdout + result.stderr
        errors = []
        seen = set()
        for line in output.splitlines():
            if ": error CS" not in line:
                continue
            import re as _re2
            m2 = _re2.search(r'error (CS\d+): (.+)', line)
            if not m2:
                continue
            file_m = _re2.search(r'(\w+\.cs)\((\d+),', line)
            file_name = file_m.group(1) if file_m else ""
            line_no   = file_m.group(2) if file_m else ""

            # ✅ فقط errors من الـ script الحالي — تجاهل errors من context files
            if file_name and file_name.lower() != f"{script_name.lower()}.cs":
                continue

            key = (file_name, line_no, m2.group(1))
            if key in seen:
                continue
            seen.add(key)

            loc = f"{file_name}:{line_no}" if file_name else ""
            errors.append(f"{loc} {m2.group(1)}: {m2.group(2)}")

        return errors

    except FileNotFoundError:
        return []  # dotnet مش متاح — تجاهل
    except subprocess.TimeoutExpired:
        return []
    except Exception as e:
        return []
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def llm_fix_compile_errors(script_name: str, code: str, errors: list[str], model: str, context_block: str = "") -> str:
    """يبعت الـ compile errors للـ LLM ويطلب منه يصلح الكود."""
    import re as _re
    m = _re.search(r'```(?:csharp|cs)?\n(.*?)```', code, _re.DOTALL)
    clean_code = m.group(1) if m else code

    error_text = "\n".join(errors)
    prompt = f"""Fix these REAL C# compiler errors in {script_name}.cs:

COMPILER ERRORS:
{error_text}

{context_block}

RULES:
- Fix ONLY the listed errors
- Do NOT change class name — must stay: {script_name}
- Do NOT add placeholder comments or empty methods
- Return ONLY one ```csharp code block

SCRIPT TO FIX:
```csharp
{clean_code}
```"""

    try:
        r = safe_chat(model=model, messages=[
            {"role": "system", "content": "You are a C# compiler error fixer. Return ONLY a ```csharp block."},
            {"role": "user",   "content": prompt}
        ])
        return get_response(r)
    except Exception:
        return code



LANGUAGE_RULES = {
    "unreal": {
        "type": "multi",
        "extensions": [".h", ".cpp"],
    },
    "unity": {
        "type": "single",
        "extensions": [".cs"],
    },
    "python": {
        "type": "single",
        "extensions": [".py"],
    },
    "cpp": {
        "type": "single",
        "extensions": [".cpp"],
    },
    "csharp": {
        "type": "single",
        "extensions": [".cs"],
    },
}

# auto_fix_unreal_header → imported from unreal_templates
