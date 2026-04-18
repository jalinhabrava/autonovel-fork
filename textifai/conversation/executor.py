from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from adapters.vault_adapter import VaultProjectAdapter
from interactive.context_commands import (
    build_chapter_context,
    build_find_context,
    build_scene_context,
    build_world_context,
)
from interactive.context_requests import (
    build_chapter_request,
    build_find_request,
    build_scene_request,
    build_world_request,
)
from interactive.payloads import validate_artifact_payload
from interactive.persistence_commands import consistency_check, decide, reject, validate
from interactive.query import parse_frontmatter, strip_frontmatter
from textifai.conversation.contracts import (
    ConversationRequest,
    ExecutionResult,
    NarrativeSignals,
    PendingConversationOperation,
    PlannedTask,
)
from textifai.editorial.contracts import (
    BeatItem,
    BeatOutline,
    EditorialStructuringResult,
    RevisionIntent,
    StoryFactItem,
    StoryFacts,
)
from textifai.editorial.narration_prep import build_narration_prep
from textifai.editorial.entity_resolution import resolve_entities
from textifai.editorial.structuring import build_editorial_structuring_result
from textifai.editorial_intent.contracts import CandidateTarget, EditorialIntent
from textifai.render import render_help
from textifai.session import TextifAISession
from textifai.conversation.state import ConversationState
from textifai.vaerl.contracts import EntityCandidate, EntityMention, EntityResolutionResult, RelatedArtifactSuggestion


class MinimalExecutionLayer:
    def __init__(self, *, session: TextifAISession | None = None) -> None:
        self.session = session

    def execute(
        self,
        task: PlannedTask,
        request: ConversationRequest,
        state: ConversationState | None = None,
    ) -> ExecutionResult:
        if task.flow_name == "noop_flow":
            unsupported_capability = task.metadata.get("unsupported_capability")
            if unsupported_capability:
                return ExecutionResult(
                    type="unsupported_flow",
                    flow_name=task.flow_name,
                    success=False,
                    result_summary=(
                        f"I understood that you want to use {unsupported_capability}, "
                        "but that conversational flow is not supported yet. Use the explicit command path for now."
                    ),
                )
            return ExecutionResult(
                type="conversation_clarification",
                flow_name=task.flow_name,
                success=False,
                result_summary=(
                    "I could not map that request to a supported runtime flow yet. "
                    "Try asking for help, context, a scene/chapter inspection, or a consistency check."
                ),
            )
        if task.flow_name == "help_flow":
            locale = self.session.locale if self.session is not None else request.interface_language
            return ExecutionResult(
                type="conversation_help",
                flow_name=task.flow_name,
                success=True,
                result_summary="Returned aligned product help.",
                result=render_help(locale),
            )

        if self.session is None:
            return ExecutionResult(
                type="missing_runtime",
                flow_name=task.flow_name,
                success=False,
                result_summary="No runtime session was available for executing this conversational flow.",
            )

        if task.flow_name == "confirm_pending_flow":
            return self._confirm_pending(task, state)
        if task.flow_name == "cancel_pending_flow":
            return self._cancel_pending(task, state)
        if task.flow_name == "editorial_structuring_flow":
            return self._execute_editorial_structuring(task, request)
        if task.flow_name == "world_lookup_flow":
            return self._execute_world(task)
        if task.flow_name == "context_search_flow":
            return self._execute_search(task, request)
        if task.flow_name == "scene_context_flow":
            return self._execute_scene(task)
        if task.flow_name == "chapter_context_flow":
            return self._execute_chapter(task)
        if task.flow_name == "consistency_check_flow":
            return self._execute_consistency_check(task)
        if task.flow_name == "decision_persistence_flow":
            return self._propose_persist_decision(task, request, state)
        if task.flow_name == "validate_artifact_flow":
            return self._propose_validate_artifact(task, state)
        if task.flow_name == "reject_artifact_flow":
            return self._propose_reject_artifact(task, state)

        return ExecutionResult(
            type="conversation_execution_stub",
            flow_name=task.flow_name,
            success=False,
            result_summary=f"Executor stub prepared {task.flow_name}.",
        )

    def _execute_editorial_structuring(self, task: PlannedTask, request: ConversationRequest) -> ExecutionResult:
        narrative_signals = _narrative_signals_from_metadata(task.metadata.get("narrative_signals"))
        editorial_intent = _editorial_intent_from_metadata(task.metadata.get("editorial_intent"))
        entity_results = _entity_results_from_metadata(task.metadata.get("vaerl_results"))
        if not entity_results:
            entity_results = resolve_entities(
                text=request.raw_text,
                vault_path=self.session.vault_path,
                known_characters=request.metadata.get("known_characters", []),
                entity_hints=list((narrative_signals.mentioned_entities if narrative_signals else []) or []),
            )
        source_text = _editorial_source_text(request.raw_text, editorial_intent)
        base_result = _last_editorial_result(self.session.last_result)

        if editorial_intent is not None and source_text is None:
            if editorial_intent.request_type == "narration_preparation" and base_result is not None:
                narration_prep = build_narration_prep(
                    target_language=task.artifact_target_language or request.project_default_language,
                    explanation_language=task.explanation_language,
                    entity_results=base_result.entity_resolution_results or entity_results,
                    beat_outline=base_result.beat_outline,
                    story_facts=base_result.story_facts,
                    revision_intent=base_result.revision_intent,
                )
                result = EditorialStructuringResult(
                    entity_resolution_results=base_result.entity_resolution_results or entity_results,
                    story_facts=base_result.story_facts,
                    beat_outline=base_result.beat_outline,
                    revision_intent=base_result.revision_intent,
                    narration_prep=narration_prep,
                    result_kind="narration_prep",
                    ready_for_validation=base_result.ready_for_validation,
                )
                return ExecutionResult(
                    type="editorial_structuring",
                    flow_name=task.flow_name,
                    success=True,
                    result_summary="Prepared editorial structure: narration prep",
                    result=result,
                    artifacts_touched=[
                        f"{entity.resolved_entity_type}:{entity.resolved_entity_id}"
                        for entity in result.entity_resolution_results
                        if entity.resolved and entity.resolved_entity_type and entity.resolved_entity_id
                    ],
                )
            return self._editorial_followup_clarification(task, editorial_intent, entity_results)

        result = build_editorial_structuring_result(
            source_text=source_text,
            language=request.user_command_language or request.interface_language,
            entity_results=entity_results,
            narrative_signals=narrative_signals,
            artifact_target_language=task.artifact_target_language,
        )
        narration_prep = build_narration_prep(
            target_language=task.artifact_target_language or request.project_default_language,
            explanation_language=task.explanation_language,
            entity_results=entity_results,
            beat_outline=result.beat_outline,
            story_facts=result.story_facts,
            revision_intent=result.revision_intent,
        )
        result = EditorialStructuringResult(
            entity_resolution_results=result.entity_resolution_results,
            story_facts=result.story_facts,
            beat_outline=result.beat_outline,
            revision_intent=result.revision_intent,
            narration_prep=narration_prep,
            result_kind=result.result_kind,
            ready_for_validation=result.ready_for_validation,
        )
        summaries = []
        if result.story_facts is not None:
            summaries.append(f"{len(result.story_facts.explicit_facts)} facts")
        if result.beat_outline is not None:
            summaries.append(f"{len(result.beat_outline.beats)} beats")
        if result.revision_intent is not None:
            summaries.append("revision intent")
        if result.narration_prep is not None and editorial_intent is not None and editorial_intent.request_type == "narration_preparation":
            summaries.append("narration prep")
        return ExecutionResult(
            type="editorial_structuring",
            flow_name=task.flow_name,
            success=True,
            result_summary="Prepared editorial structure: " + ", ".join(summaries or ["editorial result"]),
            result=result,
            artifacts_touched=[
                f"{entity.resolved_entity_type}:{entity.resolved_entity_id}"
                for entity in result.entity_resolution_results
                if entity.resolved and entity.resolved_entity_type and entity.resolved_entity_id
            ],
        )

    def _editorial_followup_clarification(
        self,
        task: PlannedTask,
        editorial_intent: EditorialIntent,
        entity_results,
    ) -> ExecutionResult:
        candidate_targets = [
            {
                "target_id": candidate.target_id,
                "target_type": candidate.target_type,
                "confidence": candidate.confidence,
            }
            for candidate in editorial_intent.candidate_targets
        ]
        resolved = {
            "target_id": editorial_intent.resolved_target_id,
            "target_type": editorial_intent.resolved_target_type,
        }
        artifact_type = editorial_intent.target_scope or resolved["target_type"]
        reason = "Need clearer narrative facts before structuring."
        if editorial_intent.request_type == "contextual_followup":
            reason = "This follow-up is anchored to a target, but it still needs a clearer note, scene, or narrative fact before we can structure it."
        elif editorial_intent.request_type in {"structuring_request", "mixed_editorial_request"}:
            reason = "This request is editorial, but the current turn does not include enough narrative facts to build a trustworthy structure."
        elif editorial_intent.request_type == "editorial_revision":
            reason = "This revision is editorial, but it needs a concrete narrative passage or fact set to revise safely."
        return ExecutionResult(
            type="conversation_clarification",
            flow_name=task.flow_name,
            success=False,
            result_summary=reason,
            result={
                "request_type": editorial_intent.request_type,
                "artifact_type": artifact_type,
                "resolved_target": resolved,
                "candidate_targets": candidate_targets,
                "related_artifacts": [
                    {
                        "target_type": candidate["target_type"],
                        "target_id": candidate["target_id"],
                        "confidence": candidate["confidence"],
                    }
                    for candidate in candidate_targets[:3]
                ],
                "next_step": "Provide the scene facts, name the note explicitly, or choose one of the candidate targets above.",
                "has_narrative_facts": False,
            },
            artifacts_touched=[],
        )

    def _execute_world(self, task: PlannedTask) -> ExecutionResult:
        resolution = self.session.resolve_language(artifact_type="world", operation_origin="user")
        request = build_world_request(
            policy=self.session.policy_name,
            token_budget=self.session.token_budget,
            interface_language=resolution.interface_language,
            user_command_language=resolution.user_command_language,
            internal_system_language=resolution.internal_system_language,
            operation_language=resolution.operation_language,
            artifact_target_language=resolution.artifact_target_language,
            mixed_language_allowed=resolution.mixed_language_allowed,
        )
        pack = build_world_context(
            str(self.session.vault_path),
            policy=self.session.policy_name,
            token_budget=self.session.token_budget,
        )
        return ExecutionResult(
            type="context_pack",
            flow_name=task.flow_name,
            success=True,
            result_summary="Loaded project/world context.",
            result=pack,
            context_request=_request_to_dict(request),
            context_pack=pack,
        )

    def _execute_search(self, task: PlannedTask, conversation_request: ConversationRequest) -> ExecutionResult:
        query = task.metadata.get("query_text") or conversation_request.raw_text
        resolution = self.session.resolve_language(operation_origin="user")
        request = build_find_request(
            query,
            policy=self.session.policy_name,
            token_budget=self.session.token_budget,
            interface_language=resolution.interface_language,
            user_command_language=resolution.user_command_language,
            internal_system_language=resolution.internal_system_language,
            operation_language=resolution.operation_language,
            artifact_target_language=resolution.artifact_target_language,
            mixed_language_allowed=resolution.mixed_language_allowed,
        )
        pack = build_find_context(
            str(self.session.vault_path),
            query,
            policy=self.session.policy_name,
            token_budget=self.session.token_budget,
        )
        return ExecutionResult(
            type="context_pack",
            flow_name=task.flow_name,
            success=True,
            result_summary="Loaded context search results.",
            result=pack,
            context_request=_request_to_dict(request),
            context_pack=pack,
        )

    def _execute_scene(self, task: PlannedTask) -> ExecutionResult:
        if not task.target_id:
            return self._missing_target(task, "A scene id is required before scene context can be inspected.")
        resolution = self.session.resolve_language(artifact_type="scene", operation_origin="user")
        request = build_scene_request(
            task.target_id,
            policy=self.session.policy_name,
            token_budget=self.session.token_budget,
            interface_language=resolution.interface_language,
            user_command_language=resolution.user_command_language,
            internal_system_language=resolution.internal_system_language,
            operation_language=resolution.operation_language,
            artifact_target_language=resolution.artifact_target_language,
            mixed_language_allowed=resolution.mixed_language_allowed,
        )
        pack = build_scene_context(
            str(self.session.vault_path),
            task.target_id,
            policy=self.session.policy_name,
            token_budget=self.session.token_budget,
        )
        return ExecutionResult(
            type="context_pack",
            flow_name=task.flow_name,
            success=True,
            result_summary=f"Loaded context for scene {task.target_id}.",
            result=pack,
            context_request=_request_to_dict(request),
            context_pack=pack,
        )

    def _execute_chapter(self, task: PlannedTask) -> ExecutionResult:
        if not task.target_id:
            return self._missing_target(task, "A chapter id is required before chapter context can be inspected.")
        resolution = self.session.resolve_language(artifact_type="chapter", operation_origin="user")
        request = build_chapter_request(
            task.target_id,
            policy=self.session.policy_name,
            token_budget=self.session.token_budget,
            interface_language=resolution.interface_language,
            user_command_language=resolution.user_command_language,
            internal_system_language=resolution.internal_system_language,
            operation_language=resolution.operation_language,
            artifact_target_language=resolution.artifact_target_language,
            mixed_language_allowed=resolution.mixed_language_allowed,
        )
        pack = build_chapter_context(
            str(self.session.vault_path),
            task.target_id,
            policy=self.session.policy_name,
            token_budget=self.session.token_budget,
        )
        return ExecutionResult(
            type="context_pack",
            flow_name=task.flow_name,
            success=True,
            result_summary=f"Loaded context for chapter {task.target_id}.",
            result=pack,
            context_request=_request_to_dict(request),
            context_pack=pack,
        )

    def _execute_consistency_check(self, task: PlannedTask) -> ExecutionResult:
        if not task.target_id or not task.target_type:
            return self._missing_target(task, "A concrete artifact target is required before running consistency check.")
        payload = _artifact_payload_from_target(self.session, task.target_type, task.target_id)
        if payload is None:
            return self._missing_target(task, "The requested artifact could not be resolved from the current vault.")
        resolution = self.session.resolve_language(
            artifact_type=payload.get("artifact_type"),
            operation_origin="user",
            explicit_artifact_language=payload.get("artifact_language") or payload.get("metadata", {}).get("artifact_language"),
        )
        payload.update(
            {
                "artifact_language": resolution.artifact_target_language,
                "operation_language": resolution.operation_language,
                "user_command_language": resolution.user_command_language,
                "internal_system_language": resolution.internal_system_language,
                "interface_language": resolution.interface_language,
                "mixed_language_allowed": resolution.mixed_language_allowed,
            }
        )
        report = consistency_check(str(self.session.vault_path), payload)
        return ExecutionResult(
            type="consistency_report",
            flow_name=task.flow_name,
            success=True,
            result_summary=report.get("summary", "Consistency check completed."),
            result=report,
            context_request=report.get("context_request"),
            context_pack=report.get("context_pack"),
        )

    def _missing_target(self, task: PlannedTask, message: str) -> ExecutionResult:
        return ExecutionResult(
            type="missing_target",
            flow_name=task.flow_name,
            success=False,
            result_summary=message,
            missing_target=True,
        )

    def _confirm_pending(self, task: PlannedTask, state: ConversationState | None) -> ExecutionResult:
        pending = state.pending_operation if state is not None else None
        if pending is None:
            return ExecutionResult(
                type="no_pending_operation",
                flow_name=task.flow_name,
                success=False,
                result_summary="There is no pending operation to confirm. Start with decide, validate, or reject first.",
            )
        if pending.operation_kind == "persist_decision":
            result = decide(str(self.session.vault_path), pending.payload)
        elif pending.operation_kind == "validate_artifact":
            result = validate(str(self.session.vault_path), pending.payload)
        elif pending.operation_kind == "reject_artifact":
            result = reject(str(self.session.vault_path), pending.payload)
        else:
            return ExecutionResult(
                type="invalid_confirmation_state",
                flow_name=task.flow_name,
                success=False,
                result_summary="The pending operation kind is not supported for confirmation.",
            )
        return ExecutionResult(
            type=result.get("type", "persisted_operation"),
            flow_name=pending.flow_name,
            success=True,
            result_summary=f"Executed pending operation: {pending.summary}",
            result=result,
            artifacts_touched=[f"{result.get('target_type')}:{result.get('target_id')}"],
            persisted=True,
            clear_pending_operation=True,
        )

    def _cancel_pending(self, task: PlannedTask, state: ConversationState | None) -> ExecutionResult:
        pending = state.pending_operation if state is not None else None
        if pending is None:
            return ExecutionResult(
                type="no_pending_operation",
                flow_name=task.flow_name,
                success=False,
                result_summary="There is no pending operation to cancel. Start with decide, validate, or reject first.",
            )
        return ExecutionResult(
            type="cancelled",
            flow_name=task.flow_name,
            success=True,
            result_summary=f"Cancelled pending operation: {pending.summary}",
            clear_pending_operation=True,
        )

    def _propose_persist_decision(
        self,
        task: PlannedTask,
        request: ConversationRequest,
        state: ConversationState | None,
    ) -> ExecutionResult:
        payload = self._decision_payload_from_request(task, request, state)
        missing_fields = [field for field in ("title", "body") if not payload.get(field)]
        summary = "persist decision"
        if payload.get("title"):
            summary = f"persist decision '{payload['title']}'"
        if missing_fields:
            return ExecutionResult(
                type="proposal_incomplete",
                flow_name=task.flow_name,
                success=False,
                result_summary=(
                    f"Decision proposal is incomplete. Missing: {', '.join(missing_fields)}. "
                    f"Provide {', '.join(missing_fields)} and ask again before confirming."
                ),
            )
        pending = PendingConversationOperation(
            operation_id=str(uuid4()),
            operation_kind="persist_decision",
            task_type=task.task_type,
            flow_name=task.flow_name,
            target_type="decision",
            target_id=None,
            artifact_target_language=task.artifact_target_language,
            explanation_language=task.explanation_language,
            payload=payload,
            summary=summary,
            executable=True,
            missing_fields=[],
            created_from_turn=(state.turn_count + 1) if state is not None else 1,
        )
        return ExecutionResult(
            type="pending_confirmation",
            flow_name=task.flow_name,
            success=True,
            result_summary=f"Prepared pending operation: {summary}. Run confirm to execute or cancel to abort.",
            pending_operation=pending,
        )

    def _propose_validate_artifact(self, task: PlannedTask, state: ConversationState | None) -> ExecutionResult:
        if not task.target_id or not task.target_type:
            return self._missing_target(task, "A concrete artifact target is required before validation can be proposed.")
        resolved = _resolve_note_target(self.session, task.target_type, task.target_id)
        if resolved is None:
            return self._missing_target(task, "The artifact to validate could not be resolved from the current vault.")
        payload = {
            "type": "artifact_state_change",
            "target_type": resolved["target_type"],
            "target_id": resolved["target_id"],
            "state": "validated",
            "origin": {
                "source": "conversation_executor",
                "user_action": "validate_artifact_flow",
            },
        }
        pending = PendingConversationOperation(
            operation_id=str(uuid4()),
            operation_kind="validate_artifact",
            task_type=task.task_type,
            flow_name=task.flow_name,
            target_type=resolved["target_type"],
            target_id=resolved["target_id"],
            artifact_target_language=task.artifact_target_language,
            explanation_language=task.explanation_language,
            payload=payload,
            summary=f"validate {resolved['target_type']}:{resolved['target_id']}",
            executable=True,
            missing_fields=[],
            created_from_turn=(state.turn_count + 1) if state is not None else 1,
        )
        return ExecutionResult(
            type="pending_confirmation",
            flow_name=task.flow_name,
            success=True,
            result_summary=f"Prepared pending operation: {pending.summary}. Run confirm to execute or cancel to abort.",
            pending_operation=pending,
        )

    def _propose_reject_artifact(self, task: PlannedTask, state: ConversationState | None) -> ExecutionResult:
        if not task.target_id or not task.target_type:
            return self._missing_target(task, "A concrete artifact target is required before rejection can be proposed.")
        resolved = _resolve_note_target(self.session, task.target_type, task.target_id)
        if resolved is None:
            return self._missing_target(task, "The artifact to reject could not be resolved from the current vault.")
        payload = {
            "type": "artifact_state_change",
            "target_type": resolved["target_type"],
            "target_id": resolved["target_id"],
            "state": "rejected",
            "origin": {
                "source": "conversation_executor",
                "user_action": "reject_artifact_flow",
            },
        }
        pending = PendingConversationOperation(
            operation_id=str(uuid4()),
            operation_kind="reject_artifact",
            task_type=task.task_type,
            flow_name=task.flow_name,
            target_type=resolved["target_type"],
            target_id=resolved["target_id"],
            artifact_target_language=task.artifact_target_language,
            explanation_language=task.explanation_language,
            payload=payload,
            summary=f"reject {resolved['target_type']}:{resolved['target_id']}",
            executable=True,
            missing_fields=[],
            created_from_turn=(state.turn_count + 1) if state is not None else 1,
        )
        return ExecutionResult(
            type="pending_confirmation",
            flow_name=task.flow_name,
            success=True,
            result_summary=f"Prepared pending operation: {pending.summary}. Run confirm to execute or cancel to abort.",
            pending_operation=pending,
        )

    def _decision_payload_from_request(
        self,
        task: PlannedTask,
        request: ConversationRequest,
        state: ConversationState | None,
    ) -> dict:
        metadata = dict(request.metadata)
        resolution = self.session.resolve_language(artifact_type="decision", operation_origin="user")
        return {
            "type": "decision_canon",
            "state": "validated",
            "title": metadata.get("decision_title") or metadata.get("title"),
            "body": metadata.get("decision_body") or metadata.get("body"),
            "affects": metadata.get("decision_affects") or metadata.get("affects") or [],
            "artifact_language": task.artifact_target_language or resolution.artifact_target_language,
            "operation_language": task.operation_language,
            "user_command_language": request.user_command_language,
            "internal_system_language": request.internal_system_language,
            "interface_language": request.interface_language,
            "mixed_language_allowed": request.mixed_language_allowed,
            "origin": {
                "source": "conversation_executor",
                "user_action": "persist_decision_flow",
            },
        }


def _request_to_dict(request) -> dict:
    return {
        "intent": request.intent,
        "target_id": request.target_id,
        "target_type": request.target_type,
        "narrative_scope": request.narrative_scope,
        "retrieval_scope": list(request.retrieval_scope),
        "query_text": request.query_text,
        "chapter_refs": list(request.chapter_refs),
        "character_ids": list(request.character_ids),
        "policy_name": request.policy_name,
        "token_budget": request.token_budget,
        "interface_language": request.interface_language,
        "user_command_language": request.user_command_language,
        "internal_system_language": request.internal_system_language,
        "operation_language": request.operation_language,
        "artifact_target_language": request.artifact_target_language,
        "mixed_language_allowed": request.mixed_language_allowed,
    }


def _artifact_payload_from_target(session: TextifAISession, target_type: str, target_id: str) -> dict | None:
    path = VaultProjectAdapter(session.vault_path).note_path(target_type, target_id)
    if not path.exists():
        return None
    text = path.read_text()
    frontmatter = parse_frontmatter(text)
    body = strip_frontmatter(text)
    payload = {
        "type": "artifact_payload",
        "artifact_kind": "note",
        "artifact_type": target_type,
        "entity_id": target_id,
        "title": frontmatter.get("title", path.stem.replace("_", " ").title()),
        "body": body,
        "state": frontmatter.get("status", "proposed"),
        "metadata": {},
        "origin": {
            "source": "conversation_executor",
            "user_action": "consistency_check_flow",
        },
    }
    artifact_language = frontmatter.get("artifact_language")
    if artifact_language:
        payload["artifact_language"] = artifact_language
    return validate_artifact_payload(payload)


def _resolve_note_target(session: TextifAISession, target_type: str, target_id: str) -> dict | None:
    try:
        path = VaultProjectAdapter(session.vault_path).note_path(target_type, target_id)
    except KeyError:
        return None
    if not path.exists():
        return None
    return {
        "target_type": target_type,
        "target_id": path.stem,
        "path": path,
    }


def _narrative_signals_from_metadata(value) -> NarrativeSignals | None:
    if not value:
        return None
    return NarrativeSignals(**value)


def _editorial_intent_from_metadata(value) -> EditorialIntent | None:
    if not value:
        return None
    candidate_targets = [CandidateTarget(**item) for item in value.get("candidate_targets", [])]
    return EditorialIntent(
        request_type=value["request_type"],
        confidence=value["confidence"],
        target_scope=value.get("target_scope"),
        resolved_target_type=value.get("resolved_target_type"),
        resolved_target_id=value.get("resolved_target_id"),
        candidate_targets=candidate_targets,
        followup_mode=value.get("followup_mode", "none"),
        preserve_constraints=list(value.get("preserve_constraints", [])),
        editorial_goals=list(value.get("editorial_goals", [])),
        metadata=dict(value.get("metadata", {})),
    )


def _entity_results_from_metadata(items) -> list[EntityResolutionResult]:
    if not items:
        return []
    results: list[EntityResolutionResult] = []
    for item in items:
        mention = EntityMention(**item["mention"])
        candidates = [EntityCandidate(**candidate) for candidate in item.get("candidate_entities", [])]
        related = [RelatedArtifactSuggestion(**suggestion) for suggestion in item.get("related_artifacts_suggested", [])]
        results.append(
            EntityResolutionResult(
                query_text=item["query_text"],
                mention=mention,
                candidate_entities=candidates,
                resolved=item["resolved"],
                resolution_confidence=item["resolution_confidence"],
                resolution_source=item.get("resolution_source"),
                resolved_entity_id=item.get("resolved_entity_id"),
                resolved_entity_type=item.get("resolved_entity_type"),
                related_artifacts_suggested=related,
                metadata=dict(item.get("metadata", {})),
            )
        )
    return results


def _editorial_source_text(raw_text: str, editorial_intent: EditorialIntent | None) -> str | None:
    if editorial_intent is None:
        return raw_text
    source_text = editorial_intent.metadata.get("narrative_source_text")
    if source_text is None:
        return None
    return source_text


def _last_editorial_result(last_result) -> EditorialStructuringResult | None:
    if not isinstance(last_result, dict) or last_result.get("type") != "editorial_structuring":
        return None
    data = last_result.get("data")
    if not isinstance(data, dict):
        return None
    entity_results = _entity_results_from_metadata(data.get("entity_resolution_results"))
    story_facts = _story_facts_from_dict(data.get("story_facts"))
    beat_outline = _beat_outline_from_dict(data.get("beat_outline"))
    revision_intent = _revision_intent_from_dict(data.get("revision_intent"))
    narration_prep = None
    return EditorialStructuringResult(
        entity_resolution_results=entity_results,
        story_facts=story_facts,
        beat_outline=beat_outline,
        revision_intent=revision_intent,
        narration_prep=narration_prep,
        result_kind=data.get("result_kind", "mixed"),
        ready_for_validation=bool(data.get("ready_for_validation", False)),
    )


def _story_facts_from_dict(value) -> StoryFacts | None:
    if not value:
        return None
    explicit_facts = [StoryFactItem(**item) for item in value.get("explicit_facts", [])]
    inferred_facts = [StoryFactItem(**item) for item in value.get("inferred_facts", [])]
    return StoryFacts(
        source_text=value["source_text"],
        language=value["language"],
        characters_involved=list(value.get("characters_involved", [])),
        locations_involved=list(value.get("locations_involved", [])),
        objects_involved=list(value.get("objects_involved", [])),
        premise=value.get("premise"),
        core_conflict=value.get("core_conflict"),
        goals=list(value.get("goals", [])),
        constraints=list(value.get("constraints", [])),
        canon_constraints=list(value.get("canon_constraints", [])),
        explicit_facts=explicit_facts,
        inferred_facts=inferred_facts,
        open_questions=list(value.get("open_questions", [])),
    )


def _beat_outline_from_dict(value) -> BeatOutline | None:
    if not value:
        return None
    beats = [BeatItem(**item) for item in value.get("beats", [])]
    return BeatOutline(
        source_kind=value["source_kind"],
        title=value.get("title"),
        beats=beats,
        emotional_arc=list(value.get("emotional_arc", [])),
        target_language=value.get("target_language"),
        continuity_notes=list(value.get("continuity_notes", [])),
        canon_checks=list(value.get("canon_checks", [])),
    )


def _revision_intent_from_dict(value) -> RevisionIntent | None:
    if not value:
        return None
    return RevisionIntent(
        source_text=value["source_text"],
        target_scope=value.get("target_scope"),
        issue_types=list(value.get("issue_types", [])),
        desired_changes=list(value.get("desired_changes", [])),
        must_preserve=list(value.get("must_preserve", [])),
        priority=value.get("priority"),
        target_hint=value.get("target_hint"),
    )
