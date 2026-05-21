from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


FIXTURE_ROOT = Path("tests/fixtures/textifai/minimal_novel")
EXPECTED_ROOT = FIXTURE_ROOT / "expected"
OBSIDIAN_IMPORT_PATH = EXPECTED_ROOT / "obsidian_import.json"
REVIEW_QUEUE_PATH = EXPECTED_ROOT / "review_queue.json"
INVARIANTS_PATH = EXPECTED_ROOT / "semantic_invariants_audit.json"

EXPECTED_CANONICALS = {
    "Mara Elian",
    "Toren",
    "Aster Hollow",
    "brújula de plata",
}
EXPECTED_CHAPTER_IDS = {"ch_001", "ch_002", "ch_003"}
KNOWN_RELATION_TYPES = {"alliance", "located_in", "related_to"}
KNOWN_REVIEW_SEVERITIES = {"high", "medium", "low"}
KNOWN_INVARIANT_STATUSES = {"pass", "warn", "fail", "skip"}


class TextifAIArtifactContractSnapshotTests(unittest.TestCase):
    def test_expected_directory_and_artifacts_exist_and_are_json(self):
        self.assertTrue(EXPECTED_ROOT.exists())
        self.assertTrue(EXPECTED_ROOT.is_dir())
        for artifact_path in [OBSIDIAN_IMPORT_PATH, REVIEW_QUEUE_PATH, INVARIANTS_PATH]:
            self.assertTrue(artifact_path.exists(), artifact_path)
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertIsInstance(payload, dict)

    def test_expected_artifacts_do_not_point_to_runs_or_vault_or_job_logs(self):
        forbidden_names = {
            "web_ingestion_job.log",
            "web_ingestion_job.json",
            "obsidian_import_audit.json",
        }
        for path in EXPECTED_ROOT.rglob("*"):
            if not path.is_file():
                continue
            self.assertNotIn(path.name, forbidden_names)
            if path.suffix.lower() != ".json":
                continue
            serialized = path.read_text(encoding="utf-8")
            self.assertNotIn("runs/", serialized)
            self.assertNotIn("vault/", serialized)
            self.assertNotIn("../runs", serialized)
            self.assertNotIn("../vault", serialized)

    def test_obsidian_import_contract_shape(self):
        payload = json.loads(OBSIDIAN_IMPORT_PATH.read_text(encoding="utf-8"))
        entities = payload.get("entities")
        self.assertIsInstance(entities, list)
        self.assertTrue(entities)

        canonical_names = set()
        guardia_review_state = None
        mara_aliases = []

        for entity in entities:
            self.assertIsInstance(entity.get("canonical_name"), str)
            self.assertTrue(entity["canonical_name"].strip())
            self.assertIsInstance(entity.get("entity_kind"), str)
            self.assertTrue(entity["entity_kind"].strip())

            slug = entity.get("preferred_slug")
            self.assertIsInstance(slug, str)
            self.assertRegex(slug, r"^[a-z0-9_]+$")

            self.assertIsInstance(entity.get("aliases"), list)
            self.assertIsInstance(entity.get("key_facts"), list)
            self.assertIsInstance(entity.get("relationships"), list)
            self.assertIsInstance(entity.get("chapter_refs"), list)
            self.assertIsInstance(entity.get("source_mentions"), list)
            self.assertIn("confidence", entity)
            self.assertIn("review_state", entity)
            self.assertIsInstance(entity.get("review_state"), str)

            for chapter_id in entity.get("chapter_refs") or []:
                self.assertIn(chapter_id, EXPECTED_CHAPTER_IDS)

            canonical_names.add(entity["canonical_name"])

            if entity["canonical_name"] == "Mara Elian":
                mara_aliases = list(entity.get("aliases") or [])
            if entity["canonical_name"] == "guardia cansado":
                guardia_review_state = entity.get("review_state")

        self.assertTrue(EXPECTED_CANONICALS.issubset(canonical_names))
        self.assertIn("Mara", mara_aliases)
        if guardia_review_state is not None:
            self.assertNotEqual(str(guardia_review_state).casefold(), "canonical")

    def test_relationship_contract_shape_and_mara_toren_link(self):
        payload = json.loads(OBSIDIAN_IMPORT_PATH.read_text(encoding="utf-8"))
        entities = payload.get("entities") or []

        found_mara_toren = False
        for entity in entities:
            relationships = entity.get("relationships") or []
            self.assertIsInstance(relationships, list)
            for rel in relationships:
                self.assertIsInstance(rel, dict)
                self.assertIsInstance(rel.get("target"), str)
                self.assertTrue(rel["target"].strip())
                self.assertIsInstance(rel.get("type"), str)
                self.assertIn(rel["type"], KNOWN_RELATION_TYPES)
                self.assertIsInstance(rel.get("facts"), list)
                for fact in rel.get("facts") or []:
                    self.assertIsInstance(fact, str)
                if entity.get("canonical_name") == "Mara Elian" and rel.get("target") == "Toren":
                    found_mara_toren = True
        self.assertTrue(found_mara_toren)

    def test_review_queue_contract_shape(self):
        payload = json.loads(REVIEW_QUEUE_PATH.read_text(encoding="utf-8"))
        items = payload.get("items")
        self.assertIsInstance(items, list)
        self.assertTrue(items)
        self.assertIn(payload.get("status"), {"ready_for_author_review", "empty"})

        for item in items:
            self.assertIsInstance(item.get("review_type"), str)
            self.assertTrue(item["review_type"].strip())
            self.assertIsInstance(item.get("severity"), str)
            self.assertIn(item["severity"], KNOWN_REVIEW_SEVERITIES)
            self.assertIn("source_entity", item)
            self.assertIn("target_text", item)
            self.assertIn("candidate_entities", item)
            self.assertIn("evidence", item)
            self.assertIsInstance(item.get("candidate_entities"), list)
            self.assertIsInstance(item.get("evidence"), list)
            self.assertIn("metadata", item)
            self.assertIsInstance(item.get("metadata"), dict)

    def test_semantic_invariants_contract_shape(self):
        payload = json.loads(INVARIANTS_PATH.read_text(encoding="utf-8"))
        checks = payload.get("checks")
        self.assertIsInstance(checks, list)
        self.assertTrue(checks)
        self.assertIn("status", payload)

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


if __name__ == "__main__":
    unittest.main()
