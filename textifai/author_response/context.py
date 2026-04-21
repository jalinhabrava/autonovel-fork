from __future__ import annotations

from pathlib import Path
import re

from textifai.obsidian import build_obsidian_context_bundle
from textifai.obsidian.source import open_obsidian_source
from textifai.editorial_intent.contracts import EditorialIntent
from textifai.vaerl.contracts import EntityResolutionResult
from vault.schema import slugify


def build_response_context(
    *,
    vault_root: str | Path,
    editorial_intent: EditorialIntent | None,
    entity_results: list[EntityResolutionResult],
    include_candidates: bool = True,
) -> list[dict[str, str]]:
    snippets: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add_target(target_type: str | None, target_id: str | None, *, source: str) -> None:
        if not target_type or not target_id:
            return
        key = (target_type, target_id)
        if key in seen:
            return
        bundle = build_obsidian_context_bundle(vault_root, note_id=target_id, related_limit=3)
        if bundle.primary is None:
            fallback_notes = _find_supporting_notes(vault_root, target_id=target_id, target_type=target_type)
            for note in fallback_notes:
                fallback_key = (note.artifact_type, note.note_id)
                if fallback_key in seen:
                    continue
                snippets.append(
                    {
                        "artifact_type": note.artifact_type,
                        "artifact_id": note.note_id,
                        "title": note.title,
                        "excerpt": _trim_excerpt(note.body_text),
                        "source": f"{source}_fallback_search",
                        "path": note.path,
                        "context_source_reliability": None,
                        "context_source_kind": "vault_markdown",
                    }
                )
                seen.add(fallback_key)
            return
        snippets.append(
            {
                "artifact_type": bundle.primary.artifact_type,
                "artifact_id": bundle.primary.note_id,
                "title": bundle.primary.title,
                "excerpt": _trim_excerpt(bundle.primary.body_text),
                "source": source,
                "path": bundle.primary.path,
                "context_source_reliability": bundle.source_status.reliability if bundle.source_status else None,
                "context_source_kind": bundle.source_status.source_kind if bundle.source_status else None,
            }
        )
        seen.add(key)
        for related in bundle.related:
            related_key = (related.artifact_type, related.note_id)
            if related_key in seen:
                continue
            snippets.append(
                {
                    "artifact_type": related.artifact_type,
                    "artifact_id": related.note_id,
                    "title": related.title,
                    "excerpt": _trim_excerpt(related.body_text),
                    "source": f"{source}_obsidian_related",
                    "path": related.path,
                    "context_source_reliability": bundle.source_status.reliability if bundle.source_status else None,
                    "context_source_kind": bundle.source_status.source_kind if bundle.source_status else None,
                }
            )
            seen.add(related_key)

    if editorial_intent is not None:
        add_target(
            editorial_intent.resolved_target_type,
            editorial_intent.resolved_target_id,
            source="resolved_target",
        )
        if include_candidates:
            for candidate in editorial_intent.candidate_targets[:3]:
                add_target(candidate.target_type, candidate.target_id, source="candidate_target")

    for result in entity_results:
        if result.resolved and result.resolved_entity_type and result.resolved_entity_id:
            add_target(result.resolved_entity_type, result.resolved_entity_id, source="vaerl_resolved")
        for suggestion in result.related_artifacts_suggested[:2]:
            add_target(suggestion.artifact_type, suggestion.artifact_id, source="related_artifact")

    return snippets


def _trim_excerpt(text: str, limit: int = 700) -> str:
    collapsed = " ".join(text.split())
    return collapsed[:limit] + ("..." if len(collapsed) > limit else "")


def _find_supporting_notes(
    vault_root: str | Path,
    *,
    target_id: str,
    target_type: str | None,
    limit: int = 4,
):
    source = open_obsidian_source(vault_root)
    reader = source.reader
    normalized_target = slugify(target_id)
    pattern = re.compile(r"(?<!\w)" + re.escape(target_id.casefold()) + r"(?!\w)")
    scored: list[tuple[int, object]] = []
    for note in reader.list_notes():
        vault_path = str(note.vault_relative_path).replace("\\", "/")
        note_role = str(note.frontmatter.get("note_role") or "").strip().casefold()
        if "99_Import_Staging/" in vault_path or vault_path.startswith("99_Import_Staging/"):
            continue
        if "90_Review/" in vault_path or vault_path.startswith("90_Review/"):
            continue
        if note_role == "review":
            continue
        score = 0
        if target_type and note.artifact_type == target_type:
            score += 3
        if note.note_id == normalized_target:
            score += 10
        if slugify(note.title) == normalized_target:
            score += 9
        note_aliases = [*note.aliases, *note.project_confirmed_aliases]
        if any(slugify(alias) == normalized_target for alias in note_aliases):
            score += 8
        frontmatter_values = [
            note.frontmatter.get("canonical_subject"),
            note.frontmatter.get("character_refs"),
            note.frontmatter.get("lore_refs"),
            note.frontmatter.get("entities"),
        ]
        for value in frontmatter_values:
            if value is None:
                continue
            values = value if isinstance(value, list) else str(value).split(",")
            if any(slugify(str(item).strip()) == normalized_target for item in values if str(item).strip()):
                score += 6
                break
        if pattern.search(note.body_text.casefold()):
            score += 5
        if note_role == "primary":
            score += 4
        elif note_role == "chapter_summary":
            score += 2
        elif note_role == "chapter":
            score += 1
        if score > 0:
            scored.append((score, note))
    scored.sort(key=lambda item: (item[0], item[1].title.casefold()), reverse=True)
    return [note for _, note in scored[:limit]]
