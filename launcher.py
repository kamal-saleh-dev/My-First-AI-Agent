# launcher.py — Website auto-launch after generation
import os, sys, time, threading, webbrowser, subprocess, json

def launch_website(project_folder: str, engine: str):
    """Open the generated website in browser after generation."""
    import os

    folder = os.path.join("Generated_Scripts", project_folder.replace(" ", "_"))
    if not os.path.exists(folder):
        print(f"⚠ Folder not found: {folder}", flush=True)
        return

    def _launch():
        if engine == "html":
            # Plain HTML — open index.html directly
            index = os.path.join(folder, "index.html")
            if not os.path.exists(index):
                # Try first .html file
                htmls = [f for f in os.listdir(folder) if f.endswith(".html")]
                if htmls:
                    index = os.path.join(folder, htmls[0])
                else:
                    print("❌ No HTML file found to open.", flush=True)
                    return
            abs_path = os.path.abspath(index)
            print(f"🌐 Opening {abs_path} ...", flush=True)
            webbrowser.open(f"file:///{abs_path}")
            print("✅ Browser opened!", flush=True)

        elif engine == "react":
            # React — needs npm install + npm run dev
            pkg = os.path.join(folder, "package.json")
            if not os.path.exists(pkg):
                # No package.json — create minimal one
                _write_react_package_json(folder)
            print("⚙️ Installing React dependencies (npm install)...", flush=True)
            r = subprocess.run(["npm", "install"], cwd=folder, capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                print(f"❌ npm install failed: {r.stderr[:200]}", flush=True)
                return
            print("🚀 Starting React dev server (npm run dev)...", flush=True)
            proc = subprocess.Popen(["npm", "run", "dev"], cwd=folder,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                from process_registry import register
                register(proc)
            except Exception:
                pass
            time.sleep(4)
            if proc.poll() is None:
                webbrowser.open("http://localhost:5173")
                print("✅ React app running at http://localhost:5173", flush=True)
            else:
                print("❌ React server failed to start.", flush=True)

        elif engine == "angular":
            print("⚙️ Starting Angular dev server (ng serve)...", flush=True)
            proc = subprocess.Popen(
                ["npx", "@angular/cli", "serve", "--open"],
                cwd=folder, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            try:
                from process_registry import register
                register(proc)
            except Exception:
                pass
            time.sleep(6)
            if proc.poll() is None:
                print("✅ Angular app running at http://localhost:4200", flush=True)
            else:
                print("❌ Angular server failed. Run 'ng serve' manually.", flush=True)

        elif engine == "dotnet":
            print("⚙️ Restoring .NET packages (dotnet restore)...", flush=True)
            restore = subprocess.run(
                ["dotnet", "restore"],
                cwd=folder, capture_output=True, text=True, timeout=120
            )
            if restore.returncode != 0:
                print(f"❌ dotnet restore failed:\n{restore.stderr[:400]}", flush=True)
                return

            print("🔨 Building project (dotnet build)...", flush=True)
            build = subprocess.run(
                ["dotnet", "build", "--no-restore", "-c", "Release"],
                cwd=folder, capture_output=True, text=True, timeout=120
            )
            if build.returncode != 0:
                # Show only the actual error lines
                err_lines = [l for l in build.stdout.split("\n") if "error" in l.lower() or "Error" in l]
                print(f"❌ dotnet build failed:\n" + "\n".join(err_lines[:10]), flush=True)
                return

            print("🚀 Starting .NET server...", flush=True)
            env = os.environ.copy()
            env["ASPNETCORE_URLS"] = "http://localhost:5000"
            proc = subprocess.Popen(
                ["dotnet", "run", "--no-build", "-c", "Release", "--urls", "http://localhost:5000"],
                cwd=folder,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=env
            )
            try:
                from process_registry import register
                register(proc)
            except Exception:
                pass
            # Wait up to 20s for server to actually respond
            import urllib.request as _ureq
            _started = False
            for _ in range(40):
                time.sleep(0.5)
                if proc.poll() is not None:
                    break
                try:
                    resp = _ureq.urlopen("http://localhost:5000", timeout=2)
                    _started = True
                    break
                except Exception as ex:
                    # 404/403/302 = server is up but no route yet — still open browser
                    if any(c in str(ex) for c in ["404","403","302","200"]):
                        _started = True
                        break
                    # ConnectionRefused = not ready, keep waiting
            if _started or (proc.poll() is None and _ >= 15):
                webbrowser.open("http://localhost:5000")
                print("✅ .NET app running at http://localhost:5000", flush=True)
            else:
                out = proc.stderr.read().decode()[:500] if proc.poll() is not None else "Server did not respond in time"
                print(f"❌ dotnet run failed:\n{out}", flush=True)

        else:
            print(f"ℹ️ Auto-launch not supported for {engine}.", flush=True)

    # Run in background thread — don't block the agent
    t = threading.Thread(target=_launch, daemon=True)
    t.start()

def _write_react_package_json(folder: str):
    """Create a minimal Vite+React package.json if missing."""
    import json, os
    pkg = {
        "name": os.path.basename(folder).lower(),
        "version": "1.0.0",
        "scripts": {
            "dev":   "vite",
            "build": "vite build",
        },
        "dependencies": {
            "react": "^18.2.0",
            "react-dom": "^18.2.0",
            "react-router-dom": "^6.0.0"
        },
        "devDependencies": {
            "@vitejs/plugin-react": "^4.0.0",
            "vite": "^5.0.0",
            "tailwindcss": "^3.0.0"
        }
    }
    with open(os.path.join(folder, "package.json"), "w") as f:
        json.dump(pkg, f, indent=2)
    # Create minimal vite.config.js
    vite_cfg = """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig({ plugins: [react()] })
"""
    with open(os.path.join(folder, "vite.config.js"), "w") as f:
        f.write(vite_cfg)
