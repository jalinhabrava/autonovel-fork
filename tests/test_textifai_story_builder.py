from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textifai.bootstrap.source_reader import build_source_document_inventory
from textifai.import_review.story_builder import StoryBuildConfig, build_story_notes
from vault.bootstrap import bootstrap_vault
from vault.notes import write_or_update_note


class _FakeProvider:
    def generate(self, request):
        content = request.messages[0].content
        if "Classify structural boundary candidates" in content:
            candidate_id = "candidate_001"
            if '"candidate_id"' in content:
                import json

                payload = json.loads(content)
                candidate_id = payload["candidates"][0]["candidate_id"]
            return type(
                "_Response",
                (),
                {
                    "text": '{"decisions":[{"candidate_id":"%s","classification":"chapter","normalized_title":"Chapter 1: Arrival at Thiseia","chapter_number":"1","confidence":0.91,"reason":"isolated markdown heading starts a chapter-sized unit"}]}' % candidate_id
                },
            )()
        return type(
            "_Response",
            (),
            {
                "text": '{"summary_markdown":"[[Sera]] wakes in the [[Castle of Thiseia]] and thinks about [[Thiseia]].","characters":[{"name":"Sera","aliases":["Serélyne"],"facts":["Princess of [[Thiseia]]."],"confidence":0.9}],"places":[{"name":"Castle of Thiseia","aliases":[],"facts":["A castle in [[Thiseia]]."],"confidence":0.8}],"concepts":[],"events":[],"relations":[],"new_traits":[],"aliases":[],"review_items":[],"confidence":0.86}'
            },
        )()


class TextifAIStoryBuilderTests(unittest.TestCase):
    def test_story_builder_writes_chapter_and_summary_with_wikilinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            source_root = Path(tmp) / "source"
            bootstrap_vault(vault_root, title="Test Project")
            source_root.mkdir(parents=True, exist_ok=True)
            write_or_update_note(
                vault_root,
                note_type="character",
                slug="sera",
                title="Sera",
                body="Princess of [[Thiseia]].",
                metadata={"note_role": "primary", "artifact_stage": "promoted_artifact"},
            )
            write_or_update_note(
                vault_root,
                note_type="place",
                slug="castle_of_thiseia",
                title="Castle of Thiseia",
                body="A castle inside [[Thiseia]].",
                metadata={"note_role": "primary", "artifact_stage": "promoted_artifact"},
            )
            write_or_update_note(
                vault_root,
                note_type="lore",
                slug="thiseia",
                title="Thiseia",
                body="A kingdom.",
                metadata={"note_role": "primary", "artifact_stage": "promoted_artifact"},
            )
            (source_root / "chapter_01.md").write_text(
                "# Chapter 1: Arrival at Thiseia\n\nSera wakes in the Castle of Thiseia and thinks about Thiseia.\n",
                encoding="utf-8",
            )
            inventory = build_source_document_inventory(source_root)

            with patch("textifai.import_review.story_builder.get_text_provider_config_error", return_value=None), patch(
                "textifai.import_review.story_builder.get_text_provider",
                return_value=_FakeProvider(),
            ):
                result = build_story_notes(
                    vault_root,
                    inventory=inventory,
                    config=StoryBuildConfig(provider_name="openai", model="gpt-5.4", max_chapters=1),
                )

            self.assertEqual(len(result.chapter_paths), 1)
            self.assertEqual(len(result.summary_paths), 1)
            chapter_text = Path(result.chapter_paths[0]).read_text(encoding="utf-8")
            summary_text = Path(result.summary_paths[0]).read_text(encoding="utf-8")
            self.assertIn("[[Sera]]", chapter_text)
            self.assertIn("[[Castle of Thiseia]]", chapter_text)
            self.assertIn("[[Sera]]", summary_text)
            self.assertIn("/04_Story/Chapters/".strip("/"), result.chapter_paths[0])
            self.assertIn("/04_Story/Chapter_Summaries/".strip("/"), result.summary_paths[0])
            self.assertIn("note_role: chapter", chapter_text)
            self.assertIn("note_role: chapter_summary", summary_text)
            self.assertTrue((vault_root / "99_System" / "chapter_detection_audit.json").exists())
            self.assertTrue((vault_root / "99_System" / "chapter_analysis_audit.json").exists())
            self.assertTrue((vault_root / "99_System" / "chapter_map_audit.json").exists())
            self.assertTrue((vault_root / "99_System" / "primary_update_audit.json").exists())


if __name__ == "__main__":
    unittest.main()
