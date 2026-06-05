import json
import subprocess
import tempfile
import threading
import textwrap
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
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
from textifai.web_viewer.project_reader import ProjectCatalog, build_graph, read_artifact, read_editor_chapters, read_note, read_project
from textifai.web_viewer.project_reader import ProjectRef
from textifai.web_viewer.server import _make_handler, build_ingestion_config
from textifai.web_viewer.upload_staging import UploadSession, save_upload_session, stage_uploaded_files


class TextifAIWebViewerTests(unittest.TestCase):
    def test_pronoun_review_items_are_grouped_with_occurrence_count_and_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "runs" / "sample_run"
            system = run / "99_System"
            evidence = run / "evidence"
            chapters_dir = run / "markdown" / "Chapters"
            system.mkdir(parents=True)
            evidence.mkdir(parents=True)
            chapters_dir.mkdir(parents=True)
            (chapters_dir / "Ch_001.md").write_text("# Episodio 1\n\nElla miró puerta.\n", encoding="utf-8")
            (system / "obsidian_import.json").write_text(
                json.dumps(
                    {
                        "work": {"title": "Sample", "language": "es"},
                        "chapters": [{"chapter_id": "ch_001", "chapter_title_original": "Episodio 1"}],
                        "entities": [{"canonical_name": "Ari Mar", "entity_kind": "character", "review_state": "canonical"}],
                    }
                ),
                encoding="utf-8",
            )
            (system / "review_queue.json").write_text(
                json.dumps(
                    {
                        "schema_version": "textifai.review_queue.v1",
                        "item_count": 3,
                        "items": [
                            {"id": "p1", "target_label": "ella", "chapter_id": "ch_001", "source_refs": [{"source_ref": "src:ch_001:chunk_001"}]},
                            {"id": "p2", "target_label": "ella", "chapter_id": "ch_001", "source_refs": [{"source_ref": "src:ch_001:chunk_001"}]},
                            {"id": "n1", "target_label": "Ari Mar", "chapter_id": "ch_001", "summary": "Alias posible"},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (evidence / "source_map.json").write_text(
                json.dumps(
                    {"chunks": {"chunk_001": {"chapter_id": "ch_001", "chapter_path": "markdown/Chapters/Ch_001.md", "char_start": 0, "char_end": 18}}},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (evidence / "evidence_index.json").write_text(
                json.dumps(
                    {
                        "items": [
                            {"review_item_id": "p1", "source_ref": "src:ch_001:chunk_001", "chunk_id": "chunk_001"},
                            {"review_item_id": "p2", "source_ref": "src:ch_001:chunk_001", "chunk_id": "chunk_001"},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            catalog = ProjectCatalog([root / "runs"])
            project = catalog.get_project(catalog.list_projects()[0]["project_id"])
            payload = read_project(project)

        items = payload["canon"]["review_queue"]["decision_items"]
        pronoun_items = [row for row in items if row["type"] == "pronoun_pov"]
        self.assertEqual(len(pronoun_items), 1)
        pronoun = pronoun_items[0]
        self.assertEqual(pronoun["metadata"]["occurrence_count"], 2)
        self.assertEqual(pronoun["technical_details"]["occurrence_count"], 2)
        self.assertEqual(pronoun["technical_details"]["grouped_review_item_ids"], ["p1", "p2"])
        self.assertEqual(pronoun["metadata"]["evidence_resolution"], "resolved")
        self.assertTrue(pronoun["evidence_refs"])
        self.assertEqual(pronoun["evidence_refs"][0]["chapter_label"], "Episodio 1")
        self.assertIn("Hay fragmento de evidencia disponible", pronoun["human_reason"])
        self.assertNotEqual(pronoun["title"], "Pronombre · sin entidad sugerida")
        non_pronoun = next(row for row in items if row["type"] != "pronoun_pov")
        self.assertEqual(non_pronoun["title"], "Ari Mar → Ari Mar")

    def test_pronoun_review_without_candidates_does_not_invent_entities_and_handles_missing_source_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "runs" / "sample_run"
            system = run / "99_System"
            system.mkdir(parents=True)
            (system / "obsidian_import.json").write_text(
                json.dumps(
                    {
                        "work": {"title": "Sample", "language": "es"},
                        "chapters": [{"chapter_id": "ch_002", "chapter_title_original": "Episodio 2"}],
                        "entities": [{"canonical_name": "Sera", "entity_kind": "character", "review_state": "canonical"}],
                    }
                ),
                encoding="utf-8",
            )
            (system / "review_queue.json").write_text(
                json.dumps(
                    {
                        "schema_version": "textifai.review_queue.v1",
                        "item_count": 1,
                        "items": [
                            {
                                "id": "p3",
                                "target_label": "ella",
                                "chapter_id": "ch_002",
                                "source_refs": [{"source_ref": "src:ch_002:chunk_missing"}],
                                "candidate_entities": [],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            catalog = ProjectCatalog([root / "runs"])
            project = catalog.get_project(catalog.list_projects()[0]["project_id"])
            payload = read_project(project)

        pronoun = payload["canon"]["review_queue"]["decision_items"][0]
        self.assertEqual(pronoun["type"], "pronoun_pov")
        self.assertEqual(pronoun["candidate_entities"], [])
        self.assertIsNone(pronoun["target_entity"])
        self.assertEqual(pronoun["metadata"]["evidence_resolution"], "missing_source_map")
        self.assertIn("No hay entidad candidata sugerida", pronoun["human_reason"])
        self.assertIn("missing_source_map", pronoun["human_reason"])
        self.assertIn("Episodio 2", pronoun["title"])

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
        self.assertTrue(config["can_upload"])
        self.assertEqual(config["default_output_root"], "runs/web_ingestion")
        self.assertEqual(config["recommended_command"]["program"][:5], ["uv", "run", "python", "scripts/textifai.py", "init"])
        self.assertEqual(config["supported_input_mode"], "local_path")
        self.assertIn("upload_staging", config["supported_input_modes"])

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
        self.assertEqual(spec["args"][1:5], ["run", "python", "scripts/textifai.py", "init"])
        self.assertTrue(Path(spec["args"][0]).is_absolute())
        self.assertIn("--vault-root", spec["args"])
        self.assertIn("--source-root", spec["args"])
        self.assertIn("--project-title", spec["args"])
        self.assertIn("--skip-plugin-install", spec["args"])
        self.assertEqual(spec["input_mode"], "local_path")
        self.assertNotIn("shell=True", " ".join(spec["args"]))

    def test_build_ingestion_command_accepts_upload_session_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            output_root = repo_root / "runs" / "web_ingestion"
            session = stage_uploaded_files(repo_root, [("sample.md", b"# One\n\nBody",)])
            spec = build_ingestion_command(
                {"upload_session_id": session.upload_session_id, "project_title": "Upload Demo", "run_name": "upload-run"},
                repo_root=repo_root,
                output_root=output_root,
            )
        self.assertEqual(spec["input_mode"], "upload_session")
        self.assertEqual(spec["upload_session_id"], session.upload_session_id)
        self.assertIn(str(repo_root / "runs" / "web_ingestion_uploads" / session.upload_session_id), spec["args"])
        self.assertIn("--source-root", spec["args"])

    def test_build_ingestion_command_rejects_bad_upload_source_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            output_root = repo_root / "runs" / "web_ingestion"
            source_root = repo_root / "source"
            source_root.mkdir(parents=True)
            session = stage_uploaded_files(repo_root, [("sample.md", b"# One",)])
            with self.assertRaisesRegex(ValueError, "exactly one of source_root or upload_session_id"):
                build_ingestion_command(
                    {"source_root": str(source_root), "upload_session_id": session.upload_session_id, "project_title": "Demo", "run_name": "demo"},
                    repo_root=repo_root,
                    output_root=output_root,
                )
            with self.assertRaisesRegex(ValueError, "exactly one of source_root or upload_session_id"):
                build_ingestion_command(
                    {"project_title": "Demo", "run_name": "demo"},
                    repo_root=repo_root,
                    output_root=output_root,
                )
            with self.assertRaises(FileNotFoundError):
                build_ingestion_command(
                    {"upload_session_id": "upl_missing", "project_title": "Demo", "run_name": "demo"},
                    repo_root=repo_root,
                    output_root=output_root,
                )
            empty_session = UploadSession(upload_session_id="upl_empty", created_at="2026-01-01T00:00:00+00:00", files=[])
            save_upload_session(repo_root, empty_session)
            with self.assertRaisesRegex(ValueError, "upload session has no valid staged files"):
                build_ingestion_command(
                    {"upload_session_id": "upl_empty", "project_title": "Demo", "run_name": "demo"},
                    repo_root=repo_root,
                    output_root=output_root,
                )

    def test_build_ingestion_command_rejects_bad_source_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            output_root = repo_root / "runs" / "web_ingestion"
            with self.assertRaisesRegex(ValueError, "exactly one of source_root or upload_session_id"):
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

    def test_result_detection_distinguishes_structural_and_semantic_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "run_001"
            system_root = output_root / "99_System"
            graph_root = output_root / "graph"
            vaerl_root = output_root / "vaerl"
            system_root.mkdir(parents=True, exist_ok=True)
            graph_root.mkdir(parents=True, exist_ok=True)
            vaerl_root.mkdir(parents=True, exist_ok=True)
            (output_root / "textifai.project.json").write_text("{}", encoding="utf-8")
            (system_root / "markdown_manifest.json").write_text("{}", encoding="utf-8")
            (system_root / "markdown_graph_index.json").write_text("{}", encoding="utf-8")
            (system_root / "writer_outcome.json").write_text("{}", encoding="utf-8")

            structural = detect_job_result(output_root)
            self.assertTrue(structural["project_package_ready"])
            self.assertFalse(structural["semantic_artifacts_available"])
            self.assertEqual(structural["semantic_status"], "structural_only")

            (vaerl_root / "entities.json").write_text(json.dumps({"entities": [{"canonical_name": "Sera"}]}, ensure_ascii=False), encoding="utf-8")
            (vaerl_root / "relationships.json").write_text(json.dumps({"relationships": [{"source": "Sera", "target": "Ren"}]}, ensure_ascii=False), encoding="utf-8")
            (vaerl_root / "review_queue.json").write_text(json.dumps({"item_count": 1, "items": [{"id": "r1"}]}, ensure_ascii=False), encoding="utf-8")
            (graph_root / "graph.json").write_text(json.dumps({"nodes": [{"id": "Sera"}], "edges": [{"source": "Sera", "target": "Ren"}]}, ensure_ascii=False), encoding="utf-8")

            semantic = detect_job_result(output_root)
            self.assertTrue(semantic["semantic_artifacts_available"])
            self.assertEqual(semantic["semantic_status"], "semantic_ready")
            self.assertEqual(semantic["semantic_artifact_counts"]["entities"], 1)
            self.assertEqual(semantic["semantic_artifact_counts"]["review_items"], 1)

    def test_structural_only_job_does_not_fake_workspace_or_project_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            session = stage_uploaded_files(repo_root, [("chapter.md", b"chapter body",)])
            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            job = registry.create_job({"upload_session_id": session.upload_session_id, "project_title": "Demo", "run_name": "upload"})
            job.finalize(
                status="succeeded",
                project_id="proj_1",
                result_detected=True,
                project_package_ready=True,
                semantic_artifacts_available=False,
                semantic_status="structural_only",
                result_warnings=["semantic artifacts not found; deterministic structural package is not semantic/VaERL ready"],
                result_status="completed_with_warnings",
            )
            payload = job.snapshot()
        stages = {stage["id"]: stage for stage in payload["stage_status"]["stages"]}
        self.assertEqual(payload["stage_status"]["global_status"], "completed_with_warnings")
        self.assertFalse(payload["stage_status"]["project_ready"])
        self.assertEqual(stages["building_vaerl"]["status"], "warning")
        self.assertEqual(stages["workspace_ready"]["status"], "warning")
        self.assertIn("semantic artifacts not found", " ".join(payload["result_warnings"]).casefold())

    def test_semantic_ready_job_completes_semantic_workspace_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            session = stage_uploaded_files(repo_root, [("chapter.md", b"chapter body",)])
            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            job = registry.create_job({"upload_session_id": session.upload_session_id, "project_title": "Demo", "run_name": "upload"})
            job.finalize(
                status="succeeded",
                project_id="proj_1",
                result_detected=True,
                project_package_ready=True,
                semantic_artifacts_available=True,
                semantic_status="semantic_ready",
                semantic_artifact_counts={"entities": 1, "relationships": 1, "graph_nodes": 2, "graph_edges": 1, "review_items": 1},
                result_status="completed",
            )
            payload = job.snapshot()
        stages = {stage["id"]: stage for stage in payload["stage_status"]["stages"]}
        self.assertEqual(payload["stage_status"]["global_status"], "completed")
        self.assertTrue(payload["stage_status"]["project_ready"])
        self.assertEqual(stages["extracting_entities"]["status"], "completed")
        self.assertEqual(stages["building_vaerl"]["status"], "completed")
        self.assertEqual(stages["normalizing_entities"]["status"], "completed")
        self.assertEqual(stages["building_graph"]["status"], "completed")
        self.assertEqual(stages["building_review_queue"]["status"], "completed")
        self.assertEqual(stages["validating_project"]["status"], "completed")
        self.assertEqual(stages["workspace_ready"]["status"], "completed")

    def test_no_project_package_keeps_workspace_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            session = stage_uploaded_files(repo_root, [("chapter.md", b"chapter body",)])
            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            job = registry.create_job({"upload_session_id": session.upload_session_id, "project_title": "Demo", "run_name": "upload"})
            job.finalize(status="succeeded", result_detected=False, result_warnings=["99_System directory not found"], result_status="warning")
            payload = job.snapshot()
        stages = {stage["id"]: stage for stage in payload["stage_status"]["stages"]}
        self.assertEqual(payload["stage_status"]["global_status"], "completed_with_warnings")
        self.assertFalse(payload["stage_status"]["project_ready"])
        self.assertEqual(stages["building_vaerl"]["status"], "warning")
        self.assertEqual(stages["workspace_ready"]["status"], "warning")

    def test_result_detection_surfaces_bootstrap_failures_as_warnings_not_success_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "run_001"
            system_root = output_root / "99_System"
            system_root.mkdir(parents=True, exist_ok=True)
            (output_root / "textifai.project.json").write_text("{}", encoding="utf-8")
            (system_root / "markdown_manifest.json").write_text("{}", encoding="utf-8")
            (system_root / "markdown_graph_index.json").write_text("{}", encoding="utf-8")
            (system_root / "writer_outcome.json").write_text("{}", encoding="utf-8")
            (system_root / "bootstrap_progress.jsonl").write_text(json.dumps({"event": "chapter_extraction_failed", "chapter_title": "Capítulo 1", "failure_type": "parse_failure", "attempt_count": 3}) + "\n", encoding="utf-8")

            detection = detect_job_result(output_root)

        self.assertIn("Chapter extraction warning", " ".join(detection["result_warnings"]))
        self.assertEqual(detection["semantic_status"], "structural_only")

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
            self.assertEqual(payload["input_mode"], "local_path")
            self.assertEqual(payload["stage_status"]["schema"], "textifai.ingestion_job_progress.v1")
            self.assertIn("detecting_chapters", [stage["id"] for stage in payload["stage_status"]["stages"]])
            self.assertIn("command_preview", payload)

    def test_upload_backed_job_snapshot_exposes_truthful_stage_status_without_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            session = stage_uploaded_files(repo_root, [("chapter.md", b"secret chapter body",)])
            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            job = registry.create_job({"upload_session_id": session.upload_session_id, "project_title": "Demo", "run_name": "upload"})
            payload = job.snapshot()
        self.assertEqual(payload["input_mode"], "upload_session")
        self.assertEqual(payload["upload_session_id"], session.upload_session_id)
        self.assertTrue(Path(payload["output_root"]).is_relative_to(repo_root / "runs" / "web_ingestion"))
        self.assertEqual(payload["stage_status"]["global_status"], "queued")
        stages = {stage["id"]: stage for stage in payload["stage_status"]["stages"]}
        self.assertEqual(stages["preparing_manuscript"]["label"], "Preparing manuscript")
        self.assertEqual(stages["preparing_manuscript"]["status"], "completed")
        self.assertEqual(stages["detecting_chapters"]["label"], "Detecting chapters")
        self.assertEqual(stages["detecting_chapters"]["status"], "running")
        self.assertEqual(stages["writing_markdown"]["label"], "Creating markdown chapters")
        self.assertEqual(stages["writing_markdown"]["status"], "pending")
        self.assertEqual(stages["writing_markdown"].get("progress"), 0)
        self.assertNotIn("secret chapter body", json.dumps(payload))

    def test_finished_ingestion_snapshot_exposes_restored_phase_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            session = stage_uploaded_files(repo_root, [("chapter.md", b"chapter body",)])
            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            job = registry.create_job({"upload_session_id": session.upload_session_id, "project_title": "Demo", "run_name": "upload"})
            job.finalize(status="succeeded", project_id="proj_1", result_detected=True, review_queue_available=True, inspectable_artifacts_available=True, result_status="completed")
            payload = job.snapshot()
        stages = {stage["id"]: stage for stage in payload["stage_status"]["stages"]}
        self.assertEqual(payload["stage_status"]["global_status"], "completed")
        self.assertEqual(stages["workspace_ready"]["label"], "Workspace ready")
        self.assertEqual(stages["workspace_ready"]["status"], "completed")
        self.assertNotEqual(payload["stage_status"]["current_stage_id"], "upload_session")

    def test_completed_warning_without_project_keeps_full_stage_contract_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            session = stage_uploaded_files(repo_root, [("chapter.md", b"chapter body",)])
            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            job = registry.create_job({"upload_session_id": session.upload_session_id, "project_title": "Demo", "run_name": "upload"})
            job.finalize(status="succeeded", result_detected=False, result_warnings=["obsidian_import.json not found"], result_status="warning")
            payload = job.snapshot()
        stages = {stage["id"]: stage for stage in payload["stage_status"]["stages"]}
        self.assertEqual(payload["stage_status"]["global_status"], "completed_with_warnings")
        self.assertFalse(payload["stage_status"]["project_ready"])
        self.assertIsNone(payload["stage_status"]["progress"])
        self.assertEqual(payload["stage_status"]["current_stage_id"], "extracting_entities")
        for stage_id in [
            "preparing_manuscript",
            "detecting_chapters",
            "writing_markdown",
            "extracting_entities",
            "building_vaerl",
            "normalizing_entities",
            "building_graph",
            "building_review_queue",
            "validating_project",
            "workspace_ready",
        ]:
            self.assertIn(stage_id, stages)
        self.assertEqual(stages["extracting_entities"]["status"], "warning")
        self.assertEqual(stages["building_vaerl"]["status"], "warning")
        self.assertEqual(stages["workspace_ready"]["status"], "warning")

    def test_finished_ingestion_snapshot_marks_semantic_stages_warning_for_structural_only_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            session = stage_uploaded_files(repo_root, [("chapter.md", b"chapter body",)])
            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            job = registry.create_job({"upload_session_id": session.upload_session_id, "project_title": "Demo", "run_name": "upload"})
            job.finalize(
                status="succeeded",
                project_id="proj_1",
                result_detected=True,
                project_package_ready=True,
                semantic_artifacts_available=False,
                semantic_status="structural_only",
                result_warnings=["semantic provider unavailable"],
                result_status="completed_with_warnings",
            )
            payload = job.snapshot()
        stages = {stage["id"]: stage for stage in payload["stage_status"]["stages"]}
        self.assertEqual(payload["stage_status"]["global_status"], "completed_with_warnings")
        self.assertFalse(payload["stage_status"]["project_ready"])
        self.assertEqual(stages["writing_markdown"]["status"], "completed")
        self.assertEqual(stages["extracting_entities"]["status"], "warning")
        self.assertEqual(stages["building_vaerl"]["status"], "warning")
        self.assertEqual(stages["building_graph"]["status"], "warning")
        self.assertEqual(stages["workspace_ready"]["status"], "warning")

    def test_read_editor_chapters_uses_manifest_paths_when_kind_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            chapters_dir = project_root / "04_Story" / "Chapters"
            chapters_dir.mkdir(parents=True)
            (project_root / "99_System").mkdir(parents=True)
            manifest = {
                "schema": "textifai.project",
                "title": "Demo",
                "paths": {},
            }
            (project_root / "textifai.project.json").write_text(json.dumps(manifest), encoding="utf-8")
            markdown_manifest = {
                "notes": [
                    {"path": "04_Story/Chapters/ch_002.md", "title": "Two"},
                    {"path": "04_Story/Chapters/ch_001.md", "title": "One"},
                    {"path": "04_Story/Chapter_Summaries/summary.md", "title": "Skip"},
                ]
            }
            project = ProjectRef(project_id="demo", name="project", root=project_root, system_root=project_root / "99_System", kind="textifai_project", manifest_path=project_root / "textifai.project.json", manifest=manifest)
            chapters = read_editor_chapters(project, markdown_manifest=markdown_manifest)
        self.assertEqual([chapter["path"] for chapter in chapters["chapters"]], ["04_Story/Chapters/ch_001.md", "04_Story/Chapters/ch_002.md"])

    def test_stage_snapshot_uses_progress_jsonl_for_sequential_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / "source").mkdir(parents=True)
            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            job = registry.create_job({"source_root": str(repo_root / "source"), "project_title": "Demo", "run_name": "demo"})
            system_root = Path(job.output_root) / "99_System"
            system_root.mkdir(parents=True, exist_ok=True)
            (system_root / "bootstrap_progress.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"event": "chapter_extraction_started", "chapter_id": "ch_001"}),
                        json.dumps({"event": "chapter_extraction_completed", "chapter_id": "ch_001"}),
                        json.dumps({"event": "chapter_extraction_started", "chapter_id": "ch_002"}),
                        json.dumps({"event": "global_normalization_batch_started", "batch_index": 1, "chapter_ids": ["ch_001", "ch_002"]}),
                        json.dumps({"event": "global_normalization_batch_completed", "batch_index": 1, "chapter_ids": ["ch_001", "ch_002"]}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            payload = job.snapshot()
        stages = {stage["id"]: stage for stage in payload["stage_status"]["stages"]}
        self.assertEqual(stages["detecting_chapters"]["progress"], 50)
        self.assertEqual(stages["writing_markdown"]["progress"], 50)
        self.assertEqual(stages["extracting_entities"]["progress"], 100)

    def test_build_graph_prefers_full_semantic_graph_when_author_graph_is_only_chapters(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            (project_root / "graph").mkdir(parents=True)
            (project_root / "vaerl").mkdir(parents=True)
            (project_root / "99_System").mkdir(parents=True)
            manifest = {"paths": {"graph": "graph/graph.json"}}
            (project_root / "textifai.project.json").write_text(json.dumps(manifest), encoding="utf-8")
            (project_root / "graph" / "author_graph.json").write_text(json.dumps({"nodes": [{"id": "chapter:1", "kind": "chapter"}], "edges": []}), encoding="utf-8")
            (project_root / "graph" / "graph.json").write_text(json.dumps({"nodes": [{"id": "chapter:1", "kind": "chapter"}, {"id": "entity:sera", "kind": "character"}], "edges": [{"source": "chapter:1", "target": "entity:sera"}]}), encoding="utf-8")
            project = ProjectRef(project_id="demo", name="project", root=project_root, system_root=project_root / "99_System", kind="textifai_project", manifest_path=project_root / "textifai.project.json", manifest=manifest)
            graph = build_graph(project)
        self.assertEqual(len(graph["nodes"]), 2)
        self.assertEqual(graph["metadata"]["graph_mode"], "semantic_graph")

    def test_post_ingestion_jobs_accepts_upload_session_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / "runs").mkdir(parents=True)
            session = stage_uploaded_files(repo_root, [("chapter.md", b"private manuscript body",)])
            catalog = ProjectCatalog([repo_root / "runs"])
            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            handler = _make_handler(catalog, registry, repo_root=repo_root)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                data = json.dumps({"upload_session_id": session.upload_session_id, "project_title": "Demo", "run_name": "upload"}).encode("utf-8")
                request = Request(f"http://127.0.0.1:{server.server_port}/api/ingestion/jobs", data=data, method="POST")
                request.add_header("Content-Type", "application/json")
                with urlopen(request) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=1.0)

        self.assertEqual(payload["input_mode"], "upload_session")
        self.assertEqual(payload["upload_session_id"], session.upload_session_id)
        self.assertEqual(payload["stage_status"]["schema"], "textifai.ingestion_job_progress.v1")
        self.assertNotIn("private manuscript body", json.dumps(payload))

    def test_post_ingestion_jobs_rejects_invalid_source_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            runs_root = repo_root / "runs"
            runs_root.mkdir(parents=True)
            source_root = repo_root / "source"
            source_root.mkdir(parents=True)
            session = stage_uploaded_files(repo_root, [("chapter.md", b"body",)])
            catalog = ProjectCatalog([runs_root])
            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            handler = _make_handler(catalog, registry, repo_root=repo_root)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                cases = [
                    {"project_title": "Demo", "run_name": "none"},
                    {"source_root": str(source_root), "upload_session_id": session.upload_session_id, "project_title": "Demo", "run_name": "both"},
                    {"upload_session_id": "upl_missing", "project_title": "Demo", "run_name": "missing"},
                ]
                messages = []
                for payload in cases:
                    data = json.dumps(payload).encode("utf-8")
                    request = Request(f"http://127.0.0.1:{server.server_port}/api/ingestion/jobs", data=data, method="POST")
                    request.add_header("Content-Type", "application/json")
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(request)
                    messages.append(json.loads(caught.exception.read().decode("utf-8"))["message"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=1.0)

        self.assertIn("exactly one of source_root or upload_session_id", messages[0])
        self.assertIn("exactly one of source_root or upload_session_id", messages[1])
        self.assertTrue(any("upload_session.json" in message for message in messages))

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

    def test_no_destructive_endpoints_exist_and_upload_staging_is_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            runs_root = repo_root / "runs"
            runs_root.mkdir(parents=True)
            catalog = ProjectCatalog([runs_root])
            registry = IngestionJobRegistry(repo_root=repo_root, start_immediately=False)
            handler = _make_handler(catalog, registry, repo_root=repo_root)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with self.assertRaises(HTTPError) as caught:
                    urlopen(f"http://127.0.0.1:{server.server_port}/api/ingestion/uploads")
                self.assertEqual(caught.exception.code, 400)
                payload = json.loads(caught.exception.read().decode('utf-8'))
                self.assertEqual(payload['error'], 'bad_request')
                self.assertIn('upload_session_id is required', payload['message'])
                for path in ("/api/ingestion/jobs/delete", "/api/ingestion/jobs/cleanup"):
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

    def test_review_group_summary_counts_cover_groups_severity_related_object_and_legacy(self):
        grouped = _run_viewer_js_export(
            "groupReviewItemsForPresentation",
            [
                {
                    "review_type": "entity_retention_review",
                    "severity": "medium",
                    "source_entity": "Ari Mar",
                    "target_text": "el capitán del paso",
                    "suggested_action": "review_attach_role_or_title",
                    "evidence": [{"text": "rol", "chapter_id": "ch_001"}],
                    "candidate_entities": [{"canonical_name": "Ari Mar", "entity_kind": "character"}],
                    "metadata": {
                        "recommended_action": "review_attach_role_or_title",
                        "descriptor_category": "role_descriptor",
                        "signal_tier": "medium",
                        "candidate_requires_review": True,
                        "do_not_auto_merge": True,
                        "do_not_auto_promote": True,
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
                    "evidence": [{"text": "variante", "chapter_id": "ch_002"}],
                    "candidate_entities": [{"canonical_name": "Ari Mar", "entity_kind": "character"}],
                    "metadata": {
                        "recommended_action": "review_attach_role_or_title",
                        "descriptor_category": "role_descriptor",
                        "signal_tier": "low",
                        "candidate_requires_review": True,
                        "degraded_due_to_equivalent_signal": True,
                        "equivalent_signal_group": "ari-role-1",
                        "primary_equivalent_surface": "el capitán del paso",
                    },
                },
                {
                    "review_type": "entity_retention_review",
                    "severity": "high",
                    "source_entity": "llave de cristal",
                    "target_text": "llave de cristal",
                    "suggested_action": "review_create_primary",
                    "evidence": [{"text": "objeto durable", "chapter_id": "ch_003"}],
                    "candidate_entities": [],
                    "metadata": {
                        "recommended_action": "review_create_primary",
                        "candidate_status": "no_clear_existing_primary",
                        "semantic_value": "durable_object",
                    },
                },
                {
                    "review_type": "review_entity",
                    "severity": "low",
                    "source_entity": "mención vieja",
                    "target_text": "algo viejo",
                    "suggested_action": "",
                    "candidate_entities": [],
                    "metadata": {},
                },
            ],
        )
        summary = _run_viewer_js_export("summarizeReviewPresentationGroups", grouped)
        self.assertEqual(summary["total_groups"], 2)
        self.assertEqual(summary["requires_human_review_groups"], 1)
        self.assertEqual(summary["groups_by_highest_severity"]["high"], 1)
        self.assertEqual(summary["groups_by_highest_severity"]["medium"], 1)
        self.assertEqual(summary["groups_with_related_items"], 1)
        self.assertEqual(summary["object_retention_groups"], 1)
        self.assertEqual(summary["legacy_ungrouped_count"], 1)

    def test_review_group_header_and_summary_render_candidate_action_counts_and_badges(self):
        grouped = {
            "groups": [
                {
                    "group_type": "descriptor_group",
                    "group_key": "descriptor|ari",
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
                        "evidence": [{"text": "rol", "chapter_id": "ch_001"}],
                        "metadata": {
                            "recommended_action": "review_attach_role_or_title",
                            "signal_tier": "medium",
                            "candidate_requires_review": True,
                            "do_not_auto_merge": True,
                            "do_not_auto_promote": True,
                            "future_viewer_actions": ["attach_role_or_title"],
                        },
                    },
                    "related_items": [
                        {
                            "review_type": "entity_retention_review",
                            "severity": "low",
                            "source_entity": "Ari Mar",
                            "target_text": "el custodio del paso",
                            "suggested_action": "review_attach_role_or_title",
                            "evidence": [{"text": "variante", "chapter_id": "ch_002"}],
                            "candidate_entities": [{"canonical_name": "Ari Mar", "entity_kind": "character"}],
                            "metadata": {
                                "recommended_action": "review_attach_role_or_title",
                                "signal_tier": "low",
                                "degraded_due_to_equivalent_signal": True,
                            },
                        }
                    ],
                }
            ],
            "ungrouped": [],
        }
        summary_html = _run_viewer_js_export("renderReviewPresentationSummary", grouped)
        group_html = _run_viewer_js_export("renderReviewGroupCard", grouped["groups"][0])
        self.assertIn("Total review groups", summary_html)
        self.assertIn("Requires human review", summary_html)
        self.assertIn("Groups with related/equivalent items", summary_html)
        self.assertIn("Ari Mar", group_html)
        self.assertIn("review_attach_role_or_title", group_html)
        self.assertIn("1 related", group_html)
        self.assertIn("Evidence", group_html)
        self.assertIn("Read-only", group_html)
        self.assertIn("Requires human review", group_html)

    def test_review_quick_filters_reduce_groups_by_priority_related_object_legacy_and_future_actions(self):
        grouped = {
            "groups": [
                {
                    "group_type": "descriptor_group",
                    "candidate_name": "Ari Mar",
                    "recommended_action": "review_attach_role_or_title",
                    "principal": {
                        "severity": "medium",
                        "source_entity": "Ari Mar",
                        "target_text": "el capitán del paso",
                        "suggested_action": "review_attach_role_or_title",
                        "candidate_entities": [{"canonical_name": "Ari Mar", "entity_kind": "character"}],
                        "metadata": {
                            "candidate_requires_review": True,
                            "recommended_action": "review_attach_role_or_title",
                            "future_viewer_actions": ["attach_role_or_title"],
                        },
                    },
                    "related_items": [{"severity": "low", "target_text": "el custodio del paso", "metadata": {}}],
                },
                {
                    "group_type": "object_retention_group",
                    "candidate_name": "llave de cristal",
                    "recommended_action": "review_create_primary",
                    "principal": {
                        "severity": "high",
                        "source_entity": "llave de cristal",
                        "target_text": "llave de cristal",
                        "suggested_action": "review_create_primary",
                        "candidate_entities": [],
                        "metadata": {
                            "recommended_action": "review_create_primary",
                            "candidate_status": "no_clear_existing_primary",
                        },
                    },
                    "related_items": [],
                },
            ],
            "ungrouped": [{"target_text": "algo viejo", "severity": "low", "metadata": {}}],
        }
        self.assertEqual(len(_run_viewer_js_export("applyReviewQuickFilter", {"grouped": grouped, "filterKey": "all"})["groups"]), 2)
        self.assertEqual(len(_run_viewer_js_export("applyReviewQuickFilter", {"grouped": grouped, "filterKey": "medium"})["groups"]), 1)
        self.assertEqual(len(_run_viewer_js_export("applyReviewQuickFilter", {"grouped": grouped, "filterKey": "high"})["groups"]), 1)
        self.assertEqual(len(_run_viewer_js_export("applyReviewQuickFilter", {"grouped": grouped, "filterKey": "requires_human_review"})["groups"]), 1)
        self.assertEqual(len(_run_viewer_js_export("applyReviewQuickFilter", {"grouped": grouped, "filterKey": "has_related"})["groups"]), 1)
        self.assertEqual(len(_run_viewer_js_export("applyReviewQuickFilter", {"grouped": grouped, "filterKey": "object_retention"})["groups"]), 1)
        self.assertEqual(len(_run_viewer_js_export("applyReviewQuickFilter", {"grouped": grouped, "filterKey": "future_actions"})["groups"]), 1)
        legacy_only = _run_viewer_js_export("applyReviewQuickFilter", {"grouped": grouped, "filterKey": "legacy"})
        self.assertEqual(len(legacy_only["groups"]), 0)
        self.assertEqual(len(legacy_only["ungrouped"]), 1)

    def test_review_active_filter_and_clear_filter_metadata_are_visible(self):
        active = _run_viewer_js_export("reviewQuickFilterPresentation", "medium")
        cleared = _run_viewer_js_export("reviewQuickFilterPresentation", "all")
        self.assertEqual(active["key"], "medium")
        self.assertIn("Active filter: Medium", active["label"])
        self.assertTrue(active["showClear"])
        self.assertEqual(cleared["key"], "all")
        self.assertFalse(cleared["showClear"])

    def test_candidate_centric_drilldown_lists_candidates_counts_and_filters_associated_groups(self):
        grouped = {
            "groups": [
                {
                    "group_type": "descriptor_group",
                    "candidate_name": "Ari Mar",
                    "recommended_action": "review_attach_role_or_title",
                    "principal": {
                        "severity": "medium",
                        "source_entity": "Ari Mar",
                        "target_text": "el capitán del paso",
                        "candidate_entities": [{"canonical_name": "Ari Mar", "entity_kind": "character"}],
                        "metadata": {
                            "candidate_requires_review": True,
                            "candidate_review_state": "review",
                        },
                    },
                    "related_items": [],
                },
                {
                    "group_type": "descriptor_group",
                    "candidate_name": "Luma Ser",
                    "recommended_action": "review_enrich_existing_entity",
                    "principal": {
                        "severity": "medium",
                        "source_entity": "Luma Ser",
                        "target_text": "la navegante velada",
                        "candidate_entities": [{"canonical_name": "Luma Ser", "entity_kind": "character"}],
                        "metadata": {
                            "candidate_requires_review": True,
                            "candidate_review_state": "review",
                        },
                    },
                    "related_items": [],
                },
            ],
            "ungrouped": [{"target_text": "algo viejo", "severity": "low", "metadata": {}}],
        }
        candidates = _run_viewer_js_export("deriveReviewCandidates", grouped)
        self.assertEqual([entry["name"] for entry in candidates], ["Ari Mar", "Luma Ser"])
        self.assertEqual(candidates[0]["group_count"], 1)
        self.assertEqual(candidates[0]["review_state"], "review")
        self.assertTrue(candidates[0]["requires_human_review"])
        filtered = _run_viewer_js_export("applyReviewCandidateFilter", {"grouped": grouped, "candidateName": "Ari Mar"})
        self.assertEqual(len(filtered["groups"]), 1)
        self.assertEqual(filtered["groups"][0]["candidate_name"], "Ari Mar")
        self.assertEqual(len(filtered["ungrouped"]), 1)
        all_again = _run_viewer_js_export("applyReviewCandidateFilter", {"grouped": grouped, "candidateName": ""})
        self.assertEqual(len(all_again["groups"]), 2)

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
        self.assertIn("summarizeReviewPresentationGroups", source)
        self.assertIn("renderReviewPresentationSummary", source)
        self.assertIn("applyReviewQuickFilter", source)
        self.assertIn("deriveReviewCandidates", source)
        self.assertIn("applyReviewCandidateFilter", source)
        self.assertIn("review-group", source)
        self.assertNotIn("fetch(\"/api/review", source)
        self.assertNotIn("/api/review/merge", source)
        self.assertNotIn("/api/review/promote", source)


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
          documentElement: {{ dataset: {{ ui: "legacy" }} }},
          getElementById(id) {{
            if (!elements.has(id)) elements.set(id, elementFactory());
            return elements.get(id);
          }},
          querySelectorAll() {{
            return [];
          }},
          addEventListener() {{}},
          removeEventListener() {{}},
        }};
        const context = {{
          console,
          setTimeout,
          clearTimeout,
          document,
          window: {{ location: {{ search: "" }} }},
          fetch: async () => ({{ ok: true, json: async () => [] }}),
          URLSearchParams,
          globalThis: {{}},
        }};
        context.window = context;
        context.location = {{ search: "" }};
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
