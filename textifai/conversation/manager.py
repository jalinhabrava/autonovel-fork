from __future__ import annotations

from dataclasses import asdict, is_dataclass

from textifai.conversation.contracts import ConversationRequest, ConversationTurn, ExecutionResult
from textifai.author_understanding.hybrid_analysis import HybridAuthorUnderstandingAnalyzer
from textifai.conversation.executor import MinimalExecutionLayer
from textifai.conversation.hybrid_recognizer import HybridIntentRecognizer
from textifai.conversation.planner import TaskPlanner
from textifai.conversation.state import ConversationState, apply_turn_to_state, create_conversation_state
from textifai.editorial_intent.classifier import classify_editorial_intent
from textifai.editorial.entity_resolution import resolve_entities
from textifai.session import TextifAISession


class ConversationManager:
    def __init__(
        self,
        *,
        session: TextifAISession | None = None,
        state: ConversationState | None = None,
        recognizer: HybridIntentRecognizer | None = None,
        planner: TaskPlanner | None = None,
        executor: MinimalExecutionLayer | None = None,
        author_understanding_analyzer: HybridAuthorUnderstandingAnalyzer | None = None,
    ) -> None:
        self.session = session
        self.state = state or (session.conversation_state if session is not None else None)
        self.recognizer = recognizer or HybridIntentRecognizer()
        self.planner = planner or TaskPlanner()
        self.executor = executor or MinimalExecutionLayer(session=session)
        self.author_understanding_analyzer = author_understanding_analyzer or HybridAuthorUnderstandingAnalyzer.from_session(session)
        self.last_execution_result: ExecutionResult | None = None

    def handle_request(self, request: ConversationRequest) -> ConversationTurn:
        if self.state is None:
            self.state = create_conversation_state(
                explanation_language=request.explanation_language or request.interface_language,
                artifact_target_language=request.artifact_target_language,
            )
        intent = self.recognizer.recognize(request, self.state)
        intent = self._enrich_editorial_intent(intent, request)
        task = self.planner.plan(request, intent, self.state)
        if self._has_pending_conflict(task):
            self.last_execution_result = ExecutionResult(
                type="pending_operation_conflict",
                flow_name=task.flow_name,
                success=False,
                result_summary="There is already a pending operation. Confirm or cancel it before starting another persistent action.",
            )
            turn = ConversationTurn(
                turn_index=self.state.turn_count + 1,
                request=request,
                recognized_intent=intent,
                planned_task=task,
                result_type="pending_operation_conflict",
                result_summary=(
                    "There is already a pending operation. Confirm or cancel it before starting another persistent action."
                ),
                artifacts_touched=[],
                context_used=False,
                persisted=False,
                response_generation_ready=False,
                semantic_response_kind=task.metadata.get("semantic_response_kind"),
            )
            self.state = apply_turn_to_state(self.state, turn)
            if self.session is not None:
                self.session.conversation_state = self.state
            return turn
        execution = self.executor.execute(task, request, self.state)
        self.last_execution_result = execution
        turn = ConversationTurn(
            turn_index=self.state.turn_count + 1,
            request=request,
            recognized_intent=intent,
            planned_task=task,
            result_type=execution.type,
            result_summary=execution.result_summary,
            artifacts_touched=execution.artifacts_touched,
            context_used=execution.context_pack is not None or task.requires_context,
            persisted=execution.persisted,
            response_generation_ready=execution.response_generation_ready,
            semantic_response_kind=execution.semantic_response_kind,
            anchored_prompt_payload=execution.anchored_prompt_payload,
            author_facing_response=execution.author_facing_response,
            response_support_summary=execution.response_support_summary,
            provider_mode=execution.provider_mode,
            response_generation_mode=execution.response_generation_mode,
            response_generation_reason=execution.response_generation_reason,
            provider_execution_enabled=execution.provider_execution_enabled,
            provider_execution_mode=execution.provider_execution_mode,
            provider_model_used=execution.provider_model_used,
            live_model_response=execution.live_model_response,
            simulated_preview_enabled=execution.simulated_preview_enabled,
            simulated_preview_output=execution.simulated_preview_output,
        )
        self.state = apply_turn_to_state(
            self.state,
            turn,
            context_request=execution.context_request,
            context_pack=execution.context_pack,
            pending_operation=execution.pending_operation,
            clear_pending_operation=execution.clear_pending_operation,
        )
        if self.session is not None:
            self.session.conversation_state = self.state
            if isinstance(execution.result, dict):
                remembered = execution.result
            elif execution.result is not None and is_dataclass(execution.result):
                remembered = {"type": execution.type, "summary": execution.result_summary, "data": asdict(execution.result)}
            else:
                remembered = {"type": execution.type, "summary": execution.result_summary}
            remembered["response_generation_ready"] = execution.response_generation_ready
            remembered["semantic_response_kind"] = execution.semantic_response_kind
            remembered["author_facing_response"] = execution.author_facing_response
            remembered["anchored_prompt_payload"] = execution.anchored_prompt_payload
            remembered["response_support_summary"] = execution.response_support_summary
            remembered["provider_mode"] = execution.provider_mode
            remembered["response_generation_mode"] = execution.response_generation_mode
            remembered["response_generation_reason"] = execution.response_generation_reason
            remembered["provider_execution_enabled"] = execution.provider_execution_enabled
            remembered["provider_execution_mode"] = execution.provider_execution_mode
            remembered["provider_model_used"] = execution.provider_model_used
            remembered["live_model_response"] = execution.live_model_response
            remembered["simulated_preview_enabled"] = execution.simulated_preview_enabled
            remembered["simulated_preview_output"] = execution.simulated_preview_output
            self.session.remember(remembered, request=execution.context_request)
        return turn

    def _enrich_editorial_intent(self, intent, request: ConversationRequest):
        entity_results = []
        entity_hints = []
        request_entity_hints = request.metadata.get("entity_hints", [])
        if isinstance(request_entity_hints, list):
            entity_hints.extend(request_entity_hints)
        project_confirmed_aliases = request.metadata.get("project_confirmed_aliases", [])
        if isinstance(project_confirmed_aliases, list):
            entity_hints.extend(project_confirmed_aliases)
        if intent.narrative_signals is not None:
            entity_hints.extend(intent.narrative_signals.mentioned_entities)
        if self.session is not None:
            entity_results = resolve_entities(
                text=request.raw_text,
                vault_path=self.session.vault_path,
                known_characters=request.metadata.get("known_characters", []),
                entity_hints=entity_hints,
            )
        author_understanding = self.author_understanding_analyzer.analyze(
            request=request,
            rule_intent=intent,
            narrative_signals=intent.narrative_signals,
            entity_results=entity_results,
            state=self.state,
        )
        editorial_intent = classify_editorial_intent(
            raw_text=request.raw_text,
            recognized_intent_name=intent.intent_name,
            entity_results=entity_results,
            narrative_signals=intent.narrative_signals,
            state=self.state,
            author_understanding=author_understanding,
        )
        if editorial_intent is None:
            metadata = dict(intent.metadata)
            metadata["author_understanding"] = asdict(author_understanding)
            metadata["vaerl_results"] = [asdict(item) for item in entity_results]
            return intent.__class__(
                intent_name=intent.intent_name,
                confidence=intent.confidence,
                target_type=intent.target_type,
                target_id=intent.target_id,
                requires_target=intent.requires_target,
                ephemeral_hint=intent.ephemeral_hint,
                persistent_hint=intent.persistent_hint,
                signals=list(intent.signals),
                narrative_signals=intent.narrative_signals,
                editorial_intent=None,
                recognizer_kind=intent.recognizer_kind,
                metadata=metadata,
            )
        metadata = dict(intent.metadata)
        metadata["author_understanding"] = asdict(author_understanding)
        metadata["editorial_intent"] = asdict(editorial_intent)
        metadata["vaerl_results"] = [asdict(item) for item in entity_results]
        return intent.__class__(
            intent_name=intent.intent_name,
            confidence=intent.confidence,
            target_type=intent.target_type,
            target_id=intent.target_id,
            requires_target=intent.requires_target,
            ephemeral_hint=intent.ephemeral_hint,
            persistent_hint=intent.persistent_hint,
            signals=list(intent.signals),
            narrative_signals=intent.narrative_signals,
            editorial_intent=editorial_intent,
            recognizer_kind=intent.recognizer_kind,
            metadata=metadata,
        )

    def _has_pending_conflict(self, task) -> bool:
        if self.state is None or self.state.pending_operation is None:
            return False
        return task.flow_name in {
            "decision_persistence_flow",
            "validate_artifact_flow",
            "reject_artifact_flow",
        }
