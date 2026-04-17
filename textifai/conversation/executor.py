from __future__ import annotations

from pathlib import Path

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
from interactive.persistence_commands import consistency_check
from interactive.query import parse_frontmatter, strip_frontmatter
from textifai.conversation.contracts import ConversationRequest, ExecutionResult, PlannedTask
from textifai.render import render_help
from textifai.session import TextifAISession
from textifai.conversation.state import ConversationState


class MinimalExecutionLayer:
    def __init__(self, *, session: TextifAISession | None = None) -> None:
        self.session = session

    def execute(
        self,
        task: PlannedTask,
        request: ConversationRequest,
        state: ConversationState | None = None,
    ) -> ExecutionResult:
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

        return ExecutionResult(
            type="conversation_execution_stub",
            flow_name=task.flow_name,
            success=False,
            result_summary=f"Executor stub prepared {task.flow_name}.",
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
