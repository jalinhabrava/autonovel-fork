from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from textifai.bootstrap.source_reader import build_source_document_inventory
from textifai.bootstrap.language import detect_language_profile, sample_text_for_language_detection
from textifai.import_review.bootstrap_profile import build_bootstrap_profile
from textifai.import_review.entity_cleanup import cleanup_resolved_entities
from textifai.import_review.auxiliary_ingestion import (
    AuxiliaryDocumentInput,
    _build_auxiliary_document_record,
    _chunk_auxiliary_document,
    ingest_auxiliary_documents,
)
from textifai.import_review.entity_cluster_resolution import _coalesce_same_kind_entities, resolve_entity_clusters
from textifai.import_review.entity_reconciliation import reconcile_entities_for_vaerl, reconcile_primary_relationship_mentions
from textifai.import_review.primary_note_synthesis import synthesize_primary_note_summaries
from textifai.import_review.empirical_ranker import EmpiricalPolicy
from textifai.import_review.model_router import resolve_model_plan
from textifai.import_review.provider_snapshot import ProviderModelSnapshot, ProviderSnapshot, build_provider_snapshot
from textifai.import_review.model_registry import get_model_capabilities
from textifai.obsidian.json_import import import_json_to_vault
from textifai.obsidian.taxonomy import taxonomy_payload_for_entity, taxonomy_tags
from textifai.vaerl.invariants import evaluate_semantic_invariants, write_semantic_invariants_audit
from textifai.vaerl.review_queue import build_review_queue
from textifai.import_review.structured_bootstrap_v1 import (
    NovelBootstrapV1Config,
    _estimate_global_batch_complexity_penalty,
    _resolve_structured_model,
    _extract_title_entity_hints,
    _promote_recurring_chapter_entities,
    _promote_title_hint_entities,
    _stabilize_character_entities_with_title_hints,
    assemble_obsidian_import,
    _build_global_normalization_batches,
    build_ambiguous_entity_queue,
    build_canonical_entity_map,
    build_global_normalization_pass1,
    build_novel_index,
    build_selective_normalization_metrics,
    _append_pass1_trace_events,
    _append_selective_trace,
    _extract_title_parse_signals,
    _build_chapter_extraction_prompt,
    _build_global_normalization_prompt,
    _build_semantic_context_probe,
    _normalize_chapter_payload,
    _validate_explanatory_language_texts,
    _validate_explanatory_language_with_policy,
    _validate_global_normalization_language,
    _validate_chapter_extraction_payload,
    run_semantic_ingestion_replay,
    run_structured_bootstrap_v1,
)


class _StructuredBootstrapFakeProvider:
    def generate(self, request):
        if request.task == "bootstrap_global_normalization":
            return type(
                "_Response",
                (),
                {
                    "text": json.dumps(
                        {
                            "work": {
                                "title": "Test Novel",
                                "language": "es",
                                "normalization_notes": ["planner:test_global_pass_ok"],
                            },
                            "entities": [
                                {
                                    "canonical_name": "Sera",
                                    "canonical_candidate": "Sera",
                                    "entity_kind": "character",
                                    "preferred_slug": "sera",
                                    "aliases": ["Serelyne"],
                                    "summary": "Princesa con una magia inestable.",
                                    "key_facts": ["Huye del castillo."],
                                    "relationships": [],
                                    "chapter_refs": ["ch_001"],
                                    "source_mentions": ["Sera", "Serelyne"],
                                    "confidence": 0.95,
                                    "review_state": "canonical",
                                    "naming_quality": "proper_name",
                                    "is_stable_entity": True,
                                    "needs_review": False,
                                    "review_reason": "",
                                },
                                {
                                    "canonical_name": "Thiseia",
                                    "canonical_candidate": "Thiseia",
                                    "entity_kind": "place",
                                    "preferred_slug": "thiseia",
                                    "aliases": [],
                                    "summary": "Reino relevante para la historia.",
                                    "key_facts": ["Contiene el castillo real."],
                                    "relationships": [],
                                    "chapter_refs": ["ch_001", "ch_002"],
                                    "source_mentions": ["Thiseia"],
                                    "confidence": 0.91,
                                    "review_state": "canonical",
                                    "naming_quality": "proper_name",
                                    "is_stable_entity": True,
                                    "needs_review": False,
                                    "review_reason": "",
                                },
                            ],
                            "merge_plan": [
                                {
                                    "canonical_name": "Sera",
                                    "merged_surfaces": ["Sera", "Serelyne"],
                                    "reason": "same character",
                                    "confidence": 0.95,
                                }
                            ],
                        },
                        ensure_ascii=False,
                    )
                },
            )()
        chapter_id = "ch_001"
        if "CHAPTER_ID:" in request.messages[0].content:
            for line in request.messages[0].content.splitlines():
                if line.startswith("CHAPTER_ID:"):
                    chapter_id = line.split(":", 1)[1].strip()
                    break
        chapter_title = f"{chapter_id} title"
        sequence_index = 1 if chapter_id == "ch_001" else 2
        label_type = "other"
        label_number = None
        if "CHAPTER_TITLE:" in request.messages[0].content:
            for line in request.messages[0].content.splitlines():
                if line.startswith("CHAPTER_TITLE:"):
                    chapter_title = line.split(":", 1)[1].strip()
                    break
        if "Prólogo" in chapter_title:
            label_type = "prologue"
        elif "Interludio" in chapter_title:
            label_type = "interlude"
        elif "Episodio" in chapter_title:
            label_type = "episode"
            match = re.search(r"Episodio\s+(\d+)", chapter_title)
            label_number = int(match.group(1)) if match else None
        return type(
            "_Response",
            (),
            {
                "text": json.dumps(
                    {
                        "work": {"title": "Test Novel", "language": "es"},
                        "chapters": [
                            {
                                "chapter_id": chapter_id,
                                "chapter_title_original": chapter_title,
                                "chapter_title_canonical": chapter_title,
                                "sequence_index": sequence_index,
                                "chapter_label_type": label_type,
                                "chapter_number_in_label": label_number,
                                "title_parse_signals": _extract_title_parse_signals(chapter_title),
                                "chapter_summary": "Sera actúa en Thiseia.",
                                "chapter_text_markdown": "Sera viaja por Thiseia.",
                                "characters": [
                                    {
                                        "surface": "Sera",
                                        "canonical": "Sera",
                                        "canonical_candidate": "Sera",
                                        "naming_quality": "proper_name",
                                        "needs_review": False,
                                        "facts": ["Aparece activamente en el capítulo."],
                                        "confidence": 0.95,
                                    }
                                ],
                                "places": [
                                    {
                                        "surface": "Thiseia",
                                        "canonical": "Thiseia",
                                        "canonical_candidate": "Thiseia",
                                        "naming_quality": "proper_name",
                                        "needs_review": False,
                                        "facts": ["Es el marco del capítulo."],
                                        "confidence": 0.9,
                                    }
                                ],
                                "concepts": [],
                                "events": [],
                                "relations": [],
                                "unresolved_mentions": [],
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
            },
        )()


class _StructuredBootstrapChapterFailureProvider(_StructuredBootstrapFakeProvider):
    def generate(self, request):
        if request.task == "bootstrap_global_normalization":
            return super().generate(request)
        if "CHAPTER_ID: ch_002" in request.messages[0].content:
            return type("_Response", (), {"text": "not json"})()
        return super().generate(request)


class StructuredBootstrapV1Tests(unittest.TestCase):
    def _chapter_payload(
        self,
        *,
        title: str,
        sequence_index: int = 1,
        label_type: str | None = "episode",
        label_number: int | None = 1,
    ) -> dict:
        chapter = {
            "chapter_id": "ch_001",
            "chapter_title_original": title,
            "chapter_title_canonical": title,
            "sequence_index": sequence_index,
            "chapter_summary": "Resumen estable.",
            "characters": [],
            "places": [],
            "concepts": [],
            "events": [],
            "relations": [],
            "unresolved_mentions": [],
        }
        if label_type is not None:
            chapter["chapter_label_type"] = label_type
        chapter["chapter_number_in_label"] = label_number
        chapter["title_parse_signals"] = _extract_title_parse_signals(title)
        return {"work": {"title": "Test", "language": "es"}, "chapters": [chapter]}

    def test_extract_title_parse_signals_detects_explicit_number(self):
        signals = _extract_title_parse_signals("Episodio 16: Lo que Ren no pudo proteger")
        self.assertTrue(signals["has_explicit_number"])
        self.assertEqual(signals["explicit_number_value"], 16)

    def test_extract_title_parse_signals_handles_title_without_number(self):
        signals = _extract_title_parse_signals("Prólogo El Testigo")
        self.assertFalse(signals["has_explicit_number"])
        self.assertIsNone(signals["explicit_number_value"])

    def test_extract_title_parse_signals_splits_colon_prefix_and_suffix(self):
        signals = _extract_title_parse_signals("Episodio 16: Lo que Ren no pudo proteger")
        self.assertTrue(signals["has_colon"])
        self.assertFalse(signals["has_em_dash"])
        self.assertEqual(signals["primary_separator"], ":")
        self.assertEqual(signals["prefix_segment"], "Episodio 16")
        self.assertEqual(signals["suffix_segment"], "Lo que Ren no pudo proteger")

    def test_extract_title_parse_signals_splits_em_dash_prefix_and_suffix(self):
        signals = _extract_title_parse_signals("Capítulo 4 — La caída")
        self.assertFalse(signals["has_colon"])
        self.assertTrue(signals["has_em_dash"])
        self.assertEqual(signals["primary_separator"], "—")
        self.assertEqual(signals["prefix_segment"], "Capítulo 4")
        self.assertEqual(signals["suffix_segment"], "La caída")

    def test_extract_title_parse_signals_prefers_colon_over_em_dash(self):
        signals = _extract_title_parse_signals("Episodio 7: Ren — la noche del fuego")
        self.assertTrue(signals["has_colon"])
        self.assertTrue(signals["has_em_dash"])
        self.assertEqual(signals["primary_separator"], ":")
        self.assertEqual(signals["prefix_segment"], "Episodio 7")
        self.assertEqual(signals["suffix_segment"], "Ren — la noche del fuego")

    def test_normalize_chapter_payload_recomputes_missing_title_parse_signals(self):
        payload = self._chapter_payload(title="Episodio 14：Sera — Lo que se hereda", label_type="episode", label_number=14)
        del payload["chapters"][0]["title_parse_signals"]
        normalized = _normalize_chapter_payload(
            payload,
            chapter_id="ch_001",
            sequence_index=1,
            chapter_title="Episodio 14：Sera — Lo que se hereda",
            chapter_text="Texto.",
            work_title="Test",
            language="es",
        )
        valid, errors, _warnings = _validate_chapter_extraction_payload(
            normalized,
            chapter_id="ch_001",
            sequence_index=1,
            language="es",
        )
        self.assertTrue(valid, errors)
        self.assertIn("has_em_dash", normalized["chapters"][0]["title_parse_signals"])

    def test_normalize_chapter_payload_recomputes_incomplete_title_parse_signals(self):
        payload = self._chapter_payload(title="Capítulo 4 — La caída", label_type="episode", label_number=4)
        del payload["chapters"][0]["title_parse_signals"]["has_em_dash"]
        normalized = _normalize_chapter_payload(
            payload,
            chapter_id="ch_001",
            sequence_index=1,
            chapter_title="Capítulo 4 — La caída",
            chapter_text="Texto.",
            work_title="Test",
            language="es",
        )
        valid, errors, _warnings = _validate_chapter_extraction_payload(
            normalized,
            chapter_id="ch_001",
            sequence_index=1,
            language="es",
        )
        self.assertTrue(valid, errors)
        self.assertTrue(normalized["chapters"][0]["title_parse_signals"]["has_em_dash"])

    def test_normalize_chapter_payload_without_original_title_still_fails_validation(self):
        payload = self._chapter_payload(title="Episodio 1: Inicio", label_type="episode", label_number=1)
        payload["chapters"][0]["chapter_title_original"] = ""
        normalized = _normalize_chapter_payload(
            payload,
            chapter_id="ch_001",
            sequence_index=1,
            chapter_title="",
            chapter_text="Texto.",
            work_title="Test",
            language="es",
        )
        valid, errors, _warnings = _validate_chapter_extraction_payload(
            normalized,
            chapter_id="ch_001",
            sequence_index=1,
            language="es",
        )
        self.assertFalse(valid)
        self.assertTrue(any("chapter_title_original" in error for error in errors))

    def test_normalize_chapter_payload_keeps_complete_signals_for_prologue(self):
        normalized = _normalize_chapter_payload(
            self._chapter_payload(title="Prólogo El Testigo", label_type="prologue", label_number=None),
            chapter_id="ch_001",
            sequence_index=1,
            chapter_title="Prólogo El Testigo",
            chapter_text="Texto.",
            work_title="Test",
            language="es",
        )
        signals = normalized["chapters"][0]["title_parse_signals"]
        self.assertFalse(signals["has_colon"])
        self.assertFalse(signals["has_em_dash"])

    def test_normalize_chapter_payload_keeps_complete_signals_for_interlude(self):
        normalized = _normalize_chapter_payload(
            self._chapter_payload(title="Interludio: Ausencias que informan Parte 1", label_type="interlude", label_number=None),
            chapter_id="ch_001",
            sequence_index=1,
            chapter_title="Interludio: Ausencias que informan Parte 1",
            chapter_text="Texto.",
            work_title="Test",
            language="es",
        )
        signals = normalized["chapters"][0]["title_parse_signals"]
        self.assertTrue(signals["has_colon"])
        self.assertFalse(signals["has_em_dash"])

    def test_normalize_chapter_payload_keeps_complete_signals_for_epilogue(self):
        normalized = _normalize_chapter_payload(
            self._chapter_payload(title="Epílogo", label_type="epilogue", label_number=None),
            chapter_id="ch_001",
            sequence_index=1,
            chapter_title="Epílogo",
            chapter_text="Texto.",
            work_title="Test",
            language="es",
        )
        signals = normalized["chapters"][0]["title_parse_signals"]
        self.assertFalse(signals["has_colon"])
        self.assertFalse(signals["has_em_dash"])

    def test_extract_title_parse_signals_keeps_previous_no_separator_behavior(self):
        signals = _extract_title_parse_signals("Prólogo El Testigo vuelve")
        self.assertFalse(signals["has_colon"])
        self.assertFalse(signals["has_em_dash"])
        self.assertIsNone(signals["primary_separator"])
        self.assertEqual(signals["prefix_segment"], "Prólogo El Testigo")
        self.assertEqual(signals["suffix_segment"], "vuelve")

    def test_build_novel_index_is_deterministic_and_metadata_only(self):
        chapters = [
            SimpleNamespace(title="Episodio 1: Llegada", text="Sera llega a la ciudad."),
            SimpleNamespace(title="Interludio — Eco", text="Ren escucha un eco antiguo."),
        ]

        index = build_novel_index(
            work_title="Test Novel",
            language="es",
            chapters=chapters,
            source_path=Path("/tmp/source/novel.md"),
        )

        self.assertEqual(index["generation"]["method"], "deterministic_metadata_index")
        self.assertFalse(index["generation"]["llm_required"])
        self.assertEqual([chapter["chapter_id"] for chapter in index["chapters"]], ["ch_001", "ch_002"])
        self.assertEqual(index["chapters"][0]["chapter_label_type"], "episode")
        self.assertEqual(index["chapters"][0]["chapter_number_in_label"], 1)
        self.assertEqual(index["chapters"][1]["title_parse_signals"]["primary_separator"], "—")
        self.assertEqual(
            index["chapters"][0]["content_hash"],
            build_novel_index(
                work_title="Test Novel",
                language="es",
                chapters=chapters,
                source_path=Path("/tmp/source/novel.md"),
            )["chapters"][0]["content_hash"],
        )

    def test_global_normalization_pass1_selects_ambiguous_and_dense_chapters(self):
        chapters = [
            SimpleNamespace(title="Episodio 1: Llegada", text="a " * 100),
            SimpleNamespace(title="Episodio 1: Regreso", text="b " * 100),
            SimpleNamespace(title="Sin señal clara", text="c " * 9000),
            SimpleNamespace(title="Episodio 4: Cierre", text="d " * 100),
        ]
        novel_index = build_novel_index(
            work_title="Test Novel",
            language="es",
            chapters=chapters,
            source_path=Path("/tmp/source/novel.md"),
        )

        pass1 = build_global_normalization_pass1(
            novel_index=novel_index,
            config=NovelBootstrapV1Config(
                provider_name="lmstudio",
                model="qwen/qwen3.5-9b",
                selective_global_min_chapters=2,
                selective_global_max_chapters=3,
                selective_global_dense_token_threshold=200,
            ),
        )
        queue = build_ambiguous_entity_queue(pass1)

        self.assertIn("ch_003", pass1["selected_chapter_ids"])
        self.assertLessEqual(len(pass1["selected_chapter_ids"]), 3)
        self.assertTrue(pass1["ambiguous_clusters"])
        self.assertEqual(queue["ambiguous_clusters"], pass1["ambiguous_clusters"])

    def test_global_normalization_pass1_marks_high_narrative_value_late_chapters(self):
        chapters = [
            SimpleNamespace(title=f"Episodio {index}", text="x " * 300)
            for index in range(1, 21)
        ]
        novel_index = build_novel_index(
            work_title="Test Novel",
            language="es",
            chapters=chapters,
            source_path=Path("/tmp/source/novel.md"),
        )

        pass1 = build_global_normalization_pass1(
            novel_index=novel_index,
            config=NovelBootstrapV1Config(
                provider_name="lmstudio",
                model="qwen/qwen3.5-9b",
                selective_global_min_chapters=2,
                selective_global_max_chapters=10,
            ),
        )

        selected_rows = {
            row["chapter_id"]: row
            for row in pass1["chapter_selection"]
            if row["selected"]
        }
        self.assertIn("ch_018", selected_rows)
        self.assertIn("high_narrative_value", selected_rows["ch_018"]["reasons"])

    def test_selective_normalization_trace_jsonl_contains_planner_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "selective_normalization_trace.jsonl"
            pass1 = {
                "chapter_count": 2,
                "selected_chapter_ids": ["ch_001"],
                "rejected_chapter_ids": ["ch_002"],
                "ambiguous_clusters": [],
                "chapter_selection": [
                    {
                        "chapter_id": "ch_001",
                        "sequence_index": 1,
                        "selected": True,
                        "reasons": ["dense_named_entities"],
                        "token_count_estimate": 2000,
                    },
                    {
                        "chapter_id": "ch_002",
                        "sequence_index": 2,
                        "selected": False,
                        "reasons": ["not_selected_low_signal"],
                        "token_count_estimate": 100,
                    },
                ],
            }

            _append_selective_trace(
                trace_path,
                run_id="run-test",
                event_type="planner_started",
                reason="metadata_first_planning",
            )
            _append_pass1_trace_events(trace_path, run_id="run-test", pass1_payload=pass1)
            events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]

            self.assertEqual(events[0]["event_type"], "planner_started")
            self.assertIn("timestamp", events[0])
            self.assertIn("planner_selected_chapter", [event["event_type"] for event in events])
            self.assertIn("planner_rejected_chapter", [event["event_type"] for event in events])
            self.assertEqual(events[-1]["event_type"], "planner_finished")

    def test_selective_normalization_metrics_counts_trace_like_events_and_changes(self):
        novel_index = {"chapters": [{"chapter_id": "ch_001"}, {"chapter_id": "ch_002"}]}
        pass1 = {
            "selected_chapter_ids": ["ch_001", "ch_002"],
            "rejected_chapter_ids": [],
            "chapter_selection": [
                {"chapter_id": "ch_001", "selected": True, "reasons": ["dense_named_entities"]},
                {"chapter_id": "ch_002", "selected": True, "reasons": ["reused_explicit_number"]},
            ],
        }
        pass2 = {"expanded_chapter_ids": ["ch_001", "ch_002"]}
        global_payload = {
            "entities": [
                {
                    "canonical_name": "Sera",
                    "canonical_candidate": "Sera",
                    "aliases": ["Serelyne"],
                    "chapter_refs": ["ch_001"],
                    "needs_review": False,
                    "review_state": "canonical",
                }
            ],
            "merge_plan": [],
        }

        metrics = build_selective_normalization_metrics(
            run_status={"semantic_integrity": "complete"},
            novel_index=novel_index,
            pass1_payload=pass1,
            ambiguity_queue={"ambiguous_clusters": [{"cluster_id": "c1"}]},
            pass2_payload=pass2,
            global_payload=global_payload,
        )

        self.assertEqual(metrics["chapter_count_total"], 2)
        self.assertEqual(metrics["pass2_subcalls_started"], 2)
        self.assertEqual(metrics["pass2_subcalls_completed"], 2)
        self.assertEqual(metrics["pass2_subcalls_failed"], 0)
        self.assertEqual(metrics["selected_chapters_that_contributed_changes"], ["ch_001"])
        self.assertEqual(metrics["selected_chapters_with_no_observable_changes"], ["ch_002"])
        self.assertEqual(metrics["changed_candidate_entity_count"], 1)
        self.assertEqual(metrics["changed_alias_candidate_count"], 1)
        self.assertTrue(metrics["did_pass2_change_entity_candidates"])

    def test_selective_normalization_metrics_handles_no_selected_chapters(self):
        metrics = build_selective_normalization_metrics(
            run_status={},
            novel_index={"chapters": [{"chapter_id": "ch_001"}]},
            pass1_payload={"selected_chapter_ids": [], "rejected_chapter_ids": ["ch_001"], "chapter_selection": []},
            ambiguity_queue={"ambiguous_clusters": []},
            pass2_payload={"expanded_chapter_ids": []},
            global_payload={"entities": [], "merge_plan": []},
        )

        self.assertEqual(metrics["chapter_count_selected_for_pass2"], 0)
        self.assertEqual(metrics["pass2_subcalls_started"], 0)
        self.assertEqual(metrics["selected_chapters_that_contributed_changes"], [])
        self.assertFalse(metrics["did_pass2_change_global_normalization"])

    def test_selective_normalization_metrics_detects_selected_without_observable_changes(self):
        metrics = build_selective_normalization_metrics(
            run_status={},
            novel_index={"chapters": [{"chapter_id": "ch_001"}]},
            pass1_payload={
                "selected_chapter_ids": ["ch_001"],
                "rejected_chapter_ids": [],
                "chapter_selection": [{"chapter_id": "ch_001", "selected": True, "reasons": ["dense_named_entities"]}],
            },
            ambiguity_queue={"ambiguous_clusters": []},
            pass2_payload={"expanded_chapter_ids": ["ch_001"]},
            global_payload={"entities": [], "merge_plan": []},
        )

        self.assertEqual(metrics["pass2_subcalls_completed"], 1)
        self.assertEqual(metrics["selected_chapters_with_no_observable_changes"], ["ch_001"])
        self.assertEqual(metrics["changed_candidate_entity_count"], 0)
        self.assertFalse(metrics["did_pass2_change_entity_candidates"])

    def test_chapter_extraction_payload_accepts_prologue_label(self):
        payload = self._chapter_payload(title="Prólogo El Testigo", label_type="prologue", label_number=None)
        valid, errors, warnings = _validate_chapter_extraction_payload(
            payload,
            chapter_id="ch_001",
            sequence_index=1,
            language="es",
        )
        self.assertTrue(valid, errors)
        self.assertEqual(warnings, [])

    def test_chapter_extraction_payload_accepts_numbered_episode_label(self):
        payload = self._chapter_payload(title="Episodio 16: Lo que Ren no pudo proteger", label_type="episode", label_number=16)
        valid, errors, _warnings = _validate_chapter_extraction_payload(
            payload,
            chapter_id="ch_001",
            sequence_index=1,
            language="es",
        )
        self.assertTrue(valid, errors)

    def test_chapter_extraction_payload_accepts_interlude_without_secondary_part_number(self):
        payload = self._chapter_payload(title="Interludio: Ausencias que informan Parte 2", label_type="interlude", label_number=None)
        valid, errors, _warnings = _validate_chapter_extraction_payload(
            payload,
            chapter_id="ch_001",
            sequence_index=1,
            language="es",
        )
        self.assertTrue(valid, errors)

    def test_chapter_extraction_sequence_index_stays_physical_order(self):
        payload = self._chapter_payload(title="Episodio 16: Lo que Ren no pudo proteger", sequence_index=20, label_type="episode", label_number=16)
        valid, errors, _warnings = _validate_chapter_extraction_payload(
            payload,
            chapter_id="ch_001",
            sequence_index=20,
            language="es",
        )
        self.assertTrue(valid, errors)
        chapter = payload["chapters"][0]
        self.assertEqual(chapter["sequence_index"], 20)
        self.assertEqual(chapter["chapter_number_in_label"], 16)

    def test_chapter_extraction_validation_fails_without_label_type(self):
        payload = self._chapter_payload(title="Episodio 1: Inicio", label_type=None, label_number=1)
        valid, errors, _warnings = _validate_chapter_extraction_payload(
            payload,
            chapter_id="ch_001",
            sequence_index=1,
            language="es",
        )
        self.assertFalse(valid)
        self.assertTrue(any("chapter_label_type" in error for error in errors))

    def test_chapter_extraction_validation_fails_without_title_parse_signals(self):
        payload = self._chapter_payload(title="Episodio 1: Inicio", label_type="episode", label_number=1)
        del payload["chapters"][0]["title_parse_signals"]
        valid, errors, _warnings = _validate_chapter_extraction_payload(
            payload,
            chapter_id="ch_001",
            sequence_index=1,
            language="es",
        )
        self.assertFalse(valid)
        self.assertTrue(any("title_parse_signals" in error for error in errors))

    def test_chapter_extraction_validation_fails_for_non_integer_label_number(self):
        payload = self._chapter_payload(title="Episodio 1: Inicio", label_type="episode", label_number=None)
        payload["chapters"][0]["chapter_number_in_label"] = "1"
        valid, errors, _warnings = _validate_chapter_extraction_payload(
            payload,
            chapter_id="ch_001",
            sequence_index=1,
            language="es",
        )
        self.assertFalse(valid)
        self.assertTrue(any("chapter_number_in_label" in error for error in errors))

    def test_chapter_extraction_validation_rejects_invalid_title_parse_signal_types(self):
        payload = self._chapter_payload(title="Episodio 1: Inicio", label_type="episode", label_number=1)
        payload["chapters"][0]["title_parse_signals"]["has_explicit_number"] = "true"
        valid, errors, _warnings = _validate_chapter_extraction_payload(
            payload,
            chapter_id="ch_001",
            sequence_index=1,
            language="es",
        )
        self.assertFalse(valid)
        self.assertTrue(any("has_explicit_number" in error for error in errors))

    def test_chapter_extraction_validation_fails_without_new_title_separator_fields(self):
        payload = self._chapter_payload(title="Episodio 1: Inicio", label_type="episode", label_number=1)
        del payload["chapters"][0]["title_parse_signals"]["has_em_dash"]
        del payload["chapters"][0]["title_parse_signals"]["primary_separator"]
        valid, errors, _warnings = _validate_chapter_extraction_payload(
            payload,
            chapter_id="ch_001",
            sequence_index=1,
            language="es",
        )
        self.assertFalse(valid)
        self.assertTrue(any("has_em_dash" in error for error in errors))
        self.assertTrue(any("primary_separator" in error for error in errors))

    def test_chapter_extraction_validation_rejects_invalid_primary_separator(self):
        payload = self._chapter_payload(title="Episodio 1: Inicio", label_type="episode", label_number=1)
        payload["chapters"][0]["title_parse_signals"]["primary_separator"] = "-"
        valid, errors, _warnings = _validate_chapter_extraction_payload(
            payload,
            chapter_id="ch_001",
            sequence_index=1,
            language="es",
        )
        self.assertFalse(valid)
        self.assertTrue(any("primary_separator" in error for error in errors))

    def test_language_validation_detects_english_explanatory_prose_in_spanish_run(self):
        errors = _validate_explanatory_language_texts(
            texts=[
                "Ren attempts to protect the grandfather's small iron bell from a thief.",
                "The event changes Ren's understanding of their own abilities and the danger around them.",
            ],
            language="es",
            context="chapter_extraction",
        )
        self.assertTrue(errors)
        self.assertIn("chapter_extraction contains explanatory prose outside the configured language", errors[0])

    def test_language_validation_accepts_spanish_prose_with_proper_names(self):
        errors = _validate_explanatory_language_texts(
            texts=[
                "Sera abandona el castillo de Thiseia y escucha a Beld-san explicar el legado del Báculo.",
            ],
            language="es",
            context="global_normalization",
        )
        self.assertEqual(errors, [])

    def test_global_normalization_language_validation_rejects_english_summary_and_notes(self):
        errors = _validate_global_normalization_language(
            payload={
                "work": {
                    "title": "OnT",
                    "language": "es",
                    "normalization_notes": [
                        "Normalization based on chapters ch_001 and ch_002 only.",
                    ],
                },
                "entities": [
                    {
                        "canonical_name": "Sera",
                        "summary": "Sera confronts the reality of her estrangement from the castle.",
                        "key_facts": ["Sera abandona el castillo."],
                        "relationships": [],
                    }
                ],
            },
            language="es",
            validator_name="heuristic",
            validation_mode="strict",
        )
        self.assertTrue(errors[0])
        self.assertTrue(any("global_normalization" in error for error in errors[0]))

    def test_chapter_extraction_validation_rejects_english_chapter_summary(self):
        payload = self._chapter_payload(title="Episodio 1: Inicio", label_type="episode", label_number=1)
        payload["chapters"][0]["chapter_summary"] = "Sera confronts the reality of her estrangement from the castle."
        valid, errors, _warnings = _validate_chapter_extraction_payload(
            payload,
            chapter_id="ch_001",
            sequence_index=1,
            language="es",
        )
        self.assertFalse(valid)
        self.assertTrue(any("chapter_extraction" in error for error in errors))

    def test_global_normalization_prompt_uses_single_work_language_variable(self):
        prompt = _build_global_normalization_prompt(
            work_title="OnT",
            language="es",
            batch_index=1,
            batch=[{"sequence_index": 1, "title": "Prólogo", "text": "Texto."}],
            novel_index={"work": {"title": "OnT", "language": "es"}, "chapters": []},
            pass1_payload={"normalization_notes": []},
            ambiguity_queue={},
        )
        self.assertIn("WORK_LANGUAGE: es", prompt)
        self.assertIn("The working language for all generated prose fields is: WORK_LANGUAGE.", prompt)
        self.assertIn("Do not translate proper names or canonical names.", prompt)

    def test_chapter_extraction_prompt_preserves_names_and_uses_work_language(self):
        prompt = _build_chapter_extraction_prompt(
            work_title="OnT",
            language="es",
            chapter_id="ch_001",
            sequence_index=1,
            chapter_title="Episodio 1: Sera y Beld-san",
            chapter_text="Texto.",
            canonical_entity_map=[{"canonical_name": "Sera"}],
        )
        self.assertIn("WORK_LANGUAGE: es", prompt)
        self.assertIn("Do not translate chapter titles, character names, place names, faction names, object names, or canonical names.", prompt)

    def test_detect_language_profile_separates_english_and_spanish_prose(self):
        english = detect_language_profile("Sera confronts the reality of her estrangement from the castle and her uncertain identity.")
        spanish = detect_language_profile("Sera afronta la realidad de su alejamiento del castillo y la incertidumbre de su identidad.")
        self.assertEqual(english.dominant_language, "en")
        self.assertEqual(spanish.dominant_language, "es")

    def test_language_validation_fails_closed_in_strict_mode_without_validator(self):
        errors, warnings = _validate_explanatory_language_with_policy(
            texts=["Sera abandona el castillo y escucha a Beld-san."],
            language="es",
            context="global_normalization",
            validator_name="none",
            validation_mode="strict",
        )
        self.assertTrue(errors)
        self.assertEqual(warnings, [])

    def test_language_validation_warns_only_in_warn_mode_without_validator(self):
        errors, warnings = _validate_explanatory_language_with_policy(
            texts=["Sera abandona el castillo y escucha a Beld-san."],
            language="es",
            context="global_normalization",
            validator_name="none",
            validation_mode="warn",
        )
        self.assertEqual(errors, [])
        self.assertTrue(warnings)

    def test_resolve_entity_clusters_preserves_or_generates_preferred_slug(self):
        resolved, _, _ = resolve_entity_clusters(
            global_data={
                "entities": [
                    {
                        "canonical_name": "Adelman Leofrick",
                        "canonical_candidate": "Adelman Leofrick",
                        "entity_kind": "character",
                        "preferred_slug": "adelman_leofrick",
                        "aliases": [],
                        "summary": "Regente del reino.",
                        "key_facts": ["Gobierna tras la caída del reino."],
                        "relationships": [],
                        "chapter_refs": ["ch_001", "ch_003"],
                        "source_mentions": ["Adelman Leofrick"],
                        "confidence": 0.95,
                        "review_state": "canonical",
                        "naming_quality": "proper_name",
                        "is_stable_entity": True,
                        "needs_review": False,
                        "review_reason": "",
                    }
                ]
            },
            chapter_outputs=[],
        )
        self.assertEqual(resolved[0]["preferred_slug"], "adelman_leofrick")

    def test_build_provider_snapshot_uses_openai_models_api_when_available(self):
        fake_payload = {
            "data": [
                {"id": "gpt-4o-mini"},
                {"id": "gpt-4.1-mini"},
                {"id": "text-embedding-3-small"},
            ]
        }
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False), patch(
            "textifai.import_review.provider_snapshot.httpx.get"
        ) as mock_get:
            mock_get.return_value.json.return_value = fake_payload
            mock_get.return_value.raise_for_status.return_value = None
            snapshot = build_provider_snapshot(
                provider_name="openai",
                requested_model="auto",
                timeout_seconds=30,
            )
        self.assertEqual(snapshot.source, "openai_models_api")
        self.assertEqual(snapshot.available_models, ["gpt-4.1-mini", "gpt-4o-mini"])

    def test_resolve_model_plan_prefers_empirical_winner_within_guardrails(self):
        with tempfile.TemporaryDirectory() as tmp:
            telemetry_path = Path(tmp) / "telemetry.json"
            telemetry_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "records": [
                            {
                                "timestamp": "2026-04-21T10:00:00+00:00",
                                "provider_name": "openai",
                                "phase": "chapter_extraction",
                                "complexity_bucket": "small_clean",
                                "model": "gpt-4o-mini",
                                "success": True,
                                "json_valid": True,
                                "latency_seconds": 1.2,
                                "estimated_total_cost": 3000,
                                "subdivided": False,
                                "stalled": False,
                                "timed_out": False,
                            },
                            {
                                "timestamp": "2026-04-21T10:00:00+00:00",
                                "provider_name": "openai",
                                "phase": "chapter_extraction",
                                "complexity_bucket": "small_clean",
                                "model": "gpt-4o-mini",
                                "success": True,
                                "json_valid": True,
                                "latency_seconds": 1.0,
                                "estimated_total_cost": 2800,
                                "subdivided": False,
                                "stalled": False,
                                "timed_out": False,
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            profile = build_bootstrap_profile(
                work_title="Test",
                language="es",
                chapters=[
                    type("_Chapter", (), {"title": "Uno", "text": "Texto breve."})(),
                    type("_Chapter", (), {"title": "Dos", "text": "Texto breve."})(),
                ],
                estimate_tokens=lambda text: max(1, len(text) // 4),
            )
            snapshot = ProviderSnapshot(
                provider_name="openai",
                fetched_at="2026-04-22T10:00:00+00:00",
                source="test",
                available_models=["gpt-4o-mini", "gpt-4.1-mini"],
                models=[
                    ProviderModelSnapshot("gpt-4o-mini", True, get_model_capabilities("gpt-4o-mini")),
                    ProviderModelSnapshot("gpt-4.1-mini", True, get_model_capabilities("gpt-4.1-mini")),
                ],
            )
            plan, audit = resolve_model_plan(
                provider_name="openai",
                requested_model="auto",
                snapshot=snapshot,
                profile=profile,
                advisor=None,
                telemetry_path=telemetry_path,
                empirical_policy=EmpiricalPolicy(
                    min_samples_for_hard_preference=2,
                ),
            )
        self.assertEqual(plan.chapter_extraction_default_model, "gpt-4o-mini")
        self.assertIn("chapter_extraction.default_model", audit["empirical_evidence"])

    def test_resolve_model_plan_rejects_empirically_bad_global_normalization_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            telemetry_path = Path(tmp) / "telemetry.json"
            telemetry_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "records": [
                            {
                                "timestamp": "2026-04-21T10:00:00+00:00",
                                "provider_name": "openai",
                                "phase": "global_normalization",
                                "complexity_bucket": "large_or_complex",
                                "model": "gpt-4-turbo",
                                "success": False,
                                "json_valid": False,
                                "latency_seconds": 3.4,
                                "estimated_total_cost": 5000,
                                "subdivided": True,
                                "stalled": True,
                                "timed_out": False,
                            }
                            for _ in range(6)
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            profile = build_bootstrap_profile(
                work_title="Test",
                language="es",
                chapters=[type("_Chapter", (), {"title": "Uno", "text": "Texto breve."})()],
                estimate_tokens=lambda text: max(1, len(text) // 4),
            )
            snapshot = ProviderSnapshot(
                provider_name="openai",
                fetched_at="2026-04-22T10:00:00+00:00",
                source="test",
                available_models=["gpt-4-turbo", "gpt-4.1-mini", "gpt-4o-mini"],
                models=[
                    ProviderModelSnapshot("gpt-4-turbo", True, get_model_capabilities("gpt-4-turbo")),
                    ProviderModelSnapshot("gpt-4.1-mini", True, get_model_capabilities("gpt-4.1-mini")),
                    ProviderModelSnapshot("gpt-4o-mini", True, get_model_capabilities("gpt-4o-mini")),
                ],
            )
            advisor = type(
                "_Advisor",
                (),
                {
                    "model_used": "gpt-4o-mini",
                    "plan": {
                        "global_normalization": {"default_model": "gpt-4-turbo"},
                    },
                },
            )()
            plan, audit = resolve_model_plan(
                provider_name="openai",
                requested_model="auto",
                snapshot=snapshot,
                profile=profile,
                advisor=advisor,
                telemetry_path=telemetry_path,
                empirical_policy=EmpiricalPolicy(min_samples_for_hard_preference=8),
            )
        self.assertNotEqual(plan.global_normalization_default_model, "gpt-4-turbo")
        self.assertIn("global_normalization.default_model", audit["empirical_evidence"])

    def test_build_canonical_entity_map_reduces_global_payload(self):
        canonical_map = build_canonical_entity_map(
            {
                "entities": [
                    {
                        "canonical_name": "Sera",
                        "entity_kind": "character",
                        "entity_subkind": "protagonist",
                        "aliases": ["Serelyne"],
                        "summary": "Princesa",
                        "key_facts": ["Uno", "Dos", "Tres", "Cuatro", "Cinco"],
                        "review_state": "canonical",
                        "confidence": 0.9,
                        "canonical_candidate": "Sera",
                        "naming_quality": "proper_name",
                        "needs_review": False,
                    }
                ]
            }
        )
        self.assertEqual(canonical_map[0]["canonical_name"], "Sera")
        self.assertEqual(len(canonical_map[0]["key_facts"]), 4)
        self.assertEqual(canonical_map[0]["canonical_candidate"], "Sera")
        self.assertEqual(canonical_map[0]["naming_quality"], "proper_name")
        self.assertEqual(canonical_map[0]["entity_subkind"], "protagonist")

    def test_assemble_obsidian_import_enriches_chapter_refs(self):
        assembled = assemble_obsidian_import(
            global_data={
                "work": {"title": "Test", "language": "es"},
                "entities": [
                    {
                        "canonical_name": "Sera",
                        "canonical_candidate": "Sera",
                        "entity_kind": "character",
                        "summary": "Princesa",
                        "aliases": [],
                        "key_facts": [],
                        "relationships": [],
                        "chapter_refs": [],
                        "source_mentions": [],
                        "confidence": 0.9,
                        "review_state": "canonical",
                        "naming_quality": "proper_name",
                        "is_stable_entity": True,
                        "needs_review": False,
                        "review_reason": "",
                        "promotion_status": "promoted_canonical",
                        "note_role": "primary",
                    }
                ],
            },
            chapter_outputs=[
                {
                    "chapter_id": "ch_001",
                    "sequence_index": 1,
                    "characters": [{"surface": "Sera", "canonical": "Sera", "facts": [], "confidence": 0.9}],
                    "places": [],
                    "concepts": [],
                    "relations": [],
                }
            ],
        )
        self.assertEqual(assembled["entities"][0]["chapter_refs"], ["ch_001"])
        self.assertEqual(assembled["entities"][0]["source_mentions"], ["Sera"])

    def test_entity_cluster_resolution_prefers_proper_name_over_descriptor(self):
        resolved, clusters_audit, resolution_audit = resolve_entity_clusters(
            global_data={
                "entities": [
                    {
                        "canonical_name": "Mireia",
                        "canonical_candidate": "Mireia",
                        "entity_kind": "character",
                        "aliases": ["señora de las infusiones imposibles"],
                        "summary": "Madre de Nael.",
                        "key_facts": ["Es la madre de Nael.", "Mantiene una presencia doméstica persistente."],
                        "relationships": [{"target": "Nael", "type": "familial", "facts": ["Es su madre."]}],
                        "chapter_refs": ["ch_006", "ch_007"],
                        "source_mentions": ["Mireia", "señora de las infusiones imposibles"],
                        "confidence": 0.93,
                        "review_state": "canonical",
                        "naming_quality": "proper_name",
                        "is_stable_entity": True,
                        "needs_review": False,
                        "review_reason": "",
                    }
                ]
            },
            chapter_outputs=[
                {
                    "chapter_id": "ch_006",
                    "chapter_title_original": "Episodio 6: Las infusiones imposibles de Mireia",
                    "characters": [
                        {
                            "surface": "señora de las infusiones imposibles",
                            "canonical": "señora de las infusiones imposibles",
                            "canonical_candidate": "Mireia",
                            "naming_quality": "descriptor",
                            "needs_review": True,
                            "facts": ["Cuida de Nael en un contexto doméstico."],
                            "confidence": 0.88,
                        }
                    ],
                    "places": [],
                    "concepts": [],
                    "events": [],
                    "relations": [],
                    "unresolved_mentions": [],
                }
            ],
        )
        self.assertEqual(resolved[0]["canonical_name"], "Mireia")
        self.assertIn("señora de las infusiones imposibles", resolved[0]["aliases"])
        self.assertEqual(clusters_audit["cluster_count"], 1)
        self.assertEqual(resolution_audit["resolved_entity_count"], 1)

    def test_entity_cluster_resolution_prefers_global_canonical_name_over_descriptor_alias(self):
        resolved, clusters_audit, _ = resolve_entity_clusters(
            global_data={
                "work": {"title": "Test", "language": "es"},
                "entities": [
                    {
                        "canonical_name": "Sera",
                        "canonical_candidate": "Sera",
                        "entity_kind": "character",
                        "preferred_slug": "sera",
                        "aliases": ["la princesa", "heredera"],
                        "summary": "Sera es una heredera con magia inestable.",
                        "key_facts": ["Es heredera.", "Su magia es inestable."],
                        "relationships": [],
                        "chapter_refs": ["ch_001", "ch_002", "ch_003"],
                        "source_mentions": ["Sera", "la princesa"],
                        "confidence": 0.94,
                        "review_state": "canonical",
                        "naming_quality": "proper_name",
                        "is_stable_entity": True,
                        "needs_review": False,
                        "review_reason": "",
                    }
                ],
            },
            chapter_outputs=[
                {
                    "chapter_id": "ch_004",
                    "characters": [
                        {
                            "surface": "la princesa",
                            "canonical": "la princesa",
                            "canonical_candidate": "la princesa",
                            "naming_quality": "proper_name",
                            "facts": ["La reconocen como heredera."],
                            "confidence": 0.91,
                        }
                    ],
                    "places": [],
                    "concepts": [],
                    "events": [],
                    "relations": [],
                }
            ],
            language="es",
        )
        self.assertEqual(clusters_audit["cluster_count"], 1)
        self.assertEqual(resolved[0]["canonical_name"], "Sera")
        self.assertEqual(resolved[0]["preferred_slug"], "sera")
        self.assertIn("la princesa", resolved[0]["aliases"])

    def test_entity_cluster_resolution_uses_appositive_alias_as_identity_bridge(self):
        resolved, clusters_audit, _ = resolve_entity_clusters(
            global_data={
                "work": {"title": "Test", "language": "es"},
                "entities": [
                    {
                        "canonical_name": "Beld-san",
                        "canonical_candidate": "Beld-san",
                        "entity_kind": "character",
                        "preferred_slug": "beld_san",
                        "aliases": ["El abuelo —Beld-san—"],
                        "summary": "Beld-san protege a Ren.",
                        "key_facts": ["Protege a Ren.", "Porta una campana."],
                        "relationships": [],
                        "chapter_refs": ["ch_018"],
                        "source_mentions": ["Beld-san", "El abuelo —Beld-san—"],
                        "confidence": 0.95,
                        "review_state": "canonical",
                        "naming_quality": "title_plus_name",
                        "is_stable_entity": True,
                        "needs_review": False,
                        "review_reason": "",
                    }
                ],
            },
            chapter_outputs=[
                {
                    "chapter_id": "ch_004",
                    "characters": [
                        {
                            "surface": "El abuelo",
                            "canonical": "El abuelo",
                            "canonical_candidate": "El abuelo",
                            "naming_quality": "descriptor",
                            "facts": ["Cuida a Ren.", "Posee una campana."],
                            "confidence": 0.9,
                        }
                    ],
                    "places": [],
                    "concepts": [],
                    "events": [],
                    "relations": [],
                }
            ],
            language="es",
        )
        self.assertEqual(clusters_audit["cluster_count"], 1)
        self.assertEqual(resolved[0]["canonical_name"], "Beld-san")
        self.assertEqual(resolved[0]["preferred_slug"], "beld_san")
        self.assertIn("El abuelo", resolved[0]["aliases"])

    def test_entity_cluster_resolution_does_not_bridge_negated_appositive_alias(self):
        resolved, clusters_audit, _ = resolve_entity_clusters(
            global_data={
                "work": {"title": "Test", "language": "es"},
                "entities": [
                    {
                        "canonical_name": "Beld-san",
                        "canonical_candidate": "Beld-san",
                        "entity_kind": "character",
                        "preferred_slug": "beld_san",
                        "aliases": ["El abuelo —no el abuelo—"],
                        "summary": "Beld-san protege a Sera.",
                        "key_facts": ["Protege a Sera.", "Porta una campana."],
                        "relationships": [],
                        "chapter_refs": ["ch_018"],
                        "source_mentions": ["Beld-san"],
                        "confidence": 0.95,
                        "review_state": "canonical",
                        "naming_quality": "title_plus_name",
                        "is_stable_entity": True,
                        "needs_review": False,
                        "review_reason": "",
                    }
                ],
            },
            chapter_outputs=[
                {
                    "chapter_id": "ch_004",
                    "characters": [
                        {
                            "surface": "El abuelo",
                            "canonical": "El abuelo",
                            "canonical_candidate": "El abuelo",
                            "naming_quality": "descriptor",
                            "facts": ["Cuida a Ren."],
                            "confidence": 0.9,
                        }
                    ],
                    "places": [],
                    "concepts": [],
                    "events": [],
                    "relations": [],
                }
            ],
            language="es",
        )
        self.assertEqual(clusters_audit["cluster_count"], 2)
        self.assertEqual({item["canonical_name"] for item in resolved}, {"Beld-san", "El abuelo"})

    def test_entity_cluster_resolution_does_not_use_pronoun_like_surface_as_identity_bridge(self):
        resolved, clusters_audit, _ = resolve_entity_clusters(
            global_data={
                "work": {"title": "Test", "language": "es"},
                "entities": [
                    {
                        "canonical_name": "El narrador",
                        "canonical_candidate": "El narrador",
                        "entity_kind": "character",
                        "preferred_slug": "narrador",
                        "aliases": ["yo"],
                        "summary": "Narrador local.",
                        "key_facts": ["Protege a su abuelo."],
                        "relationships": [],
                        "chapter_refs": ["ch_010"],
                        "source_mentions": ["yo"],
                        "confidence": 0.9,
                        "review_state": "canonical",
                        "naming_quality": "pronoun_like",
                        "is_stable_entity": True,
                        "needs_review": False,
                        "review_reason": "",
                    },
                    {
                        "canonical_name": "Sera",
                        "canonical_candidate": "Sera",
                        "entity_kind": "character",
                        "preferred_slug": "sera",
                        "aliases": ["la princesa"],
                        "summary": "Sera es heredera.",
                        "key_facts": ["Es heredera."],
                        "relationships": [],
                        "chapter_refs": ["ch_001"],
                        "source_mentions": ["Sera"],
                        "confidence": 0.95,
                        "review_state": "canonical",
                        "naming_quality": "proper_name",
                        "is_stable_entity": True,
                        "needs_review": False,
                        "review_reason": "",
                    },
                ],
            },
            chapter_outputs=[
                {
                    "chapter_id": "ch_011",
                    "characters": [
                        {
                            "surface": "yo",
                            "canonical": "Sera",
                            "canonical_candidate": "Sera",
                            "naming_quality": "pronoun_like",
                            "facts": ["Despierta sin magia."],
                            "confidence": 0.9,
                        }
                    ],
                    "places": [],
                    "concepts": [],
                    "events": [],
                    "relations": [],
                }
            ],
            language="es",
        )
        self.assertEqual(clusters_audit["cluster_count"], 2)
        by_name = {item["canonical_name"]: item for item in resolved}
        self.assertEqual(set(by_name), {"El narrador", "Sera"})
        self.assertIn("Despierta sin magia.", by_name["Sera"]["key_facts"])
        self.assertNotIn("Protege a su abuelo.", by_name["Sera"]["key_facts"])

    def test_entity_cluster_resolution_uses_unique_title_name_to_bridge_pronoun_like_character(self):
        resolved, clusters_audit, _ = resolve_entity_clusters(
            global_data={
                "work": {"title": "Test", "language": "es"},
                "entities": [
                    {
                        "canonical_name": "Ren",
                        "canonical_candidate": "Ren",
                        "entity_kind": "character",
                        "preferred_slug": "ren",
                        "aliases": [],
                        "summary": "",
                        "key_facts": ["Participa en una ceremonia."],
                        "relationships": [],
                        "chapter_refs": ["ch_001"],
                        "source_mentions": ["Ren"],
                        "confidence": 0.9,
                        "review_state": "canonical",
                        "naming_quality": "proper_name",
                        "is_stable_entity": True,
                        "needs_review": False,
                        "review_reason": "",
                    }
                ],
            },
            chapter_outputs=[
                {
                    "chapter_id": "ch_002",
                    "chapter_title_original": "Episodio 6: El bosque silencioso de Ren",
                    "characters": [
                        {
                            "surface": "El narrador",
                            "canonical": "El narrador",
                            "canonical_candidate": "El narrador",
                            "naming_quality": "pronoun_like",
                            "facts": ["Es nieto del abuelo."],
                            "confidence": 0.9,
                        }
                    ],
                    "places": [],
                    "concepts": [],
                    "events": [],
                    "relations": [],
                }
            ],
            language="es",
        )
        self.assertEqual(clusters_audit["cluster_count"], 1)
        self.assertEqual(resolved[0]["canonical_name"], "Ren")
        self.assertIn("Es nieto del abuelo.", resolved[0]["key_facts"])
        self.assertIn("El narrador", resolved[0]["rejected_aliases"])

    def test_entity_cluster_resolution_does_not_bridge_pronoun_like_when_title_has_multiple_names(self):
        resolved, clusters_audit, _ = resolve_entity_clusters(
            global_data={
                "work": {"title": "Test", "language": "es"},
                "entities": [
                    {
                        "canonical_name": "Ren",
                        "canonical_candidate": "Ren",
                        "entity_kind": "character",
                        "preferred_slug": "ren",
                        "aliases": [],
                        "summary": "",
                        "key_facts": ["Aparece en la historia."],
                        "relationships": [],
                        "chapter_refs": ["ch_001"],
                        "source_mentions": ["Ren"],
                        "confidence": 0.9,
                        "review_state": "canonical",
                        "naming_quality": "proper_name",
                        "is_stable_entity": True,
                        "needs_review": False,
                        "review_reason": "",
                    },
                    {
                        "canonical_name": "Sera",
                        "canonical_candidate": "Sera",
                        "entity_kind": "character",
                        "preferred_slug": "sera",
                        "aliases": [],
                        "summary": "",
                        "key_facts": ["Aparece en la historia."],
                        "relationships": [],
                        "chapter_refs": ["ch_001"],
                        "source_mentions": ["Sera"],
                        "confidence": 0.9,
                        "review_state": "canonical",
                        "naming_quality": "proper_name",
                        "is_stable_entity": True,
                        "needs_review": False,
                        "review_reason": "",
                    },
                ],
            },
            chapter_outputs=[
                {
                    "chapter_id": "ch_002",
                    "chapter_title_original": "Episodio 6: Ren y Sera",
                    "characters": [
                        {
                            "surface": "El narrador",
                            "canonical": "El narrador",
                            "canonical_candidate": "El narrador",
                            "naming_quality": "pronoun_like",
                            "facts": ["Observa la escena."],
                            "confidence": 0.9,
                        }
                    ],
                    "places": [],
                    "concepts": [],
                    "events": [],
                    "relations": [],
                }
            ],
            language="es",
        )
        self.assertEqual(clusters_audit["cluster_count"], 3)
        self.assertEqual({item["canonical_name"] for item in resolved}, {"El narrador", "Ren", "Sera"})

    def test_semantic_context_probe_flags_rejected_alias_source_mention_and_merge_candidate(self):
        audit, trace = _build_semantic_context_probe(
            cleaned_entities=[
                {
                    "canonical_name": "Ren",
                    "entity_kind": "character",
                    "preferred_slug": "ren",
                    "review_state": "canonical",
                    "note_role": "primary",
                    "aliases": [],
                    "rejected_aliases": ["El narrador"],
                    "source_mentions": ["Ren", "El narrador"],
                    "chapter_refs": ["ch_001"],
                    "key_facts": ["Protege una campanilla."],
                    "relationships": [],
                    "naming_quality": "proper_name",
                },
                {
                    "canonical_name": "El narrador",
                    "entity_kind": "character",
                    "preferred_slug": "narrador",
                    "review_state": "review",
                    "note_role": "review",
                    "aliases": ["yo"],
                    "source_mentions": ["yo", "narrador"],
                    "chapter_refs": ["ch_001", "ch_002"],
                    "key_facts": ["Es nieto del abuelo."],
                    "relationships": [],
                    "naming_quality": "pronoun_like",
                },
            ],
            chapter_outputs=[
                {"chapter_id": "ch_001", "chapter_title_original": "Episodio 1: Ren", "characters": []},
                {"chapter_id": "ch_002", "chapter_title_original": "Episodio 2: El camino de Ren", "characters": []},
            ],
            run_status={"semantic_integrity": "complete"},
        )
        self.assertEqual(audit["schema_version"], "textifai.semantic_context_probe.v1")
        self.assertEqual(audit["contamination_signal_count"], 1)
        self.assertEqual(audit["merge_candidate_count"], 1)
        self.assertEqual(audit["merge_candidates"][0]["candidate_primary"], "Ren")
        self.assertTrue(any(event["event_type"] == "semantic_probe_merge_candidate" for event in trace))

    def test_semantic_ingestion_replay_writes_downstream_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_system = root / "fixture" / "99_System"
            output_root = root / "replay"
            chapter_outputs = input_system / "chapter_outputs"
            chapter_outputs.mkdir(parents=True)
            global_payload = {
                "work": {"title": "Test", "language": "es"},
                "entities": [
                    {
                        "canonical_name": "Sera",
                        "canonical_candidate": "Sera",
                        "entity_kind": "character",
                        "preferred_slug": "sera",
                        "aliases": ["la princesa"],
                        "summary": "Sera es una heredera con magia inestable.",
                        "key_facts": ["Es heredera.", "Su magia es inestable."],
                        "relationships": [],
                        "chapter_refs": ["ch_001", "ch_002"],
                        "source_mentions": ["Sera"],
                        "confidence": 0.95,
                        "review_state": "canonical",
                        "naming_quality": "proper_name",
                        "is_stable_entity": True,
                        "needs_review": False,
                        "review_reason": "",
                    }
                ],
            }
            (input_system / "global_normalization.json").write_text(json.dumps(global_payload), encoding="utf-8")
            (input_system / "chapter_extraction_audit.json").write_text(
                json.dumps(
                    {
                        "run_status": {
                            "semantic_integrity": "complete",
                            "chapter_extraction_complete": True,
                            "expected_chapter_count": 1,
                            "generated_chapter_count": 1,
                            "failed_chapter_count": 0,
                        }
                    }
                ),
                encoding="utf-8",
            )
            (chapter_outputs / "ch_001.json").write_text(
                json.dumps(
                    {
                        "chapters": [
                            {
                                "chapter_id": "ch_001",
                                "sequence_index": 1,
                                "chapter_title_original": "Episodio 1: Sera",
                                "characters": [
                                    {
                                        "surface": "la princesa",
                                        "canonical": "Sera",
                                        "canonical_candidate": "Sera",
                                        "naming_quality": "proper_name",
                                        "facts": ["Sera huye del castillo."],
                                        "confidence": 0.92,
                                    }
                                ],
                                "places": [],
                                "concepts": [],
                                "events": [],
                                "relations": [],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            result = run_semantic_ingestion_replay(
                input_system_root=input_system,
                output_root=output_root,
                language="es",
            )
            self.assertTrue(Path(result.resolved_entities_path).exists())
            self.assertTrue(Path(result.cleaned_entities_path).exists())
            self.assertTrue(Path(result.obsidian_import_path).exists())
            self.assertTrue(Path(result.semantic_context_probe_audit_path).exists())
            self.assertTrue(Path(result.semantic_context_probe_trace_path).exists())
            self.assertTrue(Path(result.run_limits_audit_path).exists())
            self.assertTrue(Path(result.run_comparability_manifest_path).exists())
            cleaned = json.loads(Path(result.cleaned_entities_path).read_text(encoding="utf-8"))
            self.assertEqual(cleaned[0]["canonical_name"], "Sera")
            probe = json.loads(Path(result.semantic_context_probe_audit_path).read_text(encoding="utf-8"))
            self.assertEqual(probe["schema_version"], "textifai.semantic_context_probe.v1")
            comparability = json.loads(Path(result.run_comparability_manifest_path).read_text(encoding="utf-8"))
            self.assertEqual(comparability["pipeline_mode"], "downstream_replay")

    def test_entity_cluster_resolution_demotes_cross_kind_conflict_against_character(self):
        resolved, _, _ = resolve_entity_clusters(
            global_data={
                "entities": [
                    {
                        "canonical_name": "Sera",
                        "canonical_candidate": "Sera",
                        "entity_kind": "character",
                        "aliases": ["la princesa"],
                        "summary": "Protagonista.",
                        "key_facts": ["Huye del castillo.", "Su magia es anómala."],
                        "relationships": [],
                        "chapter_refs": ["ch_001", "ch_002"],
                        "source_mentions": ["Sera", "la princesa"],
                        "confidence": 0.95,
                        "review_state": "canonical",
                        "naming_quality": "proper_name",
                        "is_stable_entity": True,
                        "needs_review": False,
                        "review_reason": "",
                    },
                    {
                        "canonical_name": "Sera",
                        "canonical_candidate": "Sera",
                        "entity_kind": "concept",
                        "aliases": ["magia rota"],
                        "summary": "Tema de su herencia.",
                        "key_facts": ["Idea abstracta."],
                        "relationships": [],
                        "chapter_refs": ["ch_001"],
                        "source_mentions": ["Sera"],
                        "confidence": 0.82,
                        "review_state": "canonical",
                        "naming_quality": "proper_name",
                        "is_stable_entity": True,
                        "needs_review": False,
                        "review_reason": "",
                    },
                ]
            },
            chapter_outputs=[],
            language="es",
        )
        character = next(item for item in resolved if item["entity_kind"] == "character")
        concept = next(item for item in resolved if item["entity_kind"] == "concept")
        self.assertEqual(character["canonical_name"], "Sera")
        self.assertTrue(concept["needs_review"])
        self.assertEqual(concept["review_reason_code"], "type_conflict_stronger_identity")
        self.assertEqual(concept["review_reason_params"]["stronger_identity"], "Sera")
        self.assertIn("Conflicto de tipo", concept["review_reason"])

    def test_gender_signal_prefers_clear_local_masculine_evidence(self):
        resolved, _, _ = resolve_entity_clusters(
            global_data={
                "entities": [
                    {
                        "canonical_name": "Nael",
                        "canonical_candidate": "Nael",
                        "entity_kind": "character",
                        "aliases": [],
                        "summary": "Personaje importante.",
                        "key_facts": ["Aparece en varios capítulos."],
                        "relationships": [],
                        "chapter_refs": ["ch_001"],
                        "source_mentions": ["Nael"],
                        "confidence": 0.9,
                        "review_state": "canonical",
                        "naming_quality": "proper_name",
                        "is_stable_entity": True,
                        "needs_review": False,
                        "review_reason": "",
                    }
                ]
            },
            chapter_outputs=[
                {
                    "chapter_id": "ch_003",
                    "characters": [
                        {
                            "surface": "el abuelo de Nael",
                            "canonical": "Nael",
                            "canonical_candidate": "Nael",
                            "naming_quality": "descriptor",
                            "gender_presentation_signal": "masculine",
                            "gender_signal_confidence": 0.9,
                            "facts": ["Se le trata como muchacho en el pueblo."],
                            "confidence": 0.92,
                        }
                    ],
                    "places": [],
                    "concepts": [],
                    "events": [],
                    "relations": [],
                    "unresolved_mentions": [],
                }
            ],
            language="es",
        )
        nael = resolved[0]
        self.assertEqual(nael["gender_presentation_signal"], "masculine")
        self.assertGreaterEqual(nael["gender_signal_confidence"], 0.7)
        self.assertEqual(nael["gender_signal_evidence"][0]["kind"], "local_descriptor")

    def test_gender_signal_prefers_clear_local_feminine_evidence(self):
        resolved, _, _ = resolve_entity_clusters(
            global_data={"entities": []},
            chapter_outputs=[
                {
                    "chapter_id": "ch_002",
                    "characters": [
                        {
                            "surface": "la princesa",
                            "canonical": "Sera",
                            "canonical_candidate": "Sera",
                            "naming_quality": "descriptor",
                            "gender_presentation_signal": "feminine",
                            "gender_signal_confidence": 0.9,
                            "facts": ["La heredera huye del castillo."],
                            "confidence": 0.95,
                        }
                    ],
                    "places": [],
                    "concepts": [],
                    "events": [],
                    "relations": [],
                    "unresolved_mentions": [],
                }
            ],
        )
        sera = resolved[0]
        self.assertEqual(sera["gender_presentation_signal"], "feminine")
        self.assertGreaterEqual(sera["gender_signal_confidence"], 0.7)
        self.assertEqual(sera["gender_signal_evidence"][0]["chapter_id"], "ch_002")

    def test_gender_signal_conflict_downgrades_to_mixed(self):
        resolved, _, _ = resolve_entity_clusters(
            global_data={"entities": []},
            chapter_outputs=[
                {
                    "chapter_id": "ch_004",
                    "characters": [
                        {
                            "surface": "el protagonista",
                            "canonical": "Ren",
                            "canonical_candidate": "Ren",
                            "naming_quality": "descriptor",
                            "gender_presentation_signal": "masculine",
                            "gender_signal_confidence": 0.9,
                            "facts": ["Recibe el peso del ritual."],
                            "confidence": 0.9,
                        }
                    ],
                    "places": [],
                    "concepts": [],
                    "events": [],
                    "relations": [],
                    "unresolved_mentions": [],
                },
                {
                    "chapter_id": "ch_008",
                    "characters": [
                        {
                            "surface": "la protagonista",
                            "canonical": "Ren",
                            "canonical_candidate": "Ren",
                            "naming_quality": "descriptor",
                            "gender_presentation_signal": "feminine",
                            "gender_signal_confidence": 0.9,
                            "facts": ["Sufre un conflicto persistente."],
                            "confidence": 0.9,
                        }
                    ],
                    "places": [],
                    "concepts": [],
                    "events": [],
                    "relations": [],
                    "unresolved_mentions": [],
                },
            ],
        )
        ren = resolved[0]
        self.assertEqual(ren["gender_presentation_signal"], "mixed")
        self.assertLessEqual(ren["gender_signal_confidence"], 0.45)
        self.assertTrue(ren["gender_signal_conflict"])

    def test_gender_signal_global_alias_contamination_does_not_dominate_local_signal(self):
        resolved, _, _ = resolve_entity_clusters(
            global_data={
                "entities": [
                    {
                        "canonical_name": "Ren",
                        "canonical_candidate": "Ren",
                        "entity_kind": "character",
                        "aliases": ["la chica", "princesa"],
                        "summary": "Entidad ya contaminada globalmente.",
                        "key_facts": ["Tiene aliases dudosos."],
                        "relationships": [],
                        "chapter_refs": ["ch_001", "ch_002"],
                        "source_mentions": ["Ren"],
                        "confidence": 0.9,
                        "review_state": "review",
                        "naming_quality": "proper_name",
                        "is_stable_entity": True,
                        "needs_review": True,
                        "review_reason": "Alias contamination",
                        "gender_presentation_signal": "feminine",
                        "gender_signal_confidence": 0.9,
                    }
                ]
            },
            chapter_outputs=[
                {
                    "chapter_id": "ch_004",
                    "characters": [
                        {
                            "surface": "el protagonista",
                            "canonical": "Ren",
                            "canonical_candidate": "Ren",
                            "naming_quality": "descriptor",
                            "gender_presentation_signal": "masculine",
                            "gender_signal_confidence": 0.9,
                            "facts": ["Participa en el ritual."],
                            "confidence": 0.92,
                        }
                    ],
                    "places": [],
                    "concepts": [],
                    "events": [],
                    "relations": [],
                    "unresolved_mentions": [],
                }
            ],
            language="es",
        )
        ren = resolved[0]
        self.assertNotEqual(ren["gender_presentation_signal"], "feminine")
        self.assertEqual(ren["gender_signal_evidence"][0]["kind"], "local_descriptor")

    def test_gender_signal_without_explicit_gender_confidence_stays_unknown(self):
        resolved, _, _ = resolve_entity_clusters(
            global_data={"entities": []},
            chapter_outputs=[
                {
                    "chapter_id": "ch_008",
                    "characters": [
                        {
                            "surface": "una chica",
                            "canonical": "Ren",
                            "canonical_candidate": "Ren",
                            "naming_quality": "proper_name",
                            "gender_presentation_signal": "feminine",
                            "gender_signal_confidence": 0.0,
                            "facts": ["Su identidad es desconocida para el narrador."],
                            "confidence": 0.95,
                        },
                        {
                            "surface": "Ren",
                            "canonical": "Ren",
                            "canonical_candidate": "Ren",
                            "naming_quality": "proper_name",
                            "gender_presentation_signal": "feminine",
                            "gender_signal_confidence": 0.0,
                            "facts": ["Intenta usar magia pero no puede."],
                            "confidence": 0.9,
                        },
                    ],
                    "places": [],
                    "concepts": [],
                    "events": [],
                    "relations": [],
                    "unresolved_mentions": [],
                }
            ],
            language="es",
        )
        ren = resolved[0]
        self.assertEqual(ren["gender_presentation_signal"], "unknown")
        self.assertEqual(ren["gender_signal_confidence"], 0.0)
        self.assertTrue(ren["gender_signal_downgraded"])

    def test_gender_signal_only_penalizes_confident_conflicting_descriptor_merge(self):
        blocked = _coalesce_same_kind_entities(
            [
                {
                    "canonical_name": "guardiana",
                    "entity_kind": "character",
                    "aliases": ["protagonista"],
                    "source_mentions": ["guardiana"],
                    "chapter_refs": ["ch_001"],
                    "relationships": [],
                    "naming_quality": "descriptor",
                    "confidence": 0.8,
                    "gender_presentation_signal": "feminine",
                    "gender_signal_confidence": 0.9,
                },
                {
                    "canonical_name": "guía",
                    "entity_kind": "character",
                    "aliases": ["protagonista"],
                    "source_mentions": ["guía"],
                    "chapter_refs": ["ch_001"],
                    "relationships": [],
                    "naming_quality": "descriptor",
                    "confidence": 0.8,
                    "gender_presentation_signal": "masculine",
                    "gender_signal_confidence": 0.9,
                },
            ]
        )
        self.assertEqual(len(blocked), 2)

        permissive = _coalesce_same_kind_entities(
            [
                {
                    "canonical_name": "guardiana",
                    "entity_kind": "character",
                    "aliases": ["protagonista"],
                    "source_mentions": ["guardiana"],
                    "chapter_refs": ["ch_001"],
                    "relationships": [],
                    "naming_quality": "descriptor",
                    "confidence": 0.8,
                    "gender_presentation_signal": "feminine",
                    "gender_signal_confidence": 0.2,
                },
                {
                    "canonical_name": "guía",
                    "entity_kind": "character",
                    "aliases": ["protagonista"],
                    "source_mentions": ["guía"],
                    "chapter_refs": ["ch_001"],
                    "relationships": [],
                    "naming_quality": "descriptor",
                    "confidence": 0.8,
                    "gender_presentation_signal": "masculine",
                    "gender_signal_confidence": 0.2,
                },
            ]
        )
        self.assertEqual(len(permissive), 1)

    def test_assemble_obsidian_import_preserves_localized_review_reason_and_code(self):
        payload = assemble_obsidian_import(
            global_data={
                "work": {"title": "Test", "language": "es"},
                "entities": [
                    {
                        "canonical_name": "Báculo",
                        "entity_kind": "concept",
                        "summary": "Rol estructural.",
                        "aliases": [],
                        "key_facts": ["Mantiene el equilibrio."],
                        "relationships": [],
                        "chapter_refs": ["ch_001"],
                        "source_mentions": ["Báculo"],
                        "confidence": 0.7,
                        "review_state": "review",
                        "needs_review": True,
                        "review_reason_code": "type_conflict_stronger_identity",
                        "review_reason_params": {"stronger_identity": "Báculo"},
                        "review_reason": "Conflicto de tipo con una identidad más fuerte: Báculo.",
                    }
                ],
            },
            chapter_outputs=[],
        )
        entity = payload["entities"][0]
        self.assertEqual(entity["review_reason_code"], "type_conflict_stronger_identity")
        self.assertEqual(entity["review_reason_params"]["stronger_identity"], "Báculo")
        self.assertEqual(entity["review_reason"], "Conflicto de tipo con una identidad más fuerte: Báculo.")

    def test_entity_cleanup_demotes_descriptor_entities_and_reports_metrics(self):
        cleaned, cleanup_audit, promotion_audit = cleanup_resolved_entities(
            entities=[
                {
                    "canonical_name": "Sera",
                    "entity_kind": "character",
                    "summary": "Protagonista con magia inestable.",
                    "aliases": ["Serelyne"],
                    "key_facts": ["Huye del castillo.", "Su magia altera el equilibrio político."],
                    "relationships": [{"target": "Thiseia", "type": "located_in", "facts": ["Pertenece al reino."]}],
                    "chapter_refs": ["ch_001", "ch_002"],
                    "source_mentions": ["Sera", "Serelyne"],
                    "confidence": 0.95,
                    "review_state": "canonical",
                    "naming_quality": "proper_name",
                    "is_stable_entity": True,
                    "needs_review": False,
                    "review_reason": "",
                },
                {
                    "canonical_name": "señora de las infusiones imposibles",
                    "entity_kind": "character",
                    "summary": "Figura doméstica vista una sola vez.",
                    "aliases": [],
                    "key_facts": ["Prepara infusiones."],
                    "relationships": [],
                    "chapter_refs": ["ch_006"],
                    "source_mentions": ["señora de las infusiones imposibles"],
                    "confidence": 0.55,
                    "review_state": "review",
                    "naming_quality": "descriptor",
                    "is_stable_entity": False,
                    "needs_review": True,
                    "review_reason": "Descriptor sin nombre estable.",
                },
            ],
            chapter_outputs=[
                {"chapter_id": "ch_001", "chapter_title_original": "Episodio 1: La magia rota y la herencia silenciosa de Sera"},
                {"chapter_id": "ch_002", "chapter_title_original": "Episodio 2: La huída y el límite de la forma de Sera"},
                {"chapter_id": "ch_006", "chapter_title_original": "Episodio 6: Las infusiones imposibles"},
            ],
            language="es",
        )
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["canonical_name"], "Sera")
        self.assertEqual(cleaned[0]["promotion_status"], "promoted_canonical")
        self.assertEqual(cleanup_audit["primary_count"], 1)
        self.assertEqual(cleanup_audit["discarded_count"], 1)
        self.assertEqual(cleanup_audit["descriptor_primary_rate"], 0.0)
        self.assertEqual(promotion_audit["decisions"][1]["decision"], "discard")

    def test_entity_cleanup_retains_strong_primary_candidate_despite_review_flag(self):
        cleaned, _cleanup_audit, promotion_audit = cleanup_resolved_entities(
            entities=[
                {
                    "canonical_name": "Ren",
                    "entity_kind": "character",
                    "aliases": ["una chica"],
                    "key_facts": ["Participa en la ceremonia.", "Tiene un conflicto persistente con la magia."],
                    "relationships": [],
                    "chapter_refs": ["ch_004", "ch_008", "ch_012"],
                    "source_mentions": ["Ren"],
                    "review_state": "review",
                    "naming_quality": "proper_name",
                    "is_stable_entity": True,
                    "needs_review": True,
                    "strong_primary_candidate": True,
                }
            ],
            chapter_outputs=[],
            language="es",
        )

        self.assertEqual(cleaned[0]["promotion_status"], "promoted_canonical")
        self.assertEqual(promotion_audit["decisions"][0]["reason"], "strong_primary_candidate_retained")

    def test_entity_cleanup_rejects_alias_that_is_another_named_entity(self):
        cleaned, _cleanup_audit, _promotion_audit = cleanup_resolved_entities(
            entities=[
                {
                    "canonical_name": "Ren",
                    "entity_kind": "character",
                    "aliases": ["Sera", "una chica"],
                    "key_facts": ["Participa en varios capítulos.", "Tiene conflicto mágico."],
                    "relationships": [],
                    "chapter_refs": ["ch_004", "ch_008", "ch_012"],
                    "source_mentions": ["Ren"],
                    "review_state": "canonical",
                    "naming_quality": "proper_name",
                    "is_stable_entity": True,
                    "needs_review": False,
                    "strong_primary_candidate": True,
                },
                {
                    "canonical_name": "Sera",
                    "entity_kind": "character",
                    "aliases": ["la heredera"],
                    "key_facts": ["Es heredera.", "Tiene magia inestable."],
                    "relationships": [],
                    "chapter_refs": ["ch_002", "ch_003", "ch_014"],
                    "source_mentions": ["Sera"],
                    "review_state": "canonical",
                    "naming_quality": "proper_name",
                    "is_stable_entity": True,
                    "needs_review": False,
                    "strong_primary_candidate": True,
                },
            ],
            chapter_outputs=[],
            language="es",
        )
        ren = next(entity for entity in cleaned if entity["canonical_name"] == "Ren")
        self.assertNotIn("Sera", ren["aliases"])
        self.assertIn("Sera", ren["rejected_aliases"])

    def test_entity_cleanup_localizes_alias_contamination_reason_in_spanish(self):
        cleaned, _cleanup_audit, _promotion_audit = cleanup_resolved_entities(
            entities=[
                {
                    "canonical_name": "Ren",
                    "entity_kind": "character",
                    "aliases": ["Sera", "una chica"],
                    "rejected_aliases": [],
                    "key_facts": ["Participa en varios capítulos.", "Tiene conflicto mágico."],
                    "relationships": [],
                    "chapter_refs": ["ch_004", "ch_008", "ch_012"],
                    "source_mentions": ["Ren"],
                    "review_state": "canonical",
                    "naming_quality": "proper_name",
                    "is_stable_entity": True,
                    "needs_review": False,
                    "strong_primary_candidate": True,
                    "review_reason": "",
                    "review_reason_code": "",
                    "review_reason_params": {},
                },
                {
                    "canonical_name": "Sera",
                    "entity_kind": "character",
                    "aliases": ["la heredera"],
                    "rejected_aliases": [],
                    "key_facts": ["Es heredera.", "Tiene magia inestable."],
                    "relationships": [],
                    "chapter_refs": ["ch_002", "ch_003", "ch_014"],
                    "source_mentions": ["Sera"],
                    "review_state": "canonical",
                    "naming_quality": "proper_name",
                    "is_stable_entity": True,
                    "needs_review": False,
                    "strong_primary_candidate": True,
                    "review_reason": "",
                    "review_reason_code": "",
                    "review_reason_params": {},
                },
            ],
            chapter_outputs=[],
            language="es",
        )
        ren = next(entity for entity in cleaned if entity["canonical_name"] == "Ren")
        self.assertEqual(ren["review_reason_code"], "alias_contamination_rejected_named_aliases")
        self.assertEqual(ren["review_reason_params"]["rejected_aliases"], "Sera")
        self.assertIn("contaminación de aliases", ren["review_reason"])

    def test_pre_vaerl_reconciliation_merges_descriptor_orphan_into_named_primary(self):
        entities = [
            {
                "canonical_name": "Sera",
                "entity_kind": "character",
                "aliases": ["la princesa", "heredera"],
                "key_facts": ["Sera posee magia inestable."],
                "relationships": [],
                "chapter_refs": ["ch_001", "ch_002"],
                "source_mentions": ["Sera"],
                "review_state": "canonical",
                "note_role": "primary",
                "naming_quality": "proper_name",
            },
            {
                "canonical_name": "Ella",
                "entity_kind": "character",
                "aliases": ["la chica"],
                "key_facts": ["Es considerada una princesa por el intruso.", "No puede usar magia."],
                "relationships": [{"target": "El abuelo", "type": "familial", "facts": ["Está bajo su protección."]}],
                "chapter_refs": ["ch_010"],
                "source_mentions": ["ella", "la chica"],
                "review_state": "review",
                "note_role": "review",
                "naming_quality": "descriptor",
            },
            {
                "canonical_name": "Beld-san",
                "entity_kind": "character",
                "aliases": ["El abuelo"],
                "key_facts": ["Protege a Ren."],
                "relationships": [],
                "chapter_refs": ["ch_003", "ch_004"],
                "source_mentions": ["Beld-san", "el abuelo"],
                "review_state": "canonical",
                "note_role": "primary",
                "naming_quality": "title_plus_name",
            },
        ]

        reconciled, audit = reconcile_entities_for_vaerl(entities=entities, language="es")

        by_name = {entity["canonical_name"]: entity for entity in reconciled}
        self.assertIn("Sera", by_name)
        self.assertNotIn("Ella", by_name)
        self.assertEqual(audit["auto_merged_count"], 1)
        self.assertEqual(audit["auto_merged_entities"][0]["source_entity"], "Ella")
        self.assertEqual(audit["auto_merged_entities"][0]["target_entity"], "Sera")
        self.assertIn("No puede usar magia.", by_name["Sera"]["key_facts"])
        self.assertEqual(by_name["Sera"]["relationships"][0]["target"], "Beld-san")

    def test_pre_vaerl_reconciliation_merges_title_descriptor_into_title_plus_name_primary(self):
        entities = [
            {
                "canonical_name": "Reina Nerys",
                "entity_kind": "character",
                "aliases": ["Nerys"],
                "key_facts": ["Fue reina de Thiseia."],
                "relationships": [],
                "chapter_refs": ["ch_001", "ch_014"],
                "source_mentions": ["Reina Nerys"],
                "review_state": "canonical",
                "note_role": "primary",
                "naming_quality": "title_plus_name",
            },
            {
                "canonical_name": "Reina",
                "entity_kind": "character",
                "aliases": ["Su Majestad la Reina"],
                "key_facts": ["Acompaña al Rey en un recuerdo de la corte."],
                "relationships": [{"target": "Rey", "type": "familial", "facts": ["Está casada con él."]}],
                "chapter_refs": ["ch_014"],
                "source_mentions": ["Reina"],
                "review_state": "review",
                "note_role": "review",
                "naming_quality": "descriptor",
            },
        ]

        reconciled, audit = reconcile_entities_for_vaerl(entities=entities, language="es")

        self.assertEqual([entity["canonical_name"] for entity in reconciled], ["Reina Nerys"])
        self.assertEqual(audit["auto_merged_entities"][0]["source_entity"], "Reina")
        self.assertTrue(audit["policy"]["temporal_presence_conflicts_are_not_hard_blocks"])
        self.assertIn("Acompaña al Rey en un recuerdo de la corte.", reconciled[0]["key_facts"])

    def test_pre_vaerl_reconciliation_rewrites_relationship_targets_to_primary_aliases(self):
        entities = [
            {
                "canonical_name": "Beld-san",
                "entity_kind": "character",
                "aliases": ["el abuelo"],
                "key_facts": ["Figura protectora."],
                "relationships": [],
                "chapter_refs": ["ch_001", "ch_002"],
                "source_mentions": ["Beld-san"],
                "review_state": "canonical",
                "note_role": "primary",
                "naming_quality": "title_plus_name",
            },
            {
                "canonical_name": "campanilla",
                "entity_kind": "object",
                "aliases": [],
                "key_facts": ["Es del abuelo."],
                "relationships": [{"target": "El abuelo", "type": "owned_by", "facts": ["Siempre la lleva colgada."]}],
                "chapter_refs": ["ch_003"],
                "source_mentions": ["campanilla"],
                "review_state": "review",
                "note_role": "review",
                "naming_quality": "descriptor",
            },
        ]

        reconciled, audit = reconcile_entities_for_vaerl(entities=entities, language="es")
        campanilla = next(entity for entity in reconciled if entity["canonical_name"] == "campanilla")

        self.assertEqual(campanilla["relationships"][0]["target"], "Beld-san")
        self.assertEqual(audit["relationship_rewrite_count"], 1)

    def test_pre_vaerl_reconciliation_does_not_rewrite_long_target_to_shorter_object_alias(self):
        entities = [
            {
                "canonical_name": "Guantelete negro",
                "entity_kind": "object",
                "aliases": ["guantelete"],
                "key_facts": ["Objeto oscuro."],
                "relationships": [],
                "chapter_refs": ["ch_020"],
                "source_mentions": ["Guantelete negro"],
                "review_state": "canonical",
                "note_role": "primary",
                "naming_quality": "proper_name",
            },
            {
                "canonical_name": "Sera",
                "entity_kind": "character",
                "aliases": ["la princesa"],
                "key_facts": ["Protagonista."],
                "relationships": [{"target": "El intruso con guantelete negro", "type": "conflict", "facts": ["La persigue."]}],
                "chapter_refs": ["ch_020"],
                "source_mentions": ["Sera"],
                "review_state": "canonical",
                "note_role": "primary",
                "naming_quality": "proper_name",
            },
        ]

        reconciled, audit = reconcile_entities_for_vaerl(entities=entities, language="es")
        sera = next(entity for entity in reconciled if entity["canonical_name"] == "Sera")

        self.assertEqual(sera["relationships"][0]["target"], "El intruso con guantelete negro")
        self.assertEqual(audit["relationship_rewrite_count"], 0)

    def test_pre_vaerl_reconciliation_adds_fact_based_relationship_to_unique_primary_mention(self):
        entities = [
            {
                "canonical_name": "Ren",
                "entity_kind": "character",
                "aliases": [],
                "key_facts": ["Protagonista."],
                "relationships": [],
                "chapter_refs": ["ch_001", "ch_002"],
                "source_mentions": ["Ren", "narrador"],
                "review_state": "canonical",
                "note_role": "primary",
                "naming_quality": "proper_name",
            },
            {
                "canonical_name": "herboristería de los Halden",
                "entity_kind": "place",
                "aliases": ["herboristería"],
                "key_facts": ["Funciona como centro de tratamiento para el narrador."],
                "relationships": [],
                "chapter_refs": ["ch_006"],
                "source_mentions": ["herboristería"],
                "review_state": "review",
                "note_role": "review",
                "naming_quality": "descriptor",
            },
        ]

        reconciled, audit = reconcile_entities_for_vaerl(entities=entities, language="es")
        place = next(entity for entity in reconciled if entity["canonical_name"] == "herboristería de los Halden")

        self.assertEqual(place["relationships"][0]["target"], "Ren")
        self.assertEqual(place["relationships"][0]["type"], "related_to")
        self.assertEqual(audit["fact_relationship_added_count"], 1)

    def test_pre_vaerl_reconciliation_adds_relationship_from_relationship_fact_secondary_mention(self):
        entities = [
            {
                "canonical_name": "Sera",
                "entity_kind": "character",
                "aliases": [],
                "key_facts": ["Protagonista."],
                "relationships": [
                    {
                        "target": "Beld-san",
                        "type": "student",
                        "facts": ["Beld-san explica a Sera el linaje y la importancia del Báculo."],
                    }
                ],
                "chapter_refs": ["ch_001"],
                "source_mentions": ["Sera"],
                "review_state": "canonical",
                "note_role": "primary",
                "naming_quality": "proper_name",
            },
            {
                "canonical_name": "Beld-san",
                "entity_kind": "character",
                "aliases": ["el abuelo"],
                "key_facts": ["Mentor."],
                "relationships": [],
                "chapter_refs": ["ch_001"],
                "source_mentions": ["Beld-san"],
                "review_state": "canonical",
                "note_role": "primary",
                "naming_quality": "title_plus_name",
            },
            {
                "canonical_name": "Báculo",
                "entity_kind": "concept",
                "aliases": [],
                "key_facts": ["Posición heredada."],
                "relationships": [],
                "chapter_refs": ["ch_001"],
                "source_mentions": ["Báculo"],
                "review_state": "canonical",
                "note_role": "primary",
                "naming_quality": "proper_name",
            },
        ]

        reconciled, audit = reconcile_entities_for_vaerl(entities=entities, language="es")
        sera = next(entity for entity in reconciled if entity["canonical_name"] == "Sera")

        targets = {relationship["target"] for relationship in sera["relationships"]}
        self.assertIn("Beld-san", targets)
        self.assertIn("Báculo", targets)
        self.assertEqual(audit["fact_relationship_added_count"], 1)
        self.assertEqual(audit["fact_relationships_added"][0]["reason"], "relationship_fact_mentions_additional_primary_alias_or_source_mention")

    def test_post_assembly_relationship_reconciliation_adds_late_chapter_relation_mentions(self):
        entities = [
            {
                "canonical_name": "Sera",
                "entity_kind": "character",
                "aliases": [],
                "key_facts": ["Protagonista."],
                "relationships": [
                    {
                        "target": "Beld-san",
                        "type": "authority",
                        "facts": ["Beld-san explica a Sera el linaje y la importancia del Báculo."],
                    }
                ],
                "review_state": "canonical",
                "note_role": "primary",
            },
            {
                "canonical_name": "Beld-san",
                "entity_kind": "character",
                "aliases": ["el abuelo"],
                "key_facts": ["Mentor."],
                "relationships": [],
                "review_state": "canonical",
                "note_role": "primary",
            },
            {
                "canonical_name": "Báculo",
                "entity_kind": "concept",
                "aliases": [],
                "key_facts": ["Posición heredada."],
                "relationships": [],
                "review_state": "canonical",
                "note_role": "primary",
            },
        ]

        reconciled, audit = reconcile_primary_relationship_mentions(entities=entities)
        sera = next(entity for entity in reconciled if entity["canonical_name"] == "Sera")

        self.assertEqual(audit["schema_version"], "textifai.primary_relationship_reconciliation.v1")
        self.assertFalse(audit["policy"]["entity_merges_allowed"])
        self.assertIn("Báculo", {relationship["target"] for relationship in sera["relationships"]})
        self.assertEqual(audit["fact_relationship_added_count"], 1)

    def test_primary_note_synthesis_mentions_protagonist_role_and_reconciled_facts(self):
        synthesized, audit = synthesize_primary_note_summaries(
            entities=[
                {
                    "canonical_name": "Sera",
                    "entity_kind": "character",
                    "entity_subkind": "protagonist",
                    "aliases": ["la princesa", "Ella"],
                    "summary": "Personaje femenino cuya presencia fue confirmada.",
                    "key_facts": [
                        "No puede usar magia ni catalizadores en el momento actual.",
                        "Es considerada una princesa por el intruso.",
                    ],
                    "relationships": [
                        {
                            "target": "Reina Nerys",
                            "type": "familial",
                            "facts": ["Sera es hija de la reina Nerys."],
                        }
                    ],
                    "chapter_refs": ["ch_001", "ch_002", "ch_003", "ch_004"],
                    "review_state": "canonical",
                    "note_role": "primary",
                }
            ],
            language="es",
        )

        summary = synthesized[0]["summary"]
        self.assertIn("figura protagonista", summary)
        self.assertIn("Sera", summary)
        self.assertIn("la princesa", summary)
        self.assertIn("no puede usar magia", summary)
        self.assertEqual(audit["updated_summary_count"], 1)

    def test_primary_note_synthesis_does_not_update_review_entities(self):
        synthesized, audit = synthesize_primary_note_summaries(
            entities=[
                {
                    "canonical_name": "Ella",
                    "entity_kind": "character",
                    "aliases": ["la chica"],
                    "summary": "Resumen previo.",
                    "key_facts": ["Es considerada una princesa."],
                    "review_state": "review",
                    "note_role": "review",
                }
            ],
            language="es",
        )

        self.assertEqual(synthesized[0]["summary"], "Resumen previo.")
        self.assertEqual(audit["updated_summary_count"], 0)

    def test_auxiliary_source_index_uses_author_hint_and_title_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Fichas de personajes.md"
            path.write_text("# Ren\nDatos de Ren.", encoding="utf-8")

            with_hint = _build_auxiliary_document_record(
                AuxiliaryDocumentInput(path=str(path), author_hint="documento de fichas de personajes")
            )
            without_hint = _build_auxiliary_document_record(AuxiliaryDocumentInput(path=str(path)))

        self.assertEqual(with_hint["author_hint_status"], "provided")
        self.assertFalse(with_hint["fallback_title_hint_used"])
        self.assertEqual(without_hint["author_hint_status"], "missing")
        self.assertTrue(without_hint["fallback_title_hint_used"])
        self.assertIn("Fichas de personajes", without_hint["title_hint"])

    def test_auxiliary_chunking_packs_small_heading_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Lore.md"
            path.write_text("\n".join(f"## Tema {index}\nDato breve {index}." for index in range(1, 20)), encoding="utf-8")
            record = _build_auxiliary_document_record(AuxiliaryDocumentInput(path=str(path)))
            chunks = _chunk_auxiliary_document(record)

        self.assertLess(len(chunks), record["heading_count"])
        self.assertTrue(all(chunk["char_count"] <= 200000 for chunk in chunks))
        self.assertEqual(chunks[0]["author_hint_status"], "missing")

    def test_auxiliary_ingestion_enriches_existing_and_creates_future_primary(self):
        class Provider:
            def generate(self, request):
                return SimpleNamespace(
                    text=json.dumps(
                        {
                            "document_role": "character_sheets",
                            "document_role_confidence": 0.9,
                            "declared_entities": [
                                {
                                    "canonical_name": "Sera",
                                    "entity_kind": "character",
                                    "aliases": ["Serélyne"],
                                    "summary": "Sera es protagonista.",
                                    "facts": ["Sera heredará responsabilidades políticas."],
                                    "narrative_status": "planned",
                                    "confidence": 0.9,
                                },
                                {
                                    "canonical_name": "Liora",
                                    "entity_kind": "character",
                                    "aliases": [],
                                    "summary": "Liora aparecerá más adelante.",
                                    "facts": ["Liora tiene vínculo con Shaevar."],
                                    "narrative_status": "planned",
                                    "confidence": 0.86,
                                },
                            ],
                            "declared_relationships": [
                                {
                                    "source": "Liora",
                                    "target": "Sera",
                                    "type": "related_to",
                                    "facts": ["Liora y Sera compartirán ruta."],
                                    "narrative_status": "planned",
                                    "confidence": 0.8,
                                }
                            ],
                            "planned_events": [],
                            "backstory_items": [],
                            "uncertain_notes": [],
                        }
                    )
                )

        with tempfile.TemporaryDirectory() as tmp:
            doc_path = Path(tmp) / "Personajes.md"
            doc_path.write_text("# Sera\nNotas.\n# Liora\nNotas.", encoding="utf-8")
            system_root = Path(tmp) / "99_System"
            entities, audit = ingest_auxiliary_documents(
                system_root=system_root,
                entities=[
                    {
                        "canonical_name": "Sera",
                        "entity_kind": "character",
                        "aliases": [],
                        "key_facts": [],
                        "relationships": [],
                        "review_state": "canonical",
                        "note_role": "primary",
                    }
                ],
                auxiliary_documents=[AuxiliaryDocumentInput(path=str(doc_path), author_hint="documento de fichas")],
                language="es",
                provider=Provider(),
            )

            source_index = json.loads((system_root / "auxiliary_source_index.json").read_text(encoding="utf-8"))

        names = {entity["canonical_name"] for entity in entities}
        sera = next(entity for entity in entities if entity["canonical_name"] == "Sera")
        liora = next(entity for entity in entities if entity["canonical_name"] == "Liora")
        self.assertIn("Sera", names)
        self.assertIn("Liora", names)
        self.assertIn("Serélyne", sera["aliases"])
        self.assertIn("Sera heredará responsabilidades políticas.", sera["key_facts"])
        self.assertEqual(liora["entity_origin"], "auxiliary_declared")
        self.assertEqual(audit["created_entity_count"], 1)
        self.assertEqual(audit["enriched_entity_count"], 1)
        self.assertNotIn("text", source_index["documents"][0])

    def test_semantic_invariants_pass_for_valid_vaerl_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            system_root = Path(tmp) / "99_System"
            system_root.mkdir()
            (system_root / "chapter_outputs").mkdir()
            payload = {
                "work": {"title": "Test", "language": "es"},
                "run_status": {
                    "semantic_integrity": "complete",
                    "expected_chapter_count": 1,
                    "generated_chapter_count": 1,
                    "failed_chapter_count": 0,
                },
                "chapters": [{"chapter_id": "ch_001", "summary": "Ren acompaña a Sera."}],
                "entities": [
                    {
                        "canonical_name": "Ren",
                        "preferred_slug": "ren",
                        "entity_kind": "character",
                        "review_state": "canonical",
                        "aliases": [],
                        "summary": "Ren es protagonista.",
                        "key_facts": ["Ren protege a Sera."],
                        "relationships": [{"target": "Sera", "type": "protects", "facts": ["Ren protege a Sera."]}],
                    },
                    {
                        "canonical_name": "Sera",
                        "preferred_slug": "sera",
                        "entity_kind": "character",
                        "review_state": "canonical",
                        "aliases": [],
                        "summary": "Sera es protagonista.",
                        "key_facts": ["Sera huye del castillo."],
                        "relationships": [],
                    },
                ],
            }
            for name in [
                "global_normalization.json",
                "resolved_entities.json",
                "cleaned_entities.json",
                "chapter_extraction_audit.json",
                "run_comparability_manifest.json",
                "run_limits_audit.json",
                "obsidian_relationship_reconciliation_audit.json",
            ]:
                (system_root / name).write_text("{}", encoding="utf-8")
            (system_root / "obsidian_import.json").write_text(json.dumps(payload), encoding="utf-8")

            audit = evaluate_semantic_invariants(
                system_root=system_root,
                required_primaries=["Ren", "Sera"],
                min_primary_count=2,
                max_review_count=0,
            )

        self.assertEqual(audit["status"], "pass")
        self.assertTrue(audit["passed"])

    def test_semantic_invariants_fail_on_missing_required_primary_and_duplicate_slug(self):
        with tempfile.TemporaryDirectory() as tmp:
            system_root = Path(tmp) / "99_System"
            system_root.mkdir()
            payload = {
                "work": {"title": "Test", "language": "es"},
                "run_status": {
                    "semantic_integrity": "complete",
                    "expected_chapter_count": 0,
                    "generated_chapter_count": 0,
                    "failed_chapter_count": 0,
                },
                "chapters": [],
                "entities": [
                    {
                        "canonical_name": "Ren",
                        "preferred_slug": "ren",
                        "entity_kind": "character",
                        "review_state": "canonical",
                        "summary": "Ren es protagonista.",
                    },
                    {
                        "canonical_name": "Renn",
                        "preferred_slug": "ren",
                        "entity_kind": "character",
                        "review_state": "canonical",
                        "summary": "Renn parece duplicado.",
                    },
                ],
            }
            (system_root / "obsidian_import.json").write_text(json.dumps(payload), encoding="utf-8")

            audit = evaluate_semantic_invariants(system_root=system_root, required_primaries=["Sera"])

        self.assertFalse(audit["passed"])
        failed = {check["name"] for check in audit["checks"] if check["status"] == "fail"}
        self.assertIn("required_primaries_present", failed)
        self.assertIn("preferred_slug_present_and_unique_within_kind", failed)

    def test_semantic_invariants_warn_on_cross_kind_ontological_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            system_root = Path(tmp) / "99_System"
            system_root.mkdir()
            payload = {
                "work": {"title": "Test", "language": "es"},
                "run_status": {
                    "semantic_integrity": "complete",
                    "expected_chapter_count": 0,
                    "generated_chapter_count": 0,
                    "failed_chapter_count": 0,
                },
                "chapters": [],
                "entities": [
                    {
                        "canonical_name": "La Corona",
                        "preferred_slug": "la_corona",
                        "entity_kind": "character",
                        "review_state": "canonical",
                        "summary": "La Corona es una figura heredada.",
                    },
                    {
                        "canonical_name": "La Corona",
                        "preferred_slug": "la_corona",
                        "entity_kind": "concept",
                        "review_state": "canonical",
                        "summary": "La Corona es una institución.",
                    },
                ],
            }
            (system_root / "obsidian_import.json").write_text(json.dumps(payload), encoding="utf-8")
            for name in [
                "global_normalization.json",
                "resolved_entities.json",
                "cleaned_entities.json",
                "chapter_extraction_audit.json",
                "run_comparability_manifest.json",
                "run_limits_audit.json",
                "obsidian_relationship_reconciliation_audit.json",
            ]:
                (system_root / name).write_text("{}", encoding="utf-8")
            (system_root / "chapter_outputs").mkdir()

            audit = evaluate_semantic_invariants(system_root=system_root)

        self.assertTrue(audit["passed"])
        self.assertEqual(audit["status"], "pass_with_warnings")
        collision = next(check for check in audit["checks"] if check["name"] == "ontological_name_collisions")
        self.assertEqual(collision["status"], "warn")
        self.assertEqual(collision["details"]["collisions"][0]["collision_type"], "same_slug_cross_kind")

    def test_semantic_invariants_detect_auxiliary_errors_and_vault_broken_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            system_root = root / "99_System"
            vault_root = root / "vault"
            system_root.mkdir()
            vault_root.mkdir()
            payload = {
                "work": {"title": "Test", "language": "es"},
                "run_status": {
                    "semantic_integrity": "complete",
                    "expected_chapter_count": 0,
                    "generated_chapter_count": 0,
                    "failed_chapter_count": 0,
                },
                "chapters": [],
                "entities": [],
            }
            (system_root / "obsidian_import.json").write_text(json.dumps(payload), encoding="utf-8")
            (system_root / "auxiliary_enrichment_audit.json").write_text(
                json.dumps({"extraction_error_count": 1, "chunk_count": 2, "extraction_count": 1}),
                encoding="utf-8",
            )
            (vault_root / "ren.md").write_text("# Ren\nLink roto: [[sera]]", encoding="utf-8")
            (vault_root / "placeholder.md").write_text("", encoding="utf-8")

            audit = write_semantic_invariants_audit(
                output_path=system_root / "semantic_invariants_audit.json",
                system_root=system_root,
                vault_root=vault_root,
            )
            self.assertTrue((system_root / "semantic_invariants_audit.json").exists())

        failed = {check["name"] for check in audit["checks"] if check["status"] == "fail"}
        self.assertIn("auxiliary_ingestion_integrity", failed)
        self.assertIn("vault_wikilinks_resolve", failed)
        self.assertIn("vault_no_empty_placeholders", failed)

    def test_semantic_invariants_warn_on_unlinked_primary_mentions_and_unresolved_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            system_root = Path(tmp) / "99_System"
            system_root.mkdir()
            payload = {
                "work": {"title": "Test", "language": "es"},
                "run_status": {
                    "semantic_integrity": "complete",
                    "expected_chapter_count": 0,
                    "generated_chapter_count": 0,
                    "failed_chapter_count": 0,
                },
                "chapters": [],
                "entities": [
                    {
                        "canonical_name": "Ren",
                        "preferred_slug": "ren",
                        "entity_kind": "character",
                        "review_state": "canonical",
                        "summary": "Ren habla con Sera y observa el Báculo.",
                        "key_facts": ["Ren protege a Sera."],
                        "relationships": [{"target": "Entidad Inexistente", "type": "related_to", "facts": ["Ren recuerda a Sera."]}],
                    },
                    {
                        "canonical_name": "Sera",
                        "preferred_slug": "sera",
                        "entity_kind": "character",
                        "review_state": "canonical",
                        "aliases": ["la princesa"],
                        "summary": "Sera es protagonista.",
                        "key_facts": ["Sera huye del castillo."],
                        "relationships": [],
                    },
                    {
                        "canonical_name": "Báculo",
                        "preferred_slug": "baculo",
                        "entity_kind": "concept",
                        "review_state": "canonical",
                        "summary": "El Báculo es una posición heredada.",
                        "key_facts": ["El Báculo puede confundirse con una persona o un objeto."],
                        "relationships": [],
                    },
                ],
            }
            (system_root / "obsidian_import.json").write_text(json.dumps(payload), encoding="utf-8")

            audit = evaluate_semantic_invariants(
                system_root=system_root,
                max_unlinked_primary_mentions=0,
            )

        checks = {check["name"]: check for check in audit["checks"]}
        self.assertEqual(checks["relationship_targets_resolve_to_primary"]["status"], "warn")
        self.assertEqual(checks["unlinked_primary_mentions"]["status"], "fail")
        self.assertGreaterEqual(checks["unlinked_primary_mentions"]["details"]["finding_count"], 1)

    def test_semantic_invariants_warn_on_orphan_primary_and_weak_canonical_over_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            system_root = Path(tmp) / "99_System"
            system_root.mkdir()
            payload = {
                "work": {"title": "Test", "language": "es"},
                "run_status": {
                    "semantic_integrity": "complete",
                    "expected_chapter_count": 0,
                    "generated_chapter_count": 0,
                    "failed_chapter_count": 0,
                },
                "chapters": [],
                "entities": [
                    {
                        "canonical_name": "la princesa",
                        "preferred_slug": "la_princesa",
                        "entity_kind": "character",
                        "review_state": "canonical",
                        "naming_quality": "descriptor",
                        "aliases": ["Sera"],
                        "summary": "Sera es protagonista.",
                        "key_facts": ["Sera huye del castillo."],
                        "relationships": [],
                    },
                    {
                        "canonical_name": "Figura sin soporte",
                        "preferred_slug": "figura_sin_soporte",
                        "entity_kind": "character",
                        "review_state": "canonical",
                        "relationships": [],
                    },
                ],
            }
            (system_root / "obsidian_import.json").write_text(json.dumps(payload), encoding="utf-8")

            audit = evaluate_semantic_invariants(
                system_root=system_root,
                max_suspicious_orphan_primaries=0,
            )

        checks = {check["name"]: check for check in audit["checks"]}
        self.assertEqual(checks["canonical_name_not_weaker_than_available_alias"]["status"], "warn")
        self.assertEqual(checks["suspicious_orphan_primaries"]["status"], "fail")
        self.assertEqual(checks["suspicious_orphan_primaries"]["details"]["suspicious_count"], 1)

    def test_review_queue_builds_actionable_items_for_pending_reviews_and_relationship_targets(self):
        payload = {
            "work": {"title": "Test", "language": "es"},
            "entities": [
                {
                    "canonical_name": "Sera",
                    "preferred_slug": "sera",
                    "entity_kind": "character",
                    "review_state": "canonical",
                    "aliases": ["la princesa"],
                    "key_facts": ["Sera huye."],
                    "relationships": [{"target": "Consejo", "type": "authority", "facts": ["El Consejo vigila a Sera."]}],
                },
                {
                    "canonical_name": "Consejo",
                    "preferred_slug": "consejo",
                    "entity_kind": "faction",
                    "review_state": "review",
                    "confidence": 0.7,
                    "key_facts": ["El Consejo supervisa el castillo."],
                    "source_mentions": ["Consejo"],
                    "relationships": [],
                },
                {
                    "canonical_name": "Báculo",
                    "preferred_slug": "baculo",
                    "entity_kind": "character",
                    "review_state": "canonical",
                    "key_facts": ["Figura heredada."],
                    "relationships": [],
                },
                {
                    "canonical_name": "Báculo",
                    "preferred_slug": "baculo",
                    "entity_kind": "object",
                    "review_state": "canonical",
                    "key_facts": ["Objeto interpretado por algunos personajes."],
                    "relationships": [],
                },
            ],
        }

        queue = build_review_queue(obsidian_import=payload)

        self.assertEqual(queue["schema_version"], "textifai.review_queue.v1")
        self.assertTrue(queue["policy"]["pending_reviews_are_expected"])
        review_types = {item["review_type"] for item in queue["items"]}
        self.assertIn("review_entity", review_types)
        self.assertIn("unresolved_relationship_target", review_types)
        self.assertIn("ontological_collision", review_types)
        unresolved = next(item for item in queue["items"] if item["review_type"] == "unresolved_relationship_target")
        self.assertEqual(unresolved["target_text"], "Consejo")
        self.assertEqual(unresolved["candidate_entities"][0]["canonical_name"], "Consejo")
        self.assertFalse(unresolved["can_auto_apply"])
        self.assertTrue(unresolved["review_item_id"].startswith("rq_"))

    def test_taxonomy_maps_legacy_magic_to_concept_system(self):
        payload = taxonomy_payload_for_entity(
            {
                "canonical_name": "Maná",
                "entity_kind": "magic",
                "entity_subkind": "",
                "chapter_refs": ["ch_001", "ch_002"],
            }
        )
        self.assertEqual(payload["entity_kind"], "concept")
        self.assertEqual(payload["entity_subkind"], "system")
        self.assertEqual(payload["semantic_class"], "concept:system")

    def test_taxonomy_tags_include_role_and_kind_for_primary_entities(self):
        self.assertEqual(
            taxonomy_tags(note_role="primary", entity_kind="character", entity_subkind="protagonist"),
            ["#primary", "#character", "#protagonist"],
        )
        self.assertEqual(
            taxonomy_tags(note_role="review", entity_kind="concept", entity_subkind="ritual"),
            ["#review", "#concept", "#ritual"],
        )

    def test_language_detection_sampling_caps_large_text(self):
        text = ("Hola mundo. " * 5000) + ("This is English. " * 5000) + ("日本語です。" * 5000)
        sampled = sample_text_for_language_detection(text)
        self.assertLess(len(sampled), len(text))
        self.assertLessEqual(len(sampled), 24000 + 2)

    def test_recurring_chapter_entities_can_be_promoted_when_global_canon_misses_them(self):
        promoted = _promote_recurring_chapter_entities(
            global_entities=[],
            chapter_outputs=[
                {
                    "chapter_id": "ch_001",
                    "characters": [{"surface": "Sera", "canonical": "Sera", "facts": ["Princesa aislada."], "confidence": 0.95}],
                    "places": [],
                    "concepts": [],
                    "events": [],
                    "relations": [],
                },
                {
                    "chapter_id": "ch_002",
                    "characters": [{"surface": "Sera", "canonical": "Sera", "facts": ["Su magia es inestable."], "confidence": 0.94}],
                    "places": [],
                    "concepts": [],
                    "events": [],
                    "relations": [],
                },
            ],
        )
        names = [item["canonical_name"] for item in promoted]
        self.assertIn("Sera", names)

    def test_title_entity_hints_capture_explicit_named_focus(self):
        self.assertEqual(
            _extract_title_entity_hints("Episodio 1: La magia Rota y la herencia silenciosa de Sera"),
            ["Sera"],
        )
        self.assertEqual(
            _extract_title_entity_hints("Episodio 3: El ritual del humo de Ren· Parte 1"),
            ["Ren"],
        )

    def test_title_hint_entities_can_promote_missing_focal_identity(self):
        promoted = _promote_title_hint_entities(
            global_entities=[],
            chapter_outputs=[
                {
                    "chapter_id": "ch_002",
                    "chapter_title_original": "Episodio 1: La magia rota y la herencia silenciosa de Sera",
                    "chapter_summary": "Sera decide abandonar el castillo.",
                    "characters": [{"surface": "Ren", "canonical": "Ren", "facts": ["Su magia es inestable."], "confidence": 0.9}],
                },
                {
                    "chapter_id": "ch_003",
                    "chapter_title_original": "Episodio 2: La huída y el límite de la forma de Sera",
                    "chapter_summary": "Sera escapa del castillo.",
                    "characters": [{"surface": "Ren", "canonical": "Ren", "facts": ["Huye hacia el bosque."], "confidence": 0.9}],
                },
            ],
        )
        names = [item["canonical_name"] for item in promoted]
        self.assertIn("Sera", names)

    def test_stabilize_character_entities_filters_title_conflicted_refs(self):
        stabilized = _stabilize_character_entities_with_title_hints(
            [
                {
                    "canonical_name": "Ren",
                    "entity_kind": "character",
                    "summary": "Ren mezcla hechos de otra protagonista.",
                    "aliases": [],
                    "key_facts": ["Hecho contaminado."],
                    "relationships": [],
                    "chapter_refs": ["ch_002", "ch_004", "ch_005"],
                    "source_mentions": ["Ren"],
                    "confidence": 0.95,
                    "review_state": "canonical",
                }
            ],
            [
                {
                    "chapter_id": "ch_002",
                    "chapter_title_original": "Episodio 1: La magia rota y la herencia silenciosa de Sera",
                    "chapter_summary": "Sera se enfrenta al castillo.",
                    "characters": [{"surface": "Ren", "canonical": "Ren", "facts": ["Hecho contaminado."], "confidence": 0.9}],
                },
                {
                    "chapter_id": "ch_004",
                    "chapter_title_original": "Episodio 3: El ritual del humo de Ren Parte 1",
                    "chapter_summary": "Ren participa en el ritual.",
                    "characters": [{"surface": "Ren", "canonical": "Ren", "facts": ["Participa en un ritual cargado de tensión."], "confidence": 0.95}],
                },
                {
                    "chapter_id": "ch_005",
                    "chapter_title_original": "Episodio 4: El ritual del humo de Ren Parte 2",
                    "chapter_summary": "Ren protege la campanilla.",
                    "characters": [{"surface": "Ren", "canonical": "Ren", "facts": ["Protege la campanilla durante un ataque."], "confidence": 0.95}],
                },
            ],
            language="es",
        )
        ren = stabilized[0]
        self.assertEqual(ren["chapter_refs"], ["ch_004", "ch_005"])
        self.assertNotIn("Hecho contaminado.", ren["key_facts"])
        self.assertIn("Ren", ren["summary"])

    def test_global_normalization_batches_split_chapters_by_budget(self):
        chapter = type("_Chapter", (), {})
        chapters = []
        for idx in range(3):
            item = chapter()
            item.title = f"Chapter {idx + 1}"
            item.text = "x" * 4000
            chapters.append(item)
        batches = _build_global_normalization_batches(
            work_title="Test Novel",
            language="es",
            chapters=chapters,
            config=NovelBootstrapV1Config(
                provider_name="lmstudio",
                model="qwen/qwen3.5-9b",
                global_batch_input_token_budget=2500,
                global_batch_prompt_overhead_tokens=200,
            ),
        )
        batches, audit = batches
        self.assertGreaterEqual(len(batches), 2)
        self.assertEqual(batches[0][0]["sequence_index"], 1)
        self.assertEqual(audit["batch_count"], len(batches))
        self.assertIn("max_total_cost", audit)

    def test_global_normalization_complexity_penalty_increases_for_noisy_batches(self):
        clean = _estimate_global_batch_complexity_penalty(
            [{"title": "Chapter 1", "text": "Texto limpio."}],
            config=NovelBootstrapV1Config(provider_name="openai", model="auto"),
        )
        noisy = _estimate_global_batch_complexity_penalty(
            [{"title": "Episode [Link](http://example.com) *Noisy*", "text": "[[Sera]] http://example.com\n# Head\n" * 20}],
            config=NovelBootstrapV1Config(provider_name="openai", model="auto"),
        )
        self.assertGreater(noisy, clean)

    def test_auto_model_selection_prefers_phase_appropriate_openai_models(self):
        self.assertEqual(
            _resolve_structured_model(
                NovelBootstrapV1Config(provider_name="openai", model="auto"),
                phase="global_normalization",
            ),
            "gpt-4.1-mini",
        )
        self.assertEqual(
            _resolve_structured_model(
                NovelBootstrapV1Config(provider_name="openai", model="auto"),
                phase="chapter_extraction",
                input_tokens=12000,
            ),
            "gpt-4o-mini",
        )
        self.assertEqual(
            _resolve_structured_model(
                NovelBootstrapV1Config(provider_name="openai", model="auto"),
                phase="chapter_extraction",
                input_tokens=180000,
            ),
            "gpt-4.1-mini",
        )

    def test_json_import_filters_numeric_empty_primaries_and_marks_system_and_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_json = Path(tmp) / "obsidian_import.json"
            vault_root = Path(tmp) / "vault"
            source_json.write_text(
                json.dumps(
                    {
                        "work": {"title": "Test", "language": "es"},
                        "chapters": [
                            {
                                "chapter_id": "ch_001",
                                "chapter_title_original": "Episodio 1: Inicio",
                                "chapter_title_canonical": "Episodio 1: Inicio",
                                "sequence_index": 1,
                                "chapter_summary": "Resumen",
                                "chapter_text_markdown": "Texto",
                                "characters": [],
                                "places": [],
                                "concepts": [],
                                "events": [],
                                "relations": [],
                                "unresolved_mentions": [],
                            }
                        ],
                        "entities": [
                            {
                                "canonical_name": "1",
                                "entity_kind": "character",
                                "summary": "",
                                "key_facts": [],
                                "relationships": [],
                                "aliases": [],
                                "chapter_refs": [],
                                "source_mentions": [],
                                "confidence": 0.2,
                                "review_state": "canonical",
                            },
                            {
                                "canonical_name": "Sera",
                                "entity_kind": "character",
                                "entity_subkind": "protagonist",
                                "summary": "Protagonista.",
                                "key_facts": ["Huye del castillo.", "Su magia es inestable."],
                                "relationships": [],
                                "aliases": ["Serelyne"],
                                "chapter_refs": ["ch_001", "ch_002"],
                                "source_mentions": ["Sera"],
                                "confidence": 0.95,
                                "review_state": "canonical",
                            },
                            {
                                "canonical_name": "Figura Dudosa",
                                "entity_kind": "character",
                                "summary": "Mencion incierta.",
                                "key_facts": ["Podría estar relacionada con el bosque."],
                                "relationships": [],
                                "aliases": [],
                                "chapter_refs": ["ch_001"],
                                "source_mentions": [],
                                "confidence": 0.4,
                                "review_state": "review",
                            },
                            {
                                "canonical_name": "Sistema de Maná",
                                "entity_kind": "magic",
                                "summary": "Sistema energético del mundo.",
                                "key_facts": ["Ordena la canalización.", "Afecta a varios personajes."],
                                "relationships": [{"target": "Sera", "type": "dependency", "facts": ["Condiciona su poder."]}],
                                "aliases": ["Maná"],
                                "chapter_refs": ["ch_001", "ch_002"],
                                "source_mentions": ["sistema de maná"],
                                "confidence": 0.93,
                                "review_state": "canonical",
                            },
                            {
                                "canonical_name": "Huida del Castillo",
                                "entity_kind": "event",
                                "summary": "Evento local de corto alcance.",
                                "key_facts": ["Sera abandona el castillo.", "Ocurre en un solo capítulo."],
                                "relationships": [],
                                "aliases": [],
                                "chapter_refs": ["ch_001"],
                                "source_mentions": ["huida"],
                                "confidence": 0.9,
                                "review_state": "canonical",
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            audit = import_json_to_vault(source_json=source_json, vault_root=vault_root)
            self.assertEqual(audit["primary_count"], 2)
            self.assertEqual(audit["review_primary_count"], 1)
            self.assertEqual(audit["skipped_primary_count"], 2)
            self.assertTrue((vault_root / "03_Characters/Profiles/sera.md").exists())
            self.assertTrue((vault_root / "90_Review/figura_dudosa.md").exists())
            self.assertTrue((vault_root / "02_World/Concepts/sistema_de_mana.md").exists())
            self.assertFalse((vault_root / "02_World/Events/huida_del_castillo.md").exists())
            self.assertFalse((vault_root / "03_Characters/Profiles/1.md").exists())
            manifest = (vault_root / "01_Project/import_manifest.md").read_text(encoding="utf-8")
            self.assertIn("#system", manifest)
            primary_note = (vault_root / "03_Characters/Profiles/sera.md").read_text(encoding="utf-8")
            self.assertIn('"#primary"', primary_note)
            self.assertIn('"#character"', primary_note)
            self.assertIn('"#protagonist"', primary_note)
            concept_note = (vault_root / "02_World/Concepts/sistema_de_mana.md").read_text(encoding="utf-8")
            self.assertIn('"#primary"', concept_note)
            self.assertIn('"#concept"', concept_note)
            self.assertIn('"#system"', concept_note)
            chapter_note = next((vault_root / "04_Story/Chapters").glob("*.md")).read_text(encoding="utf-8")
            self.assertIn("#chapter", chapter_note)
            self.assertIn("## Resumen", chapter_note)

    def test_json_import_preserves_existing_system_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_json = Path(tmp) / "obsidian_import.json"
            vault_root = Path(tmp) / "vault"
            (vault_root / "99_System").mkdir(parents=True, exist_ok=True)
            (vault_root / "99_System" / "global_batch_plan_audit.json").write_text('{"ok": true}', encoding="utf-8")
            source_json.write_text(
                json.dumps(
                    {
                        "work": {"title": "Test", "language": "es"},
                        "chapters": [],
                        "entities": [
                            {
                                "canonical_name": "Sera",
                                "entity_kind": "character",
                                "summary": "Protagonista.",
                                "key_facts": ["Huye del castillo."],
                                "relationships": [],
                                "aliases": [],
                                "chapter_refs": [],
                                "source_mentions": [],
                                "confidence": 0.95,
                                "review_state": "canonical",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            import_json_to_vault(source_json=source_json, vault_root=vault_root)
            self.assertTrue((vault_root / "99_System" / "global_batch_plan_audit.json").exists())

    def test_json_import_uses_slug_targets_for_wikilinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_json = Path(tmp) / "obsidian_import.json"
            vault_root = Path(tmp) / "vault"
            source_json.write_text(
                json.dumps(
                    {
                        "work": {"title": "Test", "language": "es"},
                        "chapters": [
                            {
                                "chapter_id": "ch_001",
                                "chapter_title_original": "Episodio 1: Inicio",
                                "chapter_title_canonical": "Episodio 1: Inicio",
                                "sequence_index": 1,
                                "chapter_summary": "Ren desconfía de Adelman Leofrick.",
                                "chapter_text_markdown": "Ren recuerda a Adelman Leofrick y al Reino de Thiseia.",
                                "characters": [
                                    {
                                        "surface": "Adelman Leofrick",
                                        "canonical": "Adelman Leofrick",
                                        "facts": ["Ren desconfía de Adelman Leofrick."],
                                    }
                                ],
                                "places": [
                                    {
                                        "surface": "Reino de Thiseia",
                                        "canonical": "Reino de Thiseia",
                                        "facts": ["Es el reino principal de la historia."],
                                    }
                                ],
                                "concepts": [],
                                "events": [],
                                "relations": [],
                                "unresolved_mentions": [],
                            }
                        ],
                        "entities": [
                            {
                                "canonical_name": "Adelman Leofrick",
                                "preferred_slug": "adelman_leofrick",
                                "entity_kind": "character",
                                "summary": "Regente del reino.",
                                "key_facts": ["Gobierna tras la caída del reino.", "Ren desconfía de él."],
                                "relationships": [],
                                "aliases": [],
                                "chapter_refs": ["ch_001", "ch_002"],
                                "source_mentions": ["Adelman Leofrick"],
                                "confidence": 0.95,
                                "review_state": "canonical",
                            },
                            {
                                "canonical_name": "Reino de Thiseia",
                                "preferred_slug": "reino_de_thiseia",
                                "entity_kind": "place",
                                "summary": "Reino principal de la historia.",
                                "key_facts": ["Contiene el castillo real.", "Es el centro político del conflicto."],
                                "relationships": [],
                                "aliases": [],
                                "chapter_refs": ["ch_001", "ch_002"],
                                "source_mentions": ["Reino de Thiseia"],
                                "confidence": 0.95,
                                "review_state": "canonical",
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            import_json_to_vault(source_json=source_json, vault_root=vault_root)

            chapter_note = next((vault_root / "04_Story/Chapters").glob("*.md")).read_text(encoding="utf-8")
            self.assertIn("[[adelman_leofrick]]", chapter_note)
            self.assertIn("[[reino_de_thiseia]]", chapter_note)
            self.assertNotIn("[[Adelman Leofrick]]", chapter_note)
            self.assertNotIn("[[Reino de Thiseia]]", chapter_note)

    def test_run_structured_bootstrap_v1_writes_json_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_root = Path(tmp) / "source"
            vault_root = Path(tmp) / "vault"
            source_root.mkdir(parents=True, exist_ok=True)
            vault_root.mkdir(parents=True, exist_ok=True)
            (source_root / "novel.md").write_text(
                (
                    "# 1 Arrival at Thiseia\n\n"
                    "Sera despierta en Thiseia y observa el castillo mientras piensa en su destino inmediato.\n\n"
                    "# 2 Escape from the Castle\n\n"
                    "Sera huye del castillo y atraviesa Thiseia con miedo, determinación y una decisión duradera.\n"
                ),
                encoding="utf-8",
            )
            inventory = build_source_document_inventory(source_root)

            with patch("textifai.import_review.structured_bootstrap_v1.get_text_provider_config_error", return_value=None), patch(
                "textifai.import_review.structured_bootstrap_v1.synchronize_runtime_environment"
            ) as sync_env, patch(
                "textifai.import_review.structured_bootstrap_v1.get_text_provider",
                return_value=_StructuredBootstrapFakeProvider(),
            ):
                result = run_structured_bootstrap_v1(
                    vault_root,
                    inventory=inventory,
                    config=NovelBootstrapV1Config(provider_name="lmstudio", model="qwen/qwen3.5-9b"),
                )

            self.assertIsNotNone(result)
            assert result is not None
            sync_env.assert_called()
            self.assertEqual(result.chapter_count, 2)
            self.assertTrue(Path(result.novel_index_path).exists())
            self.assertTrue(Path(result.global_normalization_pass1_path).exists())
            self.assertTrue(Path(result.global_normalization_pass2_path).exists())
            self.assertTrue(Path(result.ambiguous_entity_queue_path).exists())
            self.assertTrue(Path(result.selective_normalization_trace_path).exists())
            self.assertTrue(Path(result.selective_normalization_metrics_path).exists())
            self.assertTrue(Path(result.global_normalization_path).exists())
            self.assertTrue(Path(result.global_batch_audit_path).exists())
            self.assertTrue(Path(result.model_plan_audit_path).exists())
            self.assertTrue(Path(result.canonical_entity_map_path).exists())
            self.assertTrue(Path(result.resolved_entities_path).exists())
            self.assertTrue(Path(result.entity_clusters_audit_path).exists())
            self.assertTrue(Path(result.entity_resolution_audit_path).exists())
            self.assertTrue(Path(result.semantic_context_probe_audit_path).exists())
            self.assertTrue(Path(result.semantic_context_probe_trace_path).exists())
            self.assertTrue(Path(result.cleaned_entities_path).exists())
            self.assertTrue(Path(result.entity_cleanup_audit_path).exists())
            self.assertTrue(Path(result.promotion_decisions_audit_path).exists())
            self.assertTrue(Path(result.obsidian_import_path).exists())
            self.assertTrue(Path(result.playbook_boundary_audit_path).exists())
            self.assertTrue(Path(result.llm_call_ledger_path).exists())
            self.assertTrue(Path(result.run_limits_audit_path).exists())
            self.assertTrue(Path(result.run_comparability_manifest_path).exists())
            self.assertTrue((vault_root / "99_System" / "e2e_artifact_contract.json").exists())
            ledger_lines = [
                json.loads(line)
                for line in Path(result.llm_call_ledger_path).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(ledger_lines)
            self.assertTrue(all("input_hash" in line and "output_hash" in line for line in ledger_lines))
            run_limits = json.loads(Path(result.run_limits_audit_path).read_text(encoding="utf-8"))
            self.assertEqual(run_limits["artifact_status"], "complete")
            comparability = json.loads(Path(result.run_comparability_manifest_path).read_text(encoding="utf-8"))
            self.assertEqual(comparability["pipeline_mode"], "full_semantic_ingestion")
            novel_index = json.loads(Path(result.novel_index_path).read_text(encoding="utf-8"))
            self.assertEqual(len(novel_index["chapters"]), 2)
            pass1 = json.loads(Path(result.global_normalization_pass1_path).read_text(encoding="utf-8"))
            self.assertEqual(pass1["strategy"], "metadata_first_selective_expansion")
            pass2 = json.loads(Path(result.global_normalization_pass2_path).read_text(encoding="utf-8"))
            self.assertEqual(pass2["generation"]["method"], "llm_selective_chapter_expansion")
            ambiguity_queue = json.loads(Path(result.ambiguous_entity_queue_path).read_text(encoding="utf-8"))
            self.assertIn("ambiguous_clusters", ambiguity_queue)
            trace_events = [
                json.loads(line)
                for line in Path(result.selective_normalization_trace_path).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertIn("planner_started", [event["event_type"] for event in trace_events])
            self.assertIn("selective_normalization_finished", [event["event_type"] for event in trace_events])
            metrics = json.loads(Path(result.selective_normalization_metrics_path).read_text(encoding="utf-8"))
            self.assertEqual(metrics["run_status"]["semantic_integrity"], "complete")
            self.assertEqual(metrics["pass2_subcalls_started"], len(metrics["selected_chapter_ids"]))
            boundary_audit = json.loads(Path(result.playbook_boundary_audit_path).read_text(encoding="utf-8"))
            self.assertEqual(
                set(boundary_audit["boundaries"]),
                {"global_normalization", "chapter_extraction", "entity_resolution", "entity_cleanup", "obsidian_import"},
            )
            self.assertEqual(
                boundary_audit["rerun_policy"]["api_required_for_boundaries"],
                ["global_normalization", "chapter_extraction"],
            )
            self.assertEqual(
                boundary_audit["rerun_policy"]["api_not_required_for_boundaries"],
                ["entity_resolution", "entity_cleanup", "obsidian_import"],
            )
            chapter_files = sorted(Path(result.chapter_outputs_dir).glob("*.json"))
            self.assertEqual(len(chapter_files), 2)
            first_chapter_output = json.loads(chapter_files[0].read_text(encoding="utf-8"))["chapters"][0]
            self.assertIn("chapter_label_type", first_chapter_output)
            self.assertIn("chapter_number_in_label", first_chapter_output)
            self.assertIn("title_parse_signals", first_chapter_output)
            obsidian_import = json.loads(Path(result.obsidian_import_path).read_text(encoding="utf-8"))
            self.assertIn("chapter_label_type", obsidian_import["chapters"][0])
            self.assertIn("chapter_number_in_label", obsidian_import["chapters"][0])
            self.assertIn("title_parse_signals", obsidian_import["chapters"][0])

    def test_run_structured_bootstrap_v1_audits_incomplete_chapter_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_root = Path(tmp) / "source"
            vault_root = Path(tmp) / "vault"
            source_root.mkdir(parents=True, exist_ok=True)
            vault_root.mkdir(parents=True, exist_ok=True)
            (source_root / "novel.md").write_text(
                (
                    "# 1 Arrival at Thiseia\n\n"
                    "Sera despierta en Thiseia y observa el castillo mientras piensa en su destino inmediato.\n\n"
                    "# 2 Escape from the Castle\n\n"
                    "Sera huye del castillo y atraviesa Thiseia con miedo, determinación y una decisión duradera.\n"
                ),
                encoding="utf-8",
            )
            inventory = build_source_document_inventory(source_root)

            with patch("textifai.import_review.structured_bootstrap_v1.get_text_provider_config_error", return_value=None), patch(
                "textifai.import_review.structured_bootstrap_v1.synchronize_runtime_environment"
            ), patch(
                "textifai.import_review.structured_bootstrap_v1.get_text_provider",
                return_value=_StructuredBootstrapChapterFailureProvider(),
            ):
                result = run_structured_bootstrap_v1(
                    vault_root,
                    inventory=inventory,
                    config=NovelBootstrapV1Config(
                        provider_name="lmstudio",
                        model="qwen/qwen3.5-9b",
                        chapter_extraction_retries=1,
                        chapter_extraction_retry_backoff_seconds=0.0,
                    ),
                )

            self.assertIsNotNone(result)
            assert result is not None
            self.assertIn("chapter_extraction_failed:2 Escape from the Castle", result.warnings)
            self.assertFalse((Path(result.chapter_outputs_dir) / "ch_002.json").exists())
            chapter_audit = json.loads(Path(result.chapter_extraction_audit_path).read_text(encoding="utf-8"))
            self.assertEqual(chapter_audit["run_status"]["semantic_integrity"], "incomplete")
            self.assertFalse(chapter_audit["run_status"]["chapter_extraction_complete"])
            self.assertEqual([item["chapter_id"] for item in chapter_audit["failed_chapters"]], ["ch_002"])
            self.assertEqual(chapter_audit["failed_chapters"][0]["attempt_count"], 2)
            self.assertEqual(chapter_audit["failed_chapters"][0]["failure_type"], "parse_failure")
            self.assertTrue(chapter_audit["failed_chapters"][0]["response_sha256"])
            boundary_audit = json.loads(Path(result.playbook_boundary_audit_path).read_text(encoding="utf-8"))
            self.assertEqual(boundary_audit["run_status"]["semantic_integrity"], "incomplete")
            self.assertEqual(boundary_audit["boundaries"]["chapter_extraction"]["failed_chapter_count"], 1)
            obsidian_import = json.loads(Path(result.obsidian_import_path).read_text(encoding="utf-8"))
            self.assertEqual(obsidian_import["run_status"]["semantic_integrity"], "incomplete")
            entity_resolution_audit = json.loads(Path(result.entity_resolution_audit_path).read_text(encoding="utf-8"))
            self.assertEqual(entity_resolution_audit["run_status"]["semantic_integrity"], "incomplete")


if __name__ == "__main__":
    unittest.main()
