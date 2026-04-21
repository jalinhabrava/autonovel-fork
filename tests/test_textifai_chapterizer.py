from __future__ import annotations

import unittest

from textifai.bootstrap.contracts import SourceDocumentRecord
from textifai.import_review.chapterizer import detect_story_chapters


class TextifAIChapterizerTests(unittest.TestCase):
    def test_detects_multiple_chapters_with_page_ranges(self):
        document = SourceDocumentRecord(
            source_id="novel_001",
            path="/tmp/novel.pdf",
            relative_path="novel.pdf",
            filename="novel.pdf",
            extension="pdf",
            size_bytes=100,
            checksum="abc",
            dominant_language="es",
            detected_languages=["es"],
            likely_content_kinds=["chapter"],
            extracted_page_count=4,
        )
        text = "\n".join(
            [
                "<<TEXTIFAI_PAGE_0001>>",
                "Índice",
                "Capítulo 1. La llegada ........ 1",
                "Capítulo 2. La deuda ........ 3",
                "<<TEXTIFAI_PAGE_0002>>",
                "Capítulo 1. La llegada",
                "",
                "Sera entra en Thiseia y observa el castillo.",
                "",
                "<<TEXTIFAI_PAGE_0003>>",
                "Capítulo 2. La deuda",
                "",
                "Ren recuerda el precio del vínculo y teme al Regente.",
            ]
        )

        chapters = detect_story_chapters(document, text)

        self.assertEqual(len(chapters), 2)
        self.assertEqual(chapters[0].title, "Capítulo 1. La llegada")
        self.assertEqual(chapters[0].page_start, 2)
        self.assertEqual(chapters[1].page_start, 3)
        self.assertGreaterEqual(chapters[0].confidence, 0.79)


if __name__ == "__main__":
    unittest.main()
