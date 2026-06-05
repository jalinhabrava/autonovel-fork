import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from textifai.conversation.contracts import ConversationRequest
from textifai.conversation.executor import MinimalExecutionLayer
from textifai.conversation.manager import ConversationManager
from textifai.obsidian import evaluate_obsidian_operational_readiness
from textifai.obsidian.setup import ObsidianProjectSetupConfig, _resolve_bootstrap_provider_and_model, prepare_obsidian_project
from textifai.runtime_config import load_runtime_environment, synchronize_runtime_environment, update_env_values
from textifai.session import create_session
from vault.bootstrap import bootstrap_vault
from vault.schema import note_frontmatter


class _FakeStructuredBootstrapResult:
    def __init__(self, obsidian_import_path: str, *, source_document: str = "source.md", chapter_count: int = 3, warnings: list[str] | None = None):
        self.obsidian_import_path = obsidian_import_path
        self.source_document = source_document
        self.chapter_count = chapter_count
        self.warnings = warnings or []


class TextifAIObsidianSetupTests(unittest.TestCase):
    def test_update_env_values_deduplicates_provider_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / ".env").write_text(
                "\n".join(
                    [
                        "AUTONOVEL_TEXT_PROVIDER=",
                        "OPENAI_API_KEY=test-key",
                        "AUTONOVEL_TEXT_PROVIDER=openai",
                        "AUTONOVEL_WRITER_MODEL=",
                        "AUTONOVEL_WRITER_MODEL=gpt-5.4",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            update_env_values(base, {"AUTONOVEL_TEXT_PROVIDER": "openai", "AUTONOVEL_WRITER_MODEL": "gpt-5.4"})
            rendered = (base / ".env").read_text(encoding="utf-8").splitlines()
            self.assertEqual(sum(1 for line in rendered if line.startswith("AUTONOVEL_TEXT_PROVIDER=")), 1)
            self.assertEqual(sum(1 for line in rendered if line.startswith("AUTONOVEL_WRITER_MODEL=")), 1)
            self.assertIn("AUTONOVEL_TEXT_PROVIDER=openai", rendered)
            self.assertIn("AUTONOVEL_WRITER_MODEL=gpt-5.4", rendered)

    def test_bootstrap_model_defaults_to_auto_when_not_explicitly_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / ".env").write_text("AUTONOVEL_TEXT_PROVIDER=openai\nAUTONOVEL_WRITER_MODEL=gpt-5.4\n", encoding="utf-8")
            with patch.dict("os.environ", {}, clear=True):
                provider, model = _resolve_bootstrap_provider_and_model(base)
            self.assertEqual(provider, "openai")
            self.assertEqual(model, "auto")

    def test_synchronize_runtime_environment_preserves_explicit_bootstrap_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / ".env").write_text("AUTONOVEL_TEXT_PROVIDER=openai\nAUTONOVEL_WRITER_MODEL=gpt-5.4\n", encoding="utf-8")
            with patch.dict(
                "os.environ",
                {
                    "AUTONOVEL_BOOTSTRAP_PROVIDER": "openai",
                    "AUTONOVEL_BOOTSTRAP_MODEL": "gpt-4.1-mini",
                },
                clear=True,
            ):
                synchronize_runtime_environment(base)
                provider, model = _resolve_bootstrap_provider_and_model(base)
            self.assertEqual(provider, "openai")
            self.assertEqual(model, "gpt-4.1-mini")

    def test_readiness_blocks_context_when_vault_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            readiness = evaluate_obsidian_operational_readiness(Path(tmp) / "MissingVault")

            self.assertFalse(readiness.vault_valid)
            self.assertEqual(readiness.operational_mode, "bootstrap_only")
            self.assertFalse(readiness.can_query_vaerl)
            self.assertIn("editorial_structuring_flow", readiness.blocked_flow_names)

    def test_prepare_new_project_installs_bridge_and_reports_degraded_context_until_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            vault_root = base / "Vault"
            plugin_root = _fake_plugin_repo(base / "plugin")

            result = prepare_obsidian_project(
                ObsidianProjectSetupConfig(
                    vault_root=str(vault_root),
                    mode="new_project",
                    project_title="My Project",
                    install_bridge_plugin=True,
                    build_bridge_plugin=False,
                    plugin_repo_root=str(plugin_root),
                ),
                repo_root=base,
            )

            self.assertTrue(result.vault_created)
            self.assertTrue(result.vault_ready)
            self.assertIsNotNone(result.plugin_status)
            assert result.plugin_status is not None
            self.assertTrue(result.plugin_status.install_succeeded)
            self.assertEqual(result.readiness.source_reliability, "vault_reader_only")
            self.assertFalse(result.readiness.can_answer_strong_grounded)

    def test_prepare_new_project_can_convert_existing_non_vault_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            vault_root = base / "ExistingFolder"
            vault_root.mkdir()
            (vault_root / "random_notes.txt").write_text("legacy notes", encoding="utf-8")
            plugin_root = _fake_plugin_repo(base / "plugin")

            result = prepare_obsidian_project(
                ObsidianProjectSetupConfig(
                    vault_root=str(vault_root),
                    mode="new_project",
                    project_title="Converted Project",
                    install_bridge_plugin=True,
                    build_bridge_plugin=False,
                    plugin_repo_root=str(plugin_root),
                ),
                repo_root=base,
            )

            self.assertTrue(result.vault_ready)
            self.assertTrue((vault_root / "00_Project" / "Project.md").exists())
            self.assertTrue((vault_root / "random_notes.txt").exists())
            self.assertTrue(any("converted into a TextifAI vault" in note for note in result.notes))

    def test_prepare_new_project_accepts_existing_empty_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            vault_root = base / "EmptyFolder"
            vault_root.mkdir()
            plugin_root = _fake_plugin_repo(base / "plugin")

            result = prepare_obsidian_project(
                ObsidianProjectSetupConfig(
                    vault_root=str(vault_root),
                    mode="new_project",
                    project_title="Empty Folder Project",
                    install_bridge_plugin=True,
                    build_bridge_plugin=False,
                    plugin_repo_root=str(plugin_root),
                ),
                repo_root=base,
            )

            self.assertTrue(result.vault_ready)
            self.assertTrue((vault_root / ".obsidian").exists())
            self.assertTrue((vault_root / "00_Project" / "Project.md").exists())

    def test_prepare_existing_material_reports_when_structured_bootstrap_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            vault_root = base / "Vault"
            source_root = base / "Sources"
            source_root.mkdir()
            (source_root / "chapter_01.md").write_text("# Capítulo 1\n\nRen llega tarde.\n", encoding="utf-8")
            plugin_root = _fake_plugin_repo(base / "plugin")

            result = prepare_obsidian_project(
                ObsidianProjectSetupConfig(
                    vault_root=str(vault_root),
                    mode="existing_material",
                    project_title="Imported Project",
                    source_root=str(source_root),
                    primary_language="es",
                    working_languages=["es", "ja"],
                    install_bridge_plugin=True,
                    build_bridge_plugin=False,
                    plugin_repo_root=str(plugin_root),
                    importer_preference="obsidian_importer_manual_if_markdown",
                ),
                repo_root=base,
            )

            self.assertEqual(result.import_strategy_used, "deterministic_chapter_manifest_project")
            self.assertFalse(result.bootstrap_written_drafts)
            self.assertTrue((vault_root / "textifai.project.json").exists())
            self.assertTrue((vault_root / "chapters" / "chapter_manifest.json").exists())
            self.assertTrue((vault_root / "99_System" / "markdown_manifest.json").exists())
            self.assertFalse(result.official_obsidian_importer_used)
            self.assertIsNotNone(result.official_obsidian_importer_reason)
            self.assertEqual(result.readiness.source_reliability, "vault_reader_only")

    def test_prepare_existing_material_can_adopt_existing_folder_as_vault_and_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = base / "AuthorFolder"
            folder.mkdir()
            (folder / "fichas.md").write_text("# Personaje Sera\n\nSera.\n", encoding="utf-8")
            (folder / "lore.txt").write_text("Lore de Spelarita y canon del mundo.", encoding="utf-8")
            plugin_root = _fake_plugin_repo(base / "plugin")

            result = prepare_obsidian_project(
                ObsidianProjectSetupConfig(
                    vault_root=str(folder),
                    mode="existing_material",
                    source_root=None,
                    project_title="Adopted Folder",
                    primary_language="es",
                    install_bridge_plugin=True,
                    build_bridge_plugin=False,
                    plugin_repo_root=str(plugin_root),
                ),
                repo_root=base,
            )

            self.assertTrue(result.vault_ready)
            self.assertFalse(result.bootstrap_written_drafts)
            self.assertEqual(result.import_strategy_used, "structured_bootstrap_v1_unavailable")
            self.assertGreaterEqual(len(result.source_files_considered), 2)
            self.assertTrue(any(path.endswith("fichas.md") for path in result.source_files_considered))
            self.assertTrue((folder / "00_Project" / "Project.md").exists())
            self.assertTrue((folder / "fichas.md").exists())
            self.assertGreater(result.vaerl_index_entries, 0)

    def test_prepare_existing_material_uses_semantic_bootstrap_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source_root = base / "source"
            source_root.mkdir()
            (source_root / "manuscript.md").write_text("# Episodio 1\n\nTexto de prueba.\n\n# Episodio 2\n\nMás texto.\n", encoding="utf-8")
            vault_root = base / "vault"
            import_json = vault_root / "semantic.json"
            import_json.parent.mkdir(parents=True, exist_ok=True)
            import_json.write_text(
                json.dumps(
                    {
                        "work": {"title": "Demo", "language": "es"},
                        "chapters": [
                            {"chapter_id": "ch_001", "chapter_title_original": "Episodio 1", "chapter_title_canonical": "Episodio 1", "sequence_index": 1},
                            {"chapter_id": "ch_002", "chapter_title_original": "Episodio 2", "chapter_title_canonical": "Episodio 2", "sequence_index": 2},
                            {"chapter_id": "ch_003", "chapter_title_original": "Episodio 3", "chapter_title_canonical": "Episodio 3", "sequence_index": 3},
                        ],
                        "entities": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            def fake_import_json_to_vault(*, source_json, vault_root):
                (vault_root / "vaerl").mkdir(parents=True, exist_ok=True)
                (vault_root / "graph").mkdir(parents=True, exist_ok=True)
                (vault_root / "99_System").mkdir(parents=True, exist_ok=True)
                (vault_root / "vaerl" / "vaerl.json").write_text(json.dumps({"work": {"title": "Demo"}, "chapters": []}, ensure_ascii=False), encoding="utf-8")
                (vault_root / "vaerl" / "review_queue.json").write_text(json.dumps({"schema_version": "textifai.review_queue.v1", "item_count": 0, "items": [], "decision_items": [], "policy": {"pending_reviews_are_expected": True, "can_auto_apply_default": False}}, ensure_ascii=False), encoding="utf-8")
                (vault_root / "graph" / "author_graph.json").write_text(json.dumps({"schema": "textifai.author_graph", "schema_version": 1, "source": "canonical_projection", "nodes": [], "edges": [], "excluded": {}, "stats": {"node_count": 0, "edge_count": 0, "review_decision_count": 0, "raw_node_count": 0, "raw_edge_count": 0}}, ensure_ascii=False), encoding="utf-8")
                (vault_root / "textifai.project.json").write_text(json.dumps({"schema": "textifai.project", "schema_version": 1, "project_id": "demo", "title": "Demo", "language": "es", "status": {"chapters_total": 3, "chapters_ready": 3, "review_items": 0, "graph_nodes": 0, "graph_edges": 0, "vaerl_ready": True, "graph_ready": True, "review_ready": True}, "paths": {"graph": "graph/author_graph.json", "review_queue": "vaerl/review_queue.json", "writer_outcome": "99_System/writer_outcome.json"}}, ensure_ascii=False), encoding="utf-8")
                return {"primary_paths": [], "chapter_paths": [str(vault_root / "markdown" / "Chapters" / f"Ch_{index:03d}.md") for index in range(1, 4)], "summary_paths": []}

            with patch.dict("os.environ", {"AUTONOVEL_BOOTSTRAP_PROVIDER": "openai", "OPENAI_API_KEY": "test-key"}, clear=False), patch(
                "textifai.obsidian.setup._run_structured_bootstrap_pipeline",
                return_value=_FakeStructuredBootstrapResult(str(import_json), source_document=str(source_root / "manuscript.md"), chapter_count=3),
            ) as semantic_mock, patch(
                "textifai.obsidian.setup.import_json_to_vault",
                side_effect=fake_import_json_to_vault,
            ):
                result = prepare_obsidian_project(
                    ObsidianProjectSetupConfig(
                        vault_root=str(vault_root),
                        mode="existing_material",
                        source_root=str(source_root),
                        project_title="Demo",
                        primary_language="es",
                        install_bridge_plugin=False,
                    ),
                    repo_root=base,
                )

            self.assertEqual(result.import_strategy_used, "structured_bootstrap_v1_json_import")
            self.assertTrue((vault_root / "textifai.project.json").exists())
            self.assertTrue((vault_root / "vaerl" / "review_queue.json").exists())
            self.assertTrue((vault_root / "graph" / "author_graph.json").exists())
            self.assertTrue(any("structured_bootstrap_imported" in item for item in (vault_root / "99_System" / "bootstrap_progress.jsonl").read_text(encoding="utf-8").splitlines()))
            self.assertTrue(semantic_mock.called)

    def test_prepare_existing_material_records_deterministic_fallback_when_semantic_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source_root = base / "source"
            source_root.mkdir()
            (source_root / "manuscript.md").write_text("# Episodio 1\n\nTexto de prueba.\n# Episodio 2\n\nMás texto.\n", encoding="utf-8")
            vault_root = base / "vault"
            with patch.dict("os.environ", {}, clear=True), patch(
                "textifai.obsidian.setup._run_structured_bootstrap_pipeline",
                return_value=None,
            ):
                result = prepare_obsidian_project(
                    ObsidianProjectSetupConfig(
                        vault_root=str(vault_root),
                        mode="existing_material",
                        source_root=str(source_root),
                        project_title="Demo",
                        primary_language="es",
                        install_bridge_plugin=False,
                    ),
                    repo_root=base,
                )

            self.assertEqual(result.import_strategy_used, "deterministic_chapter_manifest_project")
            progress = (vault_root / "99_System" / "bootstrap_progress.jsonl").read_text(encoding="utf-8")
            self.assertIn("semantic_provider_unavailable", progress)
            self.assertIn("deterministic_fallback_used", progress)

    def test_readiness_becomes_fresh_when_valid_snapshot_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Project")
            snapshot_dir = vault_root / ".textifai"
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": "2.0",
                "source": "obsidian_textifai_bridge",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "generated_unix_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
                "vault_name": "Project",
                "vault_id": "vault-1",
                "installation_id": "install-1",
                "vault_root_hint": str(vault_root),
                "plugin_version": "0.2.0",
                "obsidian_app_version": "1.6.0",
                "export_reason": "manual_test",
                "export_sequence": 1,
                "export_complete": True,
                "note_count": 1,
                "bridge_capabilities": {"metadata_cache": True},
                "warnings": [],
                "errors": [],
                "notes": [
                    {
                        "note_id": "sera",
                        "title": "Sera Snapshot",
                        "path": "03_Characters/Profiles/sera.md",
                        "vault_relative_path": "03_Characters/Profiles/sera.md",
                        "artifact_type": "character",
                        "aliases": ["Serélyne"],
                        "project_confirmed_aliases": [],
                        "outgoing_links": [],
                        "incoming_links": [],
                        "raw_text": "# Sera Snapshot",
                        "body_text": "# Sera Snapshot",
                    }
                ],
            }
            (snapshot_dir / "obsidian-bridge-snapshot.json").write_text(json.dumps(payload), encoding="utf-8")

            readiness = evaluate_obsidian_operational_readiness(vault_root)

            self.assertEqual(readiness.source_reliability, "obsidian_bridge_snapshot_fresh")
            self.assertTrue(readiness.can_answer_strong_grounded)
            self.assertTrue(readiness.can_evaluate_prompt_quality)

    def test_semantic_request_carries_operational_readiness_in_support_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            vault_root = base_dir / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (vault_root / "03_Characters" / "Profiles" / "sera.md").write_text(
                note_frontmatter("character", "Sera", slug="sera") + "\n\n# Sera\n\nTexto.\n",
                encoding="utf-8",
            )
            (base_dir / ".env").write_text(
                "\n".join(
                    [
                        "AUTONOVEL_PROJECT_BACKEND=vault",
                        f"AUTONOVEL_VAULT_ROOT={vault_root}",
                        "AUTONOVEL_TEXT_PROVIDER=ollama",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            session = create_session(load_runtime_environment(base_dir))
            manager = ConversationManager(session=session, executor=MinimalExecutionLayer(session=session))
            request = ConversationRequest(
                raw_text="Revísame la voz de Sera sin volverla demasiado explícita.",
                source="user",
                mode="normal",
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="es",
                mixed_language_allowed=True,
                explanation_language="es",
                metadata={"known_characters": [{"id": "sera", "names": ["Sera"]}]},
            )

            turn = manager.handle_request(request)

            self.assertIsNotNone(turn.response_support_summary)
            assert turn.response_support_summary is not None
            readiness = turn.response_support_summary["obsidian_operational_readiness"]
            self.assertEqual(readiness["source_reliability"], "vault_reader_only")
            self.assertTrue(readiness["can_query_vaerl"])

    def test_short_obsidian_init_wrapper_supports_existing_folder_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = base / "AuthorFolder"
            folder.mkdir()
            (folder / "lore.md").write_text("# Lore\n\nSpelarita.\n", encoding="utf-8")
            plugin_root = _fake_plugin_repo(base / "plugin")

            completed = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/textifai_obsidian.py",
                    "init",
                    "--vault-root",
                    str(folder),
                    "--use-vault-root-as-source",
                    "--project-title",
                    "Wrapper Project",
                    "--plugin-repo-root",
                    str(plugin_root),
                ],
                cwd=Path(__file__).resolve().parents[1],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)

            self.assertEqual(payload["mode"], "existing_material")
            self.assertTrue(payload["vault_ready"])
            self.assertFalse(payload["bootstrap_written_drafts"])
            self.assertEqual(payload["import_strategy_used"], "deterministic_chapter_manifest_project")
            self.assertTrue((folder / "textifai.project.json").exists())
            self.assertTrue((folder / "chapters" / "chapter_manifest.json").exists())
            self.assertEqual(payload["plugin_status"]["install_succeeded"], True)

    def test_short_obsidian_status_wrapper_reports_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Status Project")

            completed = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/textifai_obsidian.py",
                    "status",
                    "--vault-root",
                    str(vault_root),
                ],
                cwd=Path(__file__).resolve().parents[1],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)

            self.assertEqual(payload["operational_mode"], "degraded_context")
            self.assertEqual(payload["source_reliability"], "vault_reader_only")

    def test_short_obsidian_inspect_wrapper_reports_index_and_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            vault_root = base / "Vault"
            source_root = base / "Source"
            source_root.mkdir()
            (source_root / "character.md").write_text(
                "---\nkind: character\ntitle: Sera\nslug: sera\n---\n\n# Sera\n",
                encoding="utf-8",
            )
            plugin_root = _fake_plugin_repo(base / "plugin")

            prepare_obsidian_project(
                ObsidianProjectSetupConfig(
                    vault_root=str(vault_root),
                    mode="existing_material",
                    project_title="Inspect Project",
                    source_root=str(source_root),
                    primary_language="es",
                    working_languages=["es"],
                    install_bridge_plugin=True,
                    build_bridge_plugin=False,
                    plugin_repo_root=str(plugin_root),
                ),
                repo_root=base,
            )

            completed = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/textifai_obsidian.py",
                    "inspect",
                    "--vault-root",
                    str(vault_root),
                ],
                cwd=Path(__file__).resolve().parents[1],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)

            self.assertEqual(payload["readiness"]["operational_mode"], "degraded_context")
            self.assertGreaterEqual(payload["source_note_count"], 1)
            self.assertGreaterEqual(payload["vaerl_index_entries"], 1)
            self.assertIn("note", payload["vaerl_artifact_types"])
            self.assertIn("candidate_artifact_count", payload)
            self.assertIn("manifest_summary", payload)
            self.assertIn("provider_readiness", payload)
            self.assertFalse(payload["provider_readiness"]["available_for_author_response"])

    def test_textifai_entrypoint_defaults_to_interactive_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            vault_root = base / "Vault"
            source_root = base / "Source"
            source_root.mkdir()
            (source_root / "character.md").write_text(
                "---\nkind: character\ntitle: Sera\nslug: sera\n---\n\n# Sera\n",
                encoding="utf-8",
            )
            plugin_root = _fake_plugin_repo(base / "plugin")

            completed = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/textifai.py",
                    "--json",
                    "--plugin-repo-root",
                    str(plugin_root),
                ],
                cwd=Path(__file__).resolve().parents[1],
                input="\n".join(
                    [
                        "1",
                        "Onboarding Project",
                        str(vault_root),
                        "n",
                        str(source_root),
                        "en",
                        "en,ja",
                        "y",
                    ]
                )
                + "\n",
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout[completed.stdout.find("{"):])

            self.assertEqual(payload["mode"], "existing_material")
            self.assertTrue(payload["vault_ready"])
            self.assertGreaterEqual(payload["vaerl_index_entries"], 1)

    def test_textifai_ask_requires_provider_for_author_facing_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            vault_root = base / "Vault"
            plugin_root = _fake_plugin_repo(base / "plugin")
            source_root = base / "Source"
            source_root.mkdir()
            (source_root / "lore.md").write_text("# Nushi\n\nLos Nushi son entidades del mundo.\n", encoding="utf-8")

            prepare_obsidian_project(
                ObsidianProjectSetupConfig(
                    vault_root=str(vault_root),
                    mode="existing_material",
                    project_title="Ask Project",
                    source_root=str(source_root),
                    primary_language="es",
                    working_languages=["es"],
                    install_bridge_plugin=True,
                    build_bridge_plugin=False,
                    plugin_repo_root=str(plugin_root),
                ),
                repo_root=base,
            )
            (base / ".env").write_text(
                "\n".join(
                    [
                        "AUTONOVEL_PROJECT_BACKEND=vault",
                        f"AUTONOVEL_VAULT_ROOT={vault_root}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/textifai.py",
                    "ask",
                    "--vault-root",
                    str(vault_root),
                    "--text",
                    "Necesito una guía editorial sobre los Nushi.",
                    "--json",
                ],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)

            self.assertNotEqual(completed.returncode, 0)
            self.assertFalse(payload["author_facing_available"])
            self.assertEqual(payload["reason"], "provider_not_available")
            self.assertIn("pipeline_trace_preview", payload)
            self.assertIn("semantic_interpretation_prompt", payload["pipeline_trace_preview"])
            self.assertTrue((vault_root / "99_System" / "textifai_ask_trace.jsonl").exists())

    def test_textifai_ask_trace_output_persists_preview_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            vault_root = base / "Vault"
            plugin_root = _fake_plugin_repo(base / "plugin")
            source_root = base / "Source"
            trace_output = base / "artifacts" / "ask-trace.json"
            source_root.mkdir()
            (source_root / "lore.md").write_text("# Nushi\n\nLos Nushi son entidades del mundo.\n", encoding="utf-8")

            prepare_obsidian_project(
                ObsidianProjectSetupConfig(
                    vault_root=str(vault_root),
                    mode="existing_material",
                    project_title="Ask Trace Project",
                    source_root=str(source_root),
                    primary_language="es",
                    working_languages=["es"],
                    install_bridge_plugin=True,
                    build_bridge_plugin=False,
                    plugin_repo_root=str(plugin_root),
                ),
                repo_root=base,
            )
            (base / ".env").write_text(
                "\n".join(
                    [
                        "AUTONOVEL_PROJECT_BACKEND=vault",
                        f"AUTONOVEL_VAULT_ROOT={vault_root}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/textifai.py",
                    "ask",
                    "--vault-root",
                    str(vault_root),
                    "--text",
                    "Necesito una guía editorial sobre los Nushi.",
                    "--json",
                    "--trace-output",
                    str(trace_output),
                ],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)
            persisted = json.loads(trace_output.read_text(encoding="utf-8"))

            self.assertNotEqual(completed.returncode, 0)
            self.assertTrue(trace_output.exists())
            self.assertEqual(persisted["reason"], "provider_not_available")
            self.assertEqual(persisted["trace_metadata"]["trace_mode"], "preview")
            self.assertEqual(persisted["trace_metadata"]["trace_output_path"], str(trace_output))
            self.assertEqual(persisted["pipeline_trace_preview"], payload["pipeline_trace_preview"])


def _fake_plugin_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "manifest.json").write_text(
        json.dumps(
            {
                "id": "textifai-bridge",
                "name": "TextifAI Bridge",
                "version": "0.2.0",
                "minAppVersion": "1.5.0",
                "description": "Test bridge",
                "author": "OpenAI",
                "isDesktopOnly": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (path / "main.js").write_text("module.exports = {};\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()
