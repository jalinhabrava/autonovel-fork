from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textifai.import_review.structured_bootstrap_v1 import run_semantic_ingestion_replay


REPLAY_INPUT_ROOT = Path("tests/fixtures/textifai/minimal_novel/replay_input")
EXPECTED_STABLE_CHAPTER_REFS = {"ch_001", "ch_002", "ch_003"}
EXPECTED_CORE_ENTITIES = {"Mara Elian", "Toren", "Aster Hollow"}
KNOWN_RELATION_TYPES = {"alliance", "located_in", "related_to"}
KNOWN_REVIEW_SEVERITIES = {"high", "medium", "low"}
KNOWN_INVARIANT_STATUSES = {"pass", "warn", "fail", "skip"}
SLUG_RE = re.compile(r"^[a-z0-9_]+$")


class TextifAIReplayOutputContractAssertionsTests(unittest.TestCase):
    def test_provider_free_replay_outputs_obey_contracts(self):
        before_hashes = _hash_fixture_inputs()

        with tempfile.TemporaryDirectory(prefix="textifai_replay_contract_") as temp_root:
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

            self._assert_output_boundary(output_root=output_root, system_root=system_root, result=result)
            self._assert_obsidian_import_contract(obsidian_import)
            self._assert_relationship_contract(obsidian_import)
            self._assert_review_queue_contract(review_queue)
            self._assert_invariants_contract(invariants)

        self.assertEqual(before_hashes, _hash_fixture_inputs())

    def _assert_obsidian_import_contract(self, payload: dict) -> None:
        entities = payload.get("entities")
        self.assertIsInstance(entities, list)
        self.assertTrue(entities)

        canonical_names = {entity.get("canonical_name") for entity in entities}
        self.assertTrue(EXPECTED_CORE_ENTITIES.issubset(canonical_names))

        mara = _entity_by_name(entities, "Mara Elian")
        self.assertIsNotNone(mara)
        self.assertIn("Mara", mara.get("aliases") or [])

        guardia = _entity_by_name(entities, "guardia cansado")
        if guardia is not None:
            self.assertNotEqual(str(guardia.get("review_state") or "").casefold(), "canonical")
            self.assertNotEqual(str(guardia.get("note_role") or "").casefold(), "primary")

        for entity in entities:
            for field_name in [
                "canonical_name",
                "entity_kind",
                "preferred_slug",
                "aliases",
                "key_facts",
                "relationships",
                "chapter_refs",
                "source_mentions",
                "confidence",
                "review_state",
            ]:
                self.assertIn(field_name, entity, entity)

            self.assertIsInstance(entity["canonical_name"], str)
            self.assertTrue(entity["canonical_name"].strip())
            self.assertIsInstance(entity["entity_kind"], str)
            self.assertTrue(entity["entity_kind"].strip())
            self.assertIsInstance(entity["preferred_slug"], str)
            self.assertRegex(entity["preferred_slug"], SLUG_RE)
            self.assertIsInstance(entity["aliases"], list)
            self.assertIsInstance(entity["key_facts"], list)
            self.assertIsInstance(entity["relationships"], list)
            self.assertIsInstance(entity["chapter_refs"], list)
            self.assertIsInstance(entity["source_mentions"], list)
            self.assertIsInstance(entity["confidence"], (int, float))
            self.assertIsInstance(entity["review_state"], str)

            for chapter_ref in entity["chapter_refs"]:
                self.assertIn(chapter_ref, EXPECTED_STABLE_CHAPTER_REFS)

    def _assert_relationship_contract(self, payload: dict) -> None:
        entities = payload.get("entities") or []
        found_mara_toren = False

        for entity in entities:
            relationships = entity.get("relationships") or []
            self.assertIsInstance(relationships, list)
            for relationship in relationships:
                self.assertIsInstance(relationship, dict)
                self.assertIsInstance(relationship.get("target"), str)
                self.assertTrue(relationship["target"].strip())
                self.assertIsInstance(relationship.get("type"), str)
                self.assertIn(relationship["type"], KNOWN_RELATION_TYPES)
                self.assertIsInstance(relationship.get("facts"), list)
                for fact in relationship["facts"]:
                    self.assertIsInstance(fact, str)
                    self.assertTrue(fact.strip())
                if entity.get("canonical_name") == "Mara Elian" and relationship.get("target") == "Toren":
                    found_mara_toren = True
                if entity.get("canonical_name") == "Toren" and relationship.get("target") == "Mara Elian":
                    found_mara_toren = True

        self.assertTrue(found_mara_toren)

    def _assert_review_queue_contract(self, payload: dict) -> None:
        self.assertEqual(payload.get("schema_version"), "textifai.review_queue.v1")
        self.assertIn(payload.get("status"), {"ready_for_author_review", "empty"})
        self.assertIsInstance(payload.get("items"), list)
        self.assertIsInstance(payload.get("item_count"), int)

        if not payload["items"]:
            self.assertEqual(payload["item_count"], 0)
            return

        for item in payload["items"]:
            self.assertIsInstance(item.get("review_type"), str)
            self.assertTrue(item["review_type"].strip())
            self.assertIsInstance(item.get("severity"), str)
            self.assertIn(item["severity"], KNOWN_REVIEW_SEVERITIES)
            for field_name in ["source_entity", "target_text", "candidate_entities", "evidence", "metadata"]:
                self.assertIn(field_name, item, item)
            self.assertIsInstance(item["candidate_entities"], list)
            self.assertIsInstance(item["evidence"], list)
            self.assertIsInstance(item["metadata"], dict)

    def _assert_invariants_contract(self, payload: dict) -> None:
        self.assertEqual(payload.get("schema_version"), "textifai.semantic_invariants.v1")
        self.assertIn("status", payload)
        checks = payload.get("checks")
        self.assertIsInstance(checks, list)
        self.assertTrue(checks)

        pass_count = 0
        for check in checks:
            self.assertIsInstance(check, dict)
            self.assertIsInstance(check.get("name"), str)
            self.assertTrue(check["name"].strip())
            self.assertIsInstance(check.get("status"), str)
            self.assertIn(check["status"], KNOWN_INVARIANT_STATUSES)
            self.assertIsInstance(check.get("details"), dict)
            if check["status"] == "pass":
                pass_count += 1
        self.assertGreaterEqual(pass_count, 1)

    def _assert_output_boundary(self, *, output_root: Path, system_root: Path, result) -> None:
        self.assertTrue(system_root.exists())
        self.assertFalse((system_root / "web_ingestion_job.json").exists())
        self.assertFalse((system_root / "web_ingestion_job.log").exists())

        expected_prefix = output_root.resolve()
        produced_paths = [
            Path(result.output_root),
            Path(result.global_normalization_path),
            Path(result.chapter_outputs_dir),
            Path(result.resolved_entities_path),
            Path(result.cleaned_entities_path),
            Path(result.obsidian_import_path),
            Path(result.replay_audit_path),
            Path(result.run_comparability_manifest_path),
            Path(result.semantic_invariants_audit_path),
            Path(result.review_queue_path),
        ]
        for path in produced_paths:
            resolved = path.resolve()
            self.assertTrue(resolved.is_relative_to(expected_prefix), path)
            normalized = str(resolved).replace("\\", "/")
            self.assertNotIn("/runs/", normalized)
            self.assertNotIn("/vault/", normalized)


def _load_json(path: Path) -> dict:
    self_path = str(path)
    assert path.exists(), self_path
    return json.loads(path.read_text(encoding="utf-8"))


def _entity_by_name(entities: list[dict], canonical_name: str) -> dict | None:
    for entity in entities:
        if entity.get("canonical_name") == canonical_name:
            return entity
    return None


def _hash_fixture_inputs() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(REPLAY_INPUT_ROOT.rglob("*")):
        if path.is_file():
            hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


if __name__ == "__main__":
    unittest.main()
