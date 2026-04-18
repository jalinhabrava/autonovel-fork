import tempfile
import unittest
from pathlib import Path

from textifai.bootstrap.language import build_language_profile
from textifai.bootstrap.source_reader import build_source_document_inventory, read_source_documents
from textifai.bootstrap.segmenter import segment_source_document


class TextifAIBootstrapInventoryTests(unittest.TestCase):
    def test_inventory_detects_multilingual_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_root = Path(tmp) / "sources"
            source_root.mkdir()
            (source_root / "novel_en.md").write_text("# Chapter One\n\nThe meeting began in silence.")
            (source_root / "lore_ja.txt").write_text("これは世界の記録です。魔法は代償を払う。")
            (source_root / "notes_mixed.md").write_text("El personaje said hello to the client.\n\nそして彼は黙った。")

            inventory = build_source_document_inventory(source_root)
            source_texts = read_source_documents(inventory)
            fragments_by_source = {
                document.source_id: segment_source_document(document, source_texts[document.source_id])
                for document in inventory.documents
            }
            language_profile = build_language_profile(
                inventory,
                fragments_by_source,
                source_texts,
                project_primary_language="es",
                working_languages=["es", "en", "ja"],
            )

            self.assertEqual(inventory.total_documents, 3)
            self.assertTrue(inventory.has_multilingual_material)
            self.assertIn("en", inventory.detected_working_languages)
            self.assertIn("ja", inventory.detected_working_languages)
            self.assertIn("es", inventory.detected_working_languages)
            self.assertTrue(language_profile.has_multilingual_documents)
            self.assertIn("ja", language_profile.document_languages[next(doc.source_id for doc in inventory.documents if doc.filename == "lore_ja.txt")])


if __name__ == "__main__":
    unittest.main()
