import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen
from unittest.mock import patch

from textifai.web_viewer.ingestion_jobs import (
    IngestionJob,
    IngestionJobRegistry,
    build_ingestion_command,
    detect_job_result,
    log_json,
    sanitize_run_slug,
)
from textifai.web_viewer.project_reader import ProjectCatalog, build_graph, read_artifact, read_note, read_project
from textifai.web_viewer.server import _make_handler, build_ingestion_config


class TextifAIWebViewerTests(unittest.TestCase):
    def test_project_catalog_discovers_run_and_reads_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "runs" / "sample_run"
            system = run / "99_System"
            notes = run / "03_Characters" / "Profiles"
            system.mkdir(parents=True)
            notes.mkdir(parents=True)
            (notes / "sera.md").write_text(
                "---\ntags:\n- '#primary'\n---\n# Sera\n\nRelación con [[ren]].\n",
                encoding="utf-8",
            )
            obsidian_import = {
                "work": {"title": "Sample", "language": "es"},
                "chapters": [{"chapter_id": "ch_001", "chapter_title_original": "Prólogo", "summary": "Inicio."}],
                "entities": [
                    {
                        "canonical_name": "Sera",
                        "preferred_slug": "sera",
                        "entity_kind": "character",
                        "review_state": "canonical",
                        "summary": "Protagonista de prueba.",
                        "aliases": ["la princesa"],
                        "relationships": [{"target": "Ren", "type": "alliance", "facts": ["Sera conoce a Ren."]}],
                    },
                    {
                        "canonical_name": "Ren",
                        "preferred_slug": "ren",
                        "entity_kind": "character",
                        "review_state": "review",
                        "relationships": [],
                    },
                ],
            }
            (system / "obsidian_import.json").write_text(json.dumps(obsidian_import), encoding="utf-8")
            (system / "review_queue.json").write_text(
                json.dumps({"schema_version": "textifai.review_queue.v1", "item_count": 1, "items": []}),
                encoding="utf-8",
            )

            catalog = ProjectCatalog([root / "runs"])
            projects = catalog.list_projects()
            project = catalog.get_project(projects[0]["project_id"])
            payload = read_project(project)
            note = read_note(project, "03_Characters/Profiles/sera.md")
            artifact = read_artifact(project, "obsidian_import.json")
            graph = build_graph(project)

        self.assertEqual(projects[0]["name"], "sample_run")
        self.assertEqual(projects[0]["primary_count"], 1)
        self.assertEqual(projects[0]["review_queue_count"], 1)
        self.assertEqual(payload["canon"]["primaries"][0]["canonical_name"], "Sera")
        self.assertEqual(note["frontmatter"]["tags"], ["#primary"])
        self.assertEqual(artifact["json"]["work"]["title"], "Sample")
        self.assertEqual(len(graph["nodes"]), 3)
        self.assertEqual(len(graph["edges"]), 1)
        sera_node = next(node for node in graph["nodes"] if node["id"] == "entity:sera")
        self.assertEqual(sera_node["entity"]["summary"], "Protagonista de prueba.")
        self.assertEqual(sera_node["entity"]["aliases"], ["la princesa"])
        self.assertIn("#primary", sera_node["tags"])
        self.assertIn("#character", sera_node["tags"])

    def test_ingestion_config_is_preview_only_and_safe(self):
        config = build_ingestion_config()
        self.assertEqual(config["mode"], "local_path_preview_only")
        self.assertTrue(config["can_execute"])
        self.assertFalse(config["can_upload"])
        self.assertEqual(config["default_output_root"], "runs/web_ingestion")
        self.assertEqual(config["recommended_command"]["program"][:5], ["uv", "run", "python", "scripts/textifai.py", "init"])
        self.assertEqual(config["supported_input_mode"], "local_path")
        self.assertIn("upload", config["future_input_modes"])
        required = {item["name"]: item for item in config["required_fields"]}
        self.assertTrue(required["source_root"]["required"])
        self.assertTrue(required["project_title"]["required"])
        self.assertTrue(required["run_name"]["required"])
        self.assertFalse(required["skip_plugin_install"]["required"])
        self.assertTrue(required["skip_plugin_install"]["default"])

    def test_build_ingestion_command_validates_and_uses_args_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            source_root = repo_root / "source"
            output_root = repo_root / "runs" / "web_ingestion"
            source_root.mkdir(parents=True)
            spec = build_ingestion_command(
                {
                    "source_root": str(source_root),
                    "project_title": "Proyecto Demo",
                    "run_name": "Mi Run Demo",
                    "primary_language": "es",
                    "working_languages": ["es", "en"],
                    "skip_plugin_install": True,
                },
                repo_root=repo_root,
                output_root=output_root,
            )
        self.assertEqual(spec["args"][:5], ["uv", "run", "python", "scripts/textifai.py", "init"])
        self.assertIn("--vault-root", spec["args"])
        self.assertIn("--source-root", spec["args"])
        self.assertIn("--project-title", spec["args"])
        self.assertIn("--skip-plugin-install", spec["args"])
        self.assertNotIn("shell=True", " ".join(spec["args"]))

    def test_build_ingestion_command_rejects_bad_source_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            output_root = repo_root / "runs" / "web_ingestion"
            with self.assertRaisesRegex(ValueError, "source_root is required"):
                build_ingestion_command(
                    {"source_root": "", "project_title": "Demo", "run_name": "demo"},
                    repo_root=repo_root,
                    output_root=output_root,
                )
            with self.assertRaisesRegex(ValueError, "source_root does not exist"):
                build_ingestion_command(
                    {"source_root": str(repo_root / "missing"), "project_title": "Demo", "run_name": "demo"},
                    repo_root=repo_root,
                    output_root=output_root,
                )

    def test_sanitize_run_slug_and_no_overwrite_target(self):
        self.assertEqual(sanitize_run_slug("Mi Run Demo!!"), "mi_run_demo")
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            source_root = repo_root / "source"
            output_root = repo_root / "runs" / "web_ingestion"
            source_root.mkdir(parents=True)
            fixed_timestamp = "20270101T010101Z"

            class FixedDateTime:
                @staticmethod
                def now(_tz=None):
                    class _Stamp:
                        def strftime(self, _fmt):
                            return fixed_timestamp
                    return _Stamp()

            existing_target = output_root / f"{fixed_timestamp}_demo"
            existing_target.mkdir(parents=True)
            with patch("textifai.web_viewer.ingestion_jobs.datetime", FixedDateTime):
                with self.assertRaisesRegex(ValueError, "output target already exists"):
                    build_ingestion_command(
                        {"source_root": str(source_root), "project_title": "Demo", "run_name": "demo"},
                        repo_root=repo_root,
                        output_root=output_root,
                    )

    def test_result_detection_marks_inspectable_and_missing_system_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "run_001"
            output_root.mkdir(parents=True)
            warning_result = detect_job_result(output_root)
            self.assertFalse(warning_result["result_detected"])
            self.assertTrue(any("99_System" in item for item in warning_result["result_warnings"]))

            system_root = output_root / "99_System"
            system_root.mkdir(parents=True, exist_ok=True)
            (system_root / "obsidian_import.json").write_text("{}", encoding="utf-8")
            (system_root / "review_queue.json").write_text("{}", encoding="utf-8")
            inspectable_result = detect_job_result(output_root)
            self.assertTrue(inspectable_result["result_detected"])
            self.assertTrue(inspectable_result["review_queue_available"])

    def test_duplicate_active_job_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            source_root = repo_root / "src"
            source_root.mkdir(parents=True)
            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            payload = {"source_root": str(source_root), "project_title": "Demo", "run_name": "run_demo"}
            registry.create_job(payload)
            with self.assertRaisesRegex(ValueError, "active job already exists"):
                registry.create_job(payload)

    def test_log_json_redacts_and_reports_truncation(self):
        job = IngestionJob(
            job_id="job_1",
            status="running",
            created_at="2026-01-01T00:00:00+00:00",
            output_root="runs/web_ingestion/run_1",
            command_preview=["uv", "run", "python"],
            source_root="/tmp/source",
            project_title="Demo",
            run_name="demo",
        )
        job.append_log("token=abc123\n")
        job.append_log("sk-1234567890abcdefABCDEF\n")
        snapshot = log_json(job, max_chars=10)
        self.assertIn("[REDACTED]", job.snapshot()["log_tail"])
        self.assertTrue(snapshot["log_truncated"])
        self.assertIn("last_log_lines", snapshot)

    def test_jobs_list_endpoint_returns_registry_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            source_root = repo_root / "source"
            source_root.mkdir(parents=True)
            runs_root = repo_root / "runs"
            runs_root.mkdir(parents=True)
            catalog = ProjectCatalog([runs_root])
            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            registry.create_job({"source_root": str(source_root), "project_title": "Demo", "run_name": "run_demo"})
            handler = _make_handler(catalog, registry)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/api/ingestion/jobs") as response:
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=1.0)
            self.assertIn("jobs", payload)
            self.assertEqual(len(payload["jobs"]), 1)
            self.assertEqual(payload["jobs"][0]["status"], "queued")
            self.assertIn("result_detected", payload["jobs"][0])


if __name__ == "__main__":
    unittest.main()
