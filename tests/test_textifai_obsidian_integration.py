from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from textifai.author_response.context import build_response_context
from textifai.editorial_intent.contracts import EditorialIntent
from textifai.obsidian import ObsidianBridgeSnapshotReader, ObsidianVaultReader, build_obsidian_context_bundle, resolve_obsidian_snapshot_path
from textifai.vaerl.contracts import EntityMention, EntityResolutionResult
from textifai.vaerl.index import build_vault_index
from vault.bootstrap import bootstrap_vault


class TextifAIObsidianIntegrationTests(unittest.TestCase):
    def test_reader_loads_obsidian_notes_with_frontmatter_aliases_and_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Obsidian Test")
            lore = vault_root / "02_World" / "Lore" / "memory_ritual.md"
            decision = vault_root / "06_Canon" / "Decisions" / "magic_costs.md"
            lore.write_text(
                "---\n"
                "kind: lore\n"
                "title: Memory Ritual\n"
                "slug: memory_ritual\n"
                "aliases:\n"
                "  - ritual de memoria\n"
                "  - memoriaの儀式\n"
                "project_confirmed_aliases:\n"
                "  - ritual de memoria\n"
                "---\n\n"
                "# Memory Ritual\n\n"
                "Linked with [[magic_costs]].\n",
                encoding="utf-8",
            )
            decision.write_text(
                "---\nkind: decision\ntitle: Magic Costs\nslug: magic_costs\n---\n\n# Magic Costs\n\n[[memory_ritual]] has a cost.\n",
                encoding="utf-8",
            )

            notes = ObsidianVaultReader(vault_root).list_notes()
            by_id = {note.note_id: note for note in notes}

            self.assertIn("memory_ritual", by_id)
            self.assertIn("ritual de memoria", by_id["memory_ritual"].aliases)
            self.assertIn("magic_costs", by_id["memory_ritual"].outgoing_links)
            self.assertIn("magic_costs", by_id["memory_ritual"].incoming_links)

    def test_related_context_bundle_returns_primary_and_related_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Obsidian Test")
            primary = vault_root / "03_Characters" / "Profiles" / "sera.md"
            related = vault_root / "02_World" / "Lore" / "bond_law.md"
            primary.write_text(
                "---\nkind: character\ntitle: Sera\nslug: sera\n---\n\n# Sera\n\nKnows [[bond_law]].\n",
                encoding="utf-8",
            )
            related.write_text(
                "---\nkind: lore\ntitle: Bond Law\nslug: bond_law\n---\n\n# Bond Law\n\nApplies to [[sera]].\n",
                encoding="utf-8",
            )

            bundle = build_obsidian_context_bundle(vault_root, note_id="sera")

            self.assertIsNotNone(bundle.primary)
            self.assertEqual(bundle.primary.note_id, "sera")
            self.assertEqual(bundle.related[0].note_id, "bond_law")

    def test_vaerl_index_uses_obsidian_reader_as_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Obsidian Test")
            lore = vault_root / "02_World" / "Lore" / "memory_ritual.md"
            decision = vault_root / "06_Canon" / "Decisions" / "magic_costs.md"
            lore.write_text(
                "---\nkind: lore\ntitle: Memory Ritual\nslug: memory_ritual\naliases:\n  - ritual de memoria\n---\n\n# Memory Ritual\n\n[[magic_costs]]\n",
                encoding="utf-8",
            )
            decision.write_text(
                "---\nkind: decision\ntitle: Magic Costs\nslug: magic_costs\n---\n\n# Magic Costs\n\n[[memory_ritual]]\n",
                encoding="utf-8",
            )

            entries = build_vault_index(vault_path=vault_root)
            lore_entry = next(entry for entry in entries if entry.artifact_id == "memory_ritual")

            self.assertIn("ritual de memoria", lore_entry.aliases)
            self.assertIn("magic_costs", lore_entry.links)
            self.assertIn("magic_costs", lore_entry.backlinks)

    def test_author_response_context_can_pull_obsidian_related_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Obsidian Test")
            character = vault_root / "03_Characters" / "Profiles" / "sera.md"
            lore = vault_root / "02_World" / "Lore" / "spelarita.md"
            character.write_text(
                "---\nkind: character\ntitle: Sera\nslug: sera\n---\n\n# Sera\n\nLinked to [[spelarita]].\n",
                encoding="utf-8",
            )
            lore.write_text(
                "---\nkind: lore\ntitle: Spelarita\nslug: spelarita\n---\n\n# Spelarita\n\nRelevant lore.\n",
                encoding="utf-8",
            )

            intent = EditorialIntent(
                request_type="editorial_revision",
                confidence=0.9,
                semantic_basis="author_understanding_validated",
                resolved_target_type="character",
                resolved_target_id="sera",
            )
            snippets = build_response_context(
                vault_root=vault_root,
                editorial_intent=intent,
                entity_results=[
                    EntityResolutionResult(
                        query_text="Sera",
                        mention=EntityMention(surface_text="Sera", normalized_text="sera"),
                        resolved=True,
                        resolution_confidence=0.95,
                        resolved_entity_id="sera",
                        resolved_entity_type="character",
                    )
                ],
                include_candidates=True,
            )
            self.assertTrue(any(item["artifact_id"] == "sera" for item in snippets))
            self.assertTrue(any(item["artifact_id"] == "spelarita" for item in snippets))

    def test_bridge_snapshot_reader_loads_metadata_cache_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "obsidian-bridge-snapshot.json"
            snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "source": "obsidian_textifai_bridge",
                        "generated_at": "2026-04-19T12:00:00Z",
                        "vault_name": "OnT",
                        "plugin_version": "0.1.0",
                        "obsidian_app_version": "1.8.10",
                        "export_reason": "manual_command",
                        "notes": [
                            {
                                "note_id": "sera",
                                "title": "Sera",
                                "path": "03_Characters/Profiles/sera.md",
                                "vault_relative_path": "03_Characters/Profiles/sera.md",
                                "artifact_type": "character",
                                "frontmatter": {"aliases": ["Sera"]},
                                "aliases": ["Serélyne"],
                                "project_confirmed_aliases": ["Sera"],
                                "outgoing_links": ["spelarita"],
                                "incoming_links": ["bond_law"],
                                "raw_text": "# Sera\n\nLinked to [[spelarita]].",
                                "body_text": "# Sera\n\nLinked to [[spelarita]].",
                                "tags": ["#character"],
                                "headings": [{"heading": "Sera", "level": 1}],
                                "resolved_links": {"spelarita": 1},
                                "unresolved_links": {},
                                "source_kind": "obsidian_bridge_snapshot",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            reader = ObsidianBridgeSnapshotReader(snapshot_path)
            note = reader.get_note("sera")

            self.assertIsNotNone(note)
            assert note is not None
            self.assertEqual(note.source_kind, "obsidian_bridge_snapshot")
            self.assertIn("Sera", note.project_confirmed_aliases)
            self.assertEqual(note.resolved_links.get("spelarita"), 1)

    def test_context_bundle_prefers_bridge_snapshot_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Obsidian Test")
            (vault_root / "03_Characters" / "Profiles" / "sera.md").write_text(
                "---\nkind: character\ntitle: Sera Markdown\nslug: sera\n---\n\n# Sera Markdown\n",
                encoding="utf-8",
            )
            snapshot_dir = vault_root / ".textifai"
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            (snapshot_dir / "obsidian-bridge-snapshot.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "source": "obsidian_textifai_bridge",
                        "generated_at": "2026-04-19T12:00:00Z",
                        "vault_name": "Obsidian Test",
                        "plugin_version": "0.1.0",
                        "obsidian_app_version": "1.8.10",
                        "export_reason": "metadata_resolved",
                        "notes": [
                            {
                                "note_id": "sera",
                                "title": "Sera Snapshot",
                                "path": "03_Characters/Profiles/sera.md",
                                "vault_relative_path": "03_Characters/Profiles/sera.md",
                                "artifact_type": "character",
                                "aliases": ["Serélyne"],
                                "project_confirmed_aliases": ["Sera"],
                                "outgoing_links": [],
                                "incoming_links": [],
                                "raw_text": "# Sera Snapshot",
                                "body_text": "# Sera Snapshot",
                                "resolved_links": {},
                                "unresolved_links": {},
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            bundle = build_obsidian_context_bundle(vault_root, note_id="sera")

            self.assertIsNotNone(bundle.primary)
            assert bundle.primary is not None
            self.assertEqual(bundle.primary.title, "Sera Snapshot")
            self.assertEqual(bundle.primary.source_kind, "obsidian_bridge_snapshot")

    def test_vaerl_index_prefers_snapshot_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Obsidian Test")
            (vault_root / ".textifai").mkdir(parents=True, exist_ok=True)
            (vault_root / ".textifai" / "obsidian-bridge-snapshot.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "source": "obsidian_textifai_bridge",
                        "generated_at": "2026-04-19T12:00:00Z",
                        "vault_name": "Obsidian Test",
                        "plugin_version": "0.1.0",
                        "obsidian_app_version": "1.8.10",
                        "export_reason": "manual_command",
                        "notes": [
                            {
                                "note_id": "memory_ritual",
                                "title": "Memory Ritual Snapshot",
                                "path": "02_World/Lore/memory_ritual.md",
                                "vault_relative_path": "02_World/Lore/memory_ritual.md",
                                "artifact_type": "lore",
                                "aliases": ["ritual de memoria"],
                                "project_confirmed_aliases": ["memoriaの儀式"],
                                "outgoing_links": ["magic_costs"],
                                "incoming_links": ["magic_costs"],
                                "raw_text": "# Memory Ritual Snapshot",
                                "body_text": "# Memory Ritual Snapshot",
                                "resolved_links": {"magic_costs": 1},
                                "unresolved_links": {},
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            entries = build_vault_index(vault_path=vault_root)
            entry = next(item for item in entries if item.artifact_id == "memory_ritual")

            self.assertEqual(entry.title, "Memory Ritual Snapshot")
            self.assertIn("ritual de memoria", entry.aliases)

    def test_snapshot_path_resolution_checks_default_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            vault_root.mkdir()
            expected = vault_root / "99_System" / "obsidian_bridge_snapshot.json"
            expected.parent.mkdir(parents=True, exist_ok=True)
            expected.write_text("{}", encoding="utf-8")

            resolved = resolve_obsidian_snapshot_path(vault_root)

            self.assertEqual(resolved, expected.resolve())
