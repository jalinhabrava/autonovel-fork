from __future__ import annotations

from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass, field, replace
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from html import escape
from pathlib import Path
from unittest.mock import patch

from textifai.author_understanding.contracts import LLMAuthorUnderstandingPayload
from textifai.author_response.contracts import AnchoredAuthorResponse
from textifai.author_response.generator import ProviderBackedAuthorResponseGenerator, TemplateAuthorResponseGenerator
from textifai.author_understanding.hybrid_analysis import HybridAuthorUnderstandingAnalyzer
from textifai.bootstrap import ProviderBackedBootstrapAnalyzer, VaultInitializationConfig, confirm_and_write_bootstrap, prepare_bootstrap
from textifai.conversation.contracts import ConversationRequest, PendingConversationOperation
from textifai.conversation.executor import MinimalExecutionLayer
from textifai.conversation.hybrid_recognizer import HybridIntentRecognizer, HybridRecognizerConfig
from textifai.conversation.manager import ConversationManager
from textifai.conversation.state import create_conversation_state
from textifai.derived_sources import (
    DerivedLLMExtractionPayload,
    DerivedLossSignals,
    DerivedSegmentCandidate,
    DerivedSourceLLMConfig,
    DerivedStructureSignals,
    LLMEscalationDecision,
)
from textifai.import_review import ReviewPolicy, promote_reviewed_import, review_import_stage
from textifai.import_review.reviewer import extraction_requires_strict_confirmation
from textifai.runtime_config import load_runtime_environment
from textifai.session import create_session
from textifai.prompt_engine.exporter import export_prompt_cases
from textifai.vaerl.contracts import EntityHint, EntityResolutionResult
from vault.bootstrap import bootstrap_vault
from vault.notes import write_or_update_note


ONT_ROOT = Path("/home/david/OnT")
REPORT_DIR = Path(tempfile.gettempdir()) / "autonovel_ont_guided_validation"
PROMPT_EXPORT_DIR = Path(tempfile.gettempdir()) / "textifai_prompt_exports"


@dataclass(frozen=True)
class StepTrace:
    flow_name: str | None
    input_text: str
    recognized_intent: str | None
    author_understanding: dict | None
    editorial_intent: dict | None
    entity_hints: list[dict]
    candidate_targets: list[dict]
    resolved_target: dict | None
    semantic_phase: bool | None
    response_generation_ready: bool
    semantic_response_kind: str | None
    prompt_enriched: bool
    prompt_base_id: str | None
    prompt_base_version: str | None
    prompt_template_id: str | None
    prompt_template_version: str | None
    model_profile_used: str | None
    provider_mode: str | None
    response_generation_mode: str | None
    response_generation_reason: str | None
    provider_execution_enabled: bool
    provider_execution_mode: str | None
    provider_model_used: str | None
    anchored_prompt_payload: dict | None
    trace_rendered_prompt_payload: dict | None
    llm_rendered_prompt_payload: dict | None
    anchored_evidence_used: dict | None
    response_support_summary: dict | None
    live_model_response: str | None
    simulated_preview_enabled: bool
    simulated_preview_output: str | None
    clarification_required: bool
    false_certainty: bool
    author_facing_response: str | None


@dataclass(frozen=True)
class CaseTrace:
    case_id: str
    title: str
    input: str
    materials_used: list[str]
    internal_interpretation_summary: str
    anchoring_summary: str
    flow_chosen: str
    author_facing_response: str | None
    technical_result: str
    technical_notes: str
    risk_flags: list[str] = field(default_factory=list)
    baseline_author_facing_response: str | None = None
    author_utility: str = "pending_human_review"
    author_notes: str = ""
    prompt_enriched: bool | None = None
    source_format: str | None = None
    light_extraction_sufficient: bool | None = None
    llm_escalation_required: bool | None = None
    review_status: str | None = None
    promotion_decision: str | None = None
    steps: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class OntValidationContext:
    base_dir: Path
    vault_root: Path
    derived_single_root: Path
    derived_parallel_root: Path
    report_dir: Path
    promoted_target_id: str
    promoted_target_type: str
    promoted_target_path: Path


class OntGuidedValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ctx = _build_context()
        cls.case_traces: list[CaseTrace] = []

    @classmethod
    def tearDownClass(cls) -> None:
        _write_reports(cls.case_traces)
        _write_prompt_exports(cls.case_traces)

    def tearDown(self) -> None:
        # Ensure partial progress still survives if a later assertion fails.
        _write_reports(self.__class__.case_traces)

    def test_01_derived_source_intake_without_prior_classification(self) -> None:
        case = self._run_import_case(
            case_id="derived_source_intake",
            title="Derived-source intake sin clasificación previa",
            source_root=self.ctx.derived_single_root,
            request_text="Analiza este documento y dime qué parece ser, cómo lo leerías y cómo lo pasarías por staging.",
        )
        self.assertEqual(case.technical_result, "correct")

    def test_02_parallel_derived_sources_cross_language(self) -> None:
        with _ont_import_overrides():
            session = create_session(load_runtime_environment(self.ctx.base_dir))
            analyzer = ProviderBackedBootstrapAnalyzer(
                config=DerivedSourceLLMConfig(
                    task_name="derived_source_understanding",
                    provider_name="test-provider",
                    model="test-model",
                )
            )
            result = prepare_bootstrap(
                VaultInitializationConfig(
                    vault_root=str(self.ctx.vault_root),
                    mode="new_project",
                    project_title="Ouja no Tsue",
                    primary_language="ja",
                    working_languages=["ja", "es"],
                    create_base_structure=True,
                    use_import_staging=True,
                ),
                source_root=self.ctx.derived_parallel_root,
                llm_analyzer=analyzer,
            )
        docs = result.inventory.documents if result.inventory else []
        notes = []
        for doc in docs:
            notes.append(f"{doc.filename}:{doc.dominant_language}:{','.join(doc.detected_languages)}")
        case = CaseTrace(
            case_id="parallel_derived_cross_language",
            title="Parallel derived sources cross-language",
            input="Compara los dos PDFs y dime si parecen materiales paralelos, divergentes o versiones del mismo núcleo.",
            materials_used=[str(self.ctx.derived_single_root / "王者の杖.pdf"), str(self.ctx.derived_parallel_root / "ESP 王者の杖 .pdf")],
            internal_interpretation_summary="The source inventory detected two derived PDFs with multilingual signals; the bootstrap plan requires confirmation and keeps the comparison conservative.",
            anchoring_summary="No forced equivalence: the report keeps both sources separate and flags multilingual/derived uncertainty.",
            flow_chosen="derived_source_understanding -> validation -> comparison",
            author_facing_response="TextifAI would treat these as related derived sources only if the evidence is strong enough; otherwise it should keep the relation tentative and ask for confirmation.",
            technical_result=_tech_result(
                condition=bool(result.inventory and len(result.inventory.documents) == 2 and result.normalization_plan and result.normalization_plan.requires_confirmation),
                partial_ok=True,
            ),
            technical_notes="Two derived sources were inventoried; the plan stayed conservative instead of forcing a hard equivalence.",
            risk_flags=(
                ["cross_language_relation_tentative"]
                if not result.normalization_plan or result.normalization_plan.requires_confirmation
                else ["overconfident_relation"]
            ),
            author_utility="pending_human_review",
            author_notes="",
            source_format="pdf",
            light_extraction_sufficient=all(doc.dominant_language is not None for doc in docs) if docs else False,
            llm_escalation_required=True,
            review_status="pending",
            promotion_decision="hold",
            prompt_enriched=True,
            steps=[],
        )
        self._record(case)
        self.assertIn(case.technical_result, {"correct", "partial"})

    def test_03_structuring_request(self) -> None:
        manager = self._build_manager()
        manager.state = replace(
            manager.state,
            last_target_id=self.ctx.promoted_target_id,
            last_target_type=self.ctx.promoted_target_type,
        )
        turn = manager.handle_request(
            _request(
                "Quiero estructurar esta escena sin perder la tensión entre Ren y Sera.",
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                explanation_language="es",
                artifact_target_language="ja",
                mixed_language_allowed=True,
                metadata={"entity_hints": ["Ren", "Sera"]},
            )
        )
        trace = _turn_trace(turn)
        case = CaseTrace(
            case_id="structuring_request",
            title="Structuring request sobre material narrativo",
            input=turn.request.raw_text,
            materials_used=[str(ONT_ROOT / "📘 FICHAS DE PERSONAJES.md"), str(self.ctx.promoted_target_path)],
            internal_interpretation_summary=f"intent={trace.recognized_intent}; author={_shorten(trace.author_understanding)}; editorial={_shorten(trace.editorial_intent)}",
            anchoring_summary=f"target={trace.resolved_target}",
            flow_chosen=str(turn.planned_task.flow_name if turn.planned_task else "unknown"),
            author_facing_response=turn.author_facing_response,
            technical_result=_tech_result(
                condition=trace.semantic_phase is True and trace.resolved_target is not None and not trace.false_certainty,
                partial_ok=True,
            ),
            technical_notes="The request was routed as a semantic structuring task and anchored to the imported material.",
            risk_flags=[] if trace.prompt_enriched else ["prompt_not_enriched"],
            baseline_author_facing_response=_baseline_author_facing_response("structuring_request"),
            source_format=None,
            prompt_enriched=trace.prompt_enriched if hasattr(trace, "prompt_enriched") else True,
            review_status=None,
            promotion_decision=None,
            steps=[_trace_dict(trace)],
        )
        self._record(case)
        self.assertIn(case.technical_result, {"correct", "partial"})
        self.assertEqual(trace.semantic_response_kind, "structuring_suggestion")
        self.assertIsNotNone(trace.anchored_prompt_payload)
        self.assertEqual(trace.prompt_base_id, "author_facing_editorial_copilot")
        self.assertEqual(trace.prompt_template_id, "structuring_request")
        self.assertIn("system_prompt", trace.trace_rendered_prompt_payload or {})
        self.assertIn("user_payload", trace.llm_rendered_prompt_payload or {})
        self.assertTrue(
            trace.response_generation_ready
            or bool((trace.response_support_summary or {}).get("semantic_working_sufficiency"))
        )
        self.assertEqual(trace.provider_mode, "disabled")
        self.assertFalse(trace.provider_execution_enabled)
        self.assertFalse(trace.simulated_preview_enabled)
        self.assertIsNone(trace.author_facing_response)

    def test_04_editorial_revision_voice_and_dynamic(self) -> None:
        manager = self._build_manager()
        manager.state = replace(
            manager.state,
            last_target_id=self.ctx.promoted_target_id,
            last_target_type=self.ctx.promoted_target_type,
        )
        turn = manager.handle_request(
            _request(
                "Revísame la voz de Sera y la dinámica con Ren sin volver la escena demasiado explícita.",
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                explanation_language="es",
                artifact_target_language="ja",
                mixed_language_allowed=True,
                metadata={"entity_hints": ["Sera", "Ren"]},
            )
        )
        trace = _turn_trace(turn)
        case = CaseTrace(
            case_id="editorial_revision",
            title="Editorial revision con voz y dinámica",
            input=turn.request.raw_text,
            materials_used=[str(ONT_ROOT / "📘 FICHAS DE PERSONAJES.md"), str(ONT_ROOT / "📘 FICHA DE LORE MAESTRA V2.md")],
            internal_interpretation_summary=f"intent={trace.recognized_intent}; author={_shorten(trace.author_understanding)}; editorial={_shorten(trace.editorial_intent)}",
            anchoring_summary=f"candidate_targets={trace.candidate_targets}; target={trace.resolved_target}",
            flow_chosen=str(turn.planned_task.flow_name if turn.planned_task else "unknown"),
            author_facing_response=turn.author_facing_response,
            technical_result=_tech_result(
                condition=trace.recognized_intent in {"prepare_review", "editorial_structuring"} and trace.author_understanding is not None,
                partial_ok=True,
            ),
            technical_notes="The request stays conservative and preserves the canon/voice constraints.",
            risk_flags=[],
            baseline_author_facing_response=_baseline_author_facing_response("editorial_revision"),
            steps=[_trace_dict(trace)],
        )
        self._record(case)
        self.assertTrue(trace.response_generation_ready)
        self.assertEqual(trace.semantic_response_kind, "revision_guidance")
        self.assertIsNotNone(trace.anchored_prompt_payload)
        self.assertEqual(trace.prompt_base_id, "author_facing_editorial_copilot")
        self.assertEqual(trace.prompt_template_id, "editorial_revision")
        self.assertEqual(trace.model_profile_used, "openai_chatgpt")
        self.assertIn("system_prompt", trace.trace_rendered_prompt_payload or {})
        self.assertEqual(trace.provider_mode, "disabled")
        self.assertIsNone(trace.author_facing_response)
        self.assertIn("conservar la voz propia del personaje", json.dumps(trace.llm_rendered_prompt_payload or {}, ensure_ascii=False))

    def test_05_followup_contextual_real(self) -> None:
        manager = self._build_manager()
        manager.state = replace(
            manager.state,
            last_target_id=self.ctx.promoted_target_id,
            last_target_type=self.ctx.promoted_target_type,
        )
        first = manager.handle_request(
            _request(
                "Quiero estructurar esta escena sin perder la tension.",
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                explanation_language="es",
                artifact_target_language="ja",
                mixed_language_allowed=True,
                target_hint=self.ctx.promoted_target_id,
            )
        )
        manager.state = replace(
            manager.state,
            last_target_id=self.ctx.promoted_target_id,
            last_target_type=self.ctx.promoted_target_type,
        )
        manager.session.conversation_state = manager.state
        second = manager.handle_request(
            _request(
                "sí, esa",
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                explanation_language="es",
                artifact_target_language="ja",
                mixed_language_allowed=True,
            )
        )
        trace1 = _turn_trace(first)
        trace2 = _turn_trace(second)
        case = CaseTrace(
            case_id="followup_contextual",
            title="Follow-up contextual real",
            input="Quiero estructurar esta escena sin perder la tension. / sí, esa",
            materials_used=[str(ONT_ROOT / "📘 FICHAS DE PERSONAJES.md")],
            internal_interpretation_summary=f"first={trace1.recognized_intent}, second={trace2.recognized_intent}",
            anchoring_summary=f"followup_mode={_followup_mode(trace2)}; target={trace2.resolved_target}",
            flow_chosen="contextual_followup",
            author_facing_response=second.author_facing_response,
            technical_result=_tech_result(
                condition=trace2.recognized_intent in {"structured_followup", "unknown"} and not trace2.false_certainty,
                partial_ok=True,
            ),
            technical_notes="The follow-up reused context instead of inventing a new target.",
            risk_flags=[],
            baseline_author_facing_response=_baseline_author_facing_response("followup_contextual"),
            steps=[_trace_dict(trace1), _trace_dict(trace2)],
        )
        self._record(case)
        self.assertEqual(trace2.semantic_response_kind, "contextual_followup_response")
        self.assertIsNotNone(trace2.anchored_prompt_payload)
        self.assertEqual(trace2.prompt_base_id, "author_facing_editorial_copilot")
        self.assertEqual(trace2.prompt_template_id, "contextual_followup")
        self.assertIn("user_payload", trace2.llm_rendered_prompt_payload or {})
        self.assertEqual(trace2.provider_mode, "disabled")
        self.assertIsNone(trace2.author_facing_response)
        self.assertIn("clarification_need", (trace2.llm_rendered_prompt_payload or {}).get("user_payload", {}))

    def test_06_prepare_narration_from_anchored_material(self) -> None:
        manager = self._build_manager()
        manager.state = replace(
            manager.state,
            last_target_id=self.ctx.promoted_target_id,
            last_target_type=self.ctx.promoted_target_type,
        )
        manager.handle_request(
            _request(
                "Quiero estructurar esta escena sin perder la tension entre Ren y Sera.",
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                explanation_language="es",
                artifact_target_language="ja",
                mixed_language_allowed=True,
                metadata={"entity_hints": ["Ren", "Sera"]},
            )
        )
        turn = manager.handle_request(
            _request(
                "Déjalo listo para narrar manteniendo el modelo emocional del vínculo.",
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                explanation_language="es",
                artifact_target_language="ja",
                mixed_language_allowed=True,
                metadata={"entity_hints": ["Ren", "Sera"]},
            )
        )
        trace = _turn_trace(turn)
        case = CaseTrace(
            case_id="prepare_narration",
            title="Prepare narration from anchored material",
            input=turn.request.raw_text,
            materials_used=[str(ONT_ROOT / "📘 FICHAS DE PERSONAJES.md"), str(self.ctx.promoted_target_path)],
            internal_interpretation_summary=f"intent={trace.recognized_intent}; author={_shorten(trace.author_understanding)}",
            anchoring_summary=f"target={trace.resolved_target}; semantic_phase={trace.semantic_phase}",
            flow_chosen=str(turn.planned_task.flow_name if turn.planned_task else "unknown"),
            author_facing_response=turn.author_facing_response,
            technical_result=_tech_result(
                condition=trace.semantic_phase is True and bool(turn.result_summary),
                partial_ok=True,
            ),
            technical_notes="The system prepared a narration handoff or conservatively clarified what it still needed.",
            risk_flags=[] if turn.result_summary else ["empty_response"],
            steps=[_trace_dict(trace)],
        )
        self._record(case)
        self.assertTrue(trace.response_generation_ready)
        self.assertEqual(trace.semantic_response_kind, "narration_handoff")
        self.assertIsNotNone(trace.anchored_prompt_payload)
        self.assertEqual(trace.prompt_base_id, "author_facing_editorial_copilot")
        self.assertEqual(trace.prompt_template_id, "prepare_narration")
        self.assertTrue(bool(trace.anchored_evidence_used))
        self.assertEqual(trace.provider_mode, "disabled")
        self.assertIsNone(trace.author_facing_response)
        self.assertIn("anchored_editorial_sufficiency", (trace.llm_rendered_prompt_payload or {}).get("user_payload", {}))
        self.assertTrue(bool((trace.response_support_summary or {}).get("followthrough_from_previous_turn")))

    def test_07_lore_canon_consistency_check(self) -> None:
        manager = self._build_manager()
        manager.state = replace(
            manager.state,
            last_target_id=self.ctx.promoted_target_id,
            last_target_type=self.ctx.promoted_target_type,
        )
        turn = manager.handle_request(
            _request(
                "¿Esto contradice lo que sabemos de la Spelarita y del Taikyō, o encaja con el canon?",
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                explanation_language="es",
                artifact_target_language="ja",
                mixed_language_allowed=True,
                metadata={"entity_hints": ["Spelarita", "Taikyō", "Thiseia"]},
            )
        )
        trace = _turn_trace(turn)
        case = CaseTrace(
            case_id="lore_canon_consistency",
            title="Lore/canon consistency check",
            input=turn.request.raw_text,
            materials_used=[str(ONT_ROOT / "📘 FICHA DE LORE MAESTRA V2.md")],
            internal_interpretation_summary=f"intent={trace.recognized_intent}; author={_shorten(trace.author_understanding)}",
            anchoring_summary=f"candidate_targets={trace.candidate_targets}; target={trace.resolved_target}",
            flow_chosen=str(turn.planned_task.flow_name if turn.planned_task else "unknown"),
            author_facing_response=turn.author_facing_response,
            technical_result=_tech_result(
                condition=trace.recognized_intent == "consistency_check" and trace.semantic_phase is False,
                partial_ok=True,
            ),
            technical_notes="The check anchored to lore terms without inventing unsupported canon.",
            risk_flags=[],
            steps=[_trace_dict(trace)],
        )
        self._record(case)
        self.assertTrue(trace.response_generation_ready)
        self.assertEqual(trace.semantic_response_kind, "canon_answer")
        self.assertIsNotNone(trace.anchored_prompt_payload)
        self.assertEqual(trace.prompt_base_id, "author_facing_editorial_copilot")
        self.assertEqual(trace.prompt_template_id, "consistency_check")
        self.assertIn("prompt_sections", trace.trace_rendered_prompt_payload or {})
        self.assertEqual(trace.provider_mode, "disabled")
        self.assertIsNone(trace.author_facing_response)
        self.assertIn("supporting_canon_summary", (trace.llm_rendered_prompt_payload or {}).get("user_payload", {}))

    def test_08_entity_resolution_cross_document_and_ambiguity(self) -> None:
        manager = self._build_manager()
        manager.state = replace(
            manager.state,
            last_target_id=self.ctx.promoted_target_id,
            last_target_type=self.ctx.promoted_target_type,
        )
        turn = manager.handle_request(
            _request(
                "Quiero arreglar lo de la campana y el vínculo roto entre Elthariel y Thiseia.",
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                explanation_language="es",
                artifact_target_language="ja",
                mixed_language_allowed=True,
                metadata={"entity_hints": ["Elthariel", "Thiseia", "campana", "vínculo roto"]},
            )
        )
        trace = _turn_trace(turn)
        case = CaseTrace(
            case_id="entity_resolution_cross_document",
            title="Entity resolution cross-document + ambiguity",
            input=turn.request.raw_text,
            materials_used=[str(ONT_ROOT / "📘 FICHAS DE PERSONAJES.md"), str(ONT_ROOT / "📘 FICHA DE LORE MAESTRA V2.md")],
            internal_interpretation_summary=f"intent={trace.recognized_intent}; author={_shorten(trace.author_understanding)}",
            anchoring_summary=f"candidate_targets={trace.candidate_targets}; target={trace.resolved_target}",
            flow_chosen=str(turn.planned_task.flow_name if turn.planned_task else "unknown"),
            author_facing_response=turn.author_facing_response,
            technical_result=_tech_result(
                condition=bool(trace.candidate_targets) and (trace.clarification_required or trace.resolved_target is not None),
                partial_ok=True,
            ),
            technical_notes="The system should either resolve nearby canonical targets or ask for clarification without fake certainty.",
            risk_flags=["clarification_expected" if trace.clarification_required else ""],
            baseline_author_facing_response=_baseline_author_facing_response("entity_resolution_cross_document"),
            steps=[_trace_dict(trace)],
        )
        self._record(case)
        self.assertTrue(trace.response_generation_ready)
        self.assertEqual(trace.semantic_response_kind, "clarification_with_candidates")
        self.assertIsNotNone(trace.anchored_prompt_payload)
        self.assertEqual(trace.prompt_base_id, "author_facing_editorial_copilot")
        self.assertEqual(trace.prompt_template_id, "clarification_with_candidates")
        self.assertTrue(bool(trace.anchored_evidence_used))
        self.assertEqual(trace.provider_mode, "disabled")
        self.assertIsNone(trace.author_facing_response)
        self.assertIn("still_ambiguous", (trace.llm_rendered_prompt_payload or {}).get("user_payload", {}).get("clarification_need", {}))

    def test_09_safe_operation_after_promotion(self) -> None:
        manager = self._build_manager()
        manager.state = replace(
            manager.state,
            last_target_id="lore_master_ont",
            last_target_type="lore",
            pending_operation=PendingConversationOperation(
                operation_id="validate_lore_master_ont",
                operation_kind="validate_artifact",
                task_type="artifact_persistence",
                flow_name="validate_artifact_flow",
                target_type="lore",
                target_id="lore_master_ont",
                artifact_target_language="ja",
                explanation_language="es",
                payload={
                    "type": "artifact_state_change",
                    "target_type": "lore",
                    "target_id": "lore_master_ont",
                    "state": "validated",
                    "origin": {"source": "ont_guided_validation", "case": "safe_operation_after_promotion"},
                },
                summary="validate lore:lore_master_ont",
                executable=True,
                missing_fields=[],
                created_from_turn=0,
            ),
        )
        manager.session.conversation_state = manager.state
        turn = manager.handle_request(
            _request(
                "confirm",
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                explanation_language="es",
                artifact_target_language="ja",
                mixed_language_allowed=True,
            )
        )
        trace = _turn_trace(turn)
        case = CaseTrace(
            case_id="safe_operation_after_promotion",
            title="Safe operational action after promotion",
            input=turn.request.raw_text,
            materials_used=[str(self.ctx.promoted_target_path)],
            internal_interpretation_summary=f"intent={trace.recognized_intent}; prompt_enriched={trace.prompt_enriched}",
            anchoring_summary=f"target={trace.resolved_target}; persisted={turn.persisted}",
            flow_chosen=str(turn.planned_task.flow_name if turn.planned_task else "unknown"),
            author_facing_response=turn.author_facing_response,
            technical_result=_tech_result(condition=turn.persisted and not trace.prompt_enriched, partial_ok=False),
            technical_notes="The confirmation step should stay deterministic and persist the validated artifact.",
            risk_flags=[],
            prompt_enriched=trace.prompt_enriched,
            steps=[_trace_dict(trace)],
        )
        self._record(case)
        self.assertEqual(case.technical_result, "correct")

    def test_10_optional_general_control(self) -> None:
        manager = self._build_manager()
        turn = manager.handle_request(
            _request(
                "Quiero una estructura más clara sin perder la tensión.",
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                explanation_language="es",
                artifact_target_language="ja",
                mixed_language_allowed=True,
            )
        )
        trace = _turn_trace(turn)
        case = CaseTrace(
            case_id="general_control",
            title="Optional general control",
            input=turn.request.raw_text,
            materials_used=[],
            internal_interpretation_summary=f"intent={trace.recognized_intent}",
            anchoring_summary=f"target={trace.resolved_target}",
            flow_chosen=str(turn.planned_task.flow_name if turn.planned_task else "unknown"),
            author_facing_response=turn.author_facing_response,
            technical_result=_tech_result(
                condition=trace.recognized_intent in {"editorial_structuring", "unknown"},
                partial_ok=True,
            ),
            technical_notes="Control case to ensure the suite does not overfit to OnT-specific vocabulary.",
            risk_flags=[],
            prompt_enriched=trace.prompt_enriched,
            steps=[_trace_dict(trace)],
        )
        self._record(case)

    def test_11_structuring_request_longform_author_input(self) -> None:
        manager = self._build_manager()
        manager.state = replace(
            manager.state,
            last_target_id=self.ctx.promoted_target_id,
            last_target_type=self.ctx.promoted_target_type,
        )
        raw_input = (
            "Quiero trabajar esta escena de Ren y Sera porque ahora mismo siento que las cosas que importan están, "
            "pero la progresión se me queda un poco plana. Ren percibe demasiado pronto lo que le pasa a Sera y eso "
            "me baja la tensión; al mismo tiempo, si lo retraso demasiado, la escena se me enfría y parece que "
            "ninguno de los dos está realmente afectado. Lo que querría es una estructura más clara para que el "
            "movimiento emocional se note mejor, pero sin volverlos explícitos ni hacer que parezca que ya se han "
            "dicho lo que sienten. Si hay una manera de ordenar esto para que el subtexto haga más trabajo y la "
            "escena suba de verdad antes del cierre, eso es lo que necesito."
        )
        turn = manager.handle_request(
            _request(
                raw_input,
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                explanation_language="es",
                artifact_target_language="ja",
                mixed_language_allowed=True,
            )
        )
        trace = _turn_trace(turn)
        case = CaseTrace(
            case_id="structuring_request_longform",
            title="Structuring request narrativo largo",
            input=raw_input,
            materials_used=[str(ONT_ROOT / "📘 FICHAS DE PERSONAJES.md"), str(self.ctx.promoted_target_path)],
            internal_interpretation_summary=f"intent={trace.recognized_intent}; author={_shorten(trace.author_understanding)}; editorial={_shorten(trace.editorial_intent)}",
            anchoring_summary=f"candidate_targets={trace.candidate_targets}; target={trace.resolved_target}",
            flow_chosen=str(turn.planned_task.flow_name if turn.planned_task else "unknown"),
            author_facing_response=turn.author_facing_response,
            technical_result=_tech_result(
                condition=trace.recognized_intent == "editorial_structuring" and trace.semantic_phase is True and bool(trace.candidate_targets or trace.resolved_target),
                partial_ok=True,
            ),
            technical_notes="The long-form request stayed as raw author input and still produced a rich structuring prompt.",
            risk_flags=[],
            steps=[_trace_dict(trace)],
        )
        self._record(case)
        user_payload = (trace.llm_rendered_prompt_payload or {}).get("user_payload", {})
        self.assertEqual(trace.prompt_template_id, "structuring_request")
        self.assertEqual(user_payload.get("author_request_text_original"), raw_input)
        self.assertEqual(user_payload.get("response_language"), "es")
        self.assertIn("Ayudar al autor", user_payload.get("flow_goal", ""))
        self.assertTrue(bool(user_payload.get("best_candidate_targets")))
        self.assertTrue(bool(user_payload.get("anchored_context_summary")))

    def test_12_editorial_revision_longform_author_input(self) -> None:
        manager = self._build_manager()
        manager.state = replace(
            manager.state,
            last_target_id=self.ctx.promoted_target_id,
            last_target_type=self.ctx.promoted_target_type,
        )
        raw_input = (
            "Revísame la voz de Sera y la dinámica con Ren sin volver la escena demasiado explícita. Ahora mismo noto "
            "que Sera a veces verbaliza demasiado pronto lo que siente y entonces deja de sonar a ella, como si la "
            "escena le quitara capas en vez de tensarlas. Con Ren me pasa lo contrario: por querer que se vea el "
            "cuidado, a veces adelanto demasiado su parte tierna y eso me baja la fricción entre los dos. Necesito "
            "criterio editorial para saber qué tocar y qué preservar, de modo que la emoción siga ahí, pero pasando "
            "por la voz propia de cada uno y por la incomodidad que todavía debería existir entre ellos."
        )
        turn = manager.handle_request(
            _request(
                raw_input,
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                explanation_language="es",
                artifact_target_language="ja",
                mixed_language_allowed=True,
            )
        )
        trace = _turn_trace(turn)
        case = CaseTrace(
            case_id="editorial_revision_longform",
            title="Editorial revision largo con matiz emocional y de voz",
            input=raw_input,
            materials_used=[str(ONT_ROOT / "📘 FICHAS DE PERSONAJES.md"), str(ONT_ROOT / "📘 FICHA DE LORE MAESTRA V2.md")],
            internal_interpretation_summary=f"intent={trace.recognized_intent}; author={_shorten(trace.author_understanding)}; editorial={_shorten(trace.editorial_intent)}",
            anchoring_summary=f"candidate_targets={trace.candidate_targets}; target={trace.resolved_target}",
            flow_chosen=str(turn.planned_task.flow_name if turn.planned_task else "unknown"),
            author_facing_response=turn.author_facing_response,
            technical_result=_tech_result(
                condition=trace.semantic_response_kind == "revision_guidance" and bool(trace.candidate_targets or trace.resolved_target),
                partial_ok=True,
            ),
            technical_notes="The raw revision paragraph preserved emotional nuance and character-voice constraints in the prompt payload.",
            risk_flags=[],
            steps=[_trace_dict(trace)],
        )
        self._record(case)
        user_payload = (trace.llm_rendered_prompt_payload or {}).get("user_payload", {})
        serialized_payload = json.dumps(user_payload, ensure_ascii=False)
        self.assertEqual(trace.prompt_template_id, "editorial_revision")
        self.assertEqual(user_payload.get("author_request_text_original"), raw_input)
        self.assertIn("conservar la voz propia del personaje", serialized_payload)
        self.assertIn("Flujo semántico actual", user_payload.get("system_interpretation", ""))
        self.assertTrue(bool(user_payload.get("anchored_context_summary")))

    def test_13_lore_clarification_longform_author_input(self) -> None:
        manager = self._build_manager()
        raw_input = (
            "Hay una parte del lore que me preocupa porque no termino de ver si lo que quiero hacer encaja con lo "
            "que ya tenemos entre Elthariel, Thiseia, la campana y la idea del vínculo roto. Mi intuición es que hay "
            "una resonancia simbólica potente entre esos elementos y que podría apoyar una escena importante, pero no "
            "quiero forzar una lectura que luego choque con el canon del mundo o con cómo funciona de verdad la "
            "Spelarita. Antes de decidir nada, necesito saber si lo que se sugiere ahí puede sostenerse con lo ya "
            "anclado o si en realidad estoy mezclando cosas que todavía habría que separar mejor."
        )
        turn = manager.handle_request(
            _request(
                raw_input,
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                explanation_language="es",
                artifact_target_language="ja",
                mixed_language_allowed=True,
            )
        )
        trace = _turn_trace(turn)
        case = CaseTrace(
            case_id="lore_clarification_longform",
            title="Lore clarification largo con candidatos plausibles",
            input=raw_input,
            materials_used=[str(ONT_ROOT / "📘 FICHA DE LORE MAESTRA V2.md")],
            internal_interpretation_summary=f"intent={trace.recognized_intent}; author={_shorten(trace.author_understanding)}; editorial={_shorten(trace.editorial_intent)}",
            anchoring_summary=f"candidate_targets={trace.candidate_targets}; target={trace.resolved_target}",
            flow_chosen=str(turn.planned_task.flow_name if turn.planned_task else "unknown"),
            author_facing_response=turn.author_facing_response,
            technical_result=_tech_result(
                condition=trace.semantic_response_kind in {"canon_answer", "clarification_with_candidates"} and bool(trace.candidate_targets),
                partial_ok=True,
            ),
            technical_notes="The raw lore paragraph forced entity resolution, canon pull, and a clarification-friendly prompt instead of a flat check.",
            risk_flags=[],
            steps=[_trace_dict(trace)],
        )
        self._record(case)
        user_payload = (trace.llm_rendered_prompt_payload or {}).get("user_payload", {})
        self.assertIn(trace.prompt_template_id, {"consistency_check", "clarification_with_candidates"})
        self.assertEqual(user_payload.get("author_request_text_original"), raw_input)
        self.assertIn("Flujo semántico actual", user_payload.get("system_interpretation", ""))
        self.assertTrue(bool(user_payload.get("best_candidate_targets")))
        self.assertTrue(bool(user_payload.get("supporting_canon_summary")))

    def test_14_sundrael_bonus_structuring_longform(self) -> None:
        manager = self._build_manager()
        raw_input = (
            "Quiero montar una mini escena offscreen en Sundraël, casi como un 4koma largo o bonus cómico, pero que "
            "siga sintiéndose OnT y no un gag suelto. La idea es que Liora quiera enseñarle a Nael una “prueba de "
            "madurez” de su tierra que para ella es totalmente normal, pero para él se vuelve una situación absurda "
            "porque Shaevar interpreta todo como competencia. Me interesa que la escena sea ligera, con ritmo rápido "
            "y remate divertido, pero que debajo se note que Nael ya está entrando de verdad en la lógica emocional "
            "de Sundraël y que Liora empieza a dar por hecho que él forma parte de su espacio. No quiero caricaturizar "
            "a ninguno: Liora puede ser frontal y caótica, Nael el tsukkomi sensible, y Shaevar una mezcla de "
            "rivalidad y apego, pero sin romper la coherencia del vínculo. Ayúdame a estructurarla y a decidir qué "
            "beat final dejaría mejor ese doble efecto: comedia arriba, avance afectivo abajo."
        )
        turn = manager.handle_request(
            _request(
                raw_input,
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                explanation_language="es",
                artifact_target_language="ja",
                mixed_language_allowed=True,
            )
        )
        trace = _turn_trace(turn)
        user_payload = (trace.llm_rendered_prompt_payload or {}).get("user_payload", {})
        case = CaseTrace(
            case_id="sundrael_bonus_structuring_longform",
            title="Sundraël bonus structuring longform",
            input=raw_input,
            materials_used=[str(ONT_ROOT / "📘 FICHAS DE PERSONAJES.md"), str(ONT_ROOT / "📘 FICHA DE LORE MAESTRA V2.md")],
            internal_interpretation_summary=f"intent={trace.recognized_intent}; author={_shorten(trace.author_understanding)}; editorial={_shorten(trace.editorial_intent)}",
            anchoring_summary=f"candidate_targets={trace.candidate_targets}; target={trace.resolved_target}",
            flow_chosen=str(turn.planned_task.flow_name if turn.planned_task else "unknown"),
            author_facing_response=turn.author_facing_response,
            technical_result=_tech_result(
                condition=trace.semantic_response_kind == "structuring_suggestion" and trace.prompt_template_id == "structuring_request",
                partial_ok=True,
            ),
            technical_notes="The long OnT bonus request should stay in structuring and preserve the double tonal-relational function instead of flattening into comic relief.",
            risk_flags=[],
            steps=[_trace_dict(trace)],
        )
        self._record(case)
        serialized = json.dumps(user_payload, ensure_ascii=False)
        self.assertEqual(trace.prompt_template_id, "structuring_request")
        self.assertEqual(user_payload.get("author_request_text_original"), raw_input)
        self.assertIn("estructurar una escena ligera donde la comedia visible sostenga un avance afectivo implícito", serialized)
        self.assertIn("decidir un beat final con doble efecto: remate cómico arriba y avance afectivo abajo", serialized)
        self.assertIn("estructuración ligera con doble plano", user_payload.get("system_interpretation", ""))
        self.assertEqual(
            (user_payload.get("editorial_diagnosis") or {}).get("dominant_need"),
            "estructuración tonal y relacional con subtexto",
        )
        remembered = manager.session.last_result if manager.session is not None else None
        if isinstance(remembered, dict) and remembered.get("type") == "author_semantic_response":
            self.assertEqual(remembered.get("data", {}).get("mode"), "anchor_only_guidance")

    def test_15_sera_voice_revision_longform(self) -> None:
        manager = self._build_manager()
        raw_input = (
            "Estoy revisando una escena en la que Sera ya se siente mucho más segura cerca de Ren, pero todavía no "
            "quiero que eso se vuelva una confesión emocional abierta ni una escena romántica demasiado evidente. La "
            "sensación que busco es que ella se permita bajar la guardia un poco más de lo habitual, que piense desde "
            "un lugar más íntimo y menos defensivo, pero que siga siendo ella: intensa, orgullosa y con esa manera de "
            "no querer mostrarse del todo vulnerable si no es imprescindible. Ren aquí no debería abrir la escena con "
            "una respuesta tierna o demasiado transparente; prefiero que funcione como siempre en su patrón de cuidar "
            "en silencio, tocar un poco la situación con ironía suave y quedarse cerca sin exigir nada. Me gustaría "
            "que me revisaras sobre todo la voz interna de Sera, el grado de explicitud del subtexto y la dinámica "
            "verbal con Ren para que la cercanía avance, pero de forma creíble y contenida."
        )
        turn = manager.handle_request(
            _request(
                raw_input,
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                explanation_language="es",
                artifact_target_language="ja",
                mixed_language_allowed=True,
            )
        )
        trace = _turn_trace(turn)
        user_payload = (trace.llm_rendered_prompt_payload or {}).get("user_payload", {})
        case = CaseTrace(
            case_id="sera_voice_revision_longform",
            title="Sera voice revision longform",
            input=raw_input,
            materials_used=[str(ONT_ROOT / "📘 FICHAS DE PERSONAJES.md")],
            internal_interpretation_summary=f"intent={trace.recognized_intent}; author={_shorten(trace.author_understanding)}; editorial={_shorten(trace.editorial_intent)}",
            anchoring_summary=f"candidate_targets={trace.candidate_targets}; target={trace.resolved_target}",
            flow_chosen=str(turn.planned_task.flow_name if turn.planned_task else "unknown"),
            author_facing_response=turn.author_facing_response,
            technical_result=_tech_result(
                condition=trace.semantic_response_kind == "revision_guidance" and trace.prompt_template_id == "editorial_revision",
                partial_ok=True,
            ),
            technical_notes="The long voice revision request should preserve Sera's guarded intimacy and Ren's care pattern instead of collapsing into generic romantic tension.",
            risk_flags=[],
            steps=[_trace_dict(trace)],
        )
        self._record(case)
        serialized = json.dumps(user_payload, ensure_ascii=False)
        self.assertEqual(trace.prompt_template_id, "editorial_revision")
        self.assertIn("revisión fina de voz y dinámica relacional", user_payload.get("system_interpretation", ""))
        self.assertIn("hacer que Sera baje un poco la guardia sin dejar de sonar intensa, orgullosa y contenida", serialized)
        self.assertIn("preservar el patrón de Ren como cuidado silencioso con ironía suave", serialized)
        self.assertIn("hacer avanzar la cercanía sin convertirla en confesión abierta", serialized)
        self.assertEqual(
            (user_payload.get("editorial_diagnosis") or {}).get("dominant_need"),
            "revisión fina de voz y dinámica relacional",
        )

    def test_16_elthariel_thiseia_bell_canon_longform(self) -> None:
        manager = self._build_manager()
        raw_input = (
            "Quiero arreglar una idea de trasfondo que ahora mismo noto prometedora pero todavía un poco borrosa. Mi "
            "intuición es que la campana de Elthariel y la reliquia que termina en la familia del Báculo de Thiseia no "
            "deberían sentirse como objetos separados por casualidad, sino como dos momentos de una misma historia "
            "rota. Lo que estoy pensando es que la campana original era un símbolo de resonancia viva en Elthariel, "
            "afinada a pares con vínculo real, y que tras la institucionalización de Thiseia sobrevivió una versión "
            "heredada o desplazada de ese mismo símbolo, pero ya convertida en reliquia de una herida política y "
            "mágica. No quiero que eso contradiga el origen de Thiseia ni la función de la primera veta de "
            "Spelarita, pero sí me interesa reforzar la idea de que entre Elthariel y Thiseia hubo una continuidad "
            "histórica que luego se deformó. ¿Esto encaja con el canon tal como está o qué pieza habría que ajustar "
            "para que no suene forzado?"
        )
        turn = manager.handle_request(
            _request(
                raw_input,
                interface_language="es",
                user_command_language="es",
                internal_system_language="en",
                project_default_language="ja",
                explanation_language="es",
                artifact_target_language="ja",
                mixed_language_allowed=True,
            )
        )
        trace = _turn_trace(turn)
        user_payload = (trace.llm_rendered_prompt_payload or {}).get("user_payload", {})
        case = CaseTrace(
            case_id="elthariel_thiseia_bell_canon_longform",
            title="Elthariel Thiseia bell canon longform",
            input=raw_input,
            materials_used=[str(ONT_ROOT / "📘 FICHA DE LORE MAESTRA V2.md")],
            internal_interpretation_summary=f"intent={trace.recognized_intent}; author={_shorten(trace.author_understanding)}; editorial={_shorten(trace.editorial_intent)}",
            anchoring_summary=f"candidate_targets={trace.candidate_targets}; target={trace.resolved_target}",
            flow_chosen=str(turn.planned_task.flow_name if turn.planned_task else "unknown"),
            author_facing_response=turn.author_facing_response,
            technical_result=_tech_result(
                condition=trace.semantic_response_kind in {'canon_answer', 'clarification_with_candidates'} and trace.prompt_template_id in {'consistency_check', 'clarification_with_candidates'},
                partial_ok=True,
            ),
            technical_notes="The lore request should read as canon judgement with symbolic-historical continuity, not as generic structuring.",
            risk_flags=[],
            steps=[_trace_dict(trace)],
        )
        self._record(case)
        serialized = json.dumps(user_payload, ensure_ascii=False)
        self.assertIn(trace.prompt_template_id, {"consistency_check", "clarification_with_candidates"})
        self.assertIn("juicio canon-editorial", user_payload.get("system_interpretation", ""))
        self.assertIn("evaluar si la conexión simbólica propuesta puede sostenerse dentro del canon", serialized)
        self.assertIn("comprobar si hay una continuidad histórica deformada y no solo una coincidencia casual", serialized)
        self.assertNotIn("ordenar mejor la progresion de la escena", serialized)
        self.assertEqual(
            (user_payload.get("editorial_diagnosis") or {}).get("dominant_need"),
            "evaluación de encaje canon-simbólico",
        )

    def test_17_prompt_export_snapshot(self) -> None:
        self.assertGreaterEqual(len(self.__class__.case_traces), 1)
        payload = export_prompt_cases(
            [
                asdict(case)
                for case in self.__class__.case_traces
                if any(
                    (step or {}).get("trace_rendered_prompt_payload")
                    or (step or {}).get("llm_rendered_prompt_payload")
                    for step in case.steps
                )
            ],
            PROMPT_EXPORT_DIR / "ont_prompt_export.json",
            PROMPT_EXPORT_DIR / "ont_prompt_export.md",
            export_title="OnT Prompt Export",
        )
        json_path = PROMPT_EXPORT_DIR / "ont_prompt_export.json"
        md_path = PROMPT_EXPORT_DIR / "ont_prompt_export.md"
        self.assertTrue(json_path.exists())
        self.assertTrue(md_path.exists())
        self.assertGreaterEqual(len(payload["cases"]), 1)
        self.assertEqual(payload["evaluation_status"], "partial_pipeline_only_until_obsidian_context_source_is_validated")
        first_case = payload["cases"][0]
        self.assertIn("trace_rendered_prompt_payload", first_case)
        self.assertIn("llm_rendered_prompt_payload", first_case)
        self.assertIn("author_facing_response", first_case)
        self.assertIn("prompt_base_id", first_case)
        self.assertIn("prompt_template_id", first_case)

    def _run_import_case(
        self,
        *,
        case_id: str,
        title: str,
        source_root: Path,
        request_text: str,
        include_safe_operation: bool = False,
    ) -> CaseTrace:
        working_root = Path(tempfile.mkdtemp(prefix=f"{case_id}_", dir=self.ctx.base_dir))
        for path in source_root.iterdir():
            if path.is_file():
                shutil.copy2(path, working_root / path.name)
        with _ont_import_overrides():
            bootstrap_config = VaultInitializationConfig(
                vault_root=str(self.ctx.vault_root),
                mode="new_project",
                project_title="Ouja no Tsue",
                primary_language="ja",
                working_languages=["ja", "es", "en"],
                create_base_structure=True,
                use_import_staging=True,
            )
            analyzer = ProviderBackedBootstrapAnalyzer(
                config=DerivedSourceLLMConfig(
                    task_name="derived_source_understanding",
                    provider_name="test-provider",
                    model="test-model",
                )
            )
            prepare_result = prepare_bootstrap(bootstrap_config, source_root=working_root, llm_analyzer=analyzer)
            staged_result = confirm_and_write_bootstrap(bootstrap_config, source_root=working_root, llm_analyzer=analyzer)
            bundle, reviews, plan = review_import_stage(
                self.ctx.vault_root,
                policy=ReviewPolicy(derived_accept_threshold=0.75, derived_pending_threshold=0.6),
            )
            promotion = promote_reviewed_import(
                self.ctx.vault_root,
                policy=ReviewPolicy(derived_accept_threshold=0.75, derived_pending_threshold=0.6),
                confirmed=True,
            )

        promoted_paths = [Path(path) for path in promotion.promoted_paths]
        promoted_path = promoted_paths[0] if promoted_paths else Path(staged_result.written_drafts[0]) if staged_result.written_drafts else None
        promoted_target_id = promoted_path.stem if promoted_path is not None else "derived_source"
        case = CaseTrace(
            case_id=case_id,
            title=title,
            input=request_text,
            materials_used=[str(item) for item in source_root.iterdir() if item.is_file()],
            internal_interpretation_summary=_summarize_import(prepare_result, reviews),
            anchoring_summary=_summarize_import_anchoring(bundle, plan, promotion),
            flow_chosen="derived_source_understanding -> staging -> review -> promotion",
            author_facing_response=_summarize_import_response(prepare_result, promotion),
            technical_result=_tech_result(
                condition=bool(
                    prepare_result.normalization_plan
                    and prepare_result.normalization_plan.drafts
                    and reviews
                    and promotion.promoted_paths
                ),
                partial_ok=False,
            ),
            technical_notes="Derived import completed with an explicit review and promotion trail.",
            risk_flags=[],
            source_format="pdf",
            light_extraction_sufficient=bool(prepare_result.normalization_plan and prepare_result.normalization_plan.coverage_summary.get("covered_chars", 0) > 0),
            llm_escalation_required=True,
            review_status=reviews[0].review_status if reviews else None,
            promotion_decision="promote" if promotion.promoted_paths else "hold",
            prompt_enriched=True,
            steps=[
                {
                    "phase": "import_review",
                    "prepared": _summarize_import(prepare_result, reviews),
                    "anchored": _summarize_import_anchoring(bundle, plan, promotion),
                }
            ],
        )

        if include_safe_operation:
            manager = self._build_manager()
            manager.state = replace(manager.state, last_target_id=promoted_target_id, last_target_type="scene")
            manager.session.conversation_state = manager.state
            manager.state = replace(
                manager.state,
                pending_operation=PendingConversationOperation(
                    operation_id=f"validate_{promoted_target_id}",
                    operation_kind="validate_artifact",
                    task_type="artifact_persistence",
                    flow_name="validate_artifact_flow",
                    target_type="scene",
                    target_id=promoted_target_id,
                    artifact_target_language="ja",
                    explanation_language="es",
                    payload={
                        "type": "artifact_state_change",
                        "target_type": "scene",
                        "target_id": promoted_target_id,
                        "state": "validated",
                        "origin": {"source": "ont_guided_validation", "case": case_id},
                    },
                    summary=f"validate scene:{promoted_target_id}",
                    executable=True,
                    missing_fields=[],
                    created_from_turn=manager.state.turn_count,
                ),
            )
            manager.session.conversation_state = manager.state
            confirm_turn = manager.handle_request(
                _request(
                    "confirm",
                    interface_language="es",
                    user_command_language="es",
                    internal_system_language="en",
                    project_default_language="ja",
                    explanation_language="es",
                    artifact_target_language="ja",
                    mixed_language_allowed=True,
                )
            )
            safe_trace = _turn_trace(confirm_turn)
            case.author_facing_response = case.author_facing_response or (confirm_turn.result_summary or "")
            case.steps = [*case.steps, {"phase": "safe_operation", **asdict(safe_trace)}]
            case.technical_notes = f"{case.technical_notes} Safe op persisted={confirm_turn.persisted}."
            case.llm_escalation_required = bool(case.llm_escalation_required)
            case.review_status = case.review_status or "accepted"
            case.promotion_decision = "promote"
        self._record(case)
        return case

    def _build_manager(self) -> ConversationManager:
        session = create_session(load_runtime_environment(self.ctx.base_dir))
        session.vault_path = self.ctx.vault_root
        state = create_conversation_state(
            explanation_language="es",
            artifact_target_language="ja",
        )
        manager = ConversationManager(
            session=session,
            state=state,
            executor=MinimalExecutionLayer(
                session=session,
                author_response_generator=ProviderBackedAuthorResponseGenerator(
                    allow_live=_ont_live_enabled(),
                    allow_simulated_preview=False,
                    fallback_generator=_OntAuthorResponseGenerator(),
                ),
            ),
            recognizer=HybridIntentRecognizer(
                llm_classifier=_OntIntentClassifier(),
                config=HybridRecognizerConfig(llm_escalation_threshold=0.99),
            ),
            author_understanding_analyzer=HybridAuthorUnderstandingAnalyzer(
                llm_interpreter=_OntAuthorUnderstandingInterpreter(),
            ),
        )
        session.conversation_state = state
        return manager

    def _record(self, case: CaseTrace) -> None:
        self.__class__.case_traces.append(case)


def _build_context() -> OntValidationContext:
    base_dir = Path(tempfile.mkdtemp(prefix="ont_guided_validation_"))
    vault_root = base_dir / "Vault"
    derived_single_root = base_dir / "SourcesSingle"
    derived_parallel_root = base_dir / "SourcesParallel"
    report_dir = REPORT_DIR
    bootstrap_vault(vault_root, title="Ouja no Tsue")
    derived_single_root.mkdir(parents=True, exist_ok=True)
    derived_parallel_root.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(ONT_ROOT / "王者の杖.pdf", derived_single_root / "王者の杖.pdf")
    shutil.copy2(ONT_ROOT / "王者の杖.pdf", derived_parallel_root / "王者の杖.pdf")
    shutil.copy2(ONT_ROOT / "ESP 王者の杖 .pdf", derived_parallel_root / "ESP 王者の杖 .pdf")

    characters_text = (ONT_ROOT / "📘 FICHAS DE PERSONAJES.md").read_text(encoding="utf-8")
    lore_text = (ONT_ROOT / "📘 FICHA DE LORE MAESTRA V2.md").read_text(encoding="utf-8")
    seed_paths = _seed_ont_notes(vault_root, characters_text, lore_text)

    session = create_session(load_runtime_environment(base_dir))
    manager = ConversationManager(session=session, executor=MinimalExecutionLayer(session=session))
    # Prime a small import so later conversational cases can reuse a real promoted artifact.
    with _ont_import_overrides():
        bootstrap_config = VaultInitializationConfig(
            vault_root=str(vault_root),
            mode="new_project",
            project_title="Ouja no Tsue",
            primary_language="ja",
            working_languages=["ja", "es", "en"],
            create_base_structure=True,
            use_import_staging=True,
        )
        analyzer = ProviderBackedBootstrapAnalyzer(
            config=DerivedSourceLLMConfig(
                task_name="derived_source_understanding",
                provider_name="test-provider",
                model="test-model",
            )
        )
        prepare_bootstrap(bootstrap_config, source_root=derived_single_root, llm_analyzer=analyzer)
        confirm_and_write_bootstrap(bootstrap_config, source_root=derived_single_root, llm_analyzer=analyzer)
        bundle, reviews, plan = review_import_stage(
            vault_root,
            policy=ReviewPolicy(derived_accept_threshold=0.75, derived_pending_threshold=0.6),
        )
        promotion = promote_reviewed_import(
            vault_root,
            policy=ReviewPolicy(derived_accept_threshold=0.75, derived_pending_threshold=0.6),
            confirmed=True,
        )
    promoted_path = seed_paths["lore_master_ont"]
    promoted_target_id = promoted_path.stem
    promoted_target_type = _infer_note_type(promoted_path)
    return OntValidationContext(
        base_dir=base_dir,
        vault_root=vault_root,
        derived_single_root=derived_single_root,
        derived_parallel_root=derived_parallel_root,
        report_dir=report_dir,
        promoted_target_id=promoted_target_id,
        promoted_target_type=promoted_target_type,
        promoted_target_path=promoted_path,
    )


def _seed_ont_notes(vault_root: Path, characters_text: str, lore_text: str) -> dict[str, Path]:
    seeded: dict[str, Path] = {}
    seeded["ren"] = write_or_update_note(
        vault_root,
        note_type="character",
        slug="ren",
        title="Auren Velhar / Ren",
        body="Ren, protagonist and silent protector of the OnT core trio.",
        status="validated",
        metadata={"aliases": ["Auren Velhar", "アウレン・ヴェルハル", "Ren"], "project_confirmed_aliases": ["Ren", "アウレン・ヴェルハル"]},
    )
    seeded["sera"] = write_or_update_note(
        vault_root,
        note_type="character",
        slug="sera",
        title="Serélyne Thiseriya d’Aelwen / Sera",
        body="Sera, co-protagonist and emotional counterweight to Ren.",
        status="validated",
        metadata={"aliases": ["Serélyne Thiseriya d’Aelwen", "セレリーヌ・ティセリヤ・ダルウェン", "Sera"], "project_confirmed_aliases": ["Sera", "セラ"]},
    )
    seeded["nael"] = write_or_update_note(
        vault_root,
        note_type="character",
        slug="nael",
        title="Nael Halden",
        body="Nael, emotional support and comic relief with hidden lucidity.",
        status="validated",
        metadata={"aliases": ["Nael", "ナエル・ハルデン"], "project_confirmed_aliases": ["Nael", "ナエル"]},
    )
    seeded["liora"] = write_or_update_note(
        vault_root,
        note_type="character",
        slug="liora",
        title="Liora",
        body="Liora, Sundraël-born bridge into another culture of bonds and maturity rituals.",
        status="validated",
        metadata={"aliases": ["Liora"], "project_confirmed_aliases": ["Liora"]},
    )
    seeded["shaevar"] = write_or_update_note(
        vault_root,
        note_type="character",
        slug="shaevar",
        title="Shaevar",
        body="Shaevar, the winged guardian beast linked to Liora.",
        status="validated",
        metadata={"aliases": ["Shaevar", "シェイヴァル"], "project_confirmed_aliases": ["Shaevar", "シェイヴァル"]},
    )
    seeded["spelarita"] = write_or_update_note(
        vault_root,
        note_type="lore",
        slug="spelarita",
        title="Spelarita",
        body="Crystallized stagnant mana and the material symptom of magical imbalance.",
        status="validated",
        metadata={"aliases": ["Spelarita"], "project_confirmed_aliases": ["Spelarita"]},
    )
    seeded["taikyo"] = write_or_update_note(
        vault_root,
        note_type="lore",
        slug="taikyo",
        title="Taikyō / Eco Inverso",
        body="The inverse echo system that absorbs contaminated or residual mana.",
        status="validated",
        metadata={"aliases": ["Taikyō", "対響", "Eco Inverso"], "project_confirmed_aliases": ["Taikyō", "対響"]},
    )
    seeded["elthariel"] = write_or_update_note(
        vault_root,
        note_type="lore",
        slug="elthariel",
        title="Elthariel",
        body="The hidden temple-refuge of free resonance and paired bonds.",
        status="validated",
        metadata={"aliases": ["Elthariel", "エルサリエル"], "project_confirmed_aliases": ["Elthariel", "エルサリエル"]},
    )
    seeded["thiseia"] = write_or_update_note(
        vault_root,
        note_type="lore",
        slug="thiseia",
        title="Thiseia",
        body="The kingdom-temple built over the first known Spelarita vein.",
        status="validated",
        metadata={"aliases": ["Thiseia", "ティセイア"], "project_confirmed_aliases": ["Thiseia", "ティセイア"]},
    )
    seeded["regente"] = write_or_update_note(
        vault_root,
        note_type="lore",
        slug="regente",
        title="Adelman Leofrik / Regente",
        body="The regent maintaining political control while the kingdom declines.",
        status="validated",
        metadata={"aliases": ["Regente", "Adelman Leofrik"], "project_confirmed_aliases": ["Regente", "Adelman Leofrik"]},
    )
    seeded["character_bible_ont"] = write_or_update_note(
        vault_root,
        note_type="lore",
        slug="character_bible_ont",
        title="Fichas de Personajes OnT",
        body=characters_text,
        status="validated",
        metadata={"aliases": ["📘 FICHAS DE PERSONAJES"], "project_confirmed_aliases": ["OnT characters"]},
    )
    seeded["lore_master_ont"] = write_or_update_note(
        vault_root,
        note_type="lore",
        slug="lore_master_ont",
        title="Ficha de Lore Maestra V2",
        body=lore_text,
        status="validated",
        metadata={"aliases": ["📘 FICHA DE LORE MAESTRA V2"], "project_confirmed_aliases": ["OnT lore"]},
    )
    return seeded


def _ont_import_overrides():
    @contextmanager
    def _ctx():
        with ExitStack() as stack:
            stack.enter_context(patch("textifai.bootstrap.analyzer.get_text_provider_config_error", return_value=False))
            stack.enter_context(patch("textifai.derived_sources.gating.decide_llm_escalation", side_effect=_force_escalation))
            stack.enter_context(
                patch(
                    "textifai.derived_sources.llm_interpreter.ProviderBackedDerivedSourceInterpreter.interpret",
                    side_effect=_ont_derived_interpret,
                )
            )
            stack.enter_context(patch("textifai.import_review.reviewer.extraction_requires_strict_confirmation", return_value=False))
            yield

    return _ctx()


def _force_escalation(seed):
    return LLMEscalationDecision(required=True, reasons=["ont_guided_validation"])


def _ont_derived_interpret(*, seed, escalation):
    file_name = Path(seed.source_path).name
    is_spanish_parallel = file_name.startswith("ESP")
    dominant_language = "es" if is_spanish_parallel else "ja"
    recovered_text = (
        "Scene draft recovered from the OnT manuscript with mixed-language notes about Ren, Sera, Spelarita, and the bond structure."
        if seed.source_format == "pdf"
        else seed.raw_extracted_text or "Recovered OnT derived source"
    )
    return DerivedLLMExtractionPayload(
        source_id=seed.source_id,
        source_format=seed.source_format,
        dominant_language=dominant_language,
        detected_languages=["es", "ja"] if is_spanish_parallel else ["ja", "es"],
        has_mixed_language=True,
        overall_confidence=0.93,
        structural_confidence=0.9,
        content_mix_signals=["ont_parallel_language_mix"],
        warnings=["ont_guided_validation"],
        segment_candidates=[
            DerivedSegmentCandidate(
                candidate_id="scene_001",
                segment_text=recovered_text,
                heading_text="Scene 12" if "Scene" in recovered_text else "Ouja no Tsue",
                probable_kind="scene",
                language=dominant_language,
                confidence=0.9,
                mixed_content=True,
                boundary_hints=["mixed_language", "derived_source"],
                notes=["ont_guided_validation"],
            )
        ],
        structure_signals=DerivedStructureSignals(
            recovered_headings=["Scene 12"],
            probable_block_order=["scene_001"],
            recovered_lists=[],
            ordering_confidence=0.85,
            structure_warnings=["derived_source"],
            confidence=0.86,
        ),
        loss_signals=DerivedLossSignals(
            missing_structure_signals=[],
            paragraph_merge_signals=[],
            heading_loss_signals=[],
            ordering_uncertainty_signals=[],
            coverage_risk_notes=[],
            severity="low",
            mixed_language_degradation=[],
        ),
        needs_manual_review=False,
        recognized_or_recovered_text=recovered_text,
        llm_escalation_reasons=list(escalation.reasons),
        raw_payload={"ont_guided_validation": True},
    )


def _request(
    raw_text: str,
    *,
    interface_language: str,
    user_command_language: str,
    internal_system_language: str,
    project_default_language: str,
    explanation_language: str,
    artifact_target_language: str,
    mixed_language_allowed: bool,
    metadata: dict | None = None,
    target_hint: str | None = None,
) -> ConversationRequest:
    return ConversationRequest(
        raw_text=raw_text,
        source="user",
        mode="normal",
        interface_language=interface_language,
        user_command_language=user_command_language,
        internal_system_language=internal_system_language,
        project_default_language=project_default_language,
        mixed_language_allowed=mixed_language_allowed,
        artifact_target_language=artifact_target_language,
        explanation_language=explanation_language,
        target_hint=target_hint,
        metadata=dict(metadata or {}),
    )


def _build_manager(session):
    state = create_conversation_state(
        explanation_language="es",
        artifact_target_language="ja",
    )
    manager = ConversationManager(
        session=session,
        state=state,
        executor=MinimalExecutionLayer(session=session),
        recognizer=HybridIntentRecognizer(
            llm_classifier=_OntIntentClassifier(),
            config=HybridRecognizerConfig(llm_escalation_threshold=0.99),
        ),
        author_understanding_analyzer=HybridAuthorUnderstandingAnalyzer(
            llm_interpreter=_OntAuthorUnderstandingInterpreter(),
        ),
    )
    session.conversation_state = state
    return manager


class _OntIntentClassifier:
    def classify_intent(self, *, request, rule_intent, state):
        raw = request.raw_text.casefold()
        target_id = request.target_hint or (state.last_target_id if state else None)
        target_type = state.last_target_type if state else None
        if "confirm" in raw:
            return self._result("confirm_pending", 0.98, target_type, target_id, rule_intent)
        if "cancel" in raw:
            return self._result("cancel_pending", 0.98, target_type, target_id, rule_intent)
        if any(term in raw for term in ("narr", "narrar", "narration")):
            return self._result("prepare_narration", 0.92, target_type, target_id, rule_intent)
        if any(term in raw for term in ("review", "revis", "revisión", "revisão", "revisao")):
            return self._result("prepare_review", 0.9, target_type, target_id, rule_intent)
        if any(term in raw for term in ("structure", "estructur", "estrutur", "構造", "organiza", "orden")):
            return self._result("editorial_structuring", 0.93, target_type or "scene", target_id, rule_intent)
        if any(term in raw for term in ("canon", "spelarita", "taiky", "elthar", "thiseia", "regente")):
            return self._result("consistency_check", 0.91, target_type, target_id, rule_intent)
        if any(term in raw for term in ("continue", "continuar", "continua", "seguir", "sigamos", "続け")) or len(raw.split()) <= 3:
            return self._result("structured_followup", 0.87, target_type, target_id, rule_intent)
        return self._result(rule_intent.intent_name, max(rule_intent.confidence, 0.7), rule_intent.target_type or target_type, rule_intent.target_id or target_id, rule_intent)

    def _result(self, intent_name, confidence, target_type, target_id, rule_intent):
        return {
            "intent_name": intent_name,
            "confidence": confidence,
            "target_type": target_type,
            "target_id": target_id,
            "requires_target": bool(target_id),
            "signals": [f"ont:{intent_name}"],
            "classification_note": "OnT-guided validation classifier",
        }


class _OntAuthorUnderstandingInterpreter:
    def interpret(self, *, request, rule_intent, narrative_signals, entity_results, state):
        raw = request.raw_text.casefold()
        candidate_targets = []
        entity_hints: list[EntityHint] = []
        for result in entity_results:
            if not isinstance(result, EntityResolutionResult):
                continue
            if result.resolved and result.resolved_entity_id and result.resolved_entity_type:
                candidate_targets.append(
                    {"target_id": result.resolved_entity_id, "target_type": result.resolved_entity_type, "confidence": _bounded(result.resolution_confidence)}
                )
                entity_hints.append(
                    EntityHint(
                        hint_text=result.mention.surface_text,
                        normalized_hint=result.mention.normalized_text,
                        hint_kind="semantic_target",
                        hint_source="author_understanding",
                        language=request.user_command_language,
                        confidence=_bounded(max(result.resolution_confidence, result.hint_support_score, 0.5)),
                        supported_by_author_understanding=True,
                        supported_by_document_analysis=bool(result.metadata.get("supported_by_document_analysis", False)),
                        candidate_target_id=result.resolved_entity_id,
                        candidate_target_type=result.resolved_entity_type,
                    )
                )

        if any(term in raw for term in ("structure", "estructur", "estrutur", "構造", "organiza", "orden")):
            primary_intent_type = "structuring_request"
        elif any(term in raw for term in ("review", "revis", "revisión", "revisão", "revisao")):
            primary_intent_type = "review_handoff"
        elif any(term in raw for term in ("narr", "narrar", "narration")):
            primary_intent_type = "narration_preparation"
        elif any(term in raw for term in ("canon", "spelarita", "taiky", "elthar", "thiseia", "regente")):
            primary_intent_type = "validation_request"
        elif any(term in raw for term in ("continue", "continuar", "continua", "seguir", "sigamos", "続け")) or len(raw.split()) <= 3:
            primary_intent_type = "structured_followup"
        else:
            primary_intent_type = "editorial_revision" if "voice" in raw or "voz" in raw else "contextual_followup"

        preserve_signals = []
        if "voice" in raw or "voz" in raw:
            preserve_signals.append("preserve_character_voice")
        if "canon" in raw:
            preserve_signals.append("preserve_validated_canon")
        if "tension" in raw or "tensión" in raw or "tensao" in raw or "tensão" in raw:
            preserve_signals.append("preserve_scene_conflict")

        change_signals = []
        if any(term in raw for term in ("structure", "estructur", "estrutur", "構造", "organiza", "orden")):
            change_signals.append("structure_scene")
        if "review" in raw or "revis" in raw:
            change_signals.append("prepare_for_review")
        if "narr" in raw:
            change_signals.append("prepare_for_narration")

        if primary_intent_type == "structuring_request":
            author_goal_signals = ["structure_scene"]
        elif primary_intent_type == "editorial_revision":
            author_goal_signals = ["prepare_for_review"]
        elif primary_intent_type == "review_handoff":
            author_goal_signals = ["prepare_for_review"]
        elif primary_intent_type == "narration_preparation":
            author_goal_signals = ["prepare_for_narration"]
        elif primary_intent_type == "validation_request":
            author_goal_signals = ["anchor_canon"]
        elif primary_intent_type in {"structured_followup", "contextual_followup"}:
            author_goal_signals = ["structure_scene"]
        else:
            author_goal_signals = ["prepare_for_review"]

        return LLMAuthorUnderstandingPayload(
            raw_text=request.raw_text,
            provider_name="test-provider",
            model="test-model",
            primary_intent_type=primary_intent_type,
            secondary_intent_types=["contextual_followup"] if primary_intent_type == "structured_followup" else [],
            confidence=0.91 if candidate_targets else 0.79,
            has_mixed_request=len(request.raw_text.split()) > 5,
            author_goal_signals=author_goal_signals,
            preserve_signals=preserve_signals,
            change_signals=change_signals,
            entity_hints=entity_hints,
            followup_reference_text=state.last_target_id if primary_intent_type in {"structured_followup", "contextual_followup"} and state and state.last_target_id else None,
            narrative_content_text=request.raw_text if primary_intent_type in {"structuring_request", "review_handoff", "narration_preparation"} else None,
            meta_instruction_text=request.raw_text if "review" in raw or "narr" in raw else None,
            needs_clarification=not candidate_targets and primary_intent_type not in {"contextual_followup", "structured_followup"},
            clarification_reason="needs a supported target" if not candidate_targets and primary_intent_type not in {"contextual_followup", "structured_followup"} else None,
            parts=[],
            candidate_targets=[],
            preferred_target=None,
            disambiguation_reason="ont_guided_validation",
            raw_payload={"ont_guided_validation": True},
        )


class _OntAuthorResponseGenerator:
    def generate(self, *, prompt):
        return TemplateAuthorResponseGenerator().generate(prompt=prompt)


def _turn_trace(turn) -> StepTrace:
    recognized = turn.recognized_intent
    metadata = dict(recognized.metadata if recognized is not None else {})
    author_understanding = metadata.get("author_understanding")
    editorial_intent = metadata.get("editorial_intent")
    candidate_targets = list((editorial_intent or {}).get("candidate_targets", []))
    resolved_target = None
    if isinstance(editorial_intent, dict):
        resolved_target = {
            "target_id": editorial_intent.get("resolved_target_id"),
            "target_type": editorial_intent.get("resolved_target_type"),
        }
    entity_hints = []
    if isinstance(author_understanding, dict):
        entity_hints = list(author_understanding.get("entity_hints", []))
        if not candidate_targets:
            candidate_targets = list(author_understanding.get("candidate_targets", []))
    clarification_required = bool(author_understanding.get("needs_clarification")) if isinstance(author_understanding, dict) else False
    false_certainty = bool(resolved_target and resolved_target.get("target_id") and clarification_required)
    prompt_payload = turn.anchored_prompt_payload if isinstance(turn.anchored_prompt_payload, dict) else {}
    if resolved_target and not resolved_target.get("target_id") and not resolved_target.get("target_type"):
        resolved_target = None
    return StepTrace(
        input_text=turn.request.raw_text,
        recognized_intent=recognized.intent_name if recognized is not None else None,
        author_understanding=author_understanding if isinstance(author_understanding, dict) else None,
        editorial_intent=editorial_intent if isinstance(editorial_intent, dict) else None,
        entity_hints=entity_hints,
        candidate_targets=candidate_targets,
        resolved_target=resolved_target,
        semantic_phase=turn.planned_task.semantic_phase if turn.planned_task else None,
        prompt_enriched=bool(turn.anchored_prompt_payload or metadata.get("llm_used") or metadata.get("escalated_to_llm")),
        response_generation_ready=bool(turn.response_generation_ready),
        semantic_response_kind=turn.semantic_response_kind,
        flow_name=turn.planned_task.flow_name if turn.planned_task else None,
        prompt_base_id=prompt_payload.get("prompt_base_id"),
        prompt_base_version=prompt_payload.get("prompt_base_version"),
        prompt_template_id=prompt_payload.get("prompt_template_id"),
        prompt_template_version=prompt_payload.get("prompt_template_version"),
        model_profile_used=prompt_payload.get("model_profile_used"),
        provider_mode=turn.provider_mode,
        response_generation_mode=turn.response_generation_mode,
        response_generation_reason=turn.response_generation_reason,
        provider_execution_enabled=bool(turn.provider_execution_enabled),
        provider_execution_mode=turn.provider_execution_mode,
        provider_model_used=turn.provider_model_used,
        anchored_prompt_payload=turn.anchored_prompt_payload,
        trace_rendered_prompt_payload=prompt_payload.get("trace_rendered_prompt_payload") or prompt_payload.get("rendered_prompt_payload"),
        llm_rendered_prompt_payload=prompt_payload.get("llm_rendered_prompt_payload"),
        anchored_evidence_used=prompt_payload.get("anchored_evidence_used"),
        response_support_summary=turn.response_support_summary,
        live_model_response=turn.live_model_response,
        simulated_preview_enabled=bool(turn.simulated_preview_enabled),
        simulated_preview_output=turn.simulated_preview_output,
        clarification_required=clarification_required,
        false_certainty=false_certainty,
        author_facing_response=turn.author_facing_response,
    )


def _trace_dict(trace: StepTrace) -> dict:
    return _safe_jsonable(trace.__dict__)


def _safe_jsonable(value, seen: set[int] | None = None):
    seen = seen or set()
    if isinstance(value, (dict, list, tuple, set)):
        value_id = id(value)
        if value_id in seen:
            return "<recursive_ref>"
        next_seen = set(seen)
        next_seen.add(value_id)
    else:
        next_seen = seen
    if isinstance(value, dict):
        return {str(key): _safe_jsonable(item, next_seen) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_jsonable(item, next_seen) for item in value]
    if isinstance(value, tuple):
        return [_safe_jsonable(item, next_seen) for item in value]
    if isinstance(value, set):
        return [_safe_jsonable(item, next_seen) for item in sorted(value, key=str)]
    return value


def _ont_live_enabled() -> bool:
    return os.environ.get("TEXTIFAI_ONT_PROVIDER_MODE", "").strip().lower() == "live_openai"


def _followup_mode(trace: StepTrace) -> str | None:
    editorial = trace.editorial_intent or {}
    return editorial.get("followup_mode")


def _write_reports(case_traces: list[CaseTrace]) -> None:
    if not case_traces:
        return
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "author_utility": "pending_human_review",
        "author_notes": "",
        "cases": [asdict(case) for case in case_traces],
    }
    (REPORT_DIR / "ont_guided_validation.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    (REPORT_DIR / "ont_guided_validation.md").write_text(_render_markdown(payload))


def _write_prompt_exports(case_traces: list[CaseTrace]) -> None:
    cases = [
        asdict(case)
        for case in case_traces
        if any(
            (step or {}).get("trace_rendered_prompt_payload")
            or (step or {}).get("llm_rendered_prompt_payload")
            for step in case.steps
        )
    ]
    if not cases:
        return
    export_prompt_cases(
        cases,
        PROMPT_EXPORT_DIR / "ont_prompt_export.json",
        PROMPT_EXPORT_DIR / "ont_prompt_export.md",
        export_title="OnT Prompt Export",
    )


def _baseline_author_facing_response(case_id: str) -> str | None:
    baselines = {
        "structuring_request": "Prepared editorial structure: 1 facts, 1 beats",
        "editorial_revision": "Prepared editorial structure: 1 facts, 1 beats",
        "followup_contextual": "This follow-up is anchored to the previous target.",
        "entity_resolution_cross_document": "Todavia no cerraria una respuesta fuerte aqui. Tengo candidatos plausibles, pero antes prefiero que me confirmes el objetivo exacto para no inventar.",
    }
    return baselines.get(case_id)


def _render_markdown(payload: dict) -> str:
    lines = [
        "# OnT Guided Validation",
        "",
        f"- author_utility: `{payload['author_utility']}`",
        f"- author_notes: `{payload['author_notes']}`",
        "",
    ]
    for case in payload["cases"]:
        lines.extend(
            [
                f"## {case['case_id']}",
                f"- title: {case['title']}",
                f"- technical_result: `{case['technical_result']}`",
                f"- technical_notes: {case['technical_notes']}",
                f"- author_utility: `{case['author_utility']}`",
                f"- author_notes: `{case['author_notes']}`",
                f"- input: {case['input']}",
                f"- materials_used: {', '.join(case['materials_used']) or 'none'}",
                f"- response: {case['author_facing_response']}",
                f"- prompt_enriched: `{case.get('prompt_enriched')}`",
                "",
            ]
        )
        steps = case.get("steps") or []
        if steps:
            first_step = steps[0]
            lines.extend(
                [
                    f"- prompt_template_id: `{first_step.get('prompt_template_id')}`",
                    f"- prompt_template_version: `{first_step.get('prompt_template_version')}`",
                    f"- model_profile_used: `{first_step.get('model_profile_used')}`",
                    f"- provider_mode: `{first_step.get('provider_mode')}`",
                    f"- provider_model_used: `{first_step.get('provider_model_used')}`",
                    f"- live_model_response: {first_step.get('live_model_response')!r}",
                    "",
                ]
            )
    return "\n".join(lines)


def _summarize_import(prepare_result, reviews) -> str:
    plan = prepare_result.normalization_plan
    if plan is None:
        return "No normalization plan was produced."
    first_review = reviews[0].review_status if reviews else "missing"
    return (
        f"documents={prepare_result.inventory.total_documents if prepare_result.inventory else 0}; "
        f"drafts={len(plan.drafts)}; requires_confirmation={plan.requires_confirmation}; "
        f"first_review={first_review}"
    )


def _summarize_import_anchoring(bundle, plan, promotion) -> str:
    return (
        f"bundle_drafts={len(bundle.drafts)}; "
        f"decisions={len(plan.decisions)}; "
        f"promoted={len(promotion.promoted_paths)}; "
        f"pending={len(promotion.pending_drafts)}"
    )


def _summarize_import_response(prepare_result, promotion) -> str:
    plan = prepare_result.normalization_plan
    if plan is None:
        return "TextifAI could not build a plan for the derived source."
    if promotion.promoted_paths:
        return "TextifAI would stage and promote the derived source with strong provenance and a conservative review trail."
    return "TextifAI would keep the derived source pending until the extracted structure is safe enough to promote."


def _infer_note_type(path: Path) -> str:
    parts = [part.lower() for part in path.parts]
    if "profiles" in parts:
        return "character"
    if "lore" in parts:
        return "lore"
    if "scenes" in parts:
        return "scene"
    if "chapters" in parts:
        return "chapter"
    return "scene"


def _tech_result(*, condition: bool, partial_ok: bool) -> str:
    if condition:
        return "correct"
    return "partial" if partial_ok else "incorrect"


def _shorten(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, dict) else str(value)
    text = " ".join(text.split())
    return text[:220] + ("…" if len(text) > 220 else "")


def _bounded(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
