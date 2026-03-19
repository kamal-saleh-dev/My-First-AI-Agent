# react_templates.py — React.js Frontend templates

REACT_SYSTEM_PROMPT = """You are a senior React developer.
RULES:
- Use React 18 with functional components and hooks
- Use TypeScript when requested, otherwise JavaScript
- Use Tailwind CSS for styling unless told otherwise
- Return ONLY one ```jsx code block per file
- No explanations outside code blocks
- Use proper imports at the top of every file
"""

REACT_PLANNING_PROMPT = """You are a senior React architect.
List the files needed to build: {task}

Output ONLY this format (one per line):
FileName:role

Roles: app, page, component, hook, service, context, model, style, config

RULES:
- Always include: App:app, index:config
- For each feature: one page + components it needs
- Max 8 files

Example for "products website":
App:app
ProductsPage:page
ProductCard:component
ProductForm:component
useProducts:hook
productService:service
index:config
"""

REACT_TEMPLATES = {

    "app": """import React from 'react';
import {{ BrowserRouter as Router, Routes, Route }} from 'react-router-dom';
import Navbar from './components/Navbar';
import HomePage from './pages/HomePage';

function App() {{
  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <main className="container mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={{<HomePage />}} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}}

export default App;
""",

    "page": """import React, {{ useState, useEffect }} from 'react';

function {name}() {{
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {{
    fetchData();
  }}, []);

  const fetchData = async () => {{
    try {{
      setLoading(true);
      const response = await fetch('/api/items');
      const result = await response.json();
      setData(result);
    }} catch (err) {{
      setError(err.message);
    }} finally {{
      setLoading(false);
    }}
  }};

  if (loading) return <div className="text-center py-10">Loading...</div>;
  if (error)   return <div className="text-red-500 text-center py-10">Error: {{error}}</div>;

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">{name}</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {{data.map((item, i) => (
          <div key={{i}} className="bg-white rounded-lg shadow p-4">
            <p>{{JSON.stringify(item)}}</p>
          </div>
        ))}}
      </div>
    </div>
  );
}}

export default {name};
""",

    "component": """import React from 'react';

function {name}({{ data, onAction }}) {{
  return (
    <div className="bg-white rounded-lg shadow p-4 hover:shadow-md transition">
      <h3 className="font-semibold text-lg mb-2">{{data?.name}}</h3>
      <p className="text-gray-600 text-sm mb-4">{{data?.description}}</p>
      <div className="flex gap-2">
        <button
          onClick={{() => onAction?.('edit', data)}}
          className="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm"
        >
          Edit
        </button>
        <button
          onClick={{() => onAction?.('delete', data)}}
          className="px-3 py-1 bg-red-500 text-white rounded hover:bg-red-600 text-sm"
        >
          Delete
        </button>
      </div>
    </div>
  );
}}

export default {name};
""",

    "hook": """import {{ useState, useEffect, useCallback }} from 'react';

function {name}(initialParams = {{}}) {{
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async (params = {{}}) => {{
    setLoading(true);
    setError(null);
    try {{
      const query = new URLSearchParams({{ ...initialParams, ...params }}).toString();
      const res = await fetch(`/api/items?${{query}}`);
      if (!res.ok) throw new Error(`HTTP ${{res.status}}`);
      setData(await res.json());
    }} catch (err) {{
      setError(err.message);
    }} finally {{
      setLoading(false);
    }}
  }}, []);

  const create = async (payload) => {{
    const res = await fetch('/api/items', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify(payload),
    }});
    if (!res.ok) throw new Error('Create failed');
    await fetchData();
    return res.json();
  }};

  const update = async (id, payload) => {{
    const res = await fetch(`/api/items/${{id}}`, {{
      method: 'PUT',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify(payload),
    }});
    if (!res.ok) throw new Error('Update failed');
    await fetchData();
  }};

  const remove = async (id) => {{
    await fetch(`/api/items/${{id}}`, {{ method: 'DELETE' }});
    await fetchData();
  }};

  useEffect(() => {{ fetchData(); }}, [fetchData]);

  return {{ data, loading, error, fetchData, create, update, remove }};
}}

export default {name};
""",

    "service": """const BASE_URL = process.env.REACT_APP_API_URL || '/api';

const headers = {{ 'Content-Type': 'application/json' }};

const handle = async (res) => {{
  if (!res.ok) throw new Error(`HTTP ${{res.status}}: ${{await res.text()}}`);
  return res.json();
}};

const {name} = {{
  getAll:  (params = '') => fetch(`${{BASE_URL}}/items${{params}}`).then(handle),
  getById: (id)          => fetch(`${{BASE_URL}}/items/${{id}}`).then(handle),
  create:  (data)        => fetch(`${{BASE_URL}}/items`, {{ method: 'POST',   headers, body: JSON.stringify(data) }}).then(handle),
  update:  (id, data)    => fetch(`${{BASE_URL}}/items/${{id}}`, {{ method: 'PUT',    headers, body: JSON.stringify(data) }}).then(handle),
  remove:  (id)          => fetch(`${{BASE_URL}}/items/${{id}}`, {{ method: 'DELETE', headers }}).then(handle),
}};

export default {name};
""",

    "context": """import React, {{ createContext, useContext, useState, useCallback }} from 'react';

const {name}Context = createContext(null);

export function {name}Provider({{ children }}) {{
  const [state, setState] = useState({{
    items: [],
    selected: null,
    loading: false,
    error: null,
  }});

  const setLoading = (loading) => setState(s => ({{ ...s, loading }}));
  const setError   = (error)   => setState(s => ({{ ...s, error }}));
  const setItems   = (items)   => setState(s => ({{ ...s, items }}));
  const select     = (item)    => setState(s => ({{ ...s, selected: item }}));

  return (
    <{name}Context.Provider value={{{{ ...state, setItems, select, setLoading, setError }}}}>
      {{children}}
    </{name}Context.Provider>
  );
}}

export function use{name}() {{
  const ctx = useContext({name}Context);
  if (!ctx) throw new Error('use{name} must be inside {name}Provider');
  return ctx;
}}
""",

    "navbar": """import React from 'react';
import {{ Link, useLocation }} from 'react-router-dom';

function {name}() {{
  const {{ pathname }} = useLocation();

  const links = [
    {{ to: '/', label: 'Home' }},
    {{ to: '/about', label: 'About' }},
  ];

  return (
    <nav className="bg-white shadow-sm border-b">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        <Link to="/" className="text-xl font-bold text-blue-600">MyApp</Link>
        <ul className="flex gap-6">
          {{links.map(link => (
            <li key={{link.to}}>
              <Link
                to={{link.to}}
                className={{`text-sm font-medium ${{
                  pathname === link.to
                    ? 'text-blue-600 border-b-2 border-blue-600'
                    : 'text-gray-600 hover:text-blue-600'
                }}`}}
              >
                {{link.label}}
              </Link>
            </li>
          ))}}
        </ul>
      </div>
    </nav>
  );
}}

export default {name};
""",

    "config": """import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
""",

    "style": """/* index.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {{
  body {{
    @apply bg-gray-50 text-gray-900;
  }}
}}

@layer components {{
  .btn {{ @apply px-4 py-2 rounded font-medium transition; }}
  .btn-primary {{ @apply btn bg-blue-600 text-white hover:bg-blue-700; }}
  .btn-danger  {{ @apply btn bg-red-500 text-white hover:bg-red-600; }}
  .card        {{ @apply bg-white rounded-lg shadow p-4; }}
  .input       {{ @apply border rounded px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500; }}
}}
""",

    "form": """import React, {{ useState }} from 'react';

function {name}({{ onSubmit, onCancel, initialData = {{}} }}) {{
  const [form, setForm] = useState({{
    name: initialData.name || '',
    description: initialData.description || '',
  }});
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (e) => {{
    setForm(f => ({{ ...f, [e.target.name]: e.target.value }}));
  }};

  const handleSubmit = async (e) => {{
    e.preventDefault();
    setSubmitting(true);
    try {{
      await onSubmit?.(form);
    }} finally {{
      setSubmitting(false);
    }}
  }};

  return (
    <form onSubmit={{handleSubmit}} className="space-y-4">
      <div>
        <label className="block text-sm font-medium mb-1">Name</label>
        <input
          name="name"
          value={{form.name}}
          onChange={{handleChange}}
          className="input"
          required
        />
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Description</label>
        <textarea
          name="description"
          value={{form.description}}
          onChange={{handleChange}}
          className="input"
          rows={{3}}
        />
      </div>
      <div className="flex gap-3">
        <button type="submit" disabled={{submitting}} className="btn-primary">
          {{submitting ? 'Saving...' : 'Save'}}
        </button>
        <button type="button" onClick={{onCancel}} className="btn bg-gray-200 hover:bg-gray-300">
          Cancel
        </button>
      </div>
    </form>
  );
}}

export default {name};
""",
}

REACT_TEMPLATED_ROLES = set(REACT_TEMPLATES.keys())

REACT_ROLE_KEYWORDS = {
    "app":       ["app", "application", "root", "main"],
    "page":      ["page", "screen", "view", "home", "about", "dashboard"],
    "component": ["card", "item", "list", "button", "modal", "table", "header", "footer"],
    "hook":      ["use", "hook", "state", "logic"],
    "service":   ["service", "api", "client", "http", "fetch"],
    "context":   ["context", "provider", "store", "state"],
    "navbar":    ["navbar", "nav", "navigation", "header"],
    "config":    ["index", "main", "config", "setup"],
    "style":     ["css", "style", "index.css", "tailwind"],
    "form":      ["form", "input", "editor", "create", "edit"],
}

def get_react_role(name: str) -> str:
    nl = name.lower()
    for role, keywords in REACT_ROLE_KEYWORDS.items():
        if any(kw in nl for kw in keywords):
            return role
    if nl.endswith("page"):      return "page"
    if nl.endswith("form"):      return "form"
    if nl.startswith("use"):     return "hook"
    if nl.endswith("service"):   return "service"
    if nl.endswith("context"):   return "context"
    if nl.endswith("provider"):  return "context"
    return "component"

def get_react_ext(name: str, role: str) -> str:
    if role == "style" or name.endswith(".css"): return ".css"
    return ".jsx"

def get_react_template(name: str, role: str = None) -> str:
    if role is None:
        role = get_react_role(name)
    tpl = REACT_TEMPLATES.get(role, REACT_TEMPLATES["component"])
    return tpl.format(name=name)
