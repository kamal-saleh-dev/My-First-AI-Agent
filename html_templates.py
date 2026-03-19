# html_templates.py — Plain HTML/CSS/JS templates (no framework)

HTML_SYSTEM_PROMPT = """You are a senior frontend developer.
RULES:
- Write clean semantic HTML5, modern CSS3, vanilla JavaScript
- Use Bootstrap 5 CDN for styling unless told otherwise
- Return ONLY one ```html code block per file
- No explanations outside code blocks
- Make responsive layouts by default
- Use fetch() API for backend calls
"""

HTML_PLANNING_PROMPT = """You are a senior frontend architect.
List the files needed to build: {task}

Output ONLY this format (one per line):
FileName:role

Roles: page, layout, css, javascript, component

RULES:
- Always include at least: index:page, style:css, app:javascript
- One file per page/feature
- Max 6 files

Example for "products website":
index:page
products:page
style:css
app:javascript
"""

HTML_TEMPLATES = {

    "page": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{name}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" />
    <link rel="stylesheet" href="style.css" />
</head>
<body>

  <!-- Navbar -->
  <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
    <div class="container">
      <a class="navbar-brand fw-bold" href="index.html">MyApp</a>
      <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#nav">
        <span class="navbar-toggler-icon"></span>
      </button>
      <div class="collapse navbar-collapse" id="nav">
        <ul class="navbar-nav ms-auto">
          <li class="nav-item"><a class="nav-link" href="index.html">Home</a></li>
        </ul>
      </div>
    </div>
  </nav>

  <!-- Main Content -->
  <main class="container mt-4">
    <h1 class="mb-4">{name}</h1>

    <!-- Loading -->
    <div id="loading" class="text-center py-5 d-none">
      <div class="spinner-border text-primary"></div>
    </div>

    <!-- Error -->
    <div id="error" class="alert alert-danger d-none"></div>

    <!-- Content -->
    <div id="content">
      <div class="row" id="items-grid">
        <!-- Items loaded here by JavaScript -->
      </div>
    </div>
  </main>

  <!-- Add/Edit Modal -->
  <div class="modal fade" id="itemModal" tabindex="-1">
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">Item</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
        </div>
        <div class="modal-body">
          <form id="itemForm">
            <div class="mb-3">
              <label class="form-label">Name</label>
              <input type="text" id="itemName" class="form-control" required />
            </div>
            <div class="mb-3">
              <label class="form-label">Description</label>
              <textarea id="itemDesc" class="form-control" rows="3"></textarea>
            </div>
          </form>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
          <button type="button" class="btn btn-primary" id="saveBtn">Save</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Footer -->
  <footer class="bg-dark text-white text-center py-3 mt-5">
    <p class="mb-0">&copy; 2024 MyApp</p>
  </footer>

  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
  <script src="app.js"></script>
</body>
</html>
""",

    "css": """/* style.css — Custom styles */

:root {{
  --primary: #0d6efd;
  --dark: #212529;
  --light-bg: #f8f9fa;
}}

body {{
  background-color: var(--light-bg);
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}}

/* Cards */
.item-card {{
  transition: transform 0.2s, box-shadow 0.2s;
  border: none;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}}
.item-card:hover {{
  transform: translateY(-3px);
  box-shadow: 0 6px 16px rgba(0,0,0,0.15);
}}

/* Buttons */
.btn {{ border-radius: 6px; }}

/* Navbar */
.navbar-brand {{ font-size: 1.3rem; }}

/* Loading spinner */
.spinner-overlay {{
  position: fixed; inset: 0;
  background: rgba(255,255,255,0.7);
  display: flex; align-items: center; justify-content: center;
  z-index: 9999;
}}

/* Responsive table */
@media (max-width: 768px) {{
  .table-responsive {{ font-size: 0.85rem; }}
}}
""",

    "javascript": """// app.js — Main JavaScript

const API = '/api';

// ─── Utilities ──────────────────────────────────────────
const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

function showLoading(show) {{
  document.getElementById('loading')?.classList.toggle('d-none', !show);
}}

function showError(msg) {{
  const el = document.getElementById('error');
  if (el) {{ el.textContent = msg; el.classList.toggle('d-none', !msg); }}
}}

// ─── API Client ─────────────────────────────────────────
const api = {{
  get:    (url)       => fetch(`${{API}}${{url}}`).then(r => r.ok ? r.json() : Promise.reject(r)),
  post:   (url, data) => fetch(`${{API}}${{url}}`, {{ method:'POST',   headers:{{'Content-Type':'application/json'}}, body: JSON.stringify(data) }}).then(r => r.json()),
  put:    (url, data) => fetch(`${{API}}${{url}}`, {{ method:'PUT',    headers:{{'Content-Type':'application/json'}}, body: JSON.stringify(data) }}).then(r => r.json()),
  delete: (url)       => fetch(`${{API}}${{url}}`, {{ method:'DELETE' }}).then(r => r.ok),
}};

// ─── Render ─────────────────────────────────────────────
function renderItems(items) {{
  const grid = document.getElementById('items-grid');
  if (!grid) return;
  grid.innerHTML = items.map(item => `
    <div class="col-md-4 mb-4">
      <div class="card item-card h-100">
        <div class="card-body">
          <h5 class="card-title">${{item.name}}</h5>
          <p class="card-text text-muted">${{item.description || ''}}</p>
        </div>
        <div class="card-footer d-flex gap-2">
          <button class="btn btn-sm btn-warning" onclick="editItem(${{item.id}})">Edit</button>
          <button class="btn btn-sm btn-danger"  onclick="deleteItem(${{item.id}})">Delete</button>
        </div>
      </div>
    </div>
  `).join('');
}}

// ─── CRUD ────────────────────────────────────────────────
async function loadItems() {{
  showLoading(true);
  showError('');
  try {{
    const items = await api.get('/items');
    renderItems(items);
  }} catch (err) {{
    showError('Failed to load items: ' + err.message);
  }} finally {{
    showLoading(false);
  }}
}}

async function editItem(id) {{
  const item = await api.get(`/items/${{id}}`);
  document.getElementById('itemName').value = item.name;
  document.getElementById('itemDesc').value = item.description || '';
  document.getElementById('saveBtn').onclick = () => updateItem(id);
  new bootstrap.Modal(document.getElementById('itemModal')).show();
}}

async function updateItem(id) {{
  const data = {{
    name: document.getElementById('itemName').value,
    description: document.getElementById('itemDesc').value,
  }};
  await api.put(`/items/${{id}}`, data);
  bootstrap.Modal.getInstance(document.getElementById('itemModal')).hide();
  loadItems();
}}

async function deleteItem(id) {{
  if (!confirm('Delete this item?')) return;
  await api.delete(`/items/${{id}}`);
  loadItems();
}}

// ─── Init ────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {{
  loadItems();

  document.getElementById('saveBtn')?.addEventListener('click', async () => {{
    const data = {{
      name: document.getElementById('itemName').value,
      description: document.getElementById('itemDesc').value,
    }};
    await api.post('/items', data);
    bootstrap.Modal.getInstance(document.getElementById('itemModal')).hide();
    loadItems();
  }});
}});
""",

    "component": """<!-- {name} Component — reusable HTML snippet -->

<div class="card item-card" id="{name_lower}-component">
  <div class="card-header d-flex justify-content-between align-items-center">
    <h5 class="mb-0">{name}</h5>
    <button class="btn btn-sm btn-primary" id="{name_lower}-add-btn">+ Add</button>
  </div>
  <div class="card-body">
    <div id="{name_lower}-loading" class="text-center d-none">
      <div class="spinner-border spinner-border-sm"></div>
    </div>
    <div id="{name_lower}-content">
      <!-- Dynamic content loaded here -->
    </div>
  </div>
</div>

<script>
(function() {{
  const id = '{name_lower}';

  async function load() {{
    document.getElementById(id+'-loading').classList.remove('d-none');
    try {{
      const data = await api.get('/{name_lower}s');
      document.getElementById(id+'-content').innerHTML =
        data.map(item => `<div class="py-1 border-bottom">${{item.name}}</div>`).join('');
    }} finally {{
      document.getElementById(id+'-loading').classList.add('d-none');
    }}
  }}

  document.getElementById(id+'-add-btn')?.addEventListener('click', () => {{
    // Open add form
  }});

  load();
}})();
</script>
""",
}

HTML_TEMPLATED_ROLES = set(HTML_TEMPLATES.keys())

HTML_ROLE_KEYWORDS = {
    "page":      ["page", "index", "home", "about", "contact", "dashboard", "html"],
    "css":       ["css", "style", "stylesheet"],
    "javascript":["js", "javascript", "app", "script", "main"],
    "component": ["component", "widget", "card", "section", "partial"],
}

def get_html_role(name: str) -> str:
    nl = name.lower()
    for role, keywords in HTML_ROLE_KEYWORDS.items():
        if any(kw in nl for kw in keywords):
            return role
    if nl.endswith(".html") or nl.endswith(".htm"): return "page"
    if nl.endswith(".css"):  return "css"
    if nl.endswith(".js"):   return "javascript"
    return "page"

def get_html_ext(name: str, role: str) -> str:
    if role == "css"  or name.lower().endswith(".css"):  return ".css"
    if role == "javascript" or name.lower().endswith(".js"): return ".js"
    return ".html"

def get_html_template(name: str, role: str = None) -> str:
    if role is None:
        role = get_html_role(name)
    tpl = HTML_TEMPLATES.get(role, HTML_TEMPLATES["page"])
    name_lower = name.lower().replace(".html","").replace(".css","").replace(".js","")
    return tpl.format(name=name, name_lower=name_lower)
