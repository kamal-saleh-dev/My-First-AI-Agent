# plugins/unity_plugin.py — Unity C# domain plugin
from plugins.base_plugin import DomainPlugin, register_plugin


class UnityPlugin(DomainPlugin):
    name           = "unity"
    keywords       = ["unity", "يونتي"]
    language_label = "Unity C#"
    file_extension = ".cs"
    launchable     = False

    def system_prompt(self) -> str:
        return (
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

    def get_file_ext(self, script_name: str, role: str) -> str:
        return ".cs"

    def get_template(self, script_name: str, role: str):
        from unity_templates import UNIVERSAL_TEMPLATES, TEMPLATED_ROLES
        if role in TEMPLATED_ROLES:
            tpl = UNIVERSAL_TEMPLATES.get(role)
            return tpl.format(name=script_name) if tpl else None
        return None

    def validate(self, code: str) -> tuple:
        from compiler_tools import validate_unity
        return validate_unity(code)

    def post_process(self, code: str) -> str:
        from unity_pipeline import auto_fix_unity_code
        return auto_fix_unity_code(code)


register_plugin(UnityPlugin())
