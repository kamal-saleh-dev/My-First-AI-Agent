# plugins/web_plugin.py — Web/DB domain plugins (dotnet, react, angular, html, sql)
from plugins.base_plugin import DomainPlugin, register_plugin


class DotnetPlugin(DomainPlugin):
    name           = "dotnet"
    keywords       = ["dotnet", ".net", "asp.net", "aspnet", "web api", "webapi"]
    language_label = "ASP.NET Core C#"
    file_extension = ".cs"
    launchable     = True

    def system_prompt(self) -> str:
        from dotnet_templates import DOTNET_SYSTEM_PROMPT
        return DOTNET_SYSTEM_PROMPT

    def get_file_ext(self, script_name: str, role: str) -> str:
        from dotnet_templates import get_dotnet_ext
        return get_dotnet_ext(script_name, role)

    def get_template(self, script_name: str, role: str):
        from dotnet_templates import get_dotnet_template
        return get_dotnet_template(script_name, role)

    def planning_prompt(self, task: str):
        from dotnet_templates import DOTNET_PLANNING_PROMPT, DOTNET_FULLSTACK_PLANNING_PROMPT
        base = (DOTNET_FULLSTACK_PLANNING_PROMPT
                if any(w in task.lower() for w in ["website","web app","mvc","razor","موقع","frontend"])
                else DOTNET_PLANNING_PROMPT)
        return base.format(task=task)

    def launch(self, project_folder: str):
        from launcher import launch_website
        launch_website(project_folder, "dotnet")


class ReactPlugin(DomainPlugin):
    name           = "react"
    keywords       = ["react", "reactjs", "react.js", "vite", "nextjs", "next.js"]
    language_label = "React.js"
    file_extension = ".jsx"
    launchable     = True

    def system_prompt(self) -> str:
        from react_templates import REACT_SYSTEM_PROMPT
        return REACT_SYSTEM_PROMPT

    def get_file_ext(self, script_name: str, role: str) -> str:
        from react_templates import get_react_ext
        return get_react_ext(script_name, role)

    def get_template(self, script_name: str, role: str):
        from react_templates import get_react_template
        return get_react_template(script_name, role)

    def planning_prompt(self, task: str):
        from react_templates import REACT_PLANNING_PROMPT
        return REACT_PLANNING_PROMPT.format(task=task)

    def launch(self, project_folder: str):
        from launcher import launch_website
        launch_website(project_folder, "react")


class AngularPlugin(DomainPlugin):
    name           = "angular"
    keywords       = ["angular", "angularjs", "ng "]
    language_label = "Angular TypeScript"
    file_extension = ".ts"
    launchable     = True

    def system_prompt(self) -> str:
        from angular_templates import ANGULAR_SYSTEM_PROMPT
        return ANGULAR_SYSTEM_PROMPT

    def get_file_ext(self, script_name: str, role: str) -> str:
        from angular_templates import get_angular_ext
        return get_angular_ext(script_name, role)

    def get_template(self, script_name: str, role: str):
        from angular_templates import get_angular_template
        return get_angular_template(script_name, role)

    def planning_prompt(self, task: str):
        from angular_templates import ANGULAR_PLANNING_PROMPT
        return ANGULAR_PLANNING_PROMPT.format(task=task)

    def launch(self, project_folder: str):
        from launcher import launch_website
        launch_website(project_folder, "angular")


class HtmlPlugin(DomainPlugin):
    name           = "html"
    keywords       = ["html", "html5", "vanilla js", "static site", "plain website"]
    language_label = "HTML/CSS/JS"
    file_extension = ".html"
    launchable     = True

    def system_prompt(self) -> str:
        from html_templates import HTML_SYSTEM_PROMPT
        return HTML_SYSTEM_PROMPT

    def get_file_ext(self, script_name: str, role: str) -> str:
        from html_templates import get_html_ext
        return get_html_ext(script_name, role)

    def get_template(self, script_name: str, role: str):
        from html_templates import get_html_template
        return get_html_template(script_name, role)

    def planning_prompt(self, task: str):
        from html_templates import HTML_PLANNING_PROMPT
        return HTML_PLANNING_PROMPT.format(task=task)

    def launch(self, project_folder: str):
        from launcher import launch_website
        launch_website(project_folder, "html")


class SqlPlugin(DomainPlugin):
    name           = "sql"
    keywords       = ["sql", "database", "postgres", "postgresql", "mysql",
                      "sqlite", "db schema", "قاعدة بيانات"]
    language_label = "SQL"
    file_extension = ".sql"
    launchable     = False

    def system_prompt(self) -> str:
        from sql_templates import SQL_SYSTEM_PROMPT
        return SQL_SYSTEM_PROMPT

    def get_file_ext(self, script_name: str, role: str) -> str:
        return ".sql"

    def get_template(self, script_name: str, role: str):
        from sql_templates import get_sql_template
        return get_sql_template(script_name, role)

    def planning_prompt(self, task: str):
        from sql_templates import SQL_PLANNING_PROMPT
        return SQL_PLANNING_PROMPT.format(task=task)


# ── Register all ─────────────────────────────────────────────────────────────
for _p in (DotnetPlugin, ReactPlugin, AngularPlugin, HtmlPlugin, SqlPlugin):
    register_plugin(_p())
