from __future__ import annotations

import json
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path("scripts/dev/capture_bootstrap_prompts.py").resolve()
MODULE_SPEC = importlib.util.spec_from_file_location("capture_bootstrap_prompts", MODULE_PATH)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"Unable to load module from {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_SPEC.name] = MODULE
MODULE_SPEC.loader.exec_module(MODULE)
capture_bootstrap_prompts = MODULE.capture_bootstrap_prompts


class TextifAIRealBootstrapPromptCaptureHarnessTests(unittest.TestCase):
    def test_capture_harness_records_real_pipeline_requests_without_provider_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_root = Path(tmp) / "source"
            output_root = Path(tmp) / "capture"
            source_root.mkdir(parents=True)
            (source_root / "novel.md").write_text(
                (
                    "# 1 Arrival at Thiseia\n\n"
                    "Sera wakes in Thiseia and sees Ren near the gate.\n\n"
                    "# 2 Escape from the Castle\n\n"
                    "Sera runs with Ren after hearing a distant bell.\n"
                ),
                encoding="utf-8",
            )

            manifest_path = capture_bootstrap_prompts(
                source_root=source_root,
                output_root=output_root,
                primary_language="ja",
                max_chapters=1,
                timestamp="test-capture",
            )

            manifest = _load_json(manifest_path)
            capture_dir = manifest_path.parent
            self.assertEqual(manifest["provider_calls"], False)
            self.assertEqual(manifest["capture_only"], True)
            self.assertEqual(manifest["request_count"], 2)
            self.assertTrue(str(capture_dir).startswith(str(output_root)))
            self.assertFalse((capture_dir / "runs").exists())
            self.assertFalse((capture_dir / "vault").exists())

            request_paths = sorted(capture_dir.glob("request_*.json"))
            markdown_paths = sorted(capture_dir.glob("request_*.md"))
            self.assertEqual(len(request_paths), 2)
            self.assertEqual(len(markdown_paths), 2)
            for path in request_paths:
                request = _load_json(path)
                self.assertEqual(request["provider_calls"], False)
                self.assertEqual(request["capture_only"], True)
                self.assertIn("task", request)
                self.assertIn("system", request)
                self.assertIn("messages", request)
                self.assertIn("max_tokens", request)
                self.assertGreater(request["estimated_input_chars"], 0)
                blob = json.dumps(request, ensure_ascii=False)
                self.assertNotIn("OPENAI_API_KEY", blob)
                self.assertNotIn("ANTHROPIC_API_KEY", blob)
                self.assertNotIn("https://api.", blob)
                self.assertNotIn("/runs/", blob)
                self.assertNotIn("/vault/", blob)

            chapter_request = next(item for item in map(_load_json, request_paths) if item["task"] == "bootstrap_chapter_extraction")
            self.assertEqual(chapter_request["detected_chapter_id"], "ch_001")
            self.assertEqual(chapter_request["detected_chapter_title"], "1 Arrival at Thiseia")
            self.assertGreater(chapter_request["chapter_text_char_count"], 0)

    def test_capture_markdown_is_copyable_prompt_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_root = Path(tmp) / "source"
            output_root = Path(tmp) / "capture"
            source_root.mkdir(parents=True)
            (source_root / "novel.md").write_text(
                "# Chapter 1: Arrival\n\nSera arrives at Thiseia with Ren.\n",
                encoding="utf-8",
            )

            manifest_path = capture_bootstrap_prompts(
                source_root=source_root,
                output_root=output_root,
                primary_language="en",
                max_chapters=1,
                timestamp="test-copyable",
            )
            capture_dir = manifest_path.parent
            md_text = sorted(capture_dir.glob("request_*.md"))[0].read_text(encoding="utf-8")
            self.assertIn("# TextifAI Bootstrap Prompt Capture", md_text)
            self.assertIn("## System", md_text)
            self.assertIn("## Messages", md_text)
            self.assertIn("Return only valid JSON", md_text)
            self.assertNotIn("Expected output", md_text)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
