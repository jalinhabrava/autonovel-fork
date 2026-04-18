import tempfile
import unittest
import zipfile
from pathlib import Path

from textifai.derived_sources import (
    detect_source_format,
    extract_light_source,
)


def _write_docx(path: Path, paragraphs: list[str]) -> None:
    content = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">',
        "<w:body>",
    ]
    for paragraph in paragraphs:
        content.append(f"<w:p><w:r><w:t>{_escape_xml(paragraph)}</w:t></w:r></w:p>")
    content.append("</w:body></w:document>")
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", "".join(content))


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


class TextifAIDerivedSourceExtractorTests(unittest.TestCase):
    def test_detects_supported_derived_formats_and_light_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            md = root / "note.md"
            txt = root / "note.txt"
            docx = root / "chapter.docx"
            pdf = root / "scan.pdf"
            doc = root / "legacy.doc"

            md.write_text("# Note\n\nThe author left a remark.", encoding="utf-8")
            txt.write_text("This is a plain note in English.\n\nAnother paragraph.", encoding="utf-8")
            _write_docx(docx, ["Scene notes", "The hallway was silent.", "Then the door opened."])
            pdf.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")
            doc.write_text("Legacy memo\n\nShort note in Spanish: El autor pidió calma.", encoding="utf-8")

            self.assertEqual(detect_source_format(md), "md")
            self.assertEqual(detect_source_format(txt), "txt")
            self.assertEqual(detect_source_format(docx), "docx")
            self.assertEqual(detect_source_format(pdf), "pdf")
            self.assertEqual(detect_source_format(doc), "doc")

            md_seed = extract_light_source(md)
            txt_seed = extract_light_source(txt)
            docx_seed = extract_light_source(docx)
            pdf_seed = extract_light_source(pdf)
            doc_seed = extract_light_source(doc)

            self.assertTrue(md_seed.format_profile.is_native_text)
            self.assertTrue(txt_seed.format_profile.is_native_text)
            self.assertFalse(docx_seed.format_profile.is_native_text)
            self.assertFalse(pdf_seed.format_profile.is_native_text)
            self.assertFalse(doc_seed.format_profile.is_native_text)
            self.assertIn("native_text", md_seed.quality_signals)
            self.assertGreater(len(docx_seed.lightweight_blocks), 0)
            self.assertTrue(pdf_seed.format_profile.llm_escalation_required)
            self.assertTrue(doc_seed.format_profile.llm_escalation_required)
            self.assertIn("pdf", pdf_seed.source_format)
            self.assertIn("doc", doc_seed.source_format)


if __name__ == "__main__":
    unittest.main()
