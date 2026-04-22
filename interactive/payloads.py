from __future__ import annotations

from vault.schema import NOTE_STATUSES, slugify
from vault.notes import NOTE_TYPE_DIRS, ROOT_ARTIFACT_KINDS, normalize_note_type


def build_context_pack(
    *,
    scope: str,
    target_id: str,
    summary: str,
    pov: str | None = None,
    characters: list[str] | None = None,
    canon_refs: list[str] | None = None,
    lore_refs: list[str] | None = None,
    chapter_refs: list[str] | None = None,
    selected_fragment: dict[str, int] | None = None,
    matches: list[dict] | None = None,
) -> dict:
    payload = {
        "type": "context_pack",
        "scope": scope,
        "target_id": target_id,
        "pov": pov,
        "characters": characters or [],
        "canon_refs": canon_refs or [],
        "lore_refs": lore_refs or [],
        "chapter_refs": chapter_refs or [],
        "summary": summary,
        "selected_fragment": selected_fragment or {"start_line": 1, "end_line": 1},
    }
    if matches:
        payload["matches"] = matches
    return payload


def validate_decision_canon_payload(payload: dict) -> dict:
    if payload.get("type") != "decision_canon":
        raise ValueError("Expected payload type 'decision_canon'.")
    state = payload.get("state")
    if state not in NOTE_STATUSES:
        raise ValueError(f"Invalid state {state!r}. Expected one of {NOTE_STATUSES}.")
    if not payload.get("title"):
        raise ValueError("decision_canon payload requires a title.")
    if not payload.get("body"):
        raise ValueError("decision_canon payload requires a body.")
    normalized = dict(payload)
    normalized["decision_id"] = payload.get("decision_id") or slugify(str(payload["title"]))
    normalized["affects"] = list(payload.get("affects", []))
    normalized["origin"] = dict(payload.get("origin", {}))
    artifact_language = payload.get("artifact_language") or payload.get("metadata", {}).get("artifact_language")
    if artifact_language:
        normalized["artifact_language"] = str(artifact_language)
    return normalized


def validate_artifact_payload(payload: dict) -> dict:
    if payload.get("type") != "artifact_payload":
        raise ValueError("Expected payload type 'artifact_payload'.")
    artifact_kind = payload.get("artifact_kind", "note")
    artifact_type = payload.get("artifact_type")
    if artifact_kind == "note":
        artifact_type = normalize_note_type(artifact_type)
        if artifact_type not in NOTE_TYPE_DIRS:
            raise ValueError(f"Unsupported artifact_type {artifact_type!r}. Expected one of {tuple(NOTE_TYPE_DIRS)}.")
    elif artifact_kind == "root_artifact":
        if artifact_type not in ROOT_ARTIFACT_KINDS:
            raise ValueError(
                f"Unsupported root artifact_type {artifact_type!r}. Expected one of {tuple(ROOT_ARTIFACT_KINDS)}."
            )
    else:
        raise ValueError("artifact_payload requires artifact_kind 'note' or 'root_artifact'.")
    state = payload.get("state")
    if state not in NOTE_STATUSES:
        raise ValueError(f"Invalid state {state!r}. Expected one of {NOTE_STATUSES}.")
    title = payload.get("title")
    body = payload.get("body")
    entity_id = payload.get("entity_id")
    if not title:
        raise ValueError("artifact_payload requires a title.")
    if body is None:
        raise ValueError("artifact_payload requires a body.")
    if not entity_id:
        raise ValueError("artifact_payload requires an entity_id.")
    return {
        "type": "artifact_payload",
        "artifact_kind": artifact_kind,
        "artifact_type": artifact_type,
        "entity_id": slugify(str(entity_id)),
        "title": str(title),
        "body": str(body),
        "state": state,
        "metadata": dict(payload.get("metadata", {})),
        "origin": dict(payload.get("origin", {})),
        "artifact_language": payload.get("artifact_language") or payload.get("metadata", {}).get("artifact_language"),
        "operation_language": payload.get("operation_language"),
        "user_command_language": payload.get("user_command_language"),
        "internal_system_language": payload.get("internal_system_language"),
        "interface_language": payload.get("interface_language"),
        "mixed_language_allowed": payload.get("mixed_language_allowed"),
    }


def decision_payload_to_artifact_payload(payload: dict) -> dict:
    decision = validate_decision_canon_payload(payload)
    metadata: dict[str, str] = {}
    if decision["affects"]:
        metadata["affects"] = ",".join(decision["affects"])
    if decision.get("artifact_language"):
        metadata["artifact_language"] = str(decision["artifact_language"])
    return {
        "type": "artifact_payload",
        "artifact_kind": "note",
        "artifact_type": "decision",
        "entity_id": decision["decision_id"],
        "title": decision["title"],
        "body": decision["body"],
        "state": decision["state"],
        "metadata": metadata,
        "origin": decision["origin"],
        "artifact_language": decision.get("artifact_language"),
    }


def validate_state_change_payload(payload: dict, *, expected_state: str) -> dict:
    if expected_state not in NOTE_STATUSES:
        raise ValueError(f"Invalid expected state {expected_state!r}.")
    state = payload.get("state")
    if state != expected_state:
        raise ValueError(f"Expected payload state {expected_state!r}, got {state!r}.")
    target_type = payload.get("target_type")
    target_id = payload.get("target_id")
    if not target_type or not target_id:
        raise ValueError("State change payload requires target_type and target_id.")
    return {
        "type": payload.get("type", "artifact_state_change"),
        "target_type": target_type,
        "target_id": target_id,
        "state": state,
        "origin": dict(payload.get("origin", {})),
    }
