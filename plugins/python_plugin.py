# plugins/python_plugin.py — Python domain plugin
from plugins.base_plugin import DomainPlugin, register_plugin


class PythonPlugin(DomainPlugin):
    name           = "python"
    keywords       = ["python", "بايثون", "fastapi", "flask", "script", "pip"]
    language_label = "Python"
    file_extension = ".py"
    launchable     = False

    def system_prompt(self) -> str:
        from python_templates import PYTHON_SYSTEM_PROMPT
        return PYTHON_SYSTEM_PROMPT

    def get_file_ext(self, script_name: str, role: str) -> str:
        return ".py"

    def get_template(self, script_name: str, role: str):
        from python_templates import get_python_template
        return get_python_template(script_name, role)

    def planning_prompt(self, task: str):
        from python_templates import PYTHON_PLANNING_PROMPT
        return PYTHON_PLANNING_PROMPT.format(task=task)


register_plugin(PythonPlugin())
