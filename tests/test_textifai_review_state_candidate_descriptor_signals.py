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


class TextifAIReviewStateCandidateDescriptorSignalsTests(unittest.TestCase):
    def test_replay_emits_descriptor_signals_for_review_state_candidate(self):
        before_hashes = _hash_replay_input()
        with tempfile.TemporaryDirectory(prefix="textifai_review_state_candidate_") as temp_root:
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
            obsidian_import = _load_json(system_root / "obsidian_import.json")
            review_queue = _load_json(system_root / "review_queue.json")
            invariants = _load_json(system_root / "semantic_invariants_audit.json")

            self.assertEqual(review_queue.get("schema_version"), "textifai.review_queue.v1")
            self.assertEqual(invariants.get("primary_count"), 0)
            self.assertEqual((obsidian_import.get("work") or {}).get("language"), "es")
            self.assertFalse(_is_primary_entity(obsidian_import, "Ari Mar"))

            enrich = _review_item_by_surface(review_queue, "el cartógrafo sin memoria")
            self.assertIsNotNone(enrich)
            self.assertEqual(enrich.get("suggested_action"), "review_enrich_existing_entity")
            self._assert_review_state_candidate_metadata(enrich, expected_category="epithet_descriptor")

            attach = _review_item_by_surface(review_queue, "el capitán del paso")
            self.assertIsNotNone(attach)
            self.assertEqual(attach.get("suggested_action"), "review_attach_role_or_title")
            self._assert_review_state_candidate_metadata(attach, expected_category="role_descriptor")
            self.assertIn("attach_role_or_title", (attach.get("metadata") or {}).get("future_viewer_actions") or [])

            relation = _review_item_by_surface(review_queue, "el protector de Luma")
            self.assertIsNotNone(relation)
            self.assertEqual(relation.get("suggested_action"), "review_enrich_existing_entity")
            self._assert_review_state_candidate_metadata(relation, expected_category="relationship_descriptor")

            for suppressed in ["el viajero", "el caminante", "él", "mercader distraído"]:
                item = _review_item_by_surface(review_queue, suppressed)
                if item is None:
                    continue
                self.assertNotEqual(item.get("suggested_action"), "review_enrich_existing_entity")
                self.assertNotEqual(item.get("suggested_action"), "review_attach_role_or_title")

            self.assertFalse((system_root / "web_ingestion_job.json").exists())
            self.assertFalse((system_root / "web_ingestion_job.log").exists())
            for path in [
                Path(result.output_root),
                Path(result.obsidian_import_path),
                Path(result.semantic_invariants_audit_path),
                Path(result.review_queue_path),
                Path(result.replay_audit_path),
            ]:
                resolved = path.resolve()
                self.assertTrue(resolved.is_relative_to(output_root.resolve()), path)
                normalized = str(resolved).replace("\\", "/")
                self.assertNotIn("/runs/", normalized)
                self.assertNotIn("/vault/", normalized)

        self.assertEqual(before_hashes, _hash_replay_input())

    def test_language_agnostic_policy_for_review_state_candidate(self):
        english = _queue_for_review_state_candidate_surface(
            surface="silent heir",
            source_mentions=["silent heir", "silent heir"],
            key_facts=["Keeps the map oath.", "Knows hidden passage under archive."],
            category="epithet_descriptor",
            language_hint="en",
        )
        spanish = _queue_for_review_state_candidate_surface(
            surface="heredera silenciosa",
            source_mentions=["heredera silenciosa", "heredera silenciosa"],
            key_facts=["Guarda el juramento del mapa.", "Conoce el paso oculto bajo el archivo."],
            category="epithet_descriptor",
            language_hint="es",
        )

        en_item = _review_item_by_surface(english, "silent heir")
        es_item = _review_item_by_surface(spanish, "heredera silenciosa")
        self.assertIsNotNone(en_item)
        self.assertIsNotNone(es_item)
        self.assertEqual(en_item.get("suggested_action"), es_item.get("suggested_action"))
        self.assertEqual((en_item.get("metadata") or {}).get("signal_tier"), (es_item.get("metadata") or {}).get("signal_tier"))
        self.assertEqual((en_item.get("metadata") or {}).get("candidate_review_state"), "review")
        self.assertEqual((es_item.get("metadata") or {}).get("candidate_review_state"), "review")

    def _assert_review_state_candidate_metadata(self, item: dict, *, expected_category: str) -> None:
        metadata = item.get("metadata") or {}
        self.assertTrue(any(candidate.get("canonical_name") == "Ari Mar" for candidate in item.get("candidate_entities") or []))
        self.assertEqual(metadata.get("descriptor_category"), expected_category)
        self.assertEqual(metadata.get("candidate_review_state"), "review")
        self.assertEqual(metadata.get("candidate_note_role"), "review")
        self.assertFalse(metadata.get("candidate_is_primary"))
        self.assertTrue(metadata.get("candidate_requires_review"))
        self.assertTrue(metadata.get("do_not_auto_merge"))
        self.assertTrue(metadata.get("do_not_auto_promote"))


def _queue_for_review_state_candidate_surface(
    *,
    surface: str,
    source_mentions: list[str],
    key_facts: list[str],
    category: str,
    language_hint: str,
) -> dict:
    return build_review_queue(
        obsidian_import={
            "entities": [
                {
                    "canonical_name": "Atlas Vey",
                    "preferred_slug": "atlas_vey",
                    "entity_kind": "character",
                    "aliases": [surface],
                    "source_mentions": ["Atlas Vey", surface],
                    "key_facts": [
                        "Cluster kept in review for manual confirmation.",
                        "Carries stable narrative footprint across chapters.",
                    ],
                    "chapter_refs": ["ch_001", "ch_002"],
                    "confidence": 0.78,
                    "review_state": "review",
                    "note_role": "review",
                    "naming_quality": "descriptor",
                    "surface_type": "named_entity_like",
                    "semantic_value": "durable_entity",
                    "review_reason_code": "weak_or_descriptive_naming",
                }
            ]
        },
        retention_context={
            "global_entities": [
                {
                    "canonical_name": surface,
                    "canonical_candidate": "Atlas Vey",
                    "entity_kind": "character",
                    "preferred_slug": surface.casefold().replace(" ", "_"),
                    "source_mentions": source_mentions,
                    "key_facts": key_facts,
                    "chapter_refs": ["ch_002"],
                    "relationships": [{"target": "Atlas Vey", "type": "related_to"}],
                    "confidence": 0.79,
                    "review_state": "review",
                    "naming_quality": "descriptor",
                    "surface_type": "descriptor_like",
                    "semantic_value": "descriptor",
                    "descriptor_category": category,
                    "language_hint": language_hint,
                }
            ]
        },
    )


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


def _is_primary_entity(obsidian_import: dict, canonical_name: str) -> bool:
    for entity in obsidian_import.get("entities") or []:
        if entity.get("canonical_name") != canonical_name:
            continue
        if str(entity.get("review_state") or "").casefold() == "canonical" or str(entity.get("note_role") or "").casefold() == "primary":
            return True
    return False


if __name__ == "__main__":
    unittest.main()
