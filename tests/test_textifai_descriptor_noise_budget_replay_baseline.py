from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textifai.import_review.structured_bootstrap_v1 import run_semantic_ingestion_replay

FIXTURE_ROOT = Path("tests/fixtures/textifai/semantic_edges/descriptor_noise_budget")
REPLAY_INPUT_ROOT = FIXTURE_ROOT / "replay_input"
CHAPTER_OUTPUTS_ROOT = REPLAY_INPUT_ROOT / "chapter_outputs"
EXPECTED_CHAPTER_IDS = {"ch_001", "ch_002", "ch_003"}


class TextifAIDescriptorNoiseBudgetReplayBaselineTests(unittest.TestCase):
    def test_replay_input_fixture_structure_is_valid_and_safe(self):
        self.assertTrue(REPLAY_INPUT_ROOT.exists())
        self.assertTrue((REPLAY_INPUT_ROOT / "README.md").exists())
        self.assertTrue((REPLAY_INPUT_ROOT / "global_normalization.json").exists())
        self.assertTrue(CHAPTER_OUTPUTS_ROOT.exists())

        global_payload = _load_json(REPLAY_INPUT_ROOT / "global_normalization.json")
        self.assertEqual((global_payload.get("work") or {}).get("language"), "es")
        self.assertTrue(global_payload.get("entities"))

        for chapter_id in sorted(EXPECTED_CHAPTER_IDS):
            path = CHAPTER_OUTPUTS_ROOT / f"{chapter_id}.json"
            self.assertTrue(path.exists(), path)
            payload = _load_json(path)
            self.assertEqual((payload.get("chapters") or [{}])[0].get("chapter_id"), chapter_id)

        for path in REPLAY_INPUT_ROOT.rglob("*"):
            if not path.is_file():
                continue
            self.assertLess(path.stat().st_size, 150_000, path)
            normalized = str(path).replace("\\", "/")
            self.assertNotIn("/runs/", normalized)
            self.assertNotIn("/vault/", normalized)
            self.assertNotIn(path.name, {"web_ingestion_job.json", "web_ingestion_job.log", "obsidian_import.json", "review_queue.json"})
        self.assertFalse((REPLAY_INPUT_ROOT / "99_System").exists())

    def test_provider_free_replay_smoke_writes_only_inside_temp_output(self):
        before_hashes = _hash_replay_input()
        with tempfile.TemporaryDirectory(prefix="textifai_descriptor_noise_budget_replay_") as temp_root:
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
            self.assertTrue((system_root / "obsidian_import.json").exists())
            self.assertTrue((system_root / "review_queue.json").exists())
            self.assertTrue((system_root / "semantic_invariants_audit.json").exists())
            self.assertFalse((system_root / "web_ingestion_job.json").exists())
            self.assertFalse((system_root / "web_ingestion_job.log").exists())
            self._assert_output_boundary(output_root=output_root, result=result)

        self.assertEqual(before_hashes, _hash_replay_input())

    def _assert_output_boundary(self, *, output_root: Path, result) -> None:
        expected_prefix = output_root.resolve()
        produced_paths = [
            Path(result.output_root),
            Path(result.obsidian_import_path),
            Path(result.semantic_invariants_audit_path),
            Path(result.review_queue_path),
            Path(result.replay_audit_path),
        ]
        for path in produced_paths:
            resolved = path.resolve()
            self.assertTrue(resolved.is_relative_to(expected_prefix), path)
            normalized = str(resolved).replace("\\", "/")
            self.assertNotIn("/runs/", normalized)
            self.assertNotIn("/vault/", normalized)



def _load_json(path: Path) -> dict:
    assert path.exists(), str(path)
    return json.loads(path.read_text(encoding="utf-8"))



def _hash_replay_input() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(REPLAY_INPUT_ROOT.rglob("*")):
        if path.is_file():
            hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


if __name__ == "__main__":
    unittest.main()
