from __future__ import annotations

from adapters.vault_adapter import VaultProjectAdapter
from interactive.payloads import build_context_pack
from interactive.query import (
    chapter_ref,
    extract_summary,
    infer_characters,
    infer_pov,
    infer_refs,
    line_span,
    list_character_titles,
    list_note_records,
    note_record,
    read_markdown,
    search_records,
)


def build_world_context(adapter: VaultProjectAdapter) -> dict:
    world_text = adapter.read_artifact("world")
    canon_records = list_note_records(adapter.canon_decisions_dir, "decision")
    lore_records = list_note_records(adapter.world_lore_dir, "lore")
    summary = extract_summary(world_text, "Global world context assembled from vault artifacts.")
    return build_context_pack(
        scope="world",
        target_id="world",
        summary=summary,
        lore_refs=[record["id"] for record in lore_records],
        canon_refs=[record["id"] for record in canon_records],
        selected_fragment=line_span(world_text),
    )


def build_find_context(adapter: VaultProjectAdapter, query: str) -> dict:
    records = _all_searchable_records(adapter)
    matches = search_records(records, query)

    lore_records = list_note_records(adapter.world_lore_dir, "lore")
    canon_records = list_note_records(adapter.canon_decisions_dir, "decision")
    characters = list_character_titles(adapter)
    chapter_refs = sorted(
        {
            record["id"]
            for record in matches
            if record["kind"] == "chapter" and str(record["id"]).startswith("ch_")
        }
    )
    summary = f"Found {len(matches)} matches for '{query}' across the vault."
    return build_context_pack(
        scope="find",
        target_id=query,
        summary=summary,
        characters=infer_characters(query, characters),
        canon_refs=[record["id"] for record in canon_records if record["id"] in _match_ids(matches)],
        lore_refs=[record["id"] for record in lore_records if record["id"] in _match_ids(matches)],
        chapter_refs=chapter_refs,
        selected_fragment=matches[0]["selected_fragment"] if matches else {"start_line": 1, "end_line": 1},
        matches=matches,
    )


def build_load_context(
    adapter: VaultProjectAdapter,
    *,
    artifacts: list[str] | None = None,
    scene_ids: list[str] | None = None,
    chapter_ids: list[str] | None = None,
) -> dict:
    artifacts = artifacts or []
    scene_ids = scene_ids or []
    chapter_ids = chapter_ids or []

    loaded_texts: list[str] = []
    for artifact in artifacts:
        loaded_texts.append(adapter.read_artifact(artifact))
    for scene_id in scene_ids:
        scene_path = adapter.note_path("scene", scene_id)
        loaded_texts.append(read_markdown(scene_path))
    for chapter_id in chapter_ids:
        loaded_texts.append(_read_chapter(adapter, chapter_id)["text"])

    combined_text = "\n\n".join(text for text in loaded_texts if text).strip()
    lore_records = list_note_records(adapter.world_lore_dir, "lore")
    canon_records = list_note_records(adapter.canon_decisions_dir, "decision")
    characters = list_character_titles(adapter)

    return build_context_pack(
        scope="load",
        target_id="load-context",
        summary=extract_summary(combined_text, "Combined context pack assembled from explicit vault targets."),
        pov=infer_pov(combined_text, characters),
        characters=infer_characters(combined_text, characters),
        canon_refs=infer_refs(combined_text, canon_records),
        lore_refs=infer_refs(combined_text, lore_records),
        chapter_refs=[chapter_ref(chapter_id) or str(chapter_id) for chapter_id in chapter_ids],
        selected_fragment=line_span(combined_text),
    )


def build_scene_context(adapter: VaultProjectAdapter, scene_id: str) -> dict:
    scene = note_record(adapter.note_path("scene", scene_id), "scene")
    scene_text = scene["text"]
    lore_records = list_note_records(adapter.world_lore_dir, "lore")
    canon_records = list_note_records(adapter.canon_decisions_dir, "decision")
    characters = list_character_titles(adapter)
    related_chapter = chapter_ref(scene["chapter"])

    return build_context_pack(
        scope="scene",
        target_id=scene_id,
        summary=extract_summary(scene_text, f"Scene context for {scene_id}."),
        pov=infer_pov(scene_text, characters),
        characters=infer_characters(scene_text, characters),
        canon_refs=infer_refs(scene_text, canon_records),
        lore_refs=infer_refs(scene_text, lore_records),
        chapter_refs=[related_chapter] if related_chapter else [],
        selected_fragment=line_span(scene_text),
    )


def build_chapter_context(adapter: VaultProjectAdapter, chapter_id: str) -> dict:
    chapter = _read_chapter(adapter, chapter_id)
    chapter_text = chapter["text"]
    lore_records = list_note_records(adapter.world_lore_dir, "lore")
    canon_records = list_note_records(adapter.canon_decisions_dir, "decision")
    scene_records = list_note_records(adapter.outline_scenes_dir, "scene")
    characters = list_character_titles(adapter)
    chapter_key = chapter["id"]

    scene_text = "\n\n".join(
        record["text"] for record in scene_records if chapter_ref(record["chapter"]) == chapter_key
    )
    combined_text = "\n\n".join(part for part in [chapter_text, scene_text] if part).strip()
    return build_context_pack(
        scope="chapter",
        target_id=chapter_key,
        summary=extract_summary(combined_text, f"Chapter context for {chapter_key}."),
        pov=infer_pov(combined_text, characters),
        characters=infer_characters(combined_text, characters),
        canon_refs=infer_refs(combined_text, canon_records),
        lore_refs=infer_refs(combined_text, lore_records),
        chapter_refs=[chapter_key],
        selected_fragment=line_span(chapter_text),
    )


def _all_searchable_records(adapter: VaultProjectAdapter) -> list[dict]:
    records = [
        note_record(adapter.artifact_path("world"), "artifact"),
        note_record(adapter.artifact_path("characters"), "artifact"),
        note_record(adapter.artifact_path("outline"), "artifact"),
        note_record(adapter.artifact_path("canon"), "artifact"),
    ]
    records.extend(list_note_records(adapter.world_lore_dir, "lore"))
    records.extend(list_note_records(adapter.character_profiles_dir, "character"))
    records.extend(list_note_records(adapter.outline_scenes_dir, "scene"))
    records.extend(list_note_records(adapter.canon_decisions_dir, "decision"))
    for path in adapter.list_chapter_paths():
        records.append(note_record(path, "chapter"))
        records[-1]["id"] = path.stem
    return records


def _match_ids(matches: list[dict]) -> set[str]:
    return {str(match["id"]) for match in matches}


def _read_chapter(adapter: VaultProjectAdapter, chapter_id: str) -> dict:
    chapter_key = chapter_ref(chapter_id) or str(chapter_id)
    if chapter_key.startswith("ch_"):
        path = adapter.resolve(f"05_Draft/Chapters/{chapter_key}.md")
    else:
        path = adapter.resolve(f"05_Draft/Chapters/{chapter_key}.md")
    record = note_record(path, "chapter")
    record["id"] = chapter_key
    return record
