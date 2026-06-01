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
REACT_NVMRC = REACT_SHELL / ".nvmrc"
REACT_BUILD_WRAPPER = REPO_ROOT / "scripts/dev/textifai_react_build.sh"
REQUIRED_NODE_MIN = 22
REQUIRED_NODE_MAX_EXCLUSIVE = 23


def _parse_major(version_text: str) -> int | None:
    text = version_text.strip()
    if text.startswith("v"):
        text = text[1:]
    major = text.split(".", 1)[0]
    return int(major) if major.isdigit() else None


def _read_react_package_metadata() -> tuple[str | None, str | None]:
    if not REACT_PACKAGE_JSON.exists():
        return None, None
    payload = json.loads(REACT_PACKAGE_JSON.read_text(encoding="utf-8"))
    engines = payload.get("engines") or {}
    return engines.get("node"), payload.get("packageManager")


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
    react_build_ready = True

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
        node_version = detail if ok else None
    else:
        node_version = None
    if npm_bin:
        ok, detail = _run(["npm", "--version"])
        checks.append(("npm_version", "ok" if ok else "error", detail))

    react_node_engine, react_package_manager = _read_react_package_metadata()
    checks.append((
        "react_nvmrc",
        "ok" if REACT_NVMRC.exists() else "error",
        REACT_NVMRC.read_text(encoding="utf-8").strip() if REACT_NVMRC.exists() else f"missing: {REACT_NVMRC}",
    ))
    checks.append((
        "react_node_engine",
        "ok" if react_node_engine else "error",
        react_node_engine or f"missing in {REACT_PACKAGE_JSON}",
    ))
    checks.append((
        "react_package_manager",
        "ok" if react_package_manager else "warning",
        react_package_manager or f"missing in {REACT_PACKAGE_JSON}",
    ))

    current_major = _parse_major(node_version) if node_version else None
    node_compatible = current_major is not None and REQUIRED_NODE_MIN <= current_major < REQUIRED_NODE_MAX_EXCLUSIVE
    if not node_compatible:
        react_build_ready = False
    checks.append((
        "react_node_compatibility",
        "ok" if node_compatible else "error",
        (
            f"Node {react_node_engine or '>=22 <23'} required; current={node_version}. Use {REACT_BUILD_WRAPPER}"
            if node_version
            else f"Node {react_node_engine or '>=22 <23'} required; current=missing. Use {REACT_BUILD_WRAPPER}"
        ),
    ))
    checks.append((
        "react_build_wrapper",
        "ok" if REACT_BUILD_WRAPPER.exists() else "error",
        str(REACT_BUILD_WRAPPER),
    ))

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
        str(GENERATED_BUNDLE) if GENERATED_BUNDLE.exists() else f"missing; run `{REACT_BUILD_WRAPPER}`",
    ))

    common_paths = [REPO_ROOT / "scripts/textifai.py", REPO_ROOT / "textifai/web_viewer/server.py", REPO_ROOT / "docs"]
    for path in common_paths:
        checks.append((f"path:{path.name}", "ok" if path.exists() else "error", str(path)))

    required_failed = any(status == "error" for _, status, _ in checks)
    overall = "ready" if not required_failed else "not_ready"
    print(f"TextifAI Environment Doctor: {overall}")
    print(f"react_build_ready={str(react_build_ready).lower()}")
    for name, status, detail in checks:
        print(f"[{status.upper():7}] {name}: {detail}")

    report = {
        "overall": overall,
        "react_build_ready": react_build_ready,
        "react_build_command": str(REACT_BUILD_WRAPPER),
        "react_node_engine": react_node_engine,
        "react_nvmrc": REACT_NVMRC.read_text(encoding="utf-8").strip() if REACT_NVMRC.exists() else None,
        "detected_node_version": node_version,
        "python_invocation": "uv run python",
        "bare_python_allowed": False,
        "checks": [{"name": name, "status": status, "detail": detail} for name, status, detail in checks],
    }
    print("\nJSON:")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if required_failed else 0


if __name__ == "__main__":
    raise SystemExit(run_doctor())
