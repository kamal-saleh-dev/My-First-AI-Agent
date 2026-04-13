# unity_pipeline.py — Unity C# auto-fix pipeline (Robust & Safe)
import re

# ── Safe regex helper ─────────────────────────────────────────────────────────
def _safe_sub(pattern, replacement, code, **kwargs):
    """re.sub with fallback — if regex fails, return code unchanged."""
    try:
        return re.sub(pattern, replacement, code, **kwargs)
    except Exception:
        return code

def _safe_search(pattern, code, **kwargs):
    try:
        return re.search(pattern, code, **kwargs)
    except Exception:
        return None

# ── Fix functions ─────────────────────────────────────────────────────────────

def _fix_syntax_errors(code):
    """Fix invalid event += syntax and inline comments in conditions."""
    code = _safe_sub(r'^\s*public\s+\w+\s+\w+\s*\+=\s*\w+\s*;.*$', '', code, flags=re.MULTILINE)
    code = _safe_sub(r'if\s*\(\s*/\*.*?\*/\s*true\s*\)', 'if (true)', code, flags=re.DOTALL)
    code = _safe_sub(r'if\s*\(\s*/\*.*?\*/\s*\)', 'if (true)', code, flags=re.DOTALL)
    code = _safe_sub(r'/\*[^*\n]*\*/', 'true', code)
    return code

def _fix_gameobject_prefix(code):
    """Fix FindGameObjectsWithTag / FindWithTag missing GameObject. prefix."""
    code = _safe_sub(
        r'(?<!GameObject\.)(?<!UnityEngine\.)\bFindGameObjectsWithTag\b',
        'GameObject.FindGameObjectsWithTag', code
    )
    code = _safe_sub(
        r'(?<!GameObject\.)(?<!UnityEngine\.)\bFindGameObjectWithTag\b',
        'GameObject.FindGameObjectWithTag', code
    )
    return code

def _fix_placeholders(code):
    """
    Remove LLM placeholder comments — but ONLY standalone comment lines.
    Protects method names like AddScore(), AddForce(), implement() etc.
    A placeholder comment must be the ONLY thing on its line (possibly indented).
    """
    # "// assuming..." on its own line — safe to remove
    code = _safe_sub(r'^\ *//\ *assuming\b.*$', '', code, flags=re.MULTILINE | re.IGNORECASE)

    # "// TODO ...", "// your logic", "// add logic here" etc — standalone comment lines only
    # Negative lookahead ensures we don't match lines that also have real code after the comment
    PLACEHOLDER_PATTERN = (
        r'^\ *//\ *'                          # line starts with optional indent + //
        r'(TODO|FIXME|replace\s|implement\s|'
        r'your\ logic|your\ code|add\ logic\ here|'
        r'add\ your|insert\ your|put\ your)'  # keyword
        r'.*$'                                  # rest of comment
    )
    code = _safe_sub(PLACEHOLDER_PATTERN, '', code, flags=re.MULTILINE | re.IGNORECASE)
    return code

def _fix_blank_lines(code):
    """Collapse 3+ blank lines to 2."""
    return _safe_sub(r'\n{3,}', '\n\n', code)

def _fix_duplicate_enums(code):
    """Remove duplicate public enum declarations — keep first occurrence."""
    try:
        seen = set()
        def _dedup(m):
            name = m.group(1)
            if name in seen:
                return ''
            seen.add(name)
            return m.group(0)
        return re.sub(r'public\s+enum\s+(\w+)\s*\{[^}]*\}', _dedup, code)
    except Exception:
        return code  # fallback: return unchanged

def _fix_duplicate_class(code):
    """Remove duplicate public class declarations — keep first occurrence."""
    try:
        matches = list(re.finditer(r'^public class (\w+)\s*[:{]', code, re.MULTILINE))
        if len(matches) <= 1:
            return code
        seen = set()
        for m in matches:
            name = m.group(1)
            if name in seen:
                # Truncate at this duplicate definition
                return code[:m.start()].rstrip()
            seen.add(name)
        return code
    except Exception:
        return code  # fallback: return unchanged

def _fix_null_check_pattern(code):
    """Fix wrong null-check pattern: if (x != null) x = GetComponent → if (x == null)."""
    # Common LLM mistake: != null when checking before assigning
    code = _safe_sub(
        r'if\s*\(\s*(\w+)\s*!=\s*null\s*\)\s*\n?\s*\1\s*=\s*GetComponent',
        r'if (\1 == null)\n        \1 = GetComponent',
        code
    )
    return code

def _fix_array_init(code):
    """Fix arrays initialized in field declarations with non-constant sizes."""
    # e.g. private GemType[,] grid = new GemType[gridSizeX, gridSizeY]; → remove initializer
    code = _safe_sub(
        r'(private\s+\w+\[,?\]\s+\w+)\s*=\s*new\s+\w+\[[^\]]*\w[^\]]*\](\[.*\])?;',
        r'\1;',
        code
    )
    return code

def _fix_using_statements(code):
    """Add missing using statements intelligently. MUST run last."""
    try:
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
    except Exception:
        pass  # Never break on using-fix failure
    return code

# ── Ordered pipeline ─────────────────────────────────────────────────────────
# Each step is independent — failure of one never stops the pipeline
_UNITY_FIX_PIPELINE = [
    ("syntax_errors",        _fix_syntax_errors),
    ("gameobject_prefix",    _fix_gameobject_prefix),
    ("placeholders",         _fix_placeholders),
    ("blank_lines",          _fix_blank_lines),
    ("duplicate_enums",      _fix_duplicate_enums),
    ("duplicate_class",      _fix_duplicate_class),
    ("null_check_pattern",   _fix_null_check_pattern),
    ("array_init",           _fix_array_init),
    ("using_statements",     _fix_using_statements),   # MUST BE LAST
]

def auto_fix_unity_code(code: str, debug: bool = False) -> str:
    """
    Pipeline-based Unity C# post-processor.
    Each step is isolated — a failing step returns the code unchanged,
    never crashing or corrupting the output.
    """
    for name, fix_fn in _UNITY_FIX_PIPELINE:
        try:
            before = code
            code = fix_fn(code)
            if debug and code != before:
                print(f"  [fix:{name}] modified code", flush=True)
        except Exception as e:
            # Hard safety: even if the wrapper fails, continue
            if debug:
                print(f"  ⚠️ fix step '{name}' error: {e}", flush=True)
    return code.strip()

# Alias for backward compatibility
auto_clean_unity_code = auto_fix_unity_code
