import tempfile
import unittest
import zipfile
from pathlib import Path

from textifai.derived_sources import build_derived_understanding_prompt, decide_llm_escalation, extract_light_source


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


class TextifAIDerivedSourceGatingTests(unittest.TestCase):
    def test_docx_simple_can_skip_llm_when_light_extraction_is_sufficient(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "simple.docx"
            _write_docx(path, ["Scene notes", "The corridor was quiet.", "He wrote one line and left."])
            seed = extract_light_source(path)
            escalation = decide_llm_escalation(seed)
            prompt = build_derived_understanding_prompt(seed=seed, escalation=escalation)

            self.assertFalse(escalation.required)
            self.assertIn("docx", prompt.user_payload["source_format"])
            self.assertIn("quality_signals", prompt.user_payload)
            self.assertIn("lightweight_blocks", prompt.user_payload)
            self.assertIn("translate", prompt.system_prompt.lower())

    def test_pdf_without_text_escalates_to_llm(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scan.pdf"
            path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")
            seed = extract_light_source(path)
            escalation = decide_llm_escalation(seed)
            prompt = build_derived_understanding_prompt(seed=seed, escalation=escalation)

            self.assertTrue(escalation.required)
            self.assertIn("non_extractable_text", escalation.reasons)
            self.assertEqual(prompt.user_payload["llm_escalation"]["required"], True)
            self.assertIn("recognized_or_recovered_text", prompt.required_output_schema)


if __name__ == "__main__":
    unittest.main()
