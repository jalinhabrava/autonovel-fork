from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from textifai.import_review.structured_bootstrap_v1 import build_canonical_entity_map

MODULE_PATH = Path("scripts/dev/capture_bootstrap_prompts.py").resolve()
MODULE_SPEC = importlib.util.spec_from_file_location("capture_bootstrap_prompts_populated", MODULE_PATH)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"Unable to load module from {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_SPEC.name] = MODULE
MODULE_SPEC.loader.exec_module(MODULE)
capture_bootstrap_prompts = MODULE.capture_bootstrap_prompts


class TextifAIRealBootstrapPopulatedMapCaptureHarnessTests(unittest.TestCase):
    def test_cli_help_accepts_global_normalization_json_option(self):
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--global-normalization-json", result.stdout)

    def test_legacy_behavior_without_override_remains_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_root = Path(tmp) / "source"
            output_root = Path(tmp) / "capture"
            source_root.mkdir(parents=True)
            (source_root / "novel.md").write_text(
                "# 1 Arrival\n\nSera arrives at Thiseia with a bell.\n",
                encoding="utf-8",
            )

            manifest_path = capture_bootstrap_prompts(
                source_root=source_root,
                output_root=output_root,
                primary_language="ja",
                max_chapters=1,
                timestamp="legacy-capture",
            )

            manifest = _load_json(manifest_path)
            self.assertEqual(manifest["provider_calls"], False)
            self.assertEqual(manifest["capture_only"], True)
            self.assertEqual(manifest["request_count"], 2)
            self.assertEqual(manifest["global_normalization_override_enabled"], False)
            self.assertIsNone(manifest["global_normalization_override_json"])
            self.assertIsNone(manifest["canonical_entity_map_from_override"])
            self.assertFalse((manifest_path.parent / "canonical_entity_map_from_override.json").exists())

    def test_override_populates_canonical_map_in_captured_chapter_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_root = Path(tmp) / "source"
            output_root = Path(tmp) / "capture"
            override_path = Path(tmp) / "manual_global.json"
            source_root.mkdir(parents=True)
            (source_root / "novel.md").write_text(
                "# 1 Arrival at Thiseia\n\nSera carries a bell through Thiseia.\n",
                encoding="utf-8",
            )
            override_payload = _synthetic_global_payload()
            override_path.write_text(json.dumps(override_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            manifest_path = capture_bootstrap_prompts(
                source_root=source_root,
                output_root=output_root,
                primary_language="ja",
                max_chapters=1,
                timestamp="override-capture",
                global_normalization_json=override_path,
            )

            manifest = _load_json(manifest_path)
            capture_dir = manifest_path.parent
            self.assertEqual(manifest["provider_calls"], False)
            self.assertEqual(manifest["capture_only"], True)
            self.assertEqual(manifest["global_normalization_override_enabled"], True)
            self.assertEqual(Path(manifest["global_normalization_override_json"]), override_path.resolve())
            self.assertTrue(manifest["canonical_entity_map_pipeline_path"])

            override_map_path = capture_dir / "canonical_entity_map_from_override.json"
            self.assertEqual(Path(manifest["canonical_entity_map_from_override"]), override_map_path)
            self.assertTrue(override_map_path.exists())
            canonical_map = _load_json(override_map_path)
            self.assertIsInstance(canonical_map, list)
            self.assertGreater(len(canonical_map), 0)
            self.assertEqual(canonical_map, build_canonical_entity_map(override_payload))

            request_payloads = [_load_json(path) for path in sorted(capture_dir.glob("request_*.json"))]
            chapter_request = next(item for item in request_payloads if item["task"] == "bootstrap_chapter_extraction")
            prompt_blob = (chapter_request.get("system") or "") + "\n" + "\n".join(message.get("content") or "" for message in chapter_request.get("messages") or [])
            self.assertIn("CANONICAL_ENTITY_MAP:", prompt_blob)
            self.assertNotIn("CANONICAL_ENTITY_MAP: []", prompt_blob)
            self.assertIn("セラ", prompt_blob)
            self.assertIn("ベル", prompt_blob)
            self.assertIn("objects", prompt_blob)
            self.assertIn("CANONICAL_MAP_MODE", prompt_blob)
            self.assertIn("relation_category", prompt_blob)
            self.assertIn("relation_label", prompt_blob)
            self.assertIn("event_importance", prompt_blob)

            markdown_path = next(path for path in sorted(capture_dir.glob("request_*.md")) if "bootstrap_chapter_extraction" in path.name)
            markdown_text = markdown_path.read_text(encoding="utf-8")
            self.assertIn("CANONICAL_ENTITY_MAP:", markdown_text)
            self.assertIn("セラ", markdown_text)
            self.assertIn("ベル", markdown_text)

            blob = json.dumps(manifest, ensure_ascii=False)
            self.assertNotIn("OPENAI_API_KEY", blob)
            self.assertNotIn("ANTHROPIC_API_KEY", blob)
            self.assertNotIn("https://api.", blob)
            self.assertNotIn("/runs/", blob)
            self.assertNotIn("/vault/", blob)


def _synthetic_global_payload() -> dict:
    return {
        "work": {"title": "Synthetic Work", "language": "ja", "normalization_notes": ["synthetic override"]},
        "entities": [
            {
                "canonical_name": "セラ",
                "canonical_candidate": "セラ",
                "entity_kind": "character",
                "entity_subkind": "heroine",
                "preferred_slug": "sera",
                "aliases": ["セラ", "姫"],
                "summary": "セラは主人公である。",
                "key_facts": ["セラは王城で暮らす。"],
                "relationships": [],
                "chapter_refs": ["ch_001"],
                "source_mentions": ["セラ", "姫"],
                "confidence": 0.95,
                "review_state": "canonical",
                "naming_quality": "proper_name",
                "is_stable_entity": True,
                "needs_review": False,
                "review_reason": "",
            },
            {
                "canonical_name": "ベル",
                "canonical_candidate": "ベル",
                "entity_kind": "object",
                "entity_subkind": "ritual_key",
                "preferred_slug": "bell",
                "aliases": ["ベル", "舌のないベル"],
                "summary": "ベルは重要な鍵である。",
                "key_facts": ["ベルは継承の鍵である。"],
                "relationships": [],
                "chapter_refs": ["ch_001"],
                "source_mentions": ["ベル", "舌のないベル"],
                "confidence": 0.9,
                "review_state": "canonical",
                "naming_quality": "descriptor",
                "is_stable_entity": True,
                "needs_review": False,
                "review_reason": "",
            },
        ],
        "merge_plan": [
            {
                "canonical_name": "ベル",
                "merged_surfaces": ["ベル", "舌のないベル"],
                "reason": "same artifact",
                "confidence": 0.91,
            }
        ],
    }



def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
