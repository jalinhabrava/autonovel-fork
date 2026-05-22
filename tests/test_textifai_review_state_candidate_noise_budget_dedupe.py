from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textifai.import_review.structured_bootstrap_v1 import run_semantic_ingestion_replay
from textifai.vaerl.review_queue import build_review_queue

FIXTURE_ROOT = Path("tests/fixtures/textifai/semantic_edges/descriptor_noise_budget")
REPLAY_INPUT_ROOT = FIXTURE_ROOT / "replay_input"


class TextifAIReviewStateCandidateNoiseBudgetDedupeTests(unittest.TestCase):
    def test_replay_degrades_equivalent_role_descriptor_signals(self):
        before_hashes = _hash_replay_input()
        with tempfile.TemporaryDirectory(prefix="textifai_review_state_dedupe_") as temp_root:
            output_root = Path(temp_root) / "out"
            with patch(
                "textifai.import_review.structured_bootstrap_v1.get_text_provider",
                side_effect=AssertionError("provider call not allowed"),
            ):
                result = run_semantic_ingestion_replay(
                    input_system_root=REPLAY_INPUT_ROOT,
                    output_root=output_root,
                    language="es",
                )

            system_root = output_root / "99_System"
            review_queue = _load_json(system_root / "review_queue.json")
            obsidian_import = _load_json(system_root / "obsidian_import.json")

            role_items = [
                item
                for item in review_queue.get("items") or []
                if (item.get("metadata") or {}).get("descriptor_category") == "role_descriptor"
                and item.get("suggested_action") == "review_attach_role_or_title"
                and _candidate_named(item, "Ari Mar")
            ]
            self.assertEqual(len(role_items), 3)
            self.assertEqual(len([item for item in role_items if item.get("severity") == "medium"]), 1)
            self.assertGreaterEqual(len([item for item in role_items if item.get("severity") == "low"]), 2)

            medium_item = next(item for item in role_items if item.get("severity") == "medium")
            self.assertEqual(medium_item.get("source_entity"), "el capitán del paso")

            for item in role_items:
                metadata = item.get("metadata") or {}
                self.assertTrue(metadata.get("do_not_auto_merge"))
                self.assertTrue(metadata.get("do_not_auto_promote"))
                self.assertFalse(metadata.get("candidate_is_primary"))
                self.assertTrue(metadata.get("candidate_requires_review"))
                if item.get("severity") == "low":
                    self.assertTrue(metadata.get("degraded_due_to_equivalent_signal"))
                    self.assertEqual(metadata.get("primary_equivalent_surface"), "el capitán del paso")

            self.assertIsNotNone(_review_item_by_surface(review_queue, "el cartógrafo sin memoria"))
            self.assertIsNotNone(_review_item_by_surface(review_queue, "el protector de Luma"))
            self.assertFalse(_is_primary_entity(obsidian_import, "Ari Mar"))
            self._assert_output_boundary(output_root=output_root, result=result, system_root=system_root)

        self.assertEqual(before_hashes, _hash_replay_input())

    def test_distinct_facts_survive_same_candidate_category_and_action(self):
        queue = _queue_for_review_state_candidate_surfaces(
            [
                _surface(
                    "silent heir",
                    category="epithet_descriptor",
                    key_facts=["Knows the hidden passage below the archive.", "Keeps the oath that protects the map."],
                    relationships=[{"target": "Atlas Vey", "type": "related_to"}],
                ),
                _surface(
                    "storm witness",
                    category="epithet_descriptor",
                    key_facts=["Saw the first breach during the red storm.", "Names the tower that caused the alarm."],
                    relationships=[{"target": "Atlas Vey", "type": "related_to"}],
                ),
            ]
        )
        first = _review_item_by_surface(queue, "silent heir")
        second = _review_item_by_surface(queue, "storm witness")
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(first.get("severity"), "medium")
        self.assertEqual(second.get("severity"), "medium")
        self.assertFalse((first.get("metadata") or {}).get("degraded_due_to_equivalent_signal"))
        self.assertFalse((second.get("metadata") or {}).get("degraded_due_to_equivalent_signal"))

    def test_distinct_relationships_survive_same_candidate_category_and_action(self):
        queue = _queue_for_review_state_candidate_surfaces(
            [
                _surface(
                    "protector of Nera",
                    category="relationship_descriptor",
                    key_facts=["Protects Nera Sol during the archive breach."],
                    relationships=[{"target": "Nera Sol", "type": "protects"}],
                ),
                _surface(
                    "rival of Toren",
                    category="relationship_descriptor",
                    key_facts=["Opposes Toren Vale at the west gate."],
                    relationships=[{"target": "Toren Vale", "type": "rival"}],
                ),
            ]
        )
        first = _review_item_by_surface(queue, "protector of Nera")
        second = _review_item_by_surface(queue, "rival of Toren")
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(first.get("severity"), "medium")
        self.assertEqual(second.get("severity"), "medium")
        self.assertFalse((first.get("metadata") or {}).get("degraded_due_to_equivalent_signal"))
        self.assertFalse((second.get("metadata") or {}).get("degraded_due_to_equivalent_signal"))

    def _assert_output_boundary(self, *, output_root: Path, result, system_root: Path) -> None:
        self.assertFalse((system_root / "web_ingestion_job.json").exists())
        self.assertFalse((system_root / "web_ingestion_job.log").exists())
        expected_prefix = output_root.resolve()
        for path in [
            Path(result.output_root),
            Path(result.obsidian_import_path),
            Path(result.semantic_invariants_audit_path),
            Path(result.review_queue_path),
            Path(result.replay_audit_path),
        ]:
            resolved = path.resolve()
            self.assertTrue(resolved.is_relative_to(expected_prefix), path)
            normalized = str(resolved).replace("\\", "/")
            self.assertNotIn("/runs/", normalized)
            self.assertNotIn("/vault/", normalized)


def _queue_for_review_state_candidate_surfaces(surfaces: list[dict]) -> dict:
    aliases = [surface["canonical_name"] for surface in surfaces]
    return build_review_queue(
        obsidian_import={
            "entities": [
                {
                    "canonical_name": "Atlas Vey",
                    "preferred_slug": "atlas_vey",
                    "entity_kind": "character",
                    "aliases": aliases,
                    "source_mentions": ["Atlas Vey", *aliases],
                    "key_facts": ["Stable review-state candidate.", "Carries enough evidence for human review."],
                    "chapter_refs": ["ch_001", "ch_002"],
                    "relationships": [],
                    "confidence": 0.8,
                    "review_state": "review",
                    "note_role": "review",
                    "naming_quality": "descriptor",
                    "surface_type": "named_entity_like",
                    "semantic_value": "durable_entity",
                }
            ]
        },
        retention_context={"global_entities": surfaces},
    )


def _surface(name: str, *, category: str, key_facts: list[str], relationships: list[dict]) -> dict:
    return {
        "canonical_name": name,
        "canonical_candidate": "Atlas Vey",
        "entity_kind": "character",
        "preferred_slug": name.casefold().replace(" ", "_"),
        "source_mentions": [name],
        "key_facts": key_facts,
        "chapter_refs": ["ch_002"],
        "relationships": relationships,
        "confidence": 0.79,
        "review_state": "review",
        "naming_quality": "descriptor",
        "surface_type": "descriptor_like",
        "semantic_value": "descriptor",
        "descriptor_category": category,
        "language_hint": "en",
    }


def _load_json(path: Path) -> dict:
    assert path.exists(), str(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_replay_input() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(REPLAY_INPUT_ROOT.rglob("*")):
        if path.is_file():
            hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _review_item_by_surface(review_queue: dict, surface: str) -> dict | None:
    for item in review_queue.get("items") or []:
        if item.get("source_entity") == surface or item.get("target_text") == surface:
            return item
    return None


def _candidate_named(item: dict, canonical_name: str) -> bool:
    return any(candidate.get("canonical_name") == canonical_name for candidate in item.get("candidate_entities") or [])


def _is_primary_entity(obsidian_import: dict, canonical_name: str) -> bool:
    for entity in obsidian_import.get("entities") or []:
        if entity.get("canonical_name") != canonical_name:
            continue
        if str(entity.get("review_state") or "").casefold() == "canonical" or str(entity.get("note_role") or "").casefold() == "primary":
            return True
    return False


if __name__ == "__main__":
    unittest.main()
