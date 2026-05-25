from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from textifai.bootstrap.contracts import SourceDocumentRecord
from textifai.import_review.auxiliary_ingestion import AuxiliaryDocumentInput, _build_auxiliary_document_record, _chunk_auxiliary_document
from textifai.import_review.batch_planner import split_markdown_semantically
from textifai.import_review.chapterizer import detect_story_chapters

FIXTURE_ROOT = Path("tests/fixtures/textifai/chunking_preflight/expected")
ONT_NAMES = ["セラ", "王者の杖", "アデルマン", "ティセイア", "ベル"]


class ChunkingReductionPreflightTests(unittest.TestCase):
    def test_reports_parse_and_are_privacy_safe(self):
        files = [
            FIXTURE_ROOT / "chunking_reduction_existing_pipeline_inventory_after_sp072.json",
            FIXTURE_ROOT / "chunking_budget_policy_after_sp072.json",
            FIXTURE_ROOT / "reduction_aggregation_inventory_after_sp072.json",
            FIXTURE_ROOT / "chunking_provider_harness_integration_plan_after_sp072.json",
            FIXTURE_ROOT / "chunking_reduction_preflight_decision_after_sp072.json",
        ]
        for path in files:
            data = json.loads(path.read_text(encoding="utf-8"))
            text = json.dumps(data, ensure_ascii=False)
            self.assertIn("assessment", data)
            self.assertNotIn("sk-", text)
            self.assertNotIn("provider_response.json", text)
            self.assertNotIn("BEGIN PRIVATE", text)
            for name in ONT_NAMES:
                self.assertNotIn(name, text)

    def test_decision_enum_valid(self):
        decision = json.loads((FIXTURE_ROOT / "chunking_reduction_preflight_decision_after_sp072.json").read_text(encoding="utf-8"))
        valid = {
            "chunking_reduction_preflight_ready",
            "chunking_reduction_preflight_ready_with_gaps",
            "chunking_reduction_existing_pipeline_unclear",
            "chunking_reduction_preflight_blocked",
        }
        self.assertIn(decision["assessment"], valid)
        self.assertFalse(decision["blocker"])

    def test_structured_document_chapter_detection_and_split(self):
        text = """---\ntitle: Demo\n---\n\nTable of Contents\n0 Prólogo inicial .... 1\n1 Apertura .... 2\n2 Cierre .... 3\n\n<<TEXTIFAI_PAGE_0001>>\n0 Prólogo inicial\n\nEsto contiene muchas palabras para superar el límite mínimo de capítulo detectado por el preflight sintético.\n\n<<TEXTIFAI_PAGE_0002>>\n1 Apertura\n\nPrimer bloque con muchas palabras para superar el mínimo.\n\n## Escena A\n\n""" + ("Dato largo repetido muchas veces para dividir por secciones y conservar contexto.\n\n" * 24) + "\n<<TEXTIFAI_PAGE_0003>>\n2 Cierre\n\nCierre breve con muchas palabras para superar el mínimo requerido por el detector.\n"
        document = SourceDocumentRecord(
            source_id="demo_source",
            path="/tmp/demo.md",
            relative_path="demo.md",
            filename="demo.md",
            extension="md",
            size_bytes=len(text.encode("utf-8")),
            checksum="x" * 64,
            dominant_language="es",
            detected_languages=["es"],
            line_count=len(text.splitlines()),
            extracted_char_count=len(text),
            extracted_word_count=len(text.split()),
            extracted_page_count=0,
        )
        chapters = detect_story_chapters(document, text)
        self.assertGreaterEqual(len(chapters), 3)
        self.assertGreaterEqual(chapters[0].char_start, 0)
        self.assertTrue(all(chapters[i].char_start < chapters[i].char_end for i in range(len(chapters))))
        self.assertTrue(any("1 Apertura" in chapter.title for chapter in chapters))
        self.assertTrue(any("Escena A" in chapter.title for chapter in chapters))

        long_chapter = "\n\n".join(
            [
                f"Parrafo {index} con contenido de prueba suficientemente largo para activar split semantico por presupuesto."
                for index in range(1, 80)
            ]
        )
        chunks = split_markdown_semantically(
            chapter_text=long_chapter,
            max_chunk_tokens=60,
            estimate_tokens=lambda s: max(1, len(s.split())),
            overlap_paragraphs=1,
        )
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(chunk.strip() for chunk in chunks))
        self.assertTrue(any("Parrafo" in chunk for chunk in chunks))
        self.assertFalse(any(len(chunk.strip()) < 20 for chunk in chunks[:-1]))

    def test_auxiliary_notes_chunking_preserves_related_blocks(self):
        notes = """# Magic System\n- Coste alto\n- Afinidad\n\n## Failure Modes\n- Sobrecarga\n- Interferencia\n\n# Character Notes\n- Alias: The Regent\n- Contradictory role rumor\n\n# Loose Lore\n- Random bullet A\n- Random bullet B\n"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.md"
            path.write_text(notes, encoding="utf-8")
            record = _build_auxiliary_document_record(AuxiliaryDocumentInput(path=str(path), author_hint="worldbuilding notes"))
            chunks = _chunk_auxiliary_document(record)

        self.assertGreaterEqual(len(chunks), 1)
        self.assertTrue(all(chunk["source_id"] == record["source_id"] for chunk in chunks))
        self.assertTrue(all("chunk_id" in chunk for chunk in chunks))
        self.assertTrue(all("heading_path" in chunk for chunk in chunks))
        self.assertTrue(all("chunk_kind" in chunk for chunk in chunks))
        self.assertTrue(any(chunk["author_hint"] == "worldbuilding notes" for chunk in chunks))
        self.assertTrue(any("Magic System" in chunk["text"] for chunk in chunks))
        self.assertTrue(any("Character Notes" in chunk["text"] for chunk in chunks))

    def test_inventory_reports_capture_known_gaps(self):
        inventory = json.loads((FIXTURE_ROOT / "chunking_reduction_existing_pipeline_inventory_after_sp072.json").read_text(encoding="utf-8"))
        reduction = json.loads((FIXTURE_ROOT / "reduction_aggregation_inventory_after_sp072.json").read_text(encoding="utf-8"))
        integration = json.loads((FIXTURE_ROOT / "chunking_provider_harness_integration_plan_after_sp072.json").read_text(encoding="utf-8"))

        self.assertEqual(inventory["structured_document_support"]["status"], "present")
        self.assertEqual(inventory["unstructured_author_notes_support"]["status"], "present")
        self.assertEqual(inventory["evidence_source_spans_support"]["status"], "partial")
        self.assertIn("DeepSeek", json.dumps(integration, ensure_ascii=False))
        self.assertIn("invalid_chunk_outputs", json.dumps(reduction, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
