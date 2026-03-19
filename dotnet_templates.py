# dotnet_templates.py — ASP.NET Core Full Stack templates
# Add/edit templates here without touching agent.py

DOTNET_SYSTEM_PROMPT = """You are a senior ASP.NET Core Full Stack developer.

RULES:
- Use ASP.NET Core 8 (minimal API or MVC — based on context)
- C# with proper using statements
- Return ONLY one ```csharp code block per file
- No explanations outside code blocks
- Use Entity Framework Core for database access
- Follow Clean Architecture: Controllers → Services → Repositories → Models
"""

DOTNET_PLANNING_PROMPT = """You are a senior .NET architect.
List the files needed to build: {task}

Output ONLY this format (one per line):
FileName:role

Roles: mvc_controller, model, service, repository, viewmodel, view_index, view_form, css

STRICT RULES:
- Controller names MUST end with "Controller" only — NEVER "MvcController" or "ApiController"
- NEVER include Program, AppDbContext, or Layout — they are auto-generated
- Max 6 files

Example for "products website":
ProductsController:mvc_controller
Product:model
ProductViewModel:viewmodel
ProductIndex:view_index
ProductForm:view_form
site.css:css
"""

# ─── Templates ────────────────────────────────────────────────────────────────

DOTNET_TEMPLATES = {

    "program": """using Microsoft.EntityFrameworkCore;

// Program.cs — ASP.NET Core entry point
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
builder.Services.AddDbContext<AppDbContext>(opt =>
    opt.UseSqlite("Data Source=app.db"));

// builder.Services.AddScoped<IProductService, ProductService>();

var app = builder.Build();

if (app.Environment.IsDevelopment())
{{
    app.UseSwagger();
    app.UseSwaggerUI();
}}

app.UseHttpsRedirection();
app.UseAuthorization();
app.MapControllers();
app.Run();
""",

    "model": """using System.ComponentModel.DataAnnotations;

public class {name}
{{
    [Key]
    public int Id {{ get; set; }}

    [Required]
    [MaxLength(200)]
    public string Name {{ get; set; }} = string.Empty;

    public string Description {{ get; set; }} = string.Empty;

    public DateTime CreatedAt {{ get; set; }} = DateTime.UtcNow;

    public bool IsActive {{ get; set; }} = true;
}}
""",

    "dto": """public class {name}CreateDto
{{
    public string Name {{ get; set; }} = string.Empty;
    public string Description {{ get; set; }} = string.Empty;
}}

public class {name}UpdateDto
{{
    public string Name {{ get; set; }} = string.Empty;
    public string Description {{ get; set; }} = string.Empty;
    public bool IsActive {{ get; set; }}
}}

public class {name}ResponseDto
{{
    public int Id {{ get; set; }}
    public string Name {{ get; set; }} = string.Empty;
    public string Description {{ get; set; }} = string.Empty;
    public DateTime CreatedAt {{ get; set; }}
    public bool IsActive {{ get; set; }}
}}
""",

    "dbcontext": """using Microsoft.EntityFrameworkCore;

public class {name} : DbContext
{{
    public {name}(DbContextOptions<{name}> options) : base(options) {{ }}

    // Add your DbSets here:
    // public DbSet<Product> Products {{ get; set; }}

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {{
        base.OnModelCreating(modelBuilder);
    }}
}}
""",

    "interface": """public interface {name}
{{
    Task<IEnumerable<object>> GetAllAsync();
    Task<object?> GetByIdAsync(int id);
    Task AddAsync(object entity);
    Task UpdateAsync(object entity);
    Task DeleteAsync(int id);
}}
""",

    "service": """using Microsoft.EntityFrameworkCore;

public class {name}
{{
    private readonly AppDbContext _context;

    public {name}(AppDbContext context)
    {{
        _context = context;
    }}

    public async Task<IEnumerable<object>> GetAllAsync()
    {{
        return await _context.Set<object>().ToListAsync();
    }}

    public async Task<object?> GetByIdAsync(int id)
    {{
        return await _context.Set<object>().FindAsync(id);
    }}

    public async Task<object> CreateAsync(object dto)
    {{
        var entity = new object();
        _context.Add(entity);
        await _context.SaveChangesAsync();
        return entity;
    }}

    public async Task<bool> UpdateAsync(int id, object dto)
    {{
        var entity = await _context.Set<object>().FindAsync(id);
        if (entity == null) return false;
        await _context.SaveChangesAsync();
        return true;
    }}

    public async Task<bool> DeleteAsync(int id)
    {{
        var entity = await _context.Set<object>().FindAsync(id);
        if (entity == null) return false;
        _context.Remove(entity);
        await _context.SaveChangesAsync();
        return true;
    }}
}}
""",

    "repository": """using Microsoft.EntityFrameworkCore;

public class {name}
{{
    private readonly AppDbContext _context;

    public {name}(AppDbContext context)
    {{
        _context = context;
    }}

    public async Task<IEnumerable<object>> GetAllAsync()
        => await _context.Set<object>().ToListAsync();

    public async Task<object?> GetByIdAsync(int id)
        => await _context.Set<object>().FindAsync(id);

    public async Task AddAsync(object entity)
    {{
        await _context.Set<object>().AddAsync(entity);
        await _context.SaveChangesAsync();
    }}

    public async Task UpdateAsync(object entity)
    {{
        _context.Set<object>().Update(entity);
        await _context.SaveChangesAsync();
    }}

    public async Task DeleteAsync(int id)
    {{
        var entity = await _context.Set<object>().FindAsync(id);
        if (entity != null)
        {{
            _context.Set<object>().Remove(entity);
            await _context.SaveChangesAsync();
        }}
    }}
}}
""",

    "controller": """using Microsoft.AspNetCore.Mvc;

[ApiController]
[Route("api/[controller]")]
public class {name} : ControllerBase
{{
    private readonly AppDbContext _context;

    public {name}(AppDbContext context)
    {{
        _context = context;
    }}

    // GET: api/{name}
    [HttpGet]
    public async Task<IActionResult> GetAll()
    {{
        // var items = await _context.YourTable.ToListAsync();
        return Ok(new {{ message = "GetAll OK" }});
    }}

    // GET: api/{name}/5
    [HttpGet("{{id}}")]
    public async Task<IActionResult> GetById(int id)
    {{
        return Ok(new {{ id }});
    }}

    // POST: api/{name}
    [HttpPost]
    public async Task<IActionResult> Create([FromBody] object dto)
    {{
        if (!ModelState.IsValid) return BadRequest(ModelState);
        return CreatedAtAction(nameof(GetById), new {{ id = 1 }}, dto);
    }}

    // PUT: api/{name}/5
    [HttpPut("{{id}}")]
    public async Task<IActionResult> Update(int id, [FromBody] object dto)
    {{
        return NoContent();
    }}

    // DELETE: api/{name}/5
    [HttpDelete("{{id}}")]
    public async Task<IActionResult> Delete(int id)
    {{
        return NoContent();
    }}
}}
""",

    "middleware": """public class {name}
{{
    private readonly RequestDelegate _next;
    private readonly ILogger<{name}> _logger;

    public {name}(RequestDelegate next, ILogger<{name}> logger)
    {{
        _next = next;
        _logger = logger;
    }}

    public async Task InvokeAsync(HttpContext context)
    {{
        try
        {{
            _logger.LogInformation($"Request: {{context.Request.Method}} {{context.Request.Path}}");
            await _next(context);
            _logger.LogInformation($"Response: {{context.Response.StatusCode}}");
        }}
        catch (Exception ex)
        {{
            _logger.LogError(ex, "Unhandled exception");
            context.Response.StatusCode = 500;
            await context.Response.WriteAsJsonAsync(new {{ error = ex.Message }});
        }}
    }}
}}
""",
}

DOTNET_TEMPLATED_ROLES = set(DOTNET_TEMPLATES.keys())

DOTNET_ROLE_KEYWORDS = {
    "controller": ["controller", "api", "endpoint", "route"],
    "model":      ["model", "entity", "table", "record"],
    "dto":        ["dto", "request", "response", "payload"],
    "service":    ["service", "business", "logic", "handler"],
    "repository": ["repository", "repo", "data", "store"],
    "dbcontext":  ["dbcontext", "context", "database", "db"],
    "interface":  ["interface", "contract", "abstraction"],
    "middleware": ["middleware", "pipeline", "filter", "interceptor"],
    "program":    ["program", "startup", "main", "app"],
}

def _singularize_dotnet_name(name: str) -> str:
    """Best-effort singularization for generated MVC entity names."""
    base = (name.replace("Controller", "")
                .replace("ViewModel", "")
                .replace("Model", "")
                .replace("Form", "")
                .replace("Index", ""))
    if base.endswith("ies") and len(base) > 3:
        return base[:-3] + "y"
    if base.endswith("ses") and len(base) > 3:
        return base[:-2]
    if base.endswith("s") and not base.endswith("ss") and len(base) > 1:
        return base[:-1]
    return base

def get_dotnet_role(name: str) -> str:
    """Infer role from script name."""
    nl = name.lower()
    for role, keywords in DOTNET_ROLE_KEYWORDS.items():
        if any(kw in nl for kw in keywords):
            return role
    # Fallback by suffix
    if nl.endswith("controller"): return "controller"
    if nl.endswith("service"):    return "service"
    if nl.endswith("repository") or nl.endswith("repo"): return "repository"
    if nl.endswith("context"):    return "dbcontext"
    if nl.startswith("i") and len(nl) > 2: return "interface"
    return "controller"  # default

def get_dotnet_ext(name: str, role: str) -> str:
    """Return correct file extension for a .NET file."""
    if role in ("view_index", "view_form", "layout", "page_model"): return ".cshtml"
    if role == "css"  or name.lower().endswith(".css"):  return ".css"
    if role == "javascript" or name.lower().endswith(".js"): return ".js"
    return ".cs"

def get_dotnet_template(name: str, role: str = None) -> str:
    """Get .NET template for a file."""
    if role is None:
        role = get_dotnet_role(name)
    tpl = DOTNET_TEMPLATES.get(role, DOTNET_TEMPLATES["controller"])
    entity_name = _singularize_dotnet_name(name)
    entity_collection = entity_name + ("es" if entity_name.endswith("s") else "s")
    return tpl.format(name=name, entity_name=entity_name, entity_collection=entity_collection)


# ─── Frontend / MVC / Razor Pages ─────────────────────────────────────────────

DOTNET_TEMPLATES.update({

    "program_mvc": """using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllersWithViews();
builder.Services.AddDbContext<AppDbContext>(opt =>
    opt.UseSqlite("Data Source=app.db"));

// builder.Services.AddScoped<IProductService, ProductService>();

var app = builder.Build();

if (!app.Environment.IsDevelopment())
{{
    app.UseExceptionHandler("/Home/Error");
    app.UseHsts();
}}

app.UseHttpsRedirection();
app.UseStaticFiles();
app.UseRouting();
app.UseAuthorization();

app.MapControllerRoute(
    name: "default",
    pattern: "{{controller=Home}}/{{action=Index}}/{{id?}}");

app.Run();
""",

    "mvc_controller": """using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using System.Threading.Tasks;

public class {name} : Controller
{{
    private readonly AppDbContext _context;

    public {name}(AppDbContext context)
    {{
        _context = context;
    }}

    public async Task<IActionResult> Index()
    {{
        var items = await _context.Set<{entity_name}>().ToListAsync();
        return View(items);
    }}

    public async Task<IActionResult> Details(int id)
    {{
        var item = await _context.Set<{entity_name}>().FindAsync(id);
        if (item == null) return NotFound();
        return View(item);
    }}

    public IActionResult Create()
    {{
        return View(new {entity_name}());
    }}

    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Create([Bind("Name,Description")] {entity_name} model)
    {{
        if (!ModelState.IsValid) return View(model);

        model.CreatedAt = DateTime.UtcNow;
        model.IsActive = true;

        _context.Set<{entity_name}>().Add(model);
        await _context.SaveChangesAsync();

        return RedirectToAction(nameof(Index));
    }}

    public async Task<IActionResult> Edit(int id)
    {{
        var item = await _context.Set<{entity_name}>().FindAsync(id);
        if (item == null) return NotFound();
        return View("Create", item);
    }}

    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Edit(int id, [Bind("Id,Name,Description,CreatedAt,IsActive")] {entity_name} model)
    {{
        if (id != model.Id) return BadRequest();
        if (!ModelState.IsValid) return View("Create", model);

        _context.Update(model);
        await _context.SaveChangesAsync();

        return RedirectToAction(nameof(Index));
    }}

    [HttpPost, ActionName("Delete")]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> DeleteConfirmed(int id)
    {{
        var item = await _context.Set<{entity_name}>().FindAsync(id);
        if (item == null) return NotFound();
        _context.Set<{entity_name}>().Remove(item);
        await _context.SaveChangesAsync();
        return RedirectToAction(nameof(Index));
    }}
}}
""",

    "view_index": """@model IEnumerable<{entity_name}>
@{{
    ViewData["Title"] = "{name}";
    var items = Model ?? new List<{entity_name}>();
}}

<div class="container mt-4">
    <div class="d-flex justify-content-between align-items-center mb-3">
        <h1>{name}</h1>
        <a asp-action="Create" class="btn btn-primary">+ Add New</a>
    </div>

    <div class="table-responsive">
        <table class="table table-striped table-hover">
            <thead class="table-dark">
                <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                @foreach (var item in items)
                {{
                    <tr>
                        <td>@item.Id</td>
                        <td>@item.Name</td>
                        <td>
                            <a asp-action="Edit" asp-route-id="@item.Id" class="btn btn-sm btn-warning">Edit</a>
                            <a asp-action="Details" asp-route-id="@item.Id" class="btn btn-sm btn-info">Details</a>
                            <form asp-action="Delete" asp-route-id="@item.Id" method="post" class="d-inline">
                                <button type="submit" class="btn btn-sm btn-danger"
                                        onclick="return confirm('Delete?')">Delete</button>
                            </form>
                        </td>
                    </tr>
                }}
            </tbody>
        </table>
    </div>
</div>
""",

    "view_form": """@model {entity_name}
@{{
    ViewData["Title"] = "{name} Form";
    var formAction = Model?.Id > 0 ? "Edit" : "Create";
}}

<div class="container mt-4">
    <h1>@ViewData["Title"]</h1>
    <hr />

    <div class="row">
        <div class="col-md-6">
            <form asp-action="@formAction" method="post">
                <div asp-validation-summary="ModelOnly" class="alert alert-danger"></div>
                <input asp-for="Id" type="hidden" />
                <input asp-for="CreatedAt" type="hidden" />
                <input asp-for="IsActive" type="hidden" />

                <div class="mb-3">
                    <label asp-for="Name" class="form-label"></label>
                    <input asp-for="Name" class="form-control" />
                    <span asp-validation-for="Name" class="text-danger"></span>
                </div>

                <div class="mb-3">
                    <label asp-for="Description" class="form-label"></label>
                    <textarea asp-for="Description" class="form-control" rows="3"></textarea>
                    <span asp-validation-for="Description" class="text-danger"></span>
                </div>

                <div class="d-flex gap-2">
                    @if (!isReadOnly)
                    {{
                        <button type="submit" class="btn btn-primary">Save</button>
                    }}
                    <a asp-action="Index" class="btn btn-secondary">Cancel</a>
                </div>
            </form>
        </div>
    </div>
</div>

""",

    "layout": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>@ViewData["Title"] - {name}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" />
    <link rel="stylesheet" href="~/css/site.css" asp-append-version="true" />
</head>
<body>
    <header>
        <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
            <div class="container">
                <a class="navbar-brand" asp-controller="Home" asp-action="Index">{name}</a>
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse"
                        data-bs-target="#navbarNav">
                    <span class="navbar-toggler-icon"></span>
                </button>
                <div class="collapse navbar-collapse" id="navbarNav">
                    <ul class="navbar-nav ms-auto">
                        <li class="nav-item">
                            <a class="nav-link" asp-controller="Home" asp-action="Index">Home</a>
                        </li>
                    </ul>
                </div>
            </div>
        </nav>
    </header>

    <main class="container mt-4">
        @RenderBody()
    </main>

    <footer class="bg-dark text-white text-center py-3 mt-5">
        <p class="mb-0">&copy; @DateTime.Now.Year - {name}</p>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="~/js/site.js" asp-append-version="true"></script>
    @await RenderSectionAsync("Scripts", required: false)
</body>
</html>
""",

    "css": """/* site.css — Custom styles */

:root {{
    --primary: #0d6efd;
    --dark: #212529;
}}

body {{
    font-family: 'Segoe UI', sans-serif;
    background-color: #f8f9fa;
}}

.navbar-brand {{
    font-weight: bold;
    font-size: 1.4rem;
}}

.table th {{
    font-weight: 600;
}}

.btn {{
    border-radius: 6px;
}}

footer {{
    margin-top: auto;
}}
""",

    "javascript": """// site.js — Custom JavaScript

document.addEventListener('DOMContentLoaded', function () {{
    // Auto-dismiss alerts after 3 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {{
        setTimeout(function () {{
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert.close();
        }}, 3000);
    }});

    // Confirm delete dialogs
    document.querySelectorAll('[data-confirm]').forEach(function (el) {{
        el.addEventListener('click', function (e) {{
            if (!confirm(el.dataset.confirm)) {{
                e.preventDefault();
            }}
        }});
    }});
}});
""",

    "viewmodel": """using System.ComponentModel.DataAnnotations;

public class {name}ViewModel
{{
    public int Id {{ get; set; }}

    [Required(ErrorMessage = "Name is required")]
    [StringLength(200, ErrorMessage = "Max 200 characters")]
    [Display(Name = "Name")]
    public string Name {{ get; set; }} = string.Empty;

    [StringLength(1000)]
    [Display(Name = "Description")]
    public string Description {{ get; set; }} = string.Empty;

    [Display(Name = "Active")]
    public bool IsActive {{ get; set; }} = true;

    [Display(Name = "Created")]
    public DateTime CreatedAt {{ get; set; }} = DateTime.UtcNow;
}}
""",

    "page_model": """using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;

public class {name}Model : PageModel
{{
    private readonly AppDbContext _context;

    public {name}Model(AppDbContext context)
    {{
        _context = context;
    }}

    [BindProperty]
    public object Item {{ get; set; }} = new();

    public IList<object> Items {{ get; set; }} = new List<object>();

    public async Task OnGetAsync()
    {{
        // Items = await _context.YourTable.ToListAsync();
    }}

    public async Task<IActionResult> OnPostAsync()
    {{
        if (!ModelState.IsValid)
            return Page();

        // _context.Add(Item);
        // await _context.SaveChangesAsync();

        return RedirectToPage("./Index");
    }}

    public async Task<IActionResult> OnPostDeleteAsync(int id)
    {{
        // var item = await _context.YourTable.FindAsync(id);
        // if (item != null) _context.Remove(item);
        // await _context.SaveChangesAsync();

        return RedirectToPage("./Index");
    }}
}}
""",

})

# Update roles and keywords
DOTNET_TEMPLATED_ROLES.update({
    "program_mvc", "mvc_controller", "view_index", "view_form",
    "layout", "css", "javascript", "viewmodel", "page_model"
})

DOTNET_ROLE_KEYWORDS.update({
    "program_mvc":    ["program", "startup", "main", "app"],
    "mvc_controller": ["mvccontroller", "homecontroller", "pagecontroller"],
    "view_index":     ["view", "index", "list", "listview"],
    "view_form":      ["form", "create", "edit", "formview"],
    "layout":         ["layout", "_layout", "masterpage", "template"],
    "css":            ["css", "style", "stylesheet", "site.css"],
    "javascript":     ["javascript", "js", "script", "site.js"],
    "viewmodel":      ["viewmodel", "vm"],
    "page_model":     ["pagemodel", "razorpage", "page"],
})

# Update planning prompt for full websites
DOTNET_FULLSTACK_PLANNING_PROMPT = """You are a senior ASP.NET Core MVC architect.
List the files needed to build a COMPLETE WEBSITE for: {task}

Output ONLY this format (one per line):
FileName:role

Available roles:
Backend:  controller, mvc_controller, model, service, repository, dbcontext, interface, middleware, program_mvc, dto, viewmodel
Frontend: view_index, view_form, layout, css, javascript, page_model

RULES:
- Include BOTH backend AND frontend files
- Controller names MUST end with exactly "Controller" — NEVER "MvcController", "ApiController"
- NEVER include Program or program files — those are auto-generated
- NEVER include AppDbContext — it is auto-generated
- For each entity: model + controller + view_index
- Max 6 files

Example for "products website":
ProductsController:mvc_controller
Product:model
ProductViewModel:viewmodel
ProductIndex:view_index
ProductForm:view_form
site.css:css
"""
