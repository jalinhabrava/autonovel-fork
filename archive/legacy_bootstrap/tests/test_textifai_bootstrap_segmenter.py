import unittest

from textifai.bootstrap.contracts import SourceDocumentRecord
from textifai.bootstrap.segmenter import segment_source_document


class TextifAIBootstrapSegmenterTests(unittest.TestCase):
    def test_segmenter_splits_on_heading_boundaries(self):
        document = SourceDocumentRecord(
            source_id="chapter_01_abc123",
            path="/tmp/chapter_01.md",
            relative_path="chapter_01.md",
            filename="chapter_01.md",
            extension="md",
            size_bytes=120,
            checksum="abc123",
            dominant_language="en",
            detected_languages=["en"],
            has_mixed_language=False,
            likely_content_kinds=["chapter"],
            line_count=6,
            notes=[],
        )
        text = "# Chapter One\n\nThe meeting began.\n\n# Chapter Two\n\nThe client left."

        fragments = segment_source_document(document, text)

        self.assertEqual(len(fragments), 2)
        self.assertEqual([fragment.detected_kind for fragment in fragments], ["chapter", "chapter"])
        self.assertTrue(all(fragment.kind_confidence >= 0.9 for fragment in fragments))


if __name__ == "__main__":
    unittest.main()
