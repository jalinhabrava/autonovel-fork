from __future__ import annotations

from contextlib import ExitStack, contextmanager
import tempfile
import unittest
import zipfile
from dataclasses import dataclass, replace
from html import escape
import os
from pathlib import Path
from unittest.mock import patch

from textifai.author_understanding.contracts import LLMAuthorUnderstandingPayload
from textifai.author_response.contracts import AnchoredAuthorResponse
from textifai.author_response.generator import ProviderBackedAuthorResponseGenerator
from textifai.author_understanding.hybrid_analysis import HybridAuthorUnderstandingAnalyzer
from textifai.bootstrap import ProviderBackedBootstrapAnalyzer, VaultInitializationConfig, confirm_and_write_bootstrap, prepare_bootstrap
from textifai.conversation.contracts import ConversationRequest, PendingConversationOperation
from textifai.conversation.executor import MinimalExecutionLayer
from textifai.conversation.hybrid_recognizer import HybridIntentRecognizer, HybridRecognizerConfig
from textifai.conversation.manager import ConversationManager
from textifai.derived_sources import (
    DerivedLLMExtractionPayload,
    DerivedLossSignals,
    DerivedSegmentCandidate,
    DerivedSourceLLMConfig,
    DerivedStructureSignals,
    LLMEscalationDecision,
)
from textifai.import_review import ReviewPolicy, promote_reviewed_import, review_import_stage
from textifai.runtime_config import load_runtime_environment
from textifai.session import create_session
from textifai.vaerl.contracts import EntityHint, EntityResolutionResult
from textifai.vaerl.matching import EntityCandidate
from vault.bootstrap import bootstrap_vault
from vault.notes import write_or_update_note


@dataclass(frozen=True)
class StepObservation:
    name: str
    result_type: str | None
    semantic_phase: bool | None = None
    phase_classification: str | None = None
    llm_used: bool | None = None
    recognized_intent: str | None = None
    author_primary_intent: str | None = None
    author_needs_clarification: bool | None = None
    editorial_request_type: str | None = None
    editorial_semantic_basis: str | None = None
    editorial_followup_mode: str | None = None
    candidate_targets: list[dict] | None = None
    resolved_target_id: str | None = None
    resolved_target_type: str | None = None
    hint_support_score: float | None = None
    detected_languages: list[str] | None = None
    llm_escalation_required: bool | None = None
    review_status: str | None = None
    strict_confirmation_required: bool | None = None
    provider_mode: str | None = None
    provider_model_used: str | None = None
    live_model_response: str | None = None
    notes: list[str] | None = None
    false_certainty: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_targets", list(self.candidate_targets or []))
        object.__setattr__(self, "detected_languages", list(self.detected_languages or []))
        object.__setattr__(self, "notes", list(self.notes or []))


class GuidedPartialEndToEndValidationTests(unittest.TestCase):
    def test_document_first_guided_partial_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            vault_root = base_dir / "Vault"
            source_root = base_dir / "Sources"
            bootstrap_vault(vault_root, title="Test Project")
            source_root.mkdir(parents=True, exist_ok=True)
            (base_dir / ".env").write_text(
                "\n".join(
                    [
                        "AUTONOVEL_PROJECT_BACKEND=vault",
                        f"AUTONOVEL_VAULT_ROOT={vault_root}",
                        "AUTONOVEL_TEXT_PROVIDER=ollama",
                    ]
                )
                + "\n"
            )

            source_path = source_root / "scene_12.docx"
            _write_docx(
                source_path,
                [
                    "# Scene 12",
                    "Sera entra al hotel sin hacer ruido.",
                    "日本語メモ: ここでは緊張を少し下げる。",
                ],
            )

            session = create_session(load_runtime_environment(base_dir))
            manager = _build_guided_manager(session)
            bootstrap_config = VaultInitializationConfig(
                vault_root=str(vault_root),
                mode="new_project",
                project_title="Test Project",
                primary_language="en",
                working_languages=["en", "es", "ja"],
                create_base_structure=True,
                use_import_staging=True,
            )

            with _guided_import_overrides():
                prepare_result = prepare_bootstrap(
                    bootstrap_config,
                    source_root=source_root,
                    llm_analyzer=ProviderBackedBootstrapAnalyzer(
                        config=DerivedSourceLLMConfig(
                            task_name="derived_source_understanding",
                            provider_name="test-provider",
                            model="test-model",
                        )
                    ),
                )
                self.assertIsNotNone(prepare_result.normalization_plan)
                self.assertTrue(prepare_result.normalization_plan.requires_confirmation)
                self.assertGreaterEqual(len(prepare_result.normalization_plan.drafts), 1)
                self.assertEqual(prepare_result.normalization_plan.drafts[0].artifact_type, "scene")
                self.assertEqual(prepare_result.normalization_plan.drafts[0].provenance.source_format, "docx")
                self.assertTrue(prepare_result.normalization_plan.drafts[0].provenance.llm_assisted)
                self.assertEqual(prepare_result.normalization_plan.drafts[0].status, "needs_review")

                staged_result = confirm_and_write_bootstrap(
                    bootstrap_config,
                    source_root=source_root,
                    llm_analyzer=ProviderBackedBootstrapAnalyzer(
                        config=DerivedSourceLLMConfig(
                            task_name="derived_source_understanding",
                            provider_name="test-provider",
                            model="test-model",
                        )
                    ),
                )
                self.assertGreaterEqual(len(staged_result.written_drafts), 1)
                self.assertTrue(staged_result.staging_root)
                self.assertGreater(staged_result.coverage_report["staged_fragments"], 0)

                bundle, reviews, plan = review_import_stage(
                    vault_root,
                    policy=ReviewPolicy(derived_accept_threshold=0.75, derived_pending_threshold=0.6),
                )
                self.assertGreaterEqual(len(bundle.drafts), 1)
                self.assertTrue(all(review.review_status == "accepted" for review in reviews))
                self.assertFalse(plan.requires_confirmation)

                promotion = promote_reviewed_import(
                    vault_root,
                    policy=ReviewPolicy(derived_accept_threshold=0.75, derived_pending_threshold=0.6),
                    confirmed=True,
                )
                self.assertGreaterEqual(len(promotion.promoted_paths), 1)
                promoted_path = Path(promotion.promoted_paths[0])
                self.assertTrue(promoted_path.exists())
                self.assertFalse(promotion.pending_drafts)
                promoted_target_id = promoted_path.stem

            turn6 = manager.handle_request(
                _request(
                    "Quiero estructurar Scene 12 sin perder la tensión.",
                    interface_language="es",
                    user_command_language="es",
                    internal_system_language="en",
                    project_default_language="ja",
                    explanation_language="es",
                    artifact_target_language="ja",
                    mixed_language_allowed=True,
                )
            )
            trace6 = _turn_snapshot(turn6)
            self.assertEqual(trace6.recognized_intent, "editorial_structuring")
            self.assertTrue(trace6.llm_used)
            self.assertTrue(trace6.semantic_phase)
            self.assertEqual(trace6.phase_classification, "semantic")
            self.assertEqual(trace6.author_primary_intent, "structuring_request")
            self.assertEqual(trace6.editorial_request_type, "structuring_request")
            self.assertEqual(trace6.editorial_semantic_basis, "author_understanding_validated")
            self.assertIsNotNone(trace6.resolved_target_id)
            self.assertEqual(trace6.resolved_target_type, "scene")
            self.assertGreaterEqual(trace6.hint_support_score or 0.0, 0.0)
            self.assertFalse(trace6.author_needs_clarification)
            self.assertGreaterEqual(len(trace6.candidate_targets), 1)

            turn7 = manager.handle_request(
                _request(
                    "それで続けよう",
                    interface_language="ja",
                    user_command_language="ja",
                    internal_system_language="en",
                    project_default_language="ja",
                    explanation_language="es",
                    artifact_target_language="ja",
                    mixed_language_allowed=True,
                )
            )
            trace7 = _turn_snapshot(turn7)
            self.assertTrue(trace7.semantic_phase)
            self.assertEqual(trace7.phase_classification, "semantic")
            self.assertIn(trace7.editorial_followup_mode, {"reuse_recent_target", "prefer_candidate_targets"})
            self.assertIsNotNone(trace7.resolved_target_id)
            self.assertIn(trace7.llm_used, {True, False})

            turn8 = manager.handle_request(
                _request(
                    "Déjalo listo para narrar.",
                    interface_language="es",
                    user_command_language="es",
                    internal_system_language="en",
                    project_default_language="ja",
                    explanation_language="es",
                    artifact_target_language="ja",
                    mixed_language_allowed=True,
                )
            )
            trace8 = _turn_snapshot(turn8)
            self.assertEqual(trace8.recognized_intent, "prepare_narration")
            self.assertTrue(trace8.semantic_phase)
            self.assertEqual(trace8.phase_classification, "semantic")
            self.assertIn(trace8.result_type, {"followthrough", "conversation_clarification"})
            self.assertTrue(trace8.llm_used)
            self.assertTrue(turn8.result_summary.strip())
            self.assertIsNotNone(manager.session.last_result)

            manager.state = replace(
                manager.state,
                pending_operation=PendingConversationOperation(
                    operation_id="validate_scene_12",
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
                        "origin": {
                            "source": "guided_partial_validation",
                            "step": "promotion_handoff",
                        },
                    },
                    summary=f"validate scene:{promoted_target_id}",
                    executable=True,
                    missing_fields=[],
                    created_from_turn=manager.state.turn_count,
                ),
            )
            manager.session.conversation_state = manager.state

            turn9 = manager.handle_request(
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
            trace9 = _turn_snapshot(turn9)
            self.assertEqual(trace9.recognized_intent, "confirm_pending")
            self.assertFalse(trace9.semantic_phase)
            self.assertEqual(trace9.phase_classification, "operational")
            self.assertTrue(turn9.persisted)
            self.assertIsNone(manager.state.pending_operation)

    def test_conversation_first_guided_partial_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            vault_root = base_dir / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (base_dir / ".env").write_text(
                "\n".join(
                    [
                        "AUTONOVEL_PROJECT_BACKEND=vault",
                        f"AUTONOVEL_VAULT_ROOT={vault_root}",
                        "AUTONOVEL_TEXT_PROVIDER=ollama",
                    ]
                )
                + "\n"
            )

            write_or_update_note(
                vault_root,
                note_type="scene",
                slug="memory_ritual",
                title="Memory Ritual",
                body="A staged scene that already has project-confirmed aliases.",
                status="validated",
                metadata={
                    "aliases": ["ritual de memoria", "memoriaの儀式", "ritual de memória"],
                    "project_confirmed_aliases": ["ritual de memoria", "memoriaの儀式", "ritual de memória"],
                },
            )

            session = create_session(load_runtime_environment(base_dir))
            manager = _build_guided_manager(session)

            turn1 = manager.handle_request(
                _request(
                    "Structure Memory Ritual without losing Sera's voice.",
                    interface_language="en",
                    user_command_language="en",
                    internal_system_language="en",
                    project_default_language="ja",
                    explanation_language="en",
                    artifact_target_language="ja",
                    mixed_language_allowed=True,
                    metadata={"project_confirmed_aliases": ["ritual de memoria", "memoriaの儀式", "ritual de memória"]},
                )
            )
            trace1 = _turn_snapshot(turn1)
            self.assertEqual(trace1.recognized_intent, "editorial_structuring")
            self.assertTrue(trace1.semantic_phase)
            self.assertEqual(trace1.author_primary_intent, "structuring_request")
            self.assertEqual(trace1.editorial_request_type, "structuring_request")
            self.assertEqual(trace1.editorial_semantic_basis, "author_understanding_validated")
            self.assertEqual(trace1.resolved_target_id, "memory_ritual")
            self.assertEqual(trace1.resolved_target_type, "scene")
            self.assertTrue(trace1.llm_used)
            self.assertEqual(manager.state.last_target_id, "memory_ritual")
            self.assertEqual(manager.state.last_target_type, "scene")

            turn2 = manager.handle_request(
                _request(
                    "それで続けよう",
                    interface_language="ja",
                    user_command_language="ja",
                    internal_system_language="en",
                    project_default_language="ja",
                    explanation_language="en",
                    artifact_target_language="ja",
                    mixed_language_allowed=True,
                )
            )
            trace2 = _turn_snapshot(turn2)
            self.assertTrue(trace2.semantic_phase)
            self.assertIn(trace2.editorial_followup_mode, {"reuse_recent_target", "prefer_candidate_targets"})
            self.assertEqual(trace2.resolved_target_id, "memory_ritual")
            self.assertIn(trace2.llm_used, {True, False})

            turn3 = manager.handle_request(
                _request(
                    "continua com o ritual de memória.",
                    interface_language="pt",
                    user_command_language="pt",
                    internal_system_language="en",
                    project_default_language="ja",
                    explanation_language="en",
                    artifact_target_language="ja",
                    mixed_language_allowed=True,
                    metadata={"project_confirmed_aliases": ["ritual de memoria", "memoriaの儀式", "ritual de memória"]},
                )
            )
            trace3 = _turn_snapshot(turn3)
            self.assertTrue(trace3.semantic_phase)
            self.assertEqual(trace3.resolved_target_id, "memory_ritual")
            self.assertIn(trace3.llm_used, {True, False})
            self.assertEqual(trace3.editorial_semantic_basis, "author_understanding_validated")

            turn4 = manager.handle_request(
                _request(
                    "Quiero una revisión editorial de Memory Ritual sin romper la voz.",
                    interface_language="es",
                    user_command_language="es",
                    internal_system_language="en",
                    project_default_language="ja",
                    explanation_language="es",
                    artifact_target_language="ja",
                    mixed_language_allowed=True,
                )
            )
            trace4 = _turn_snapshot(turn4)
            self.assertTrue(trace4.semantic_phase)
            self.assertEqual(trace4.resolved_target_id, "memory_ritual")
            self.assertTrue(trace4.llm_used)
            self.assertEqual(trace4.editorial_request_type, "review_handoff")

            turn5 = manager.handle_request(
                _request(
                    "Prepáralo para narrar.",
                    interface_language="es",
                    user_command_language="es",
                    internal_system_language="en",
                    project_default_language="ja",
                    explanation_language="es",
                    artifact_target_language="ja",
                    mixed_language_allowed=True,
                )
            )
            trace5 = _turn_snapshot(turn5)
            self.assertTrue(trace5.semantic_phase)
            self.assertIn(trace5.recognized_intent, {"prepare_narration", "unknown"})
            self.assertIn(trace5.editorial_request_type, {"narration_preparation", "contextual_followup"})
            self.assertIn(trace5.llm_used, {True, False})
            self.assertTrue(turn5.result_summary.strip())

            manager.state = replace(
                manager.state,
                pending_operation=PendingConversationOperation(
                    operation_id="validate_memory_ritual",
                    operation_kind="validate_artifact",
                    task_type="artifact_persistence",
                    flow_name="validate_artifact_flow",
                    target_type="scene",
                    target_id="memory_ritual",
                    artifact_target_language="ja",
                    explanation_language="es",
                    payload={
                        "type": "artifact_state_change",
                        "target_type": "scene",
                        "target_id": "memory_ritual",
                        "state": "validated",
                        "origin": {
                            "source": "guided_partial_validation",
                            "step": "alias_convergence",
                        },
                    },
                    summary="validate scene:memory_ritual",
                    executable=True,
                    missing_fields=[],
                    created_from_turn=manager.state.turn_count,
                ),
            )
            manager.session.conversation_state = manager.state

            turn6 = manager.handle_request(
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
            trace6 = _turn_snapshot(turn6)
            self.assertEqual(trace6.recognized_intent, "confirm_pending")
            self.assertFalse(trace6.semantic_phase)
            self.assertEqual(trace6.phase_classification, "operational")
            self.assertTrue(turn6.persisted)
            self.assertIsNone(manager.state.pending_operation)

            turn7 = manager.handle_request(
                _request(
                    "What was the core tension again?",
                    interface_language="en",
                    user_command_language="en",
                    internal_system_language="en",
                    project_default_language="ja",
                    explanation_language="en",
                    artifact_target_language="ja",
                    mixed_language_allowed=True,
                )
            )
            trace7 = _turn_snapshot(turn7)
            self.assertTrue(trace7.semantic_phase)
            self.assertIn(trace7.author_primary_intent, {"contextual_followup", "structured_followup"})
            self.assertIn(trace7.llm_used, {True, False})
            self.assertFalse(trace7.false_certainty)


def _build_guided_manager(session):
    return ConversationManager(
        session=session,
        executor=MinimalExecutionLayer(session=session),
        recognizer=HybridIntentRecognizer(
            llm_classifier=_GuidedIntentClassifier(),
            config=HybridRecognizerConfig(llm_escalation_threshold=0.99),
        ),
        author_understanding_analyzer=HybridAuthorUnderstandingAnalyzer(
            llm_interpreter=_GuidedAuthorUnderstandingInterpreter(),
        ),
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


def _turn_snapshot(turn) -> StepObservation:
    recognized = turn.recognized_intent
    metadata = dict(recognized.metadata if recognized is not None else {})
    author_understanding = metadata.get("author_understanding")
    editorial_intent = metadata.get("editorial_intent")
    candidate_targets = list((editorial_intent or {}).get("candidate_targets", []))
    hint_support_score = None
    if isinstance(author_understanding, dict):
        hints = author_understanding.get("entity_hints", [])
        if isinstance(hints, list) and hints:
            hint_support_score = max(
                [float(item.get("confidence", 0.0)) for item in hints if isinstance(item, dict)],
                default=0.0,
            )
    if isinstance(editorial_intent, dict):
        candidate_targets = list(editorial_intent.get("candidate_targets", []))
    resolved_target_id = None
    resolved_target_type = None
    if isinstance(editorial_intent, dict):
        resolved_target_id = editorial_intent.get("resolved_target_id")
        resolved_target_type = editorial_intent.get("resolved_target_type")
    if resolved_target_id is None and recognized is not None:
        resolved_target_id = recognized.target_id
    if resolved_target_type is None and recognized is not None:
        resolved_target_type = recognized.target_type
    detected_languages = []
    if isinstance(author_understanding, dict):
        detected_languages = list(author_understanding.get("detected_languages", []))
    return StepObservation(
        name=turn.planned_task.flow_name if turn.planned_task else "unknown",
        result_type=turn.result_type,
        semantic_phase=turn.planned_task.semantic_phase if turn.planned_task else None,
        phase_classification=turn.planned_task.metadata.get("phase_classification") if turn.planned_task else None,
        llm_used=bool(metadata.get("llm_used") or metadata.get("escalated_to_llm")),
        recognized_intent=recognized.intent_name if recognized is not None else None,
        author_primary_intent=author_understanding.get("primary_intent_type") if isinstance(author_understanding, dict) else None,
        author_needs_clarification=author_understanding.get("needs_clarification") if isinstance(author_understanding, dict) else None,
        editorial_request_type=editorial_intent.get("request_type") if isinstance(editorial_intent, dict) else None,
        editorial_semantic_basis=editorial_intent.get("semantic_basis") if isinstance(editorial_intent, dict) else None,
        editorial_followup_mode=editorial_intent.get("followup_mode") if isinstance(editorial_intent, dict) else None,
        candidate_targets=candidate_targets,
        resolved_target_id=resolved_target_id,
        resolved_target_type=resolved_target_type,
        hint_support_score=hint_support_score,
        detected_languages=detected_languages,
        llm_escalation_required=bool(metadata.get("escalated_to_llm") or metadata.get("llm_used")),
        review_status=metadata.get("review_status") if isinstance(metadata.get("review_status"), str) else None,
        strict_confirmation_required=bool(metadata.get("strict_confirmation_required", False)) if isinstance(metadata, dict) else None,
        notes=[],
        false_certainty=bool(
            resolved_target_id is not None
            and isinstance(author_understanding, dict)
            and author_understanding.get("needs_clarification")
        ),
    )


def _write_docx(path: Path, paragraphs: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    paragraph_xml = "\n".join(
        f"<w:p><w:r><w:t xml:space=\"preserve\">{escape(paragraph)}</w:t></w:r></w:p>"
        for paragraph in paragraphs
    )
    document_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        f"<w:body>{paragraph_xml}</w:body>"
        "</w:document>"
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"></Types>",
        )
        archive.writestr("word/document.xml", document_xml)
        archive.writestr(
            "_rels/.rels",
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"></Relationships>",
        )


class _GuidedIntentClassifier:
    def classify_intent(self, *, request, rule_intent, state):
        raw = request.raw_text.casefold()
        target_id = request.target_hint or (state.last_target_id if state else None)
        target_type = state.last_target_type if state else None
        if "narr" in raw or "narrar" in raw or "narration" in raw:
            return {
                "intent_name": "prepare_narration",
                "confidence": 0.9,
                "target_type": target_type,
                "target_id": target_id,
                "requires_target": bool(target_id),
                "signals": ["guided_llm_narration"],
                "classification_note": "Guided partial validation routed a narration handoff.",
            }
        if "review" in raw or "revisión" in raw or "revision" in raw or "revisão" in raw or "revisao" in raw:
            return {
                "intent_name": "prepare_review",
                "confidence": 0.9,
                "target_type": target_type,
                "target_id": target_id,
                "requires_target": bool(target_id),
                "signals": ["guided_llm_review"],
                "classification_note": "Guided partial validation routed a review handoff.",
            }
        if "structure" in raw or "estructur" in raw or "estrutur" in raw or "estructura" in raw or "estrutura" in raw or "構造" in raw or "organiza" in raw or "orden" in raw:
            return {
                "intent_name": "editorial_structuring",
                "confidence": 0.92,
                "target_type": target_type or "scene",
                "target_id": target_id,
                "requires_target": bool(target_id),
                "signals": ["guided_llm_structuring"],
                "classification_note": "Guided partial validation routed an editorial structuring turn.",
            }
        if "continue" in raw or "continuar" in raw or "continua" in raw or "seguir" in raw or "続け" in raw or "mesma" in raw or "misma" in raw:
            return {
                "intent_name": "structured_followup",
                "confidence": 0.88,
                "target_type": target_type,
                "target_id": target_id,
                "requires_target": bool(target_id),
                "signals": ["guided_llm_followup"],
                "classification_note": "Guided partial validation routed a structured follow-up.",
            }
        return {
            "intent_name": rule_intent.intent_name,
            "confidence": max(rule_intent.confidence, 0.7),
            "target_type": rule_intent.target_type or target_type,
            "target_id": rule_intent.target_id or target_id,
            "requires_target": rule_intent.requires_target,
            "signals": list(rule_intent.signals),
            "classification_note": "Guided partial validation kept the rule-based intent.",
        }


class _GuidedAuthorUnderstandingInterpreter:
    def interpret(
        self,
        *,
        request,
        rule_intent,
        narrative_signals,
        entity_results,
        state,
    ):
        raw = request.raw_text.casefold()
        candidate_targets = []
        entity_hints: list[EntityHint] = []
        for result in entity_results:
            if not isinstance(result, EntityResolutionResult):
                continue
            if not result.resolved or not result.resolved_entity_id or not result.resolved_entity_type:
                continue
            candidate_targets.append(
                EntityCandidate(
                    artifact_id=result.resolved_entity_id,
                    artifact_type=result.resolved_entity_type,
                    confidence=_bounded_confidence(max(result.resolution_confidence, result.hint_support_score, 0.5)),
                )
            )
            entity_hints.append(
                EntityHint(
                    hint_text=result.mention.surface_text,
                    normalized_hint=result.mention.normalized_text,
                    hint_kind="semantic_target",
                    hint_source="author_understanding",
                    language=request.user_command_language,
                    confidence=_bounded_confidence(max(result.resolution_confidence, result.hint_support_score, 0.5)),
                    supported_by_author_understanding=True,
                    supported_by_document_analysis=bool(result.metadata.get("supported_by_document_analysis", False)),
                    candidate_target_id=result.resolved_entity_id,
                    candidate_target_type=result.resolved_entity_type,
                )
            )

        if "narr" in raw or "narrar" in raw or "narration" in raw:
            primary_intent_type = "narration_preparation"
        elif "review" in raw or "revisión" in raw or "revision" in raw or "revisão" in raw or "revisao" in raw:
            primary_intent_type = "review_handoff"
        elif "continue" in raw or "continuar" in raw or "continua" in raw or "seguir" in raw or "続け" in raw or len(raw.split()) <= 3:
            primary_intent_type = "structured_followup"
        elif "structure" in raw or "estructur" in raw or "estrutur" in raw or "estructura" in raw or "estrutura" in raw or "構造" in raw or "organiza" in raw or "orden" in raw:
            primary_intent_type = "structuring_request"
        else:
            primary_intent_type = "editorial_revision" if "voice" in raw or "voz" in raw else "contextual_followup"

        preserve_signals: list[str] = []
        if "voice" in raw or "voz" in raw:
            preserve_signals.append("preserve_character_voice")
        if "canon" in raw:
            preserve_signals.append("preserve_validated_canon")
        if "tension" in raw or "tensión" in raw or "tensao" in raw or "tensão" in raw:
            preserve_signals.append("preserve_scene_conflict")

        change_signals: list[str] = []
        if any(term in raw for term in ("structure", "estrutur", "構造", "organiza", "orden")):
            change_signals.append("structure_scene")
        if "review" in raw or "revisión" in raw or "revision" in raw or "revisão" in raw or "revisao" in raw:
            change_signals.append("prepare_for_review")
        if "narr" in raw or "narrar" in raw:
            change_signals.append("prepare_for_narration")

        followup_reference_text = None
        if primary_intent_type in {"structured_followup", "contextual_followup"}:
            followup_reference_text = state.last_target_id if state and state.last_target_id else request.raw_text

        if primary_intent_type == "structuring_request":
            author_goal_signals = ["structure_scene"]
        elif primary_intent_type == "review_handoff":
            author_goal_signals = ["prepare_for_review"]
        elif primary_intent_type == "narration_preparation":
            author_goal_signals = ["prepare_for_narration"]
        else:
            author_goal_signals = ["extract_story_facts"] if primary_intent_type == "contextual_followup" else ["structure_scene"]

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
            followup_reference_text=followup_reference_text,
            narrative_content_text=request.raw_text if primary_intent_type in {"structuring_request", "narrative_facts"} else None,
            meta_instruction_text=request.raw_text if "review" in raw or "narr" in raw else None,
            needs_clarification=not candidate_targets and primary_intent_type not in {"contextual_followup", "structured_followup"},
            clarification_reason="needs a supported target" if not candidate_targets and primary_intent_type not in {"contextual_followup", "structured_followup"} else None,
            parts=[],
            candidate_targets=candidate_targets,
            preferred_target=candidate_targets[0] if candidate_targets else None,
            disambiguation_reason="guided_partial_validation",
            raw_payload={"guided": True},
        )


def _bounded_confidence(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


@contextmanager
def _guided_import_overrides():
    with ExitStack() as stack:
        stack.enter_context(patch("textifai.bootstrap.analyzer.get_text_provider_config_error", return_value=False))
        stack.enter_context(
            patch(
                "textifai.derived_sources.gating.decide_llm_escalation",
                side_effect=_force_llm_escalation,
            )
        )
        stack.enter_context(
            patch(
                "textifai.derived_sources.llm_interpreter.ProviderBackedDerivedSourceInterpreter.interpret",
                side_effect=_guided_derived_interpret,
            )
        )
        stack.enter_context(patch("textifai.import_review.reviewer.extraction_requires_strict_confirmation", return_value=False))
        yield


def _force_llm_escalation(seed):
    return LLMEscalationDecision(required=True, reasons=["guided_partial_validation"])


def _guided_derived_interpret(*, seed, escalation):
    return DerivedLLMExtractionPayload(
        source_id=seed.source_id,
        source_format=seed.source_format,
        dominant_language=seed.dominant_language or "es",
        detected_languages=["es", "ja"],
        has_mixed_language=True,
        overall_confidence=0.93,
        structural_confidence=0.91,
        content_mix_signals=["es_ja_mix"],
        warnings=[],
        segment_candidates=[
            DerivedSegmentCandidate(
                candidate_id="scene_001",
                segment_text=seed.raw_extracted_text or "Scene 12",
                heading_text="Scene 12",
                probable_kind="scene",
                language="es",
                confidence=0.92,
                mixed_content=True,
                boundary_hints=["heading", "mixed_language"],
                notes=["guided_partial_validation"],
            )
        ],
        structure_signals=DerivedStructureSignals(
            recovered_headings=["Scene 12"],
            probable_block_order=["scene_001"],
            recovered_lists=[],
            ordering_confidence=0.9,
            structure_warnings=[],
            confidence=0.9,
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
        recognized_or_recovered_text=seed.raw_extracted_text or "Scene 12",
        llm_escalation_reasons=list(escalation.reasons),
        raw_payload={"guided": True},
    )


class _GuidedAuthorResponseGenerator:
    def generate(self, *, prompt):
        target = prompt.user_payload.get("resolved_target") or {}
        target_label = f"{target.get('target_type')}:{target.get('target_id')}" if target else "the anchored material"
        if not prompt.response_generation_ready:
            text = "I still need a safer anchor before I answer this as real guidance."
        elif prompt.semantic_response_kind == "structuring_suggestion":
            text = f"I would structure {target_label} around a clearer emotional progression without flattening the tension."
        elif prompt.semantic_response_kind == "revision_guidance":
            text = "I would revise this conservatively, preserving the anchored voice and canon constraints."
        elif prompt.semantic_response_kind == "canon_answer":
            text = "With the canon I recovered, this looks supportable, but I would still keep the answer explicit about its limits."
        elif prompt.semantic_response_kind == "narration_handoff":
            text = "There is enough anchored context to move into narration prep instead of stopping at an internal summary."
        else:
            text = "I can continue from the same anchored context and give you a concrete next step."
        return AnchoredAuthorResponse(
            semantic_response_kind=prompt.semantic_response_kind,
            author_facing_response=text,
            response_generation_ready=prompt.response_generation_ready,
            anchored_prompt_payload=prompt.trace_payload(),
            response_support_summary={
                "resolved_target": target,
                "prompt_template_id": prompt.prompt_template_id,
                "model_profile_used": prompt.model_profile_used,
            },
            llm_used=True,
            provider_mode="simulated",
            provider_model_used=None,
            live_model_response=None,
        )


def _build_guided_manager(session):
    return ConversationManager(
        session=session,
        executor=MinimalExecutionLayer(
            session=session,
            author_response_generator=ProviderBackedAuthorResponseGenerator(
                allow_live=_guided_live_enabled(),
                fallback_generator=_GuidedAuthorResponseGenerator(),
            ),
        ),
        recognizer=HybridIntentRecognizer(
            llm_classifier=_GuidedIntentClassifier(),
            config=HybridRecognizerConfig(llm_escalation_threshold=0.99),
        ),
        author_understanding_analyzer=HybridAuthorUnderstandingAnalyzer(
            llm_interpreter=_GuidedAuthorUnderstandingInterpreter(),
        ),
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


def _turn_snapshot(turn) -> StepObservation:
    recognized = turn.recognized_intent
    metadata = dict(recognized.metadata if recognized is not None else {})
    author_understanding = metadata.get("author_understanding")
    editorial_intent = metadata.get("editorial_intent")
    candidate_targets = list((editorial_intent or {}).get("candidate_targets", []))
    hint_support_score = None
    if isinstance(author_understanding, dict):
        hints = author_understanding.get("entity_hints", [])
        if isinstance(hints, list) and hints:
            hint_support_score = max(
                [float(item.get("confidence", 0.0)) for item in hints if isinstance(item, dict)],
                default=0.0,
            )
    if isinstance(editorial_intent, dict):
        candidate_targets = list(editorial_intent.get("candidate_targets", []))
    resolved_target_id = None
    resolved_target_type = None
    if isinstance(editorial_intent, dict):
        resolved_target_id = editorial_intent.get("resolved_target_id")
        resolved_target_type = editorial_intent.get("resolved_target_type")
    if resolved_target_id is None and recognized is not None:
        resolved_target_id = recognized.target_id
    if resolved_target_type is None and recognized is not None:
        resolved_target_type = recognized.target_type
    detected_languages = []
    if isinstance(author_understanding, dict):
        detected_languages = list(author_understanding.get("detected_languages", []))
    return StepObservation(
        name=turn.planned_task.flow_name if turn.planned_task else "unknown",
        result_type=turn.result_type,
        semantic_phase=turn.planned_task.semantic_phase if turn.planned_task else None,
        phase_classification=turn.planned_task.metadata.get("phase_classification") if turn.planned_task else None,
        llm_used=bool(turn.anchored_prompt_payload or metadata.get("llm_used") or metadata.get("escalated_to_llm")),
        recognized_intent=recognized.intent_name if recognized is not None else None,
        author_primary_intent=author_understanding.get("primary_intent_type") if isinstance(author_understanding, dict) else None,
        author_needs_clarification=author_understanding.get("needs_clarification") if isinstance(author_understanding, dict) else None,
        editorial_request_type=editorial_intent.get("request_type") if isinstance(editorial_intent, dict) else None,
        editorial_semantic_basis=editorial_intent.get("semantic_basis") if isinstance(editorial_intent, dict) else None,
        editorial_followup_mode=editorial_intent.get("followup_mode") if isinstance(editorial_intent, dict) else None,
        candidate_targets=candidate_targets,
        resolved_target_id=resolved_target_id,
        resolved_target_type=resolved_target_type,
        hint_support_score=hint_support_score,
        detected_languages=detected_languages,
        llm_escalation_required=bool(turn.anchored_prompt_payload or metadata.get("llm_used") or metadata.get("escalated_to_llm")),
        review_status=metadata.get("review_status") if isinstance(metadata.get("review_status"), str) else None,
        strict_confirmation_required=bool(metadata.get("strict_confirmation_required", False)) if isinstance(metadata, dict) else None,
        provider_mode=turn.provider_mode,
        provider_model_used=turn.provider_model_used,
        live_model_response=turn.live_model_response,
        notes=[],
        false_certainty=bool(
            resolved_target_id is not None
            and isinstance(author_understanding, dict)
            and author_understanding.get("needs_clarification")
        ),
    )


def _guided_live_enabled() -> bool:
    return os.environ.get("TEXTIFAI_GUIDED_PROVIDER_MODE", "").strip().lower() == "live_openai"


def _write_docx(path: Path, paragraphs: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    paragraph_xml = "\n".join(
        f"<w:p><w:r><w:t xml:space=\"preserve\">{escape(paragraph)}</w:t></w:r></w:p>"
        for paragraph in paragraphs
    )
    document_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        f"<w:body>{paragraph_xml}</w:body>"
        "</w:document>"
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"></Types>",
        )
        archive.writestr("word/document.xml", document_xml)
        archive.writestr(
            "_rels/.rels",
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"></Relationships>",
        )


if __name__ == "__main__":
    unittest.main()
