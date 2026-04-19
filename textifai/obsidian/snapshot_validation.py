from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from textifai.obsidian.contracts import (
    CURRENT_OBSIDIAN_SNAPSHOT_SCHEMA_VERSION,
    DEFAULT_SNAPSHOT_STALE_AFTER_SECONDS,
    SUPPORTED_OBSIDIAN_SNAPSHOT_SCHEMA_VERSIONS,
    ObsidianBridgeSnapshot,
    ObsidianNote,
    ObsidianSourceStatus,
    ValidatedObsidianSnapshot,
)
from textifai.obsidian.artifact_types import normalize_artifact_type
from textifai.obsidian.parser import parse_obsidian_frontmatter
from vault.schema import slugify


def validate_obsidian_snapshot(
    snapshot_path: str | Path,
    *,
    stale_after_seconds: int = DEFAULT_SNAPSHOT_STALE_AFTER_SECONDS,
) -> ValidatedObsidianSnapshot:
    path = Path(snapshot_path).expanduser().resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ValidatedObsidianSnapshot(
            snapshot=None,
            status=ObsidianSourceStatus(
                reliability="obsidian_bridge_snapshot_invalid",
                source_kind="obsidian_bridge_snapshot",
                snapshot_path=str(path),
                bridge_preferred=True,
                requires_caution=True,
                issues=["snapshot_missing"],
            ),
        )
    except json.JSONDecodeError as exc:
        return ValidatedObsidianSnapshot(
            snapshot=None,
            status=ObsidianSourceStatus(
                reliability="obsidian_bridge_snapshot_invalid",
                source_kind="obsidian_bridge_snapshot",
                snapshot_path=str(path),
                bridge_preferred=True,
                requires_caution=True,
                issues=[f"snapshot_json_decode_error:{exc.msg}"],
            ),
        )

    issues: list[str] = []
    schema_version = str(payload.get("schema_version") or "")
    compatibility_mode = schema_version == "1.0"
    if schema_version not in SUPPORTED_OBSIDIAN_SNAPSHOT_SCHEMA_VERSIONS:
        issues.append("unsupported_schema_version")
    source = str(payload.get("source") or "")
    if not source:
        issues.append("missing_source")
    generated_at = payload.get("generated_at")
    generated_dt = _parse_timestamp(generated_at)
    if generated_dt is None:
        issues.append("invalid_generated_at")
    export_complete = bool(payload.get("export_complete")) if "export_complete" in payload else compatibility_mode
    if not export_complete:
        issues.append("export_incomplete")
    vault_id = payload.get("vault_id")
    if not compatibility_mode and not str(vault_id or "").strip():
        issues.append("missing_vault_id")
    installation_id = payload.get("installation_id")
    if not compatibility_mode and not str(installation_id or "").strip():
        issues.append("missing_installation_id")
    notes_payload = payload.get("notes")
    if not isinstance(notes_payload, list):
        issues.append("notes_not_list")
        notes_payload = []
    declared_count = int(payload.get("note_count") or len(notes_payload))
    if not compatibility_mode and declared_count != len(notes_payload):
        issues.append("note_count_mismatch")

    notes: list[ObsidianNote] = []
    for item in notes_payload:
        if not isinstance(item, dict):
            issues.append("note_item_invalid")
            continue
        note = _note_from_snapshot(item, issues)
        if note is not None:
            notes.append(note)

    snapshot = None
    age_seconds = _age_seconds(generated_dt)
    reliability = "obsidian_bridge_snapshot_fresh"
    requires_caution = False
    compatibility_warning = schema_version != CURRENT_OBSIDIAN_SNAPSHOT_SCHEMA_VERSION
    if compatibility_warning:
        issues.append("schema_backward_compatibility_mode")

    if any(issue in issues for issue in {
        "unsupported_schema_version",
        "invalid_generated_at",
        "notes_not_list",
        "missing_vault_id",
        "missing_installation_id",
        "export_incomplete",
        "note_count_mismatch",
        "note_item_invalid",
    }):
        reliability = "obsidian_bridge_snapshot_invalid"
        requires_caution = True
    elif age_seconds is not None and age_seconds > stale_after_seconds:
        reliability = "obsidian_bridge_snapshot_stale"
        requires_caution = True
    elif compatibility_warning or payload.get("warnings"):
        reliability = "obsidian_bridge_snapshot_stale"
        requires_caution = True

    if reliability != "obsidian_bridge_snapshot_invalid":
        snapshot = ObsidianBridgeSnapshot(
            schema_version=schema_version or CURRENT_OBSIDIAN_SNAPSHOT_SCHEMA_VERSION,
            source=source or "obsidian_textifai_bridge",
            generated_at=generated_at,
            vault_name=payload.get("vault_name"),
            plugin_version=payload.get("plugin_version"),
            obsidian_app_version=payload.get("obsidian_app_version"),
            export_reason=payload.get("export_reason"),
            export_complete=export_complete,
            note_count=declared_count,
            vault_id=str(vault_id),
            installation_id=str(installation_id),
            vault_root_hint=payload.get("vault_root_hint"),
            generated_unix_ms=payload.get("generated_unix_ms"),
            export_sequence=payload.get("export_sequence"),
            bridge_capabilities=dict(payload.get("bridge_capabilities") or {}),
            errors=[str(item) for item in payload.get("errors", []) if str(item).strip()],
            warnings=[str(item) for item in payload.get("warnings", []) if str(item).strip()],
            notes=notes,
        )

    return ValidatedObsidianSnapshot(
        snapshot=snapshot,
        status=ObsidianSourceStatus(
            reliability=reliability,
            source_kind="obsidian_bridge_snapshot",
            snapshot_path=str(path),
            schema_version=schema_version or None,
            generated_at=generated_at,
            snapshot_age_seconds=age_seconds,
            bridge_preferred=True,
            fallback_used=False,
            requires_caution=requires_caution,
            issues=issues,
        ),
    )


def _note_from_snapshot(value: dict[str, Any], issues: list[str]) -> ObsidianNote | None:
    relative_path = str(value.get("vault_relative_path") or value.get("path") or "").strip()
    if not relative_path:
        issues.append("note_missing_path")
        return None
    title = str(value.get("title") or Path(relative_path).stem or "Note").strip()
    note_id = slugify(str(value.get("note_id") or value.get("slug") or Path(relative_path).with_suffix("").as_posix()))
    if not note_id:
        issues.append("note_missing_id")
        return None
    frontmatter = dict(value.get("frontmatter") or {})
    if not frontmatter and str(value.get("raw_text") or "").startswith("---\n"):
        recovered = parse_obsidian_frontmatter(str(value.get("raw_text") or ""))
        if recovered:
            frontmatter = dict(recovered)
    artifact_type = normalize_artifact_type(
        vault_relative_path=relative_path,
        frontmatter_kind=frontmatter.get("kind"),
        snapshot_artifact_type=value.get("artifact_type"),
    )
    return ObsidianNote(
        note_id=note_id,
        title=title,
        path=str(value.get("path") or relative_path),
        vault_relative_path=relative_path,
        artifact_type=artifact_type,
        frontmatter=frontmatter,
        aliases=[str(item).strip() for item in value.get("aliases", []) if str(item).strip()],
        project_confirmed_aliases=[str(item).strip() for item in value.get("project_confirmed_aliases", []) if str(item).strip()],
        outgoing_links=[slugify(str(item)) for item in value.get("outgoing_links", []) if str(item).strip()],
        incoming_links=[slugify(str(item)) for item in value.get("incoming_links", []) if str(item).strip()],
        raw_text=str(value.get("raw_text") or ""),
        body_text=str(value.get("body_text") or ""),
        tags=[str(item).strip() for item in value.get("tags", []) if str(item).strip()],
        headings=[dict(item) for item in value.get("headings", []) if isinstance(item, dict)],
        sections=[dict(item) for item in value.get("sections", []) if isinstance(item, dict)],
        wikilinks=[dict(item) for item in value.get("wikilinks", []) if isinstance(item, dict)],
        embeds=[dict(item) for item in value.get("embeds", []) if isinstance(item, dict)],
        frontmatter_links=[dict(item) for item in value.get("frontmatter_links", []) if isinstance(item, dict)],
        resolved_links={slugify(str(key)): int(count) for key, count in (value.get("resolved_links") or {}).items()},
        unresolved_links={str(key): int(count) for key, count in (value.get("unresolved_links") or {}).items()},
        source_kind="obsidian_bridge_snapshot",
    )


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_seconds(value: datetime | None) -> float | None:
    if value is None:
        return None
    return max(0.0, (datetime.now(timezone.utc) - value).total_seconds())
