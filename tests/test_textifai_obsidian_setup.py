import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from textifai.conversation.contracts import ConversationRequest
from textifai.conversation.executor import MinimalExecutionLayer
from textifai.conversation.manager import ConversationManager
from textifai.obsidian import evaluate_obsidian_operational_readiness
from textifai.obsidian.setup import ObsidianProjectSetupConfig, prepare_obsidian_project
from textifai.runtime_config import load_runtime_environment
from textifai.session import create_session
from vault.bootstrap import bootstrap_vault
from vault.schema import note_frontmatter


class TextifAIObsidianSetupTests(unittest.TestCase):
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
            self.assertTrue(any("convertida a vault" in note for note in result.notes))

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

    def test_prepare_existing_material_writes_staging_and_explains_official_importer_tradeoff(self):
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

            self.assertEqual(result.import_strategy_used, "textifai_bootstrap_staging")
            self.assertTrue(result.bootstrap_written_drafts)
            self.assertTrue(result.bootstrap_auto_promoted_paths)
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
            self.assertTrue(result.bootstrap_written_drafts)
            self.assertGreaterEqual(len(result.source_files_considered), 2)
            self.assertTrue(any(path.endswith("fichas.md") for path in result.source_files_considered))
            self.assertTrue((folder / "00_Project" / "Project.md").exists())
            self.assertTrue((folder / "fichas.md").exists())
            self.assertGreater(result.vaerl_index_entries, 0)

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
            self.assertTrue(payload["bootstrap_written_drafts"])
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
            self.assertIn("character", payload["vaerl_artifact_types"])
            self.assertIn("candidate_artifact_count", payload)
            self.assertIn("manifest_summary", payload)

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
                        "es",
                        "es,ja",
                        "s",
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

    def test_textifai_ask_entrypoint_runs_author_facing_interaction(self):
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
                        "AUTONOVEL_TEXT_PROVIDER=ollama",
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
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)

            self.assertIn("flow_name", payload)
            self.assertIn("response_support_summary", payload)
            self.assertTrue((vault_root / "99_System" / "textifai_ask_trace.jsonl").exists())


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
