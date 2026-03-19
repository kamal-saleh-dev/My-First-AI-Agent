# angular_templates.py — Angular Frontend templates

ANGULAR_SYSTEM_PROMPT = """You are a senior Angular developer.
RULES:
- Use Angular 17+ with standalone components
- Use TypeScript
- Use Angular Material or Tailwind for styling
- Return ONLY one ```typescript code block per file
- No explanations outside code blocks
- Use proper Angular decorators and lifecycle hooks
"""

ANGULAR_PLANNING_PROMPT = """You are a senior Angular architect.
List the files needed to build: {task}

Output ONLY this format (one per line):
FileName:role

Roles: component, service, module, model, guard, pipe, directive, routing, app

RULES:
- Always include: app.component:app, app.module:module, app-routing.module:routing
- For each feature: component + service
- Max 8 files

Example for "products website":
app.component:app
app.module:module
app-routing.module:routing
ProductListComponent:component
ProductFormComponent:component
ProductService:service
Product:model
"""

ANGULAR_TEMPLATES = {

    "app": """import {{ Component }} from '@angular/core';
import {{ RouterOutlet }} from '@angular/router';
import {{ CommonModule }} from '@angular/common';

@Component({{
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, CommonModule],
  template: `
    <nav class="bg-gray-800 text-white px-6 py-4">
      <div class="container mx-auto flex items-center justify-between">
        <h1 class="text-xl font-bold">MyApp</h1>
        <div class="flex gap-4">
          <a routerLink="/" class="hover:text-blue-300">Home</a>
        </div>
      </div>
    </nav>
    <main class="container mx-auto px-4 py-8">
      <router-outlet />
    </main>
  `
}})
export class {name}Component {{}}
""",

    "component": """import {{ Component, OnInit, Input, Output, EventEmitter }} from '@angular/core';
import {{ CommonModule }} from '@angular/common';
import {{ FormsModule }} from '@angular/forms';

@Component({{
  selector: 'app-{name_lower}',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="bg-white rounded-lg shadow p-4">
      <h2 class="text-xl font-semibold mb-4">{{{{ title }}}}</h2>

      <div *ngIf="loading" class="text-center py-4">Loading...</div>
      <div *ngIf="error" class="text-red-500">{{{{ error }}}}</div>

      <div *ngIf="!loading && !error">
        <div *ngFor="let item of items" class="border-b py-2">
          <span>{{{{ item | json }}}}</span>
          <button (click)="onEdit(item)" class="ml-2 text-blue-500 hover:underline text-sm">Edit</button>
          <button (click)="onDelete(item)" class="ml-2 text-red-500 hover:underline text-sm">Delete</button>
        </div>
      </div>

      <button (click)="onAdd()" class="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
        Add New
      </button>
    </div>
  `
}})
export class {name}Component implements OnInit {{
  @Input() title = '{name}';
  @Output() action = new EventEmitter<{{type: string, item: any}}>();

  items: any[] = [];
  loading = false;
  error = '';

  ngOnInit(): void {{
    this.loadData();
  }}

  loadData(): void {{
    this.loading = true;
    // inject and call your service here
    this.loading = false;
  }}

  onAdd():         {{ this.action.emit({{ type: 'add', item: null }}); }}
  onEdit(item: any): {{ this.action.emit({{ type: 'edit', item }}); }}
  onDelete(item: any): {{ this.action.emit({{ type: 'delete', item }}); }}
}}
""",

    "service": """import {{ Injectable }} from '@angular/core';
import {{ HttpClient, HttpParams }} from '@angular/common/http';
import {{ Observable, throwError }} from 'rxjs';
import {{ catchError, tap }} from 'rxjs/operators';

@Injectable({{ providedIn: 'root' }})
export class {name}Service {{
  private apiUrl = '/api/{name_lower}s';

  constructor(private http: HttpClient) {{}}

  getAll(params?: any): Observable<any[]> {{
    const httpParams = new HttpParams({{ fromObject: params || {{}} }});
    return this.http.get<any[]>(this.apiUrl, {{ params: httpParams }})
      .pipe(catchError(this.handleError));
  }}

  getById(id: number): Observable<any> {{
    return this.http.get<any>(`${{this.apiUrl}}/${{id}}`)
      .pipe(catchError(this.handleError));
  }}

  create(data: any): Observable<any> {{
    return this.http.post<any>(this.apiUrl, data)
      .pipe(catchError(this.handleError));
  }}

  update(id: number, data: any): Observable<any> {{
    return this.http.put<any>(`${{this.apiUrl}}/${{id}}`, data)
      .pipe(catchError(this.handleError));
  }}

  delete(id: number): Observable<void> {{
    return this.http.delete<void>(`${{this.apiUrl}}/${{id}}`)
      .pipe(catchError(this.handleError));
  }}

  private handleError(error: any) {{
    console.error('API error:', error);
    return throwError(() => new Error(error.message || 'Server error'));
  }}
}}
""",

    "model": """export interface {name} {{
  id?: number;
  name: string;
  description?: string;
  isActive?: boolean;
  createdAt?: Date;
}}

export interface {name}CreateDto {{
  name: string;
  description?: string;
}}

export interface {name}UpdateDto {{
  name?: string;
  description?: string;
  isActive?: boolean;
}}

export interface PaginatedResult<T> {{
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}}
""",

    "module": """import {{ NgModule }} from '@angular/core';
import {{ BrowserModule }} from '@angular/platform-browser';
import {{ HttpClientModule }} from '@angular/common/http';
import {{ FormsModule, ReactiveFormsModule }} from '@angular/forms';
import {{ AppRoutingModule }} from './app-routing.module';
import {{ AppComponent }} from './app.component';

@NgModule({{
  declarations: [AppComponent],
  imports: [
    BrowserModule,
    HttpClientModule,
    FormsModule,
    ReactiveFormsModule,
    AppRoutingModule,
  ],
  providers: [],
  bootstrap: [AppComponent]
}})
export class AppModule {{}}
""",

    "routing": """import {{ NgModule }} from '@angular/core';
import {{ RouterModule, Routes }} from '@angular/router';

const routes: Routes = [
  {{ path: '', redirectTo: '/home', pathMatch: 'full' }},
  // {{ path: 'products', component: ProductListComponent }},
  // {{ path: 'products/:id', component: ProductDetailComponent }},
  {{ path: '**', redirectTo: '/home' }},
];

@NgModule({{
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
}})
export class AppRoutingModule {{}}
""",

    "guard": """import {{ Injectable }} from '@angular/core';
import {{ CanActivate, Router, ActivatedRouteSnapshot, RouterStateSnapshot }} from '@angular/router';

@Injectable({{ providedIn: 'root' }})
export class {name}Guard implements CanActivate {{
  constructor(private router: Router) {{}}

  canActivate(route: ActivatedRouteSnapshot, state: RouterStateSnapshot): boolean {{
    const isAuthenticated = !!localStorage.getItem('token');
    if (!isAuthenticated) {{
      this.router.navigate(['/login'], {{ queryParams: {{ returnUrl: state.url }} }});
      return false;
    }}
    return true;
  }}
}}
""",

    "pipe": """import {{ Pipe, PipeTransform }} from '@angular/core';

@Pipe({{
  name: '{name_lower}',
  standalone: true
}})
export class {name}Pipe implements PipeTransform {{
  transform(value: any, ...args: any[]): any {{
    if (!value) return value;
    // Add transformation logic here
    return value;
  }}
}}
""",
}

ANGULAR_TEMPLATED_ROLES = set(ANGULAR_TEMPLATES.keys())

ANGULAR_ROLE_KEYWORDS = {
    "app":       ["app.component", "appcomponent", "root"],
    "component": ["component", "list", "detail", "form", "card", "page", "view"],
    "service":   ["service", "api", "http", "data"],
    "model":     ["model", "interface", "entity", "type"],
    "module":    ["module", "appmodule"],
    "routing":   ["routing", "routes", "router"],
    "guard":     ["guard", "auth", "permission"],
    "pipe":      ["pipe", "filter", "transform"],
}

def get_angular_role(name: str) -> str:
    nl = name.lower()
    for role, keywords in ANGULAR_ROLE_KEYWORDS.items():
        if any(kw in nl for kw in keywords):
            return role
    if nl.endswith("component"): return "component"
    if nl.endswith("service"):   return "service"
    if nl.endswith("module"):    return "module"
    if nl.endswith("guard"):     return "guard"
    if nl.endswith("pipe"):      return "pipe"
    return "component"

def get_angular_template(name: str, role: str = None) -> str:
    if role is None:
        role = get_angular_role(name)
    tpl = ANGULAR_TEMPLATES.get(role, ANGULAR_TEMPLATES["component"])
    name_lower = name.lower().replace("component","").replace("service","").strip()
    return tpl.format(name=name, name_lower=name_lower)


# ─── CSS/Style templates ──────────────────────────────────────────────────────

ANGULAR_TEMPLATES["style"] = """/* styles.css — Global Angular styles */

:root {
  --primary: #3b82f6;
  --primary-dark: #2563eb;
  --danger: #ef4444;
  --bg: #f9fafb;
  --card-bg: #ffffff;
  --text: #111827;
  --muted: #6b7280;
  --border: #e5e7eb;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Inter', sans-serif;
  background: var(--bg);
  color: var(--text);
}

.container { max-width: 1200px; margin: 0 auto; padding: 0 1rem; }

.card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 1.25rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.07);
}

.btn {
  display: inline-flex; align-items: center;
  padding: 0.45rem 1rem;
  border: none; border-radius: 0.5rem;
  font-size: 0.9rem; font-weight: 500;
  cursor: pointer; transition: background 0.2s;
}
.btn-primary { background: var(--primary); color: #fff; }
.btn-primary:hover { background: var(--primary-dark); }
.btn-danger  { background: var(--danger); color: #fff; }

.form-control {
  width: 100%; padding: 0.5rem 0.75rem;
  border: 1px solid var(--border); border-radius: 0.5rem;
  outline: none; transition: border 0.2s;
}
.form-control:focus { border-color: var(--primary); }

.table { width: 100%; border-collapse: collapse; }
.table th { padding: 0.75rem; border-bottom: 2px solid var(--border); font-weight: 600; text-align: left; }
.table td { padding: 0.75rem; border-bottom: 1px solid var(--border); }
.table tr:hover td { background: #f3f4f6; }

.spinner {
  width: 2rem; height: 2rem;
  border: 3px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
"""

ANGULAR_TEMPLATES["component_css"] = """/* {name} component styles */

:host {{ display: block; }}

.container {{ padding: 1rem; }}

.header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}}

.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}}
"""

ANGULAR_TEMPLATED_ROLES.add("style")
ANGULAR_TEMPLATED_ROLES.add("component_css")
ANGULAR_ROLE_KEYWORDS["style"]        = ["styles", "global.css", "theme"]
ANGULAR_ROLE_KEYWORDS["component_css"]= ["component.css"]

def get_angular_ext(name: str, role: str) -> str:
    """Return correct file extension for Angular files."""
    nl = name.lower()
    if role in ("style", "component_css") or nl.endswith(".css"): return ".css"
    if nl.endswith(".html"): return ".html"
    return ".ts"
