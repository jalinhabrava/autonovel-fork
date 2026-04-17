from __future__ import annotations

from pathlib import Path

from adapters.vault_adapter import VaultProjectAdapter
from interactive.context_commands import debug_context
from interactive.context_requests import build_consistency_request
from interactive.payloads import (
    decision_payload_to_artifact_payload,
    validate_artifact_payload,
    validate_state_change_payload,
)
from interactive.query import (
    filter_records_by_status,
    infer_characters,
    infer_refs,
    list_character_titles,
    list_note_records,
    note_record,
)
from vault.notes import artifact_path_for, update_note_status, write_artifact_payload


def decide(vault_root: str | Path, payload: dict) -> dict:
    artifact_payload = decision_payload_to_artifact_payload(payload)
    result = _persist_artifact_payload(vault_root, artifact_payload, mode="upsert", enforce_verify=False)
    return {
        "type": "decision_canon",
        "state": result["state"],
        "target_type": result["target_type"],
        "target_id": result["target_id"],
        "path": result["path"],
    }


def validate(vault_root: str | Path, payload: dict) -> dict:
    change = validate_state_change_payload(payload, expected_state="validated")
    path = update_note_status(
        vault_root,
        note_type=change["target_type"],
        slug=change["target_id"],
        status="validated",
    )
    return {
        "type": change["type"],
        "state": "validated",
        "target_type": change["target_type"],
        "target_id": change["target_id"],
        "path": str(path),
    }


def reject(vault_root: str | Path, payload: dict) -> dict:
    change = validate_state_change_payload(payload, expected_state="rejected")
    path = update_note_status(
        vault_root,
        note_type=change["target_type"],
        slug=change["target_id"],
        status="rejected",
    )
    return {
        "type": change["type"],
        "state": "rejected",
        "target_type": change["target_type"],
        "target_id": change["target_id"],
        "path": str(path),
    }


def consistency_check(vault_root: str | Path, payload: dict) -> dict:
    artifact = validate_artifact_payload(payload)
    return _consistency_report(vault_root, artifact)


def create_note(vault_root: str | Path, payload: dict) -> dict:
    return _persist_artifact_payload(vault_root, payload, mode="create", enforce_verify=True)


def update_note(vault_root: str | Path, payload: dict) -> dict:
    return _persist_artifact_payload(vault_root, payload, mode="update", enforce_verify=True)


def _persist_artifact_payload(
    vault_root: str | Path,
    payload: dict,
    *,
    mode: str,
    enforce_verify: bool,
) -> dict:
    artifact = validate_artifact_payload(payload)
    note_path = artifact_path_for(
        vault_root,
        artifact_kind=artifact["artifact_kind"],
        artifact_type=artifact["artifact_type"],
        entity_id=artifact["entity_id"],
    )
    exists = note_path.exists()

    if mode == "create" and exists:
        raise FileExistsError(f"Vault note already exists: {note_path}")
    if mode == "update" and not exists:
        raise FileNotFoundError(f"Vault note does not exist: {note_path}")

    report = _consistency_report(vault_root, artifact)
    if enforce_verify and not report["ok"]:
        return {
            "type": artifact["type"],
            "status": "blocked",
            "state": artifact["state"],
            "target_type": artifact["artifact_type"],
            "target_id": artifact["entity_id"],
            "verification": report,
        }

    metadata = dict(artifact["metadata"])
    metadata.update(_flatten_origin(artifact.get("origin", {})))
    path = write_artifact_payload(
        vault_root,
        artifact_kind=artifact["artifact_kind"],
        artifact_type=artifact["artifact_type"],
        entity_id=artifact["entity_id"],
        title=artifact["title"],
        body=artifact["body"],
        status=artifact["state"],
        metadata=metadata,
    )
    return {
        "type": artifact["type"],
        "status": "written",
        "state": artifact["state"],
        "artifact_kind": artifact["artifact_kind"],
        "target_type": artifact["artifact_type"],
        "target_id": artifact["entity_id"],
        "path": str(path),
        "verification": report,
    }


def _consistency_report(vault_root: str | Path, artifact: dict) -> dict:
    adapter = VaultProjectAdapter(vault_root)
    request = build_consistency_request(artifact)
    debug = debug_context(
        str(vault_root),
        intent=request.intent,
        narrative_scope=request.narrative_scope or "fragment",
        retrieval_scope=list(request.retrieval_scope),
        target_id=request.target_id,
        target_type=request.target_type,
        policy=request.policy_name,
        token_budget=request.token_budget,
        query_text=request.query_text,
        chapter_refs=list(request.chapter_refs),
        character_ids=list(request.character_ids),
        debug_mode="summary",
        max_candidates=12,
    )
    pack = debug["context_pack"]
    character_titles = list_character_titles(adapter)
    combined_validated_context = _combined_context_from_pack(pack).lower()
    text = f"{artifact['title']}\n{artifact['body']}"
    implied_characters = infer_characters(text, character_titles)
    canon_refs = [entry["id"] for entry in pack["hard_constraints"] if entry["artifact_type"] in {"canon", "decision"}]
    lore_refs = [
        entry["id"]
        for entry in pack["hard_constraints"] + pack["narrative_context"]
        if entry["artifact_type"] in {"world", "lore", "timeline"}
    ]

    issues: list[dict] = []
    suggestions: list[str] = []
    implications: list[str] = []

    risky_terms = [
        "invincible",
        "invencible",
        "immortal",
        "immortality",
        "omnipotent",
        "omnipotente",
        "unlimited power",
        "poder ilimitado",
        "unstoppable",
        "imparable",
        "godlike",
        "divine power",
    ]
    no_cost_terms = [
        "without cost",
        "no cost",
        "sin coste",
        "sin costo",
        "without limitation",
        "sin limite",
        "sin limitacion",
    ]

    lowered = text.lower()
    for term in risky_terms:
        if term in lowered and term not in combined_validated_context:
            issues.append(
                {
                    "code": "power_escalation_out_of_context",
                    "severity": "high",
                    "blocking": artifact["artifact_type"] != "decision",
                    "message": (
                        f"The note introduces '{term}' without support in validated lore or canon."
                    ),
                    "suggested_action": "Constrain the ability or add an explicit canon decision before persisting.",
                }
            )
            implications.append(f"New high-power capability implied by term '{term}'.")
            suggestions.append("If this change is intentional, register its limits and costs in canon.")
            break

    if any(term in lowered for term in no_cost_terms) and any(
        marker in combined_validated_context for marker in ["cost", "limit", "restriction", "price", "drawback"]
    ):
        issues.append(
            {
                "code": "costless_ability_conflicts_with_validated_limits",
                "severity": "high",
                "blocking": artifact["artifact_type"] != "decision",
                "message": "The note suggests abilities without cost or limit, but validated context describes costs or restrictions.",
                "suggested_action": "Restore explicit constraints or capture the systemic change as a canon decision.",
            }
        )
        suggestions.append("Review validated world/canon limits before updating this note.")

    if artifact["artifact_type"] in {"scene", "chapter", "lore"} and not (canon_refs or lore_refs):
        implications.append("This note introduces content without explicit canon/lore references.")
        suggestions.append("Consider linking this note to existing lore or validating the new implication in canon.")

    if artifact["artifact_type"] == "character" and not implied_characters:
        suggestions.append("Consider linking this profile to existing character relations or scenes for traceability.")

    blocking_issues = [issue for issue in issues if issue["blocking"]]
    summary = "No blocking consistency issues detected."
    if blocking_issues:
        summary = "Blocking consistency issues detected. Persistence should wait for revision or canon clarification."
    elif issues:
        summary = "Non-blocking consistency issues detected."
    elif implications:
        summary = "No contradictions detected, but the note introduces implications worth capturing in canon."

    return {
        "type": "consistency_report",
        "ok": not blocking_issues,
        "summary": summary,
        "artifact_kind": artifact["artifact_kind"],
        "target_type": artifact["artifact_type"],
        "target_id": artifact["entity_id"],
        "characters": implied_characters,
        "canon_refs": canon_refs,
        "lore_refs": lore_refs,
        "issues": issues,
        "implications": implications,
        "suggested_actions": _unique(suggestions),
        "context_request": {
            "intent": request.intent,
            "narrative_scope": request.narrative_scope,
            "retrieval_scope": list(request.retrieval_scope),
            "target_id": request.target_id,
            "policy": request.policy_name,
            "token_budget": request.token_budget,
        },
        "context_pack": pack,
    }


def _flatten_origin(origin: dict) -> dict[str, str]:
    metadata: dict[str, str] = {}
    if not origin:
        return metadata
    source = origin.get("source")
    if source:
        metadata["source"] = str(source)
    chapter_ids = origin.get("chapter_ids")
    if chapter_ids:
        metadata["chapter_ids"] = ",".join(str(item) for item in chapter_ids)
    user_action = origin.get("user_action")
    if user_action:
        metadata["user_action"] = str(user_action)
    return metadata


def get_existing_artifact_status(vault_root: str | Path, payload: dict) -> str | None:
    artifact = validate_artifact_payload(payload)
    path = artifact_path_for(
        vault_root,
        artifact_kind=artifact["artifact_kind"],
        artifact_type=artifact["artifact_type"],
        entity_id=artifact["entity_id"],
    )
    if not path.exists():
        return None
    record = note_record(path, artifact["artifact_type"])
    return record["frontmatter"].get("status", "proposed")


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _combined_context_from_pack(pack: dict) -> str:
    parts = []
    for entry in pack["hard_constraints"]:
        parts.append(entry["content"])
    for entry in pack["narrative_context"]:
        parts.append(entry["content"])
    for entry in pack["voice_context"]["project_voice"]:
        parts.append(entry["content"])
    for entry in pack["voice_context"]["character_voice"]:
        parts.append(entry["content"])
    for entry in pack["evidence"]:
        parts.append(entry["content"])
    return "\n".join(parts)
