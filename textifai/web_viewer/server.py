from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from textifai.web_viewer.ingestion_jobs import IngestionJobRegistry, job_to_json, jobs_history_json
from textifai.web_viewer.project_reader import ProjectCatalog, read_artifact, read_note, read_project, read_entity_card


STATIC_ROOT = Path(__file__).with_name("static")
REPO_ROOT = Path(__file__).resolve().parents[2]


def build_ingestion_config() -> dict[str, object]:
    return {
        "mode": "local_path_preview_only",
        "can_execute": True,
        "can_upload": False,
        "execution_mode": "local_path_job",
        "default_output_root": "runs/web_ingestion",
        "recommended_command": {
            "program": ["uv", "run", "python", "scripts/textifai.py", "init"],
            "style": "args_list_preview",
        },
        "local_only_warning": "Local-only tool. Execution is restricted to controlled local-path jobs under runs/web_ingestion.",
        "safety_notes": [
            "Execution uses subprocess args list only; no shell interpolation.",
            "Writes are limited to dedicated runs/web_ingestion/<timestamp>_<slug>/ targets.",
            "No overwrite is allowed for target output roots.",
            "Uploads are not enabled in this MVP shell.",
            "Skip plugin install is recommended for the MVP path flow.",
            "No real vault/ directory writes are allowed from the wizard.",
        ],
        "supported_input_mode": "local_path",
        "future_input_modes": ["upload"],
        "required_fields": [
            {"name": "source_root", "required": True},
            {"name": "project_title", "required": True},
            {"name": "run_name", "required": True},
            {"name": "primary_language", "required": False},
            {"name": "working_languages", "required": False},
            {"name": "skip_plugin_install", "required": False, "default": True},
        ],
    }


def run_viewer_server(
    *,
    roots: list[str | Path],
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = False,
) -> None:
    catalog = ProjectCatalog([Path(root) for root in roots])
    registry = IngestionJobRegistry(repo_root=REPO_ROOT)
    handler = _make_handler(catalog, registry)
    server = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{port}"
    print(f"TextifAI viewer running at {url}")
    print("Roots:")
    for root in catalog.roots:
        print(f"- {root}")
    if open_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping TextifAI viewer.")
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local TextifAI run/vault viewer.")
    parser.add_argument("--root", action="append", default=[], help="Runs/vaults root to inspect. Can be repeated.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="Open the browser after startup.")
    args = parser.parse_args(argv)
    roots = args.root or ["runs", "outputs", "vaults"]
    run_viewer_server(roots=roots, host=args.host, port=args.port, open_browser=args.open)
    return 0


def _make_handler(catalog: ProjectCatalog, registry: IngestionJobRegistry):
    class ViewerHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            try:
                self._handle_get()
            except KeyError:
                self._json({"error": "not_found"}, status=404)
            except FileNotFoundError as exc:
                self._json({"error": "not_found", "message": str(exc)}, status=404)
            except ValueError as exc:
                self._json({"error": "bad_request", "message": str(exc)}, status=400)
            except Exception as exc:  # pragma: no cover - defensive server boundary
                self._json({"error": "internal_error", "message": str(exc)}, status=500)

        def do_POST(self) -> None:  # noqa: N802
            try:
                self._handle_post()
            except KeyError:
                self._json({"error": "not_found"}, status=404)
            except FileNotFoundError as exc:
                self._json({"error": "not_found", "message": str(exc)}, status=404)
            except ValueError as exc:
                self._json({"error": "bad_request", "message": str(exc)}, status=400)
            except Exception as exc:  # pragma: no cover - defensive server boundary
                self._json({"error": "internal_error", "message": str(exc)}, status=500)

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            return

        def _handle_get(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)
            if path == "/api/ingestion/config":
                self._json(build_ingestion_config())
                return
            if path == "/api/ingestion/jobs":
                self._json(jobs_history_json(registry))
                return
            if path.startswith("/api/ingestion/jobs/") and path.endswith("/log"):
                parts = path.split("/")
                if len(parts) < 5:
                    raise KeyError(path)
                job_id = unquote(parts[4])
                max_chars = 64_000
                raw = query.get("max_chars", [""])[0]
                if raw:
                    try:
                        max_chars = max(1024, min(int(raw), 512_000))
                    except ValueError:
                        raise ValueError("max_chars must be an integer") from None
                self._json(registry.get_job_log(job_id, max_chars=max_chars))
                return
            if path.startswith("/api/ingestion/jobs/"):
                parts = path.split("/")
                if len(parts) < 5:
                    raise KeyError(path)
                job_id = unquote(parts[4])
                self._json(job_to_json(registry.get_job(job_id)))
                return
            if path == "/api/projects":
                self._json({"projects": catalog.list_projects()})
                return
            if path.startswith("/api/projects/"):
                parts = path.split("/")
                project_id = unquote(parts[3]) if len(parts) > 3 else ""
                project = catalog.get_project(project_id)
                if len(parts) == 4:
                    self._json(read_project(project))
                    return
                if len(parts) == 5 and parts[4] == "graph":
                    self._json(read_project(project)["graph"])
                    return
                if len(parts) == 5 and parts[4] == "canon":
                    self._json(read_project(project)["canon"])
                    return
                if len(parts) == 5 and parts[4] == "artifacts":
                    self._json({"artifacts": read_project(project)["artifacts"]})
                    return
                if len(parts) == 5 and parts[4] == "note":
                    note_path = query.get("path", [""])[0]
                    self._json(read_note(project, note_path))
                    return
                if len(parts) == 5 and parts[4] == "entity-card":
                    node_id = query.get("node_id", [""])[0]
                    note_path = query.get("note_path", [""])[0]
                    canonical_label = query.get("canonical_label", [""])[0]
                    self._json(read_entity_card(project, node_id=node_id or None, note_path=note_path or None, canonical_label=canonical_label or None))
                    return
                if len(parts) == 5 and parts[4] == "artifact":
                    artifact_path = query.get("path", [""])[0]
                    self._json(read_artifact(project, artifact_path))
                    return
            self._static(path)

        def _handle_post(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/api/ingestion/jobs":
                raise KeyError(parsed.path)
            payload = self._json_body()
            job = registry.create_job(payload)
            self._json(job_to_json(job), status=202)

        def _static(self, path: str) -> None:
            if path in {"", "/"}:
                path = "/index.html"
            candidate = (STATIC_ROOT / path.lstrip("/")).resolve()
            if STATIC_ROOT.resolve() not in candidate.parents and candidate != STATIC_ROOT.resolve():
                self.send_error(404)
                return
            if not candidate.exists() or not candidate.is_file():
                self.send_error(404)
                return
            content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            data = candidate.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.end_headers()
            self.wfile.write(data)

        def _json(self, payload: object, *, status: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.end_headers()
            self.wfile.write(data)

        def _json_body(self) -> dict[str, object]:
            raw_length = self.headers.get("Content-Length", "0").strip()
            try:
                length = int(raw_length)
            except ValueError as exc:
                raise ValueError("invalid Content-Length") from exc
            payload = self.rfile.read(max(length, 0))
            if not payload:
                return {}
            decoded = json.loads(payload.decode("utf-8"))
            if not isinstance(decoded, dict):
                raise ValueError("JSON payload must be an object")
            return decoded

    return ViewerHandler


if __name__ == "__main__":
    raise SystemExit(main())
