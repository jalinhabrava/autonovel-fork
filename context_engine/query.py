from __future__ import annotations

from adapters.vault_adapter import VaultProjectAdapter
from context_engine.contracts import Candidate, ResolvedScope
from interactive.query import list_note_records, note_record


EXCLUDED_STATUSES = {"rejected", "superseded"}


def fetch_candidates(adapter: VaultProjectAdapter, scope: ResolvedScope) -> list[Candidate]:
    candidates: list[Candidate] = []
    for category in scope.retrieval_scope:
        if category == "canon":
            candidates.extend(_canon_candidates(adapter))
        elif category == "lore":
            candidates.extend(_lore_candidates(adapter))
        elif category == "voice":
            candidates.extend(_voice_candidates(adapter))
        elif category == "characters":
            candidates.extend(_character_candidates(adapter))
        elif category == "scenes":
            candidates.extend(_scene_candidates(adapter))
        elif category == "chapters":
            candidates.extend(_chapter_candidates(adapter))
        elif category == "timeline":
            candidates.extend(_timeline_candidates(adapter))
        elif category == "outline":
            candidates.extend(_outline_candidates(adapter))
    return _dedupe_candidates(candidates)


def _canon_candidates(adapter: VaultProjectAdapter) -> list[Candidate]:
    candidates = []
    root_path = adapter.artifact_path("canon")
    if root_path.exists():
        record = note_record(root_path, "canon")
        if _include_status(record["frontmatter"].get("status", "proposed")):
            candidates.append(
                _candidate_from_record(
                    record,
                    category="canon",
                    artifact_kind="root_artifact",
                    artifact_type="canon",
                    reason="root canon artifact provides project-wide hard constraints",
                )
            )
    for record in list_note_records(adapter.canon_decisions_dir, "decision"):
        if _include_status(record["frontmatter"].get("status", "proposed")):
            candidates.append(
                _candidate_from_record(
                    record,
                    category="canon",
                    artifact_kind="note",
                    artifact_type="decision",
                    reason="canon decision note available for hard-constraint retrieval",
                )
            )
    return candidates


def _lore_candidates(adapter: VaultProjectAdapter) -> list[Candidate]:
    candidates = []
    root_path = adapter.artifact_path("world")
    if root_path.exists():
        record = note_record(root_path, "world")
        if _include_status(record["frontmatter"].get("status", "proposed")):
            candidates.append(
                _candidate_from_record(
                    record,
                    category="lore",
                    artifact_kind="root_artifact",
                    artifact_type="world",
                    reason="root world artifact provides global lore context",
                )
            )
    for record in list_note_records(adapter.world_lore_dir, "lore"):
        if _include_status(record["frontmatter"].get("status", "proposed")) and "timeline_model" not in record["frontmatter"]:
            candidates.append(
                _candidate_from_record(
                    record,
                    category="lore",
                    artifact_kind="note",
                    artifact_type="lore",
                    reason="lore note available for world-building retrieval",
                )
            )
    return candidates


def _voice_candidates(adapter: VaultProjectAdapter) -> list[Candidate]:
    candidates = []
    root_path = adapter.artifact_path("voice")
    if root_path.exists():
        record = note_record(root_path, "voice")
        if _include_status(record["frontmatter"].get("status", "proposed")):
            candidates.append(
                _candidate_from_record(
                    record,
                    category="voice",
                    artifact_kind="root_artifact",
                    artifact_type="voice",
                    reason="project voice artifact defines project-level voice constraints",
                )
            )
    for record in list_note_records(adapter.character_profiles_dir, "character"):
        if _include_status(record["frontmatter"].get("status", "proposed")) and "Character Voice Layer" in record["body"]:
            candidates.append(
                _candidate_from_record(
                    record,
                    category="voice",
                    artifact_kind="note",
                    artifact_type="character",
                    reason="character profile contains character voice signals",
                )
            )
    return candidates


def _character_candidates(adapter: VaultProjectAdapter) -> list[Candidate]:
    return [
        _candidate_from_record(
            record,
            category="characters",
            artifact_kind="note",
            artifact_type="character",
            reason="character profile available for cast and relation context",
        )
        for record in list_note_records(adapter.character_profiles_dir, "character")
        if _include_status(record["frontmatter"].get("status", "proposed"))
    ]


def _scene_candidates(adapter: VaultProjectAdapter) -> list[Candidate]:
    return [
        _candidate_from_record(
            record,
            category="scenes",
            artifact_kind="note",
            artifact_type="scene",
            reason="scene note available for local narrative context",
        )
        for record in list_note_records(adapter.outline_scenes_dir, "scene")
        if _include_status(record["frontmatter"].get("status", "proposed"))
    ]


def _chapter_candidates(adapter: VaultProjectAdapter) -> list[Candidate]:
    candidates = []
    for path in adapter.list_chapter_paths():
        record = note_record(path, "chapter")
        status = record["frontmatter"].get("status", "proposed")
        if not _include_status(status):
            continue
        record["id"] = path.stem
        record["title"] = record["frontmatter"].get("title", path.stem)
        candidates.append(
            _candidate_from_record(
                record,
                category="chapters",
                artifact_kind="chapter",
                artifact_type="chapter",
                reason="chapter manuscript available as direct narrative evidence",
            )
        )
    return candidates


def _timeline_candidates(adapter: VaultProjectAdapter) -> list[Candidate]:
    return [
        _candidate_from_record(
            record,
            category="timeline",
            artifact_kind="note",
            artifact_type="timeline",
            reason="provisional timeline note available as extracted temporal evidence",
        )
        for record in list_note_records(adapter.world_lore_dir, "lore")
        if _include_status(record["frontmatter"].get("status", "proposed"))
        and record["frontmatter"].get("timeline_model") == "provisional_lore_note"
    ]


def _outline_candidates(adapter: VaultProjectAdapter) -> list[Candidate]:
    candidates = []
    root_path = adapter.artifact_path("outline")
    if root_path.exists():
        record = note_record(root_path, "outline")
        if _include_status(record["frontmatter"].get("status", "proposed")):
            candidates.append(
                _candidate_from_record(
                    record,
                    category="outline",
                    artifact_kind="root_artifact",
                    artifact_type="outline",
                    reason="root outline artifact provides global structural context",
                )
            )
    return candidates


def _candidate_from_record(
    record: dict,
    *,
    category: str,
    artifact_kind: str,
    artifact_type: str,
    reason: str,
) -> Candidate:
    frontmatter = record["frontmatter"]
    chapter = frontmatter.get("chapter")
    character_ids = tuple(_character_ids_for(record, artifact_type))
    return Candidate(
        id=str(record["id"]),
        artifact_kind=artifact_kind,
        artifact_type=artifact_type,
        category=category,
        title=str(record["title"]),
        status=frontmatter.get("status", "proposed"),
        content=record["body"],
        path=str(record["path"]),
        chapter_ref=f"ch_{int(chapter):02d}" if chapter and str(chapter).isdigit() else None,
        character_ids=character_ids,
        reason=reason,
        source_refs=tuple(ref for ref in [str(record["id"]), str(record["title"])] if ref),
        metadata={str(key): str(value) for key, value in frontmatter.items()},
    )


def _character_ids_for(record: dict, artifact_type: str) -> list[str]:
    if artifact_type == "character":
        return [str(record["id"])]
    return []


def _include_status(status: str) -> bool:
    return status not in EXCLUDED_STATUSES


def _dedupe_candidates(candidates: list[Candidate]) -> list[Candidate]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[Candidate] = []
    for candidate in candidates:
        key = (candidate.id, candidate.category, candidate.path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped
