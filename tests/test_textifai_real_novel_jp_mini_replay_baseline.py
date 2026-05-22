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

class TextifAIRealNovelJPMiniReplayBaselineTests(unittest.TestCase):
    def test_provider_free_replay_writes_only_inside_temp_output(self):
        before = _hash_replay_input()
        with tempfile.TemporaryDirectory(prefix="textifai_real_novel_jp_mini_") as temp_root:
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
            self.assertTrue((system_root / "obsidian_import.json").exists())
            self.assertTrue((system_root / "review_queue.json").exists())
            self.assertTrue((system_root / "semantic_invariants_audit.json").exists())
            self.assertFalse((system_root / "web_ingestion_job.json").exists())
            self.assertFalse((system_root / "web_ingestion_job.log").exists())
            for path in [
                Path(result.output_root),
                Path(result.obsidian_import_path),
                Path(result.review_queue_path),
                Path(result.semantic_invariants_audit_path),
                Path(result.replay_audit_path),
            ]:
                resolved = path.resolve()
                self.assertTrue(resolved.is_relative_to(output_root.resolve()), path)
                normalized = str(resolved).replace("\\", "/")
                self.assertNotIn("/runs/", normalized)
                self.assertNotIn("/vault/", normalized)
        self.assertEqual(before, _hash_replay_input())


def _hash_replay_input() -> dict[str, str]:
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(REPLAY_INPUT_ROOT.rglob("*")) if path.is_file()}

if __name__ == "__main__":
    unittest.main()
