from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from textifai.bootstrap.contracts import SourceDocumentRecord
from textifai.import_review.auxiliary_ingestion import AuxiliaryDocumentInput, _build_auxiliary_document_record, _chunk_auxiliary_document
from textifai.import_review.batch_planner import (
    build_default_natural_chunking_threshold_policy,
    split_markdown_semantically,
    split_structured_chapter_into_chunks,
)
from textifai.import_review.chapterizer import detect_story_chapters
from textifai.import_review.chunking_reduction_preflight import (
    build_natural_chunking_calibration_report,
    build_natural_chunking_policy_report,
    build_natural_chunking_replan_simulation,
    build_long_provider_run_contract,
    build_patch_continuation_chapter_validation_report,
    build_private_decision_packet_contract,
    build_provider_free_chunking_reduction_fixture_report,
    build_source_ref_carry_forward_report,
    build_thin_reduction_diagnostics,
    reduce_mock_chunk_partials,
    validate_patch_continuation_chapter,
)
from textifai.import_review.deepseek_family_profiles import (
    build_continuation_repair_contract,
    build_deepseek_budget_bridge,
    build_response_control_contract,
    get_deepseek_family_profile,
)
from textifai.import_review.model_registry import get_model_capabilities
from textifai.import_review.token_budget import (
    TokenPlanningRequest,
    build_token_budget_from_planning_request,
    resolve_effective_output_budget,
)

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
            FIXTURE_ROOT / "deepseek_budget_bridge_after_sp073.json",
            FIXTURE_ROOT / "provider_free_chunking_reduction_fixture_e2e_after_sp073.json",
            FIXTURE_ROOT / "private_decision_packet_contract_after_sp073.json",
            FIXTURE_ROOT / "long_provider_run_contract_after_sp073.json",
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

    def test_structured_source_chunk_records_preserve_metadata(self):
        chapter_text = "\n\n".join(
            [
                "# Capítulo sintético",
                "## Escena 1\n\n" + "\n\n".join(
                    f"Párrafo A{index} con objeto, evento y relación." for index in range(1, 16)
                ),
                "## Escena 2\n\n" + "\n\n".join(
                    f"Párrafo B{index} con objeto, evento y relación." for index in range(1, 16)
                ),
                "## Escena 3\n\n" + "\n\n".join(
                    f"Párrafo C{index} con objeto, evento y relación." for index in range(1, 16)
                ),
            ]
        )
        chunks = split_structured_chapter_into_chunks(
            source_id="synthetic_source",
            chapter_id="ch_001",
            chapter_text=chapter_text,
            chapter_char_start=123,
            max_chunk_tokens=20,
            estimate_tokens=lambda value: max(1, len(value.split())),
            overlap_paragraphs=1,
            budget_profile_id="deepseek-v4-flash:budget:v1",
            provider_profile_id="deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1",
        )
        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(chunks[0].predecessor_chunk_id, None)
        self.assertEqual(chunks[-1].successor_chunk_id, None)
        self.assertTrue(chunks[0].successor_chunk_id)
        self.assertTrue(chunks[1].predecessor_chunk_id)
        self.assertTrue(all(chunk.source_id == "synthetic_source" for chunk in chunks))
        self.assertTrue(all(chunk.chapter_id == "ch_001" for chunk in chunks))
        self.assertTrue(all(chunk.char_start < chunk.char_end for chunk in chunks))
        self.assertTrue(all(chunk.source_span["char_start"] == chunk.char_start for chunk in chunks))
        self.assertTrue(all(chunk.estimated_tokens > 0 for chunk in chunks))
        self.assertTrue(all(chunk.provider_profile_id for chunk in chunks))

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
        self.assertTrue(all("char_start" in chunk and "char_end" in chunk for chunk in chunks))
        self.assertTrue(all(chunk["char_start"] < chunk["char_end"] for chunk in chunks))
        self.assertTrue(all(chunk["source_span"]["char_start"] == chunk["char_start"] for chunk in chunks))
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

    def test_deepseek_budget_bridge_from_profiles_to_token_planning(self):
        bridge = build_deepseek_budget_bridge()
        self.assertEqual(bridge["provider"], "deepseek")
        profile = get_deepseek_family_profile("deepseek-v4-flash")
        self.assertIsNotNone(profile)
        capabilities = get_model_capabilities("deepseek-v4-flash")
        planning = TokenPlanningRequest(
            provider="deepseek",
            model="deepseek-v4-flash",
            task="bootstrap_chapter_extraction",
            provider_profile_id=profile.profile_id,
            max_output_tokens=profile.default_max_output_tokens,
            prompt_overhead_tokens=5000,
            source_text_budget_tokens=6000,
            safety_margin=capabilities.recommended_safety_margin,
        )
        budget = build_token_budget_from_planning_request(capabilities=capabilities, planning=planning)
        self.assertEqual(budget["provider_profile_id"], profile.profile_id)
        self.assertEqual(budget["max_output_tokens"], 8192)
        self.assertEqual(budget["reserved_output_tokens"], 8192)
        self.assertGreater(budget["usable_input_budget"], budget["source_text_budget_tokens"])

    def test_provider_free_chunk_partial_reduction_fixture(self):
        chunks = split_structured_chapter_into_chunks(
            source_id="synthetic_source",
            chapter_id="ch_010",
            chapter_text="Objeto llave activa evento.\n\nObjeto sello bloquea salida.\n\nRelación autoridad presiona decisión.",
            chapter_char_start=0,
            max_chunk_tokens=8,
            estimate_tokens=lambda value: max(1, len(value.split())),
            overlap_paragraphs=0,
        )
        partials = [
            {"chunk_id": chunks[0].chunk_id, "status": "ok", "payload": {"chapters": [{"objects": [{"canonical_name": "Llave"}], "events": [{"canonical_name": "Apertura"}], "relations": [{"source": "Llave", "target": "Apertura", "type": "triggers"}]}]}},
            {"chunk_id": chunks[1].chunk_id, "status": "ok", "payload": {"chapters": [{"objects": [{"canonical_name": "Llave"}, {"canonical_name": "Sello", "review_state": "local_candidate"}], "events": [{"canonical_name": "Bloqueo"}], "relations": [{"source": "Sello", "target": "Bloqueo", "type": "causes"}]}]}},
            {"chunk_id": "missing", "status": "invalid_partial", "failure_mode": "invalid_json_unknown"},
        ]
        result = reduce_mock_chunk_partials(chunks=chunks, partials=partials, chapter_id="ch_010")
        chapter = result["chapters"][0]
        self.assertGreaterEqual(len(chapter["objects"]), 2)
        self.assertGreaterEqual(len(chapter["events"]), 2)
        self.assertGreaterEqual(len(chapter["relations"]), 2)
        self.assertTrue(any(item.get("review_state") for item in chapter["objects"]))
        self.assertTrue(all(item.get("source_refs") for item in chapter["objects"]))
        self.assertTrue(chapter["reduction_warnings"])
        report = build_provider_free_chunking_reduction_fixture_report(result)
        self.assertEqual(report["assessment"], "chunking_reduction_gaps_closed_for_provider_free_e2e")
        self.assertEqual(report["invalid_partial_count"], 1)

    def test_private_decision_and_long_run_contracts(self):
        packet = build_private_decision_packet_contract()
        long_run = build_long_provider_run_contract()
        self.assertIn("provider_response_raw.txt", packet["per_run_files"])
        self.assertFalse(packet["privacy_rules"]["commit_allowed"])
        self.assertEqual(packet["privacy_rules"]["authorization_header_policy"], "redact")
        self.assertTrue(long_run["progress_log"]["incremental"])
        self.assertIn("last_output_activity_at", long_run["progress_log"]["required_fields"])
        self.assertTrue(long_run["timeout_policy"]["stall_detection_required"])

    def test_source_ref_carry_forward_rules_and_dedupe(self):
        report = build_source_ref_carry_forward_report()
        self.assertEqual(report["assessment"], "source_refs_and_output_budget_protocol_ready")
        self.assertTrue(report["rules"]["merge_multiple_chunk_refs_without_duplicates"])

        chunks = split_structured_chapter_into_chunks(
            source_id="src",
            chapter_id="ch_100",
            chapter_text="## A\n\nUno dos tres.\n\n## B\n\nCuatro cinco seis.",
            chapter_char_start=10,
            max_chunk_tokens=4,
            estimate_tokens=lambda value: max(1, len(value.split())),
            overlap_paragraphs=0,
        )
        partials = [
            {
                "chunk_id": chunks[0].chunk_id,
                "status": "ok",
                "payload": {"chapters": [{"objects": [{"canonical_name": "Llave", "source_refs": [{"source_id": "src", "chapter_id": "ch_100", "chunk_id": chunks[0].chunk_id, "char_start": 10, "char_end": 20}]}]}]},
            },
            {
                "chunk_id": chunks[1].chunk_id,
                "status": "ok",
                "payload": {"chapters": [{"objects": [{"canonical_name": "Llave"}]}]},
            },
        ]
        reduced = reduce_mock_chunk_partials(chunks=chunks, partials=partials, chapter_id="ch_100")
        objects = reduced["chapters"][0]["objects"]
        self.assertEqual(len(objects), 1)
        self.assertGreaterEqual(len(objects[0].get("source_refs") or []), 2)

    def test_output_budget_resolver_dynamic_sources(self):
        caps = get_model_capabilities("deepseek-v4-flash")
        resolved_profile = resolve_effective_output_budget(
            provider="deepseek",
            model="deepseek-v4-flash",
            task="bootstrap_chapter_extraction",
            capabilities=caps,
            provider_profile_id="deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1",
            profile_default_max_output_tokens=8192,
            provider_default_max_output_tokens=4096,
        )
        self.assertEqual(resolved_profile.decision_source, "profile_default")
        self.assertEqual(resolved_profile.effective_max_output_tokens, 8192)

        resolved_override = resolve_effective_output_budget(
            provider="deepseek",
            model="deepseek-v4-flash",
            task="bootstrap_chapter_extraction",
            capabilities=caps,
            provider_profile_id="deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1",
            profile_default_max_output_tokens=8192,
            cli_override_max_output_tokens=7000,
            provider_default_max_output_tokens=4096,
        )
        self.assertEqual(resolved_override.decision_source, "cli_override")
        self.assertEqual(resolved_override.effective_max_output_tokens, 7000)

    def test_response_control_and_continuation_contracts(self):
        response_control = build_response_control_contract()
        continuation = build_continuation_repair_contract()
        self.assertIn("response_control", response_control)
        self.assertEqual(response_control["response_control"]["completion_status"], "complete|partial")
        self.assertIn("invalid_json_truncated", continuation["triggers"])

    def test_natural_chunking_threshold_policy_and_soft_split_behavior(self):
        policy = build_default_natural_chunking_threshold_policy(hard_max_source_tokens=6000)
        self.assertEqual(policy.soft_chunk_target_tokens, 1400)
        self.assertEqual(policy.soft_chunk_max_tokens, 2200)

        text = "\n\n".join(f"P{i} uno dos tres cuatro cinco seis siete ocho nueve diez once doce." for i in range(20))
        chunks = split_structured_chapter_into_chunks(
            source_id="src",
            chapter_id="ch_200",
            chapter_text=text,
            chapter_char_start=0,
            max_chunk_tokens=6000,
            estimate_tokens=lambda value: max(1, len(value.split())),
            threshold_policy=build_default_natural_chunking_threshold_policy(
                hard_max_source_tokens=6000,
                provider_chunking_preferences={"soft_chunk_target_tokens": 60, "soft_chunk_max_tokens": 80, "min_chunk_tokens": 20},
            ),
        )
        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0].split_reason, "soft_quality_split")

        single_section = "。".join(["長い文" for _ in range(180)])
        oversized = split_structured_chapter_into_chunks(
            source_id="src",
            chapter_id="ch_202",
            chapter_text=single_section,
            chapter_char_start=0,
            max_chunk_tokens=6000,
            estimate_tokens=lambda value: max(1, len(value) // 4),
            threshold_policy=build_default_natural_chunking_threshold_policy(
                hard_max_source_tokens=6000,
                provider_chunking_preferences={"soft_chunk_target_tokens": 80, "soft_chunk_max_tokens": 120, "min_chunk_tokens": 30},
            ),
        )
        self.assertGreater(len(oversized), 1)
        self.assertTrue(all(chunk.char_start < chunk.char_end for chunk in oversized))

    def test_min_chunk_tokens_avoids_tiny_chunks(self):
        text = "\n\n".join(["uno dos tres cuatro cinco seis"] * 5 + ["coda corta"])
        chunks = split_structured_chapter_into_chunks(
            source_id="src",
            chapter_id="ch_201",
            chapter_text=text,
            chapter_char_start=0,
            max_chunk_tokens=200,
            estimate_tokens=lambda value: max(1, len(value.split())),
            threshold_policy=build_default_natural_chunking_threshold_policy(
                hard_max_source_tokens=200,
                provider_chunking_preferences={"soft_chunk_target_tokens": 12, "soft_chunk_max_tokens": 15, "min_chunk_tokens": 6},
            ),
        )
        self.assertTrue(all(chunk.estimated_tokens >= 2 for chunk in chunks))

    def test_patch_chapter_validation_rejects_wrong_chapter(self):
        report = build_patch_continuation_chapter_validation_report()
        self.assertEqual(report["failure_mode"], "valid_json_wrong_chapter")
        validation = validate_patch_continuation_chapter(
            expected_chapter_id="ch_001",
            expected_chunk_ids=["source_x_ch_001_chunk_001"],
            patch_payload={
                "continuation_patch": {
                    "objects": [{"canonical_name": "Bastón", "source_refs": [{"chapter_id": "ch_002", "chunk_id": "source_x_ch_002_chunk_001"}]}]
                },
                "patch_metadata": {"chapter_id": "ch_002"},
            },
        )
        self.assertFalse(validation["valid"])
        self.assertEqual(validation["failure_mode"], "valid_json_wrong_chapter")

    def test_thin_no_item_reduction_diagnostics_distinguish_no_items_from_missing_refs(self):
        no_items = build_thin_reduction_diagnostics(parsed={"chapters": [{"chapter_id": "ch_001"}]})
        with_items = build_thin_reduction_diagnostics(parsed={"chapters": [{"chapter_id": "ch_001", "objects": [{"canonical_name": "Llave", "source_refs": []}], "events": [{"canonical_name": "Apertura"}], "relations": []}]})
        self.assertTrue(no_items["no_item_reduction"])
        self.assertIn("valid_reduction_no_items", no_items["warnings"])
        self.assertFalse(with_items["no_item_reduction"])
        self.assertIn("valid_reduction_thin_sections", with_items["warnings"])

    def test_replan_simulation_and_policy_reports_parse(self):
        policy = build_natural_chunking_policy_report()
        calibration = build_natural_chunking_calibration_report(rows=[{"chapter_id": "ch_001", "model": "deepseek-v4-flash", "estimated_tokens": 2400, "natural_chunk_count": 1}])
        replan = build_natural_chunking_replan_simulation(rows=[{"chapter_id": "ch_001", "model": "deepseek-v4-flash", "estimated_tokens": 2400, "natural_chunk_count": 1, "effective_source_text_budget_tokens": 6000}])
        self.assertEqual(policy["assessment"], "natural_chunking_threshold_patch_ready_for_e2e")
        self.assertEqual(calibration["rows"][0]["old_natural_chunk_count"], 1)
        self.assertTrue(replan["would_produce_natural_multichunk"])


if __name__ == "__main__":
    unittest.main()
