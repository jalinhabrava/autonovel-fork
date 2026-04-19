from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from textifai.author_response.context import build_response_context
from textifai.editorial_intent.contracts import EditorialIntent
from textifai.obsidian import (
    CURRENT_OBSIDIAN_SNAPSHOT_SCHEMA_VERSION,
    ObsidianBridgeSnapshotReader,
    ObsidianVaultReader,
    build_obsidian_context_bundle,
    open_obsidian_source,
    resolve_obsidian_snapshot_path,
    validate_obsidian_snapshot,
)
from textifai.vaerl.contracts import EntityMention, EntityResolutionResult
from textifai.vaerl.index import build_vault_index
from vault.bootstrap import bootstrap_vault


class TextifAIObsidianIntegrationTests(unittest.TestCase):
    def test_markdown_reader_loads_aliases_links_and_backlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = _bootstrap_sample_vault(Path(tmp))
            notes = ObsidianVaultReader(vault_root).list_notes()
            by_id = {note.note_id: note for note in notes}

            self.assertIn("memory_ritual", by_id)
            self.assertIn("ritual de memoria", by_id["memory_ritual"].aliases)
            self.assertIn("magic_costs", by_id["memory_ritual"].outgoing_links)
            self.assertIn("magic_costs", by_id["memory_ritual"].incoming_links)
            self.assertEqual(by_id["memory_ritual"].source_kind, "vault_markdown")

    def test_context_bundle_reports_vault_reader_only_without_bridge(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = _bootstrap_sample_vault(Path(tmp))

            bundle = build_obsidian_context_bundle(vault_root, note_id="sera")

            self.assertIsNotNone(bundle.primary)
            assert bundle.source_status is not None
            self.assertEqual(bundle.source_status.reliability, "vault_reader_only")
            self.assertEqual(bundle.source_status.fallback_reason, "bridge_snapshot_absent")

    def test_valid_snapshot_is_fresh_and_usable(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = _write_snapshot(Path(tmp), generated_at=_now_iso())

            validated = validate_obsidian_snapshot(snapshot_path)

            self.assertIsNotNone(validated.snapshot)
            self.assertEqual(validated.status.reliability, "obsidian_bridge_snapshot_fresh")
            self.assertFalse(validated.status.requires_caution)

    def test_stale_snapshot_is_usable_but_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = _write_snapshot(
                Path(tmp),
                generated_at=(datetime.now(timezone.utc) - timedelta(hours=4)).isoformat(),
            )

            validated = validate_obsidian_snapshot(snapshot_path, stale_after_seconds=60)

            self.assertIsNotNone(validated.snapshot)
            self.assertEqual(validated.status.reliability, "obsidian_bridge_snapshot_stale")
            self.assertTrue(validated.status.requires_caution)

    def test_schema_v1_snapshot_is_backward_compatible_but_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = _write_snapshot(Path(tmp), generated_at=_now_iso(), schema_version="1.0", legacy_mode=True)

            validated = validate_obsidian_snapshot(snapshot_path)

            self.assertIsNotNone(validated.snapshot)
            self.assertEqual(validated.status.reliability, "obsidian_bridge_snapshot_stale")
            self.assertIn("schema_backward_compatibility_mode", validated.status.issues)

    def test_corrupt_snapshot_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "obsidian-bridge-snapshot.json"
            snapshot_path.write_text("{not valid json", encoding="utf-8")

            validated = validate_obsidian_snapshot(snapshot_path)

            self.assertIsNone(validated.snapshot)
            self.assertEqual(validated.status.reliability, "obsidian_bridge_snapshot_invalid")
            self.assertIn("snapshot_json_decode_error", ",".join(validated.status.issues))

    def test_incomplete_snapshot_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = _write_snapshot(Path(tmp), generated_at=_now_iso(), export_complete=False)

            validated = validate_obsidian_snapshot(snapshot_path)

            self.assertIsNone(validated.snapshot)
            self.assertEqual(validated.status.reliability, "obsidian_bridge_snapshot_invalid")
            self.assertIn("export_incomplete", validated.status.issues)

    def test_open_source_prefers_fresh_bridge_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = _bootstrap_sample_vault(Path(tmp))
            _write_snapshot(vault_root / ".textifai", generated_at=_now_iso())

            source = open_obsidian_source(vault_root)
            note = source.reader.get_note("sera")

            self.assertEqual(source.status.reliability, "obsidian_bridge_snapshot_fresh")
            self.assertTrue(source.status.bridge_preferred)
            self.assertFalse(source.status.fallback_used)
            self.assertIsNotNone(note)
            assert note is not None
            self.assertEqual(note.title, "Sera Snapshot")

    def test_open_source_falls_back_to_markdown_reader_when_snapshot_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = _bootstrap_sample_vault(Path(tmp))
            snapshot_dir = vault_root / ".textifai"
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            (snapshot_dir / "obsidian-bridge-snapshot.json").write_text("{broken", encoding="utf-8")

            source = open_obsidian_source(vault_root)
            note = source.reader.get_note("sera")

            self.assertEqual(source.status.reliability, "vault_reader_only")
            self.assertTrue(source.status.fallback_used)
            self.assertEqual(source.status.fallback_reason, "invalid_snapshot_fallback_to_vault_reader")
            self.assertIsNotNone(note)
            assert note is not None
            self.assertEqual(note.title, "Sera")

    def test_vaerl_index_prefers_snapshot_and_records_reliability(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = _bootstrap_sample_vault(Path(tmp))
            _write_snapshot(vault_root / ".textifai", generated_at=_now_iso())

            entries = build_vault_index(vault_path=vault_root)
            sera = next(entry for entry in entries if entry.artifact_id == "sera")

            self.assertEqual(sera.title, "Sera Snapshot")
            self.assertEqual(sera.frontmatter.get("_context_source_reliability"), "obsidian_bridge_snapshot_fresh")

    def test_author_response_context_exposes_source_reliability(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = _bootstrap_sample_vault(Path(tmp))
            _write_snapshot(vault_root / ".textifai", generated_at=_now_iso())

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

            self.assertTrue(any(item["context_source_reliability"] == "obsidian_bridge_snapshot_fresh" for item in snippets))

    def test_snapshot_path_resolution_checks_default_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            vault_root.mkdir()
            expected = vault_root / "99_System" / "obsidian_bridge_snapshot.json"
            expected.parent.mkdir(parents=True, exist_ok=True)
            expected.write_text("{}", encoding="utf-8")

            resolved = resolve_obsidian_snapshot_path(vault_root)

            self.assertEqual(resolved, expected.resolve())


def _bootstrap_sample_vault(base: Path) -> Path:
    vault_root = base / "Vault"
    bootstrap_vault(vault_root, title="Obsidian Test")
    (vault_root / "02_World" / "Lore" / "memory_ritual.md").write_text(
        "---\n"
        "kind: lore\n"
        "title: Memory Ritual\n"
        "slug: memory_ritual\n"
        "aliases:\n"
        "  - ritual de memoria\n"
        "project_confirmed_aliases:\n"
        "  - memoriaの儀式\n"
        "---\n\n"
        "# Memory Ritual\n\n"
        "Linked with [[magic_costs]].\n",
        encoding="utf-8",
    )
    (vault_root / "06_Canon" / "Decisions" / "magic_costs.md").write_text(
        "---\nkind: decision\ntitle: Magic Costs\nslug: magic_costs\n---\n\n# Magic Costs\n\n[[memory_ritual]] has a cost.\n",
        encoding="utf-8",
    )
    (vault_root / "03_Characters" / "Profiles" / "sera.md").write_text(
        "---\nkind: character\ntitle: Sera\nslug: sera\naliases:\n  - Serélyne\n---\n\n# Sera\n\nKnows [[spelarita]].\n",
        encoding="utf-8",
    )
    (vault_root / "02_World" / "Lore" / "spelarita.md").write_text(
        "---\nkind: lore\ntitle: Spelarita\nslug: spelarita\n---\n\n# Spelarita\n\nRelevant lore.\n",
        encoding="utf-8",
    )
    return vault_root


def _write_snapshot(
    root: Path,
    *,
    generated_at: str,
    export_complete: bool = True,
    schema_version: str = CURRENT_OBSIDIAN_SNAPSHOT_SCHEMA_VERSION,
    legacy_mode: bool = False,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "obsidian-bridge-snapshot.json"
    payload = {
        "schema_version": schema_version,
        "source": "obsidian_textifai_bridge",
        "generated_at": generated_at,
        "vault_name": "OnT",
        "plugin_version": "0.2.0",
        "obsidian_app_version": "1.8.10",
        "export_reason": "manual_command",
        "bridge_capabilities": {
            "metadata_cache": True,
            "resolved_links": True,
            "unresolved_links": True,
            "headings": True,
            "sections": True,
            "tags": True,
            "wikilinks": True,
            "embeds": True,
            "frontmatter_links": True,
            "atomic_snapshot_write": True,
        },
        "errors": [] if export_complete else ["simulated_export_failure"],
        "warnings": [],
        "notes": [
            {
                "note_id": "sera",
                "title": "Sera Snapshot",
                "path": "03_Characters/Profiles/sera.md",
                "vault_relative_path": "03_Characters/Profiles/sera.md",
                "canonical_path": "03_characters/profiles/sera.md",
                "artifact_type": "character",
                "frontmatter": {"aliases": ["Serélyne"]},
                "aliases": ["Serélyne"],
                "project_confirmed_aliases": ["Sera"],
                "outgoing_links": ["spelarita"],
                "incoming_links": [],
                "raw_text": "# Sera Snapshot",
                "body_text": "# Sera Snapshot",
                "tags": ["#character"],
                "headings": [{"heading": "Sera Snapshot", "level": 1}],
                "sections": [{"type": "heading", "start_line": 0, "end_line": 2}],
                "wikilinks": [{"link_text": "spelarita", "normalized_link_text": "spelarita", "is_embed": False, "resolved_path": "02_World/Lore/spelarita.md", "resolved_note_id": "spelarita"}],
                "embeds": [],
                "frontmatter_links": [],
                "resolved_links": {"spelarita": 1},
                "unresolved_links": {},
                "source_kind": "obsidian_bridge_snapshot",
            },
            {
                "note_id": "memory_ritual",
                "title": "Memory Ritual Snapshot",
                "path": "02_World/Lore/memory_ritual.md",
                "vault_relative_path": "02_World/Lore/memory_ritual.md",
                "canonical_path": "02_world/lore/memory_ritual.md",
                "artifact_type": "lore",
                "frontmatter": {"aliases": ["ritual de memoria"]},
                "aliases": ["ritual de memoria"],
                "project_confirmed_aliases": ["memoriaの儀式"],
                "outgoing_links": ["magic_costs"],
                "incoming_links": ["magic_costs"],
                "raw_text": "# Memory Ritual Snapshot",
                "body_text": "# Memory Ritual Snapshot",
                "tags": ["#lore"],
                "headings": [{"heading": "Memory Ritual Snapshot", "level": 1}],
                "sections": [{"type": "heading", "start_line": 0, "end_line": 2}],
                "wikilinks": [{"link_text": "magic_costs", "normalized_link_text": "magic_costs", "is_embed": False, "resolved_path": "06_Canon/Decisions/magic_costs.md", "resolved_note_id": "magic_costs"}],
                "embeds": [],
                "frontmatter_links": [],
                "resolved_links": {"magic_costs": 1},
                "unresolved_links": {},
                "source_kind": "obsidian_bridge_snapshot",
            },
        ],
    }
    if not legacy_mode:
        payload.update(
            {
                "generated_unix_ms": 1776600000000,
                "vault_id": "vault_ont_123",
                "installation_id": "installation_abc",
                "vault_root_hint": "/tmp/OnT",
                "export_sequence": 4,
                "export_complete": export_complete,
                "note_count": 2,
            }
        )
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
