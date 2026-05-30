from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REACT_SHELL = REPO_ROOT / "textifai/web_viewer/react_shell"
REACT_PACKAGE_JSON = REACT_SHELL / "package.json"
NODE_MODULES = REACT_SHELL / "node_modules"
VITE_CONFIG = REACT_SHELL / "vite.config.ts"
GENERATED_BUNDLE = REPO_ROOT / "textifai/web_viewer/static/react-shell/app.js"


def _run(command: list[str], *, cwd: Path | None = None) -> tuple[bool, str]:
    try:
        proc = subprocess.run(command, cwd=cwd or REPO_ROOT, capture_output=True, text=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        return False, str(exc)
    output = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    return True, output


def _check_import(module_name: str) -> tuple[bool, str]:
    ok, detail = _run([sys.executable, "-c", f"import {module_name}"])
    return ok, detail if detail else "import ok"


def run_doctor() -> int:
    checks: list[tuple[str, str, str]] = []

    uv_bin = shutil.which("uv")
    checks.append(("uv_available", "ok" if uv_bin else "error", uv_bin or "uv missing"))

    python_under_uv = "uv" in Path(sys.executable).as_posix() or "venv" in Path(sys.executable).as_posix()
    checks.append((
        "python_context",
        "ok" if python_under_uv else "warning",
        f"sys.executable={sys.executable} (run via `uv run python scripts/dev/textifai_doctor.py`)",
    ))

    textifai_ok, textifai_detail = _check_import("textifai")
    checks.append(("project_import", "ok" if textifai_ok else "error", textifai_detail))

    sqlite_ok, sqlite_detail = _check_import("sqlite3")
    checks.append(("sqlite_stdlib", "ok" if sqlite_ok else "error", sqlite_detail))

    viewer_ok, viewer_detail = _check_import("textifai.web_viewer.server")
    checks.append(("viewer_module", "ok" if viewer_ok else "error", viewer_detail))

    node_bin = shutil.which("node")
    npm_bin = shutil.which("npm")
    checks.append(("node_available", "ok" if node_bin else "error", node_bin or "node missing"))
    checks.append(("npm_available", "ok" if npm_bin else "error", npm_bin or "npm missing"))

    if node_bin:
        ok, detail = _run(["node", "--version"])
        checks.append(("node_version", "ok" if ok else "error", detail))
    if npm_bin:
        ok, detail = _run(["npm", "--version"])
        checks.append(("npm_version", "ok" if ok else "error", detail))

    checks.append(("react_package_json", "ok" if REACT_PACKAGE_JSON.exists() else "error", str(REACT_PACKAGE_JSON)))
    checks.append(("vite_config", "ok" if VITE_CONFIG.exists() else "error", str(VITE_CONFIG)))
    checks.append((
        "react_node_modules",
        "ok" if NODE_MODULES.exists() else "warning",
        str(NODE_MODULES) if NODE_MODULES.exists() else f"missing; run `cd {REACT_SHELL} && npm ci`",
    ))
    checks.append((
        "generated_bundle",
        "ok" if GENERATED_BUNDLE.exists() else "warning",
        str(GENERATED_BUNDLE) if GENERATED_BUNDLE.exists() else "missing; run `cd textifai/web_viewer/react_shell && npm run build`",
    ))

    common_paths = [REPO_ROOT / "scripts/textifai.py", REPO_ROOT / "textifai/web_viewer/server.py", REPO_ROOT / "docs"]
    for path in common_paths:
        checks.append((f"path:{path.name}", "ok" if path.exists() else "error", str(path)))

    required_failed = any(status == "error" for _, status, _ in checks)
    overall = "ready" if not required_failed else "not_ready"
    print(f"TextifAI Environment Doctor: {overall}")
    for name, status, detail in checks:
        print(f"[{status.upper():7}] {name}: {detail}")

    report = {
        "overall": overall,
        "python_invocation": "uv run python",
        "bare_python_allowed": False,
        "checks": [{"name": name, "status": status, "detail": detail} for name, status, detail in checks],
    }
    print("\nJSON:")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if required_failed else 0


if __name__ == "__main__":
    raise SystemExit(run_doctor())
