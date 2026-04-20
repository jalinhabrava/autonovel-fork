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
        return type(
            "_Response",
            (),
            {
                "text": '{"title":"Chapter 1 Summary","summary_markdown":"[[Sera]] wakes in the [[Castle of Thiseia]] and thinks about [[Thiseia]]."}'
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
                "# Chapter 1\n\nSera wakes in the Castle of Thiseia and thinks about Thiseia.\n",
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
                    config=StoryBuildConfig(provider_name="openai", model="gpt-5.4"),
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


if __name__ == "__main__":
    unittest.main()
