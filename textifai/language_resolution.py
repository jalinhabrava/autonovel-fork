from __future__ import annotations

from dataclasses import dataclass

from textifai.language_policy import LanguagePolicy, artifact_language


@dataclass(frozen=True)
class OperationLanguageResolution:
    interface_language: str
    user_command_language: str
    internal_system_language: str
    project_default_language: str
    mixed_language_allowed: bool
    operation_origin: str
    operation_language: str
    artifact_target_language: str
    artifact_type: str | None = None


def resolve_language_for_operation(
    policy: LanguagePolicy,
    *,
    artifact_type: str | None = None,
    operation_origin: str = "user",
    explicit_operation_language: str | None = None,
    explicit_artifact_language: str | None = None,
) -> OperationLanguageResolution:
    operation_language = _resolve_operation_language(
        policy,
        operation_origin=operation_origin,
        explicit_operation_language=explicit_operation_language,
    )
    target_language = explicit_artifact_language or (
        artifact_language(policy, artifact_type) if artifact_type else policy.project_default_language
    )
    return OperationLanguageResolution(
        interface_language=policy.interface_language,
        user_command_language=policy.user_command_language,
        internal_system_language=policy.internal_system_language,
        project_default_language=policy.project_default_language,
        mixed_language_allowed=policy.mixed_language_allowed,
        operation_origin=operation_origin,
        operation_language=operation_language,
        artifact_target_language=target_language,
        artifact_type=artifact_type,
    )


def serialize_language_resolution(resolution: OperationLanguageResolution) -> dict:
    return {
        "interface_language": resolution.interface_language,
        "user_command_language": resolution.user_command_language,
        "internal_system_language": resolution.internal_system_language,
        "project_default_language": resolution.project_default_language,
        "mixed_language_allowed": resolution.mixed_language_allowed,
        "operation_origin": resolution.operation_origin,
        "operation_language": resolution.operation_language,
        "artifact_target_language": resolution.artifact_target_language,
        "artifact_type": resolution.artifact_type,
    }


def _resolve_operation_language(
    policy: LanguagePolicy,
    *,
    operation_origin: str,
    explicit_operation_language: str | None = None,
) -> str:
    if explicit_operation_language:
        return explicit_operation_language
    if operation_origin == "user":
        return policy.user_command_language or policy.interface_language or "en"
    return policy.internal_system_language or "en"
