# plugins/unreal_plugin.py — Unreal Engine C++ domain plugin
from plugins.base_plugin import DomainPlugin, register_plugin


class UnrealPlugin(DomainPlugin):
    name           = "unreal"
    keywords       = ["unreal", "c++", "أنريل", "ue4", "ue5"]
    language_label = "Unreal C++"
    file_extension = ".h"
    launchable     = False

    def system_prompt(self) -> str:
        from unreal_templates import UNREAL_SYSTEM_PROMPT
        return UNREAL_SYSTEM_PROMPT

    def get_file_ext(self, script_name: str, role: str) -> str:
        return ".h"

    def get_template(self, script_name: str, role: str):
        from unreal_templates import get_unreal_template
        return get_unreal_template(script_name, role)

    def validate(self, code: str) -> tuple:
        from unreal_templates import validate_unreal
        return validate_unreal(code)

    def post_process(self, code: str) -> str:
        from unreal_templates import auto_fix_unreal_code
        return auto_fix_unreal_code(code)


register_plugin(UnrealPlugin())
