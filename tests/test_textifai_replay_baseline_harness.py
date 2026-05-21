from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textifai.import_review.structured_bootstrap_v1 import run_semantic_ingestion_replay


class TextifAIReplayBaselineHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.replay_input_root = Path("tests/fixtures/textifai/minimal_novel/replay_input")
        self.global_normalization_path = self.replay_input_root / "global_normalization.json"
        self.chapter_outputs_root = self.replay_input_root / "chapter_outputs"

    def test_replay_input_fixture_structure_is_valid_and_safe(self):
        self.assertTrue(self.replay_input_root.exists())
        self.assertTrue(self.global_normalization_path.exists())
        self.assertTrue(self.chapter_outputs_root.exists())

        expected_chapters = [
            self.chapter_outputs_root / "ch_001.json",
            self.chapter_outputs_root / "ch_002.json",
            self.chapter_outputs_root / "ch_003.json",
        ]
        for path in [self.global_normalization_path, *expected_chapters]:
            self.assertTrue(path.exists(), path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertIsInstance(payload, dict)
            self.assertLess(path.stat().st_size, 65536, path)

            serialized = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn("runs/", serialized)
            self.assertNotIn("vault/", serialized)
            self.assertNotIn("../runs", serialized)
            self.assertNotIn("../vault", serialized)

        forbidden_names = {"web_ingestion_job.json", "web_ingestion_job.log", "review_queue.log"}
        found = {path.name for path in self.replay_input_root.rglob("*") if path.is_file() and path.name in forbidden_names}
        self.assertEqual(found, set())

    def test_provider_free_replay_smoke_writes_only_inside_temp_output(self):
        with tempfile.TemporaryDirectory(prefix="textifai_replay_harness_") as temp_root:
            output_root = Path(temp_root) / "out"
            with patch("textifai.import_review.structured_bootstrap_v1.get_text_provider", side_effect=AssertionError("provider call not allowed")):
                result = run_semantic_ingestion_replay(
                    input_system_root=self.replay_input_root,
                    output_root=output_root,
                    language="es",
                )

            system_root = output_root / "99_System"
            self.assertTrue(system_root.exists())
            self.assertTrue((system_root / "obsidian_import.json").exists())
            self.assertTrue((system_root / "review_queue.json").exists())
            self.assertTrue((system_root / "semantic_invariants_audit.json").exists())

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
            expected_prefix = output_root.resolve()
            for path in produced_paths:
                self.assertTrue(path.resolve().is_relative_to(expected_prefix), path)
                self.assertNotIn("/runs/", str(path).replace("\\", "/"))
                self.assertNotIn("/vault/", str(path).replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()
