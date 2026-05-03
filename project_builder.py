# project_builder.py — Script saving and dotnet post-processing
# Extracted from generation_engine.py
# Responsibility: persist generated code to disk + scaffold dotnet projects

import os
import re
import shutil

from logger         import log
from unity_pipeline import auto_fix_unity_code
from compiler_tools import detect_programming_domain, validate_code, LANGUAGE_RULES
from unreal_templates import save_unreal_scripts


def extract_and_save_scripts(text: str, project_name: str,
                              forced_name: str = None,
                              forced_ext: str = None) -> bool:
    """
    Extract code blocks from an LLM response and save to Generated_Scripts/<project>.
    Returns True if at least one file was saved successfully.
    """
    pattern = r"```(?:[a-zA-Z0-9+#]*)\n?(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    if not matches:
        return False

    safe_name   = re.sub(r'[\\/*?:"<>|]', "", project_name).strip().replace(" ", "_")
    folder_name = os.path.join("Generated_Scripts", safe_name)
    os.makedirs(folder_name, exist_ok=True)

    # Unreal multi-file (header + cpp) — delegate to unreal helper
    first_domain = detect_programming_domain(matches[0])
    if first_domain in LANGUAGE_RULES and LANGUAGE_RULES[first_domain].get("type") == "multi":
        return save_unreal_scripts(matches, folder_name)

    all_valid = True
    for i, code in enumerate(matches):
        code = code.strip()
        code = re.sub(r"^```[a-zA-Z]*\n?", "", code).strip().rstrip("`").strip()
        # Normalise fancy quotes / dashes that LLMs sometimes emit
        code = (
            code.replace("\u2014", "--").replace("\u2013", "-")
                .replace("\u2018", "'").replace("\u2019", "'")
                .replace("\u201c", '"').replace("\u201d", '"')
        )

        domain_check = detect_programming_domain(code)
        if domain_check == "unity":
            code = auto_fix_unity_code(code)

        is_valid, result = validate_code(code, project_name)
        if not is_valid:
            _non_critical = ("test", "config", "schema", "util", "db",
                             "handler", "settings", "spec")
            if domain_check == "python" and any(
                w in project_name.lower() for w in _non_critical
            ):
                print(f"⚠️ Validation warning: {result} — saving anyway", flush=True)
                result = code
            else:
                print(f"\n❌ Validation Failed: {result}")
                all_valid = False
                continue

        # Use validated/fixed code if it looks like real code
        if isinstance(result, str) and len(result) > 50 and (
            "using " in result or "class " in result or "def " in result
            or "#include" in result or "<" in result
        ):
            code = result

        domain    = detect_programming_domain(code)
        extension = (
            forced_ext
            if forced_ext
            else (
                LANGUAGE_RULES[domain]["extensions"][0]
                if domain in LANGUAGE_RULES
                else ".txt"
            )
        )

        if forced_name:
            class_name = forced_name
        else:
            m = re.search(
                r"class\s+(?:[A-Za-z0-9_]+\s+)?([A-Za-z_][A-Za-z0-9_]*)", code
            )
            class_name = m.group(1) if m else f"Script_{i}"

        # Sanitize class_name — strip chars invalid in Windows filenames
        class_name = re.sub(r"[\\/:*?\"<>|()';,. ]", "_", class_name).strip("_")
        if not class_name:
            class_name = f"Script_{i}"

        if forced_name and class_name.lower().endswith(extension.lower()):
            file_name = class_name
        else:
            file_name = f"{class_name}{extension}"

        file_path = os.path.join(folder_name, file_name)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)
        log.save(f"Script saved: {file_path}")

    return all_valid


def post_process_dotnet(project_name: str) -> None:
    """
    Scaffold missing dotnet project files:
      - Remove duplicate Program.* files
      - Auto-create AppDbContext.cs from entity files
      - Move loose .cshtml into Views/<Controller>/
      - Create .csproj + Program.cs + _Layout if absent
    """
    proj_folder = os.path.join("Generated_Scripts", project_name.replace(" ", "_"))
    if not os.path.exists(proj_folder):
        return

    # ── Remove duplicate Program.* files ──────────────────────────────────────
    for fn in list(os.listdir(proj_folder)):
        if fn.lower().startswith("program.") and fn.lower() != "program.cs":
            os.remove(os.path.join(proj_folder, fn))
            print(f"🗑 Removed duplicate: {fn}", flush=True)

    # ── Auto-create AppDbContext if missing ────────────────────────────────────
    db_path = os.path.join(proj_folder, "AppDbContext.cs")
    if not os.path.exists(db_path):
        entity_names = []
        for fn in os.listdir(proj_folder):
            if not fn.endswith(".cs"):
                continue
            if fn in ("AppDbContext.cs", "Program.cs"):
                continue
            if fn.endswith(("Controller.cs", "Service.cs", "Repository.cs",
                             "Dto.cs", "Middleware.cs")):
                continue
            base = fn[:-3]
            if base.endswith("ViewModel") or base.startswith("I"):
                continue
            entity_names.append(base)

        dbsets = "\n".join(
            f"    public DbSet<{e}> {e if e.endswith('s') else e + 's'} {{ get; set; }} = null!;"
            for e in sorted(dict.fromkeys(entity_names))
        )
        with open(db_path, "w", encoding="utf-8") as f:
            f.write(
                "using Microsoft.EntityFrameworkCore;\n"
                "public class AppDbContext : DbContext\n"
                "{\n"
                "    public AppDbContext(DbContextOptions<AppDbContext> options)"
                " : base(options) { }\n"
                f"{chr(10) + dbsets + chr(10) if dbsets else ''}"
                "}\n"
            )
        print("📄 Auto-created: AppDbContext.cs", flush=True)

    # ── Move loose .cshtml → Views/<Controller>/<Action>.cshtml ───────────────
    ctrl_map: dict[str, str] = {}
    for fn in os.listdir(proj_folder):
        if fn.endswith("Controller.cs"):
            cname = fn.replace("Controller.cs", "")
            ctrl_map[cname.lower()] = cname
    default_ctrl = list(ctrl_map.values())[0] if ctrl_map else "Home"

    for fn in list(os.listdir(proj_folder)):
        if not fn.endswith(".cshtml") or fn.startswith("_"):
            continue
        src       = os.path.join(proj_folder, fn)
        dest_ctrl = default_ctrl
        fn_lower  = fn.lower().replace(".cshtml", "")
        for ck, cv in ctrl_map.items():
            if ck in fn_lower:
                dest_ctrl = cv
                break
        action = "Index"
        for act in ["index", "form", "create", "edit", "details", "delete", "list"]:
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

    # ── Create .csproj + scaffold if missing ───────────────────────────────────
    csproj_path = os.path.join(proj_folder, f"{project_name}.csproj")
    if os.path.exists(csproj_path):
        return

    _write_dotnet_scaffold(proj_folder, project_name, csproj_path)


# ── Dotnet scaffold writer (private) ─────────────────────────────────────────

def _write_dotnet_scaffold(proj_folder: str, project_name: str, csproj_path: str) -> None:
    csproj = """\
<Project Sdk="Microsoft.NET.Sdk.Web">
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
    program_cs = """\
using Microsoft.EntityFrameworkCore;

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
    layout_html = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>@ViewData["Title"] - MyApp</title>
    <link rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" />
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
        with open(csproj_path, "w", encoding="utf-8") as f:
            f.write(csproj)

        prog = os.path.join(proj_folder, "Program.cs")
        if not os.path.exists(prog):
            with open(prog, "w", encoding="utf-8") as f:
                f.write(program_cs)

        shared_dir = os.path.join(proj_folder, "Views", "Shared")
        os.makedirs(shared_dir, exist_ok=True)
        os.makedirs(os.path.join(proj_folder, "Views", "Home"), exist_ok=True)
        os.makedirs(os.path.join(proj_folder, "Controllers"), exist_ok=True)

        home_ctrl = os.path.join(proj_folder, "Controllers", "HomeController.cs")
        if not os.path.exists(home_ctrl):
            with open(home_ctrl, "w", encoding="utf-8") as f:
                f.write(
                    "using Microsoft.AspNetCore.Mvc;\n"
                    "public class HomeController : Controller\n"
                    "{\n"
                    "    public IActionResult Index() { return View(); }\n"
                    "}\n"
                )

        layout_path = os.path.join(shared_dir, "_Layout.cshtml")
        if not os.path.exists(layout_path):
            with open(layout_path, "w", encoding="utf-8") as f:
                f.write(layout_html)

        viewstart = os.path.join(proj_folder, "Views", "_ViewStart.cshtml")
        if not os.path.exists(viewstart):
            with open(viewstart, "w", encoding="utf-8") as f:
                f.write('@{ Layout = "_Layout"; }\n')

        viewimports = os.path.join(proj_folder, "Views", "_ViewImports.cshtml")
        if not os.path.exists(viewimports):
            with open(viewimports, "w", encoding="utf-8") as f:
                f.write(
                    "@using Microsoft.AspNetCore.Mvc.Razor\n"
                    "@addTagHelper *, Microsoft.AspNetCore.Mvc.TagHelpers\n"
                )

        print(f"📄 Created {project_name}.csproj + Views scaffold", flush=True)

    except Exception as e:
        print(f"⚠ csproj error: {e}", flush=True)
