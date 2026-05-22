import json
import subprocess
import tempfile
import threading
import textwrap
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen
from unittest.mock import patch

from textifai.web_viewer.ingestion_jobs import (
    JOB_LOG_FILE,
    JOB_METADATA_FILE,
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

    def test_ingestion_config_is_preview_only_and_safe(self):
        config = build_ingestion_config()
        self.assertEqual(config["mode"], "local_path_preview_only")
        self.assertTrue(config["can_execute"])
        self.assertFalse(config["can_upload"])
        self.assertEqual(config["default_output_root"], "runs/web_ingestion")
        self.assertEqual(config["recommended_command"]["program"][:5], ["uv", "run", "python", "scripts/textifai.py", "init"])
        self.assertEqual(config["supported_input_mode"], "local_path")

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

    def test_metadata_file_written_on_job_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            source_root = repo_root / "src"
            source_root.mkdir(parents=True)
            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            job = registry.create_job({"source_root": str(source_root), "project_title": "Demo", "run_name": "alpha"})
            metadata_path = Path(job.output_root) / JOB_METADATA_FILE
            self.assertTrue(metadata_path.exists())
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["job_id"], job.job_id)
            self.assertEqual(payload["status"], "queued")
            self.assertEqual(payload["log_path_relative"], JOB_LOG_FILE)
            self.assertIn("command_preview", payload)

    def test_duplicate_active_job_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            source_root = repo_root / "src"
            source_root.mkdir(parents=True)
            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            payload = {"source_root": str(source_root), "project_title": "Demo", "run_name": "run_demo"}
            registry.create_job(payload)
            with self.assertRaisesRegex(ValueError, "active job already exists|output target already exists"):
                registry.create_job(payload)

    def test_rehydrate_completed_job_and_revalidate_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            output_root = repo_root / "runs" / "web_ingestion" / "20260101T000000Z_demo"
            system_root = output_root / "99_System"
            system_root.mkdir(parents=True)
            (system_root / "obsidian_import.json").write_text("{}", encoding="utf-8")
            (system_root / "review_queue.json").write_text("{}", encoding="utf-8")
            metadata = {
                "job_id": "job_done_1",
                "status": "succeeded",
                "created_at": "2026-01-01T00:00:00+00:00",
                "started_at": "2026-01-01T00:01:00+00:00",
                "finished_at": "2026-01-01T00:02:00+00:00",
                "project_title": "Demo",
                "source_root": "/tmp/source",
                "output_root": str(output_root),
                "safe_output_root": str(repo_root / "runs" / "web_ingestion"),
                "command_preview": ["uv", "run", "python"],
                "run_name": "demo",
                "result_detected": False,
                "result_status": "warning",
            }
            (output_root / JOB_METADATA_FILE).write_text(json.dumps(metadata), encoding="utf-8")
            (output_root / JOB_LOG_FILE).write_text("line1\nline2\n", encoding="utf-8")

            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            jobs = registry.list_jobs()
            self.assertEqual(len(jobs), 1)
            job = jobs[0]
            self.assertTrue(job.restored_from_disk)
            self.assertEqual(job.status, "succeeded")
            self.assertTrue(job.result_detected)
            self.assertIsNotNone(job.project_id)

    def test_rehydrate_running_job_marked_failed_with_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            output_root = repo_root / "runs" / "web_ingestion" / "20260101T000000Z_demo"
            output_root.mkdir(parents=True)
            metadata = {
                "job_id": "job_running_1",
                "status": "running",
                "created_at": "2026-01-01T00:00:00+00:00",
                "project_title": "Demo",
                "source_root": "/tmp/source",
                "output_root": str(output_root),
                "safe_output_root": str(repo_root / "runs" / "web_ingestion"),
                "command_preview": ["uv", "run", "python"],
                "run_name": "demo",
            }
            (output_root / JOB_METADATA_FILE).write_text(json.dumps(metadata), encoding="utf-8")

            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            job = registry.list_jobs()[0]
            self.assertTrue(job.restored_from_disk)
            self.assertEqual(job.status, "failed")
            self.assertTrue(any("server restarted while job was active" in item for item in job.result_warnings))

    def test_jobs_list_includes_rehydrated_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            source_root = repo_root / "source"
            source_root.mkdir(parents=True)
            restored_output = repo_root / "runs" / "web_ingestion" / "20260101T000000Z_old"
            restored_output.mkdir(parents=True)
            (restored_output / JOB_METADATA_FILE).write_text(
                json.dumps(
                    {
                        "job_id": "job_restored_1",
                        "status": "failed",
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "project_title": "Old",
                        "source_root": "/tmp/source",
                        "output_root": str(restored_output),
                        "safe_output_root": str(repo_root / "runs" / "web_ingestion"),
                        "command_preview": ["uv"],
                        "run_name": "old",
                    }
                ),
                encoding="utf-8",
            )

            runs_root = repo_root / "runs"
            runs_root.mkdir(parents=True, exist_ok=True)
            catalog = ProjectCatalog([runs_root])
            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            registry.create_job({"source_root": str(source_root), "project_title": "New", "run_name": "new"})

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

            self.assertGreaterEqual(len(payload["jobs"]), 2)
            self.assertIn("summary", payload)
            self.assertGreaterEqual(payload["summary"]["restored_count"], 1)
            self.assertIn("ignored_output_dirs_without_metadata", payload["summary"])
            restored = next(job for job in payload["jobs"] if job["job_id"] == "job_restored_1")
            self.assertTrue(restored["restored_from_disk"])
            self.assertIn("artifact_availability", restored)
            self.assertIn("can_compare", restored)
            self.assertIn("comparability_manifest_available", restored)

    def test_log_json_falls_back_to_persisted_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "run_001"
            output_root.mkdir(parents=True)
            (output_root / JOB_LOG_FILE).write_text("token=abc123\nlinea final\n", encoding="utf-8")
            job = IngestionJob(
                job_id="job_1",
                status="failed",
                created_at="2026-01-01T00:00:00+00:00",
                output_root=str(output_root),
                command_preview=["uv", "run", "python"],
                source_root="/tmp/source",
                project_title="Demo",
                run_name="demo",
                restored_from_disk=True,
            )
            payload = log_json(job, max_chars=200)
            self.assertEqual(payload["log_source"], "persisted")
            self.assertIn("[REDACTED]", payload["log"])
            self.assertFalse(payload["warning"])

    def test_rehydrate_revalidates_missing_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            output_root = repo_root / "runs" / "web_ingestion" / "20260101T000000Z_broken"
            system_root = output_root / "99_System"
            system_root.mkdir(parents=True)
            metadata = {
                "job_id": "job_bad_1",
                "status": "succeeded",
                "created_at": "2026-01-01T00:00:00+00:00",
                "project_title": "Broken",
                "source_root": "/tmp/source",
                "output_root": str(output_root),
                "safe_output_root": str(repo_root / "runs" / "web_ingestion"),
                "command_preview": ["uv"],
                "run_name": "broken",
                "result_detected": True,
            }
            (output_root / JOB_METADATA_FILE).write_text(json.dumps(metadata), encoding="utf-8")

            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            job = registry.list_jobs()[0]
            self.assertFalse(job.result_detected)
            self.assertTrue(any("obsidian_import.json" in item for item in job.result_warnings))
            self.assertIn("semantic_invariants_audit.json", job.snapshot()["artifact_availability"])

    def test_historical_job_snapshot_exposes_artifact_flags_and_missing_project_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            output_root = repo_root / "runs" / "web_ingestion" / "20260101T000000Z_demo"
            system_root = output_root / "99_System"
            system_root.mkdir(parents=True)
            (system_root / "obsidian_import.json").write_text("{}", encoding="utf-8")
            metadata = {
                "job_id": "job_hist_1",
                "status": "succeeded",
                "created_at": "2026-01-01T00:00:00+00:00",
                "project_title": "Hist",
                "source_root": "/tmp/source",
                "output_root": str(output_root),
                "safe_output_root": str(repo_root / "runs" / "web_ingestion"),
                "command_preview": ["uv"],
                "run_name": "hist",
                "project_id": None,
            }
            (output_root / JOB_METADATA_FILE).write_text(json.dumps(metadata), encoding="utf-8")
            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            snapshot = registry.list_jobs()[0].snapshot()
            self.assertIn("artifact_availability", snapshot)
            self.assertTrue(snapshot["artifact_availability"]["obsidian_import.json"])
            self.assertIn("project_id", snapshot)
            self.assertIn("can_compare", snapshot)
            self.assertIn("compare_unavailable_reason", snapshot)

    def test_web_ingestion_folders_without_metadata_reported_but_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            output_root = repo_root / "runs" / "web_ingestion"
            (output_root / "folder_without_metadata").mkdir(parents=True)
            with_metadata = output_root / "20260101T000000Z_with_metadata"
            with_metadata.mkdir(parents=True)
            (with_metadata / JOB_METADATA_FILE).write_text(
                json.dumps(
                    {
                        "job_id": "job_with_metadata",
                        "status": "failed",
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "project_title": "Demo",
                        "source_root": "/tmp/source",
                        "output_root": str(with_metadata),
                        "safe_output_root": str(output_root),
                        "command_preview": ["uv"],
                        "run_name": "demo",
                    }
                ),
                encoding="utf-8",
            )
            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            self.assertEqual(len(registry.list_jobs()), 1)
            self.assertEqual(registry.history_summary()["ignored_output_dirs_without_metadata"], 1)

    def test_no_destructive_or_upload_endpoints_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            runs_root = repo_root / "runs"
            runs_root.mkdir(parents=True)
            catalog = ProjectCatalog([runs_root])
            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            handler = _make_handler(catalog, registry)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for path in ("/api/ingestion/uploads", "/api/ingestion/jobs/delete", "/api/ingestion/jobs/cleanup"):
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(f"http://127.0.0.1:{server.server_port}{path}")
                    self.assertEqual(caught.exception.code, 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=1.0)

    def test_review_grouping_keeps_principal_then_related_equivalents(self):
        payload = [
            {
                "review_type": "entity_retention_review",
                "severity": "medium",
                "source_entity": "Ari Mar",
                "target_text": "el capitán del paso",
                "suggested_action": "review_attach_role_or_title",
                "candidate_entities": [{"canonical_name": "Ari Mar", "entity_kind": "character"}],
                "metadata": {
                    "recommended_action": "review_attach_role_or_title",
                    "descriptor_category": "role_descriptor",
                    "signal_tier": "medium",
                    "candidate_requires_review": True,
                    "candidate_review_state": "review",
                    "do_not_auto_merge": True,
                    "do_not_auto_promote": True,
                    "future_viewer_actions": ["attach_role_or_title", "keep_secondary", "reject_noise"],
                    "equivalent_signal_group": "ari-role-1",
                    "primary_equivalent_surface": "el capitán del paso",
                },
            },
            {
                "review_type": "entity_retention_review",
                "severity": "low",
                "source_entity": "Ari Mar",
                "target_text": "el guardián del archivo",
                "suggested_action": "review_attach_role_or_title",
                "candidate_entities": [{"canonical_name": "Ari Mar", "entity_kind": "character"}],
                "metadata": {
                    "recommended_action": "review_attach_role_or_title",
                    "descriptor_category": "role_descriptor",
                    "signal_tier": "low",
                    "candidate_requires_review": True,
                    "candidate_review_state": "review",
                    "do_not_auto_merge": True,
                    "do_not_auto_promote": True,
                    "degraded_due_to_equivalent_signal": True,
                    "equivalent_signal_group": "ari-role-1",
                    "primary_equivalent_surface": "el capitán del paso",
                },
            },
            {
                "review_type": "entity_retention_review",
                "severity": "low",
                "source_entity": "Ari Mar",
                "target_text": "el custodio del paso",
                "suggested_action": "review_attach_role_or_title",
                "candidate_entities": [{"canonical_name": "Ari Mar", "entity_kind": "character"}],
                "metadata": {
                    "recommended_action": "review_attach_role_or_title",
                    "descriptor_category": "role_descriptor",
                    "signal_tier": "low",
                    "candidate_requires_review": True,
                    "candidate_review_state": "review",
                    "do_not_auto_merge": True,
                    "do_not_auto_promote": True,
                    "degraded_due_to_equivalent_signal": True,
                    "equivalent_signal_group": "ari-role-1",
                    "primary_equivalent_surface": "el capitán del paso",
                },
            },
        ]
        result = _run_viewer_js_export("groupReviewItemsForPresentation", payload)
        self.assertEqual(len(result["groups"]), 1)
        group = result["groups"][0]
        self.assertEqual(group["group_type"], "descriptor_group")
        self.assertEqual(group["principal"]["target_text"], "el capitán del paso")
        self.assertEqual([item["target_text"] for item in group["related_items"]], ["el guardián del archivo", "el custodio del paso"])
        self.assertEqual(group["candidate_name"], "Ari Mar")
        self.assertEqual(group["recommended_action"], "review_attach_role_or_title")
        self.assertEqual(group["descriptor_category"], "role_descriptor")

    def test_review_grouping_does_not_mix_candidates_actions_or_object_retention(self):
        payload = [
            {
                "review_type": "entity_retention_review",
                "severity": "medium",
                "source_entity": "Ari Mar",
                "target_text": "el capitán del paso",
                "suggested_action": "review_attach_role_or_title",
                "candidate_entities": [{"canonical_name": "Ari Mar", "entity_kind": "character"}],
                "metadata": {
                    "recommended_action": "review_attach_role_or_title",
                    "descriptor_category": "role_descriptor",
                    "equivalent_signal_group": "ari-role-1",
                    "primary_equivalent_surface": "el capitán del paso",
                },
            },
            {
                "review_type": "entity_retention_review",
                "severity": "low",
                "source_entity": "Luma Ser",
                "target_text": "la capitana del borde",
                "suggested_action": "review_attach_role_or_title",
                "candidate_entities": [{"canonical_name": "Luma Ser", "entity_kind": "character"}],
                "metadata": {
                    "recommended_action": "review_attach_role_or_title",
                    "descriptor_category": "role_descriptor",
                    "equivalent_signal_group": "luma-role-1",
                    "primary_equivalent_surface": "la capitana del borde",
                    "degraded_due_to_equivalent_signal": True,
                },
            },
            {
                "review_type": "entity_retention_review",
                "severity": "medium",
                "source_entity": "Ari Mar",
                "target_text": "el cartógrafo sin memoria",
                "suggested_action": "review_enrich_existing_entity",
                "candidate_entities": [{"canonical_name": "Ari Mar", "entity_kind": "character"}],
                "metadata": {
                    "recommended_action": "review_enrich_existing_entity",
                    "descriptor_category": "epithet_descriptor",
                },
            },
            {
                "review_type": "entity_retention_review",
                "severity": "medium",
                "source_entity": "llave de cristal",
                "target_text": "llave de cristal",
                "suggested_action": "review_create_primary",
                "candidate_entities": [],
                "metadata": {
                    "recommended_action": "review_create_primary",
                    "candidate_status": "no_clear_existing_primary",
                    "semantic_value": "durable_object",
                },
            },
        ]
        result = _run_viewer_js_export("groupReviewItemsForPresentation", payload)
        groups = result["groups"]
        self.assertEqual(len(groups), 4)
        self.assertEqual(sum(1 for group in groups if group["candidate_name"] == "Ari Mar"), 2)
        self.assertEqual(sum(1 for group in groups if group["candidate_name"] == "Luma Ser"), 1)
        object_group = next(group for group in groups if group["recommended_action"] == "review_create_primary")
        self.assertEqual(object_group["group_type"], "object_retention_group")

    def test_review_grouping_preserves_legacy_ungrouped_items_and_read_only_future_actions(self):
        payload = [
            {
                "review_type": "review_entity",
                "severity": "low",
                "source_entity": "mención difusa",
                "target_text": "algo viejo",
                "suggested_action": "",
                "candidate_entities": [],
                "metadata": {},
            }
        ]
        grouped = _run_viewer_js_export("groupReviewItemsForPresentation", payload)
        self.assertEqual(len(grouped["ungrouped"]), 1)
        self.assertEqual(grouped["ungrouped"][0]["target_text"], "algo viejo")

        rendered = _run_viewer_js_export(
            "renderReviewGroupCard",
            {
                "group": {
                    "group_type": "descriptor_group",
                    "group_key": "candidate:ari|action:review_attach_role_or_title|category:role_descriptor",
                    "candidate_name": "Ari Mar",
                    "recommended_action": "review_attach_role_or_title",
                    "descriptor_category": "role_descriptor",
                    "principal": {
                        "review_type": "entity_retention_review",
                        "severity": "medium",
                        "source_entity": "Ari Mar",
                        "target_text": "el capitán del paso",
                        "suggested_action": "review_attach_role_or_title",
                        "candidate_entities": [{"canonical_name": "Ari Mar", "entity_kind": "character"}],
                        "evidence": [],
                        "metadata": {
                            "recommended_action": "review_attach_role_or_title",
                            "signal_tier": "medium",
                            "candidate_requires_review": True,
                            "candidate_review_state": "review",
                            "do_not_auto_merge": True,
                            "do_not_auto_promote": True,
                            "future_viewer_actions": ["attach_role_or_title", "keep_secondary", "reject_noise"],
                        },
                    },
                    "related_items": [],
                }
            },
        )
        self.assertIn("Read-only", rendered)
        self.assertIn("Requires human review", rendered)
        self.assertIn("No auto-merge", rendered)
        self.assertIn("No auto-promote", rendered)
        self.assertIn("Future action: Attach role/title", rendered)
        self.assertIn("disabled", rendered)

    def test_static_viewer_future_actions_are_read_only(self):
        source = Path("textifai/web_viewer/static/app.js").read_text(encoding="utf-8")
        self.assertIn("RECOMMENDED_ACTION_VIEWER_ACTIONS", source)
        self.assertIn("VIEWER_ACTION_DESCRIPTORS", source)
        self.assertIn("future-action-button", source)
        self.assertIn("do_not_auto_merge", source)
        self.assertIn("disabled", source)
        self.assertNotIn("data-future-action-post", source)
        self.assertNotIn("/api/review/actions", source)
        self.assertIn("groupReviewItemsForPresentation", source)
        self.assertIn("renderReviewGroupCard", source)
        self.assertIn("review-group", source)
        self.assertNotIn("fetch(\"/api/review", source)


def _run_viewer_js_export(export_name, payload):
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const source = fs.readFileSync("textifai/web_viewer/static/app.js", "utf8");
        const elementFactory = () => ({{
          addEventListener() {{}},
          removeEventListener() {{}},
          classList: {{ add() {{}}, remove() {{}} }},
          dataset: {{}},
          style: {{}},
          value: "",
          checked: false,
          innerHTML: "",
          textContent: "",
          open: false,
        }});
        const elements = new Map();
        const document = {{
          getElementById(id) {{
            if (!elements.has(id)) elements.set(id, elementFactory());
            return elements.get(id);
          }},
          querySelectorAll() {{
            return [];
          }},
        }};
        const context = {{
          console,
          setTimeout,
          clearTimeout,
          document,
          window: {{}},
          fetch: async () => ({{ ok: true, json: async () => [] }}),
          globalThis: {{}},
        }};
        context.window = context;
        context.globalThis = context;
        vm.createContext(context);
        vm.runInContext(source, context, {{ filename: "app.js" }});
        const exported = context.__TEXTIFAI_REVIEW_ACTIONS__;
        const fn = exported[{json.dumps(export_name)}];
        if (typeof fn !== "function") {{
          throw new Error(`missing export: {export_name}`);
        }}
        const input = {json.dumps(payload)};
        const result = fn(input);
        process.stdout.write(JSON.stringify(result));
        """
    )
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


if __name__ == "__main__":
    unittest.main()
