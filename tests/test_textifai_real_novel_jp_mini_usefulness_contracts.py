from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textifai.import_review.structured_bootstrap_v1 import run_semantic_ingestion_replay

FIXTURE_ROOT = Path("tests/fixtures/textifai/real_novel/real_novel_jp_linked_power")
REPLAY_INPUT_ROOT = FIXTURE_ROOT / "replay_input"
CHECKLIST_PATH = FIXTURE_ROOT / "expected" / "usefulness_checklist.json"
DRIFT_PATH = FIXTURE_ROOT / "expected" / "replay_drift_expectations.json"

class TextifAIRealNovelJPMiniUsefulnessContractsTests(unittest.TestCase):
    def test_real_novel_mini_fixture_surfaces_useful_real_scene_information(self):
        checklist = _load_json(CHECKLIST_PATH)
        drift = _load_json(DRIFT_PATH)
        before = _hash_replay_input()
        with tempfile.TemporaryDirectory(prefix="textifai_real_novel_jp_usefulness_") as temp_root:
            output_root = Path(temp_root) / "out"
            with patch("textifai.import_review.structured_bootstrap_v1.get_text_provider", side_effect=AssertionError("provider call not allowed")):
                result = run_semantic_ingestion_replay(
                    input_system_root=REPLAY_INPUT_ROOT,
                    output_root=output_root,
                    language="ja",
                    prose_language_validator=None,
                    prose_language_validation_mode="warn",
                )
            system_root = output_root / "99_System"
            obsidian_import = _load_json(system_root / "obsidian_import.json")
            review_queue = _load_json(system_root / "review_queue.json")
            invariants = _load_json(system_root / "semantic_invariants_audit.json")

            self._assert_entities(obsidian_import)
            self._assert_useful_facts_and_relations(obsidian_import, review_queue)
            self._assert_noise_suppression(obsidian_import)
            self._assert_review_queue_useful(review_queue, obsidian_import)
            self._assert_safety(review_queue, obsidian_import, invariants, result)
            self._assert_fixture_docs(checklist, drift)
        self.assertEqual(before, _hash_replay_input())

    def _assert_entities(self, obsidian_import: dict) -> None:
        names = _all_entity_names(obsidian_import)
        self.assertIn("レン", names)
        self.assertIn("セラ", names)
        self.assertTrue(any(name in names for name in ["ベルド", "オヤジ"]))
        self.assertIn("ベル", names)
        self.assertIn("エルサリエル", names)

    def _assert_useful_facts_and_relations(self, obsidian_import: dict, review_queue: dict) -> None:
        blob = json.dumps(obsidian_import, ensure_ascii=False)
        review_blob = json.dumps(review_queue, ensure_ascii=False)
        self.assertTrue(any(token in blob for token in ["繋がった力", "linked_magic", "運ぶ道", "支える"]))
        self.assertTrue(any(token in blob for token in ["ベルド", "オヤジ"]))
        self.assertTrue(any(token in blob for token in ["王者と杖", "possible_role", "lore_concept"]))
        self.assertTrue(any(token in blob for token in ["ベルが一度鳴る", "ベル", "path_key"]))
        self.assertTrue(any(token in blob + review_blob for token in ["死", "悼む", "使命", "guardian", "supports"]))

    def _assert_noise_suppression(self, obsidian_import: dict) -> None:
        top_level_entities = obsidian_import.get("entities") or []
        promoted = {str(entity.get("canonical_name") or "") for entity in top_level_entities if str(entity.get("review_state") or "").casefold() == "canonical"}
        for pronoun in ["彼", "彼女", "俺", "私"]:
            self.assertNotIn(pronoun, promoted)

    def _assert_review_queue_useful(self, review_queue: dict, obsidian_import: dict) -> None:
        item_count = int(review_queue.get("item_count") or len(review_queue.get("items") or []))
        blob = json.dumps(obsidian_import, ensure_ascii=False)
        self.assertTrue(item_count >= 1 or any(token in blob for token in ["linked_magic", "王者と杖", "オヤジ", "ベル"]))

    def _assert_safety(self, review_queue: dict, obsidian_import: dict, invariants: dict, result) -> None:
        self.assertEqual(review_queue.get("schema_version"), "textifai.review_queue.v1")
        for item in review_queue.get("items") or []:
            self.assertFalse(bool(item.get("can_auto_apply")))
            metadata = item.get("metadata") or {}
            if "do_not_auto_merge" in metadata:
                self.assertTrue(bool(metadata.get("do_not_auto_merge")))
            if "do_not_auto_promote" in metadata:
                self.assertTrue(bool(metadata.get("do_not_auto_promote")))
        self.assertIn("status", invariants)
        for path in [
            Path(result.output_root),
            Path(result.obsidian_import_path),
            Path(result.review_queue_path),
        ]:
            normalized = str(path.resolve()).replace("\\", "/")
            self.assertNotIn("/runs/", normalized)
            self.assertNotIn("/vault/", normalized)

    def _assert_fixture_docs(self, checklist: dict, drift: dict) -> None:
        self.assertTrue(checklist.get("must_have"))
        self.assertTrue(drift.get("real_novel_usefulness_notes"))
        self.assertIn("provider call occurs", drift.get("non_negotiable_failures") or [])


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def _hash_replay_input() -> dict[str, str]:
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(REPLAY_INPUT_ROOT.rglob("*")) if path.is_file()}

def _all_entities(obsidian_import: dict) -> list[dict]:
    entities = [item for item in (obsidian_import.get("entities") or []) if isinstance(item, dict)]
    for chapter in obsidian_import.get("chapters") or []:
        if isinstance(chapter, dict):
            entities.extend([item for item in (chapter.get("entities") or []) if isinstance(item, dict)])
    return entities

def _all_entity_names(obsidian_import: dict) -> set[str]:
    return {str(entity.get("canonical_name") or "") for entity in _all_entities(obsidian_import)}

if __name__ == "__main__":
    unittest.main()
