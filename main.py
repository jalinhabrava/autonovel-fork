from __future__ import annotations

import argparse
import json
from pathlib import Path

from adapters.vault_adapter import VaultProjectAdapter
from interactive.bootstrap_extract import extract_canon, extract_characters, extract_timeline, extract_voice
from interactive.context_commands import (
    build_chapter_context,
    build_find_context,
    build_load_context,
    build_scene_context,
    build_world_context,
)
from interactive.persistence_commands import consistency_check, create_note, decide, reject, update_note, validate
from vault.bootstrap import bootstrap_vault, validate_vault
from vault.ingest import import_existing_chapters, ingest_digested_context, load_ingest_payload
from vault.notes import export_context, write_or_update_note


def _read_body(args) -> str:
    if args.body_file:
        return Path(args.body_file).read_text()
    if args.body is not None:
        return args.body
    return ""


def _parse_metadata(items: list[str]) -> dict[str, str]:
    metadata = {}
    for item in items:
        key, _, value = item.partition("=")
        metadata[key] = value
    return metadata


def _load_json_payload(path: str) -> dict:
    return json.loads(Path(path).read_text())


def _add_note_arguments(parser):
    parser.add_argument("--path", required=True, help="Vault path")
    parser.add_argument("--type", required=True, choices=[
        "character", "lore", "scene", "decision", "chapter", "revision_brief", "review", "reader_panel"
    ])
    parser.add_argument("--slug", required=True, help="Stable note slug")
    parser.add_argument("--title", required=True, help="Note title")
    parser.add_argument("--status", default="proposed", help="Note status")
    parser.add_argument("--body", default=None, help="Inline note body")
    parser.add_argument("--body-file", default=None, help="Path to a file containing the note body")
    parser.add_argument("--meta", action="append", default=[], help="Metadata entries of the form key=value")


def _add_chapter_selection_arguments(parser):
    parser.add_argument("--chapter-id", action="append", default=[], help="Chapter ref like ch_01 or 1")
    parser.add_argument("--chapter-from", type=int, default=None, help="First chapter number to include")
    parser.add_argument("--chapter-to", type=int, default=None, help="Last chapter number to include")


def main():
    parser = argparse.ArgumentParser(description="Autonovel utility entrypoints")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-vault", help="Bootstrap a new narrative vault")
    init_parser.add_argument("--path", required=True, help="Destination path for the vault")
    init_parser.add_argument("--title", default="Untitled Novel Project", help="Project title")
    init_parser.add_argument("--force", action="store_true", help="Allow bootstrapping into a non-empty path")

    validate_parser = subparsers.add_parser("validate-vault", help="Validate a vault layout")
    validate_parser.add_argument("--path", required=True, help="Vault path to validate")

    write_parser = subparsers.add_parser("write-note", help="Create or update a vault note")
    _add_note_arguments(write_parser)

    update_parser = subparsers.add_parser("update-note", help="Alias for write-note")
    _add_note_arguments(update_parser)

    export_parser = subparsers.add_parser("export-context", help="Export logical context from a vault")
    export_parser.add_argument("--path", required=True, help="Vault path")
    export_parser.add_argument("--artifact", required=True, choices=[
        "voice", "world", "characters", "outline", "canon", "all"
    ])

    ingest_parser = subparsers.add_parser(
        "ingest-context",
        help="Persist a digested context payload produced by an external interactive workflow",
    )
    ingest_parser.add_argument("--path", required=True, help="Vault path")
    ingest_parser.add_argument("--json", required=True, help="Path to a JSON payload")

    import_parser = subparsers.add_parser(
        "import-existing-chapters",
        help="Import an existing manuscript directory into vault chapter notes",
    )
    import_parser.add_argument("--path", required=True, help="Vault path")
    import_parser.add_argument("--source-dir", required=True, help="Directory containing manuscript chapters")
    import_parser.add_argument("--pattern", default="*.md", help="Glob pattern for chapter files")
    import_parser.add_argument("--status", default="pending_revision", help="Imported chapter status")
    import_parser.add_argument("--source-label", default="existing_manuscript", help="Provenance label")

    interactive_world_parser = subparsers.add_parser(
        "interactive-world",
        help="Assemble a world-level context_pack from the vault",
    )
    interactive_world_parser.add_argument("--path", required=True, help="Vault path")

    interactive_find_parser = subparsers.add_parser(
        "interactive-find",
        help="Search the vault and emit a context_pack for the query",
    )
    interactive_find_parser.add_argument("--path", required=True, help="Vault path")
    interactive_find_parser.add_argument("--query", required=True, help="Case-insensitive text query")

    interactive_load_parser = subparsers.add_parser(
        "interactive-load-context",
        help="Load explicit artifacts, scenes, or chapters into a context_pack",
    )
    interactive_load_parser.add_argument("--path", required=True, help="Vault path")
    interactive_load_parser.add_argument("--artifact", action="append", default=[], help="Artifact name to load")
    interactive_load_parser.add_argument("--scene-id", action="append", default=[], help="Scene slug to load")
    interactive_load_parser.add_argument("--chapter-id", action="append", default=[], help="Chapter ref to load")

    interactive_scene_parser = subparsers.add_parser(
        "interactive-scene-context",
        help="Assemble a scene-level context_pack from the vault",
    )
    interactive_scene_parser.add_argument("--path", required=True, help="Vault path")
    interactive_scene_parser.add_argument("--scene-id", required=True, help="Scene slug")

    interactive_chapter_parser = subparsers.add_parser(
        "interactive-chapter-context",
        help="Assemble a chapter-level context_pack from the vault",
    )
    interactive_chapter_parser.add_argument("--path", required=True, help="Vault path")
    interactive_chapter_parser.add_argument("--chapter-id", required=True, help="Chapter ref like ch_01 or 1")

    decide_parser = subparsers.add_parser(
        "interactive-decide",
        help="Persist a decision_canon payload into the vault",
    )
    decide_parser.add_argument("--path", required=True, help="Vault path")
    decide_parser.add_argument("--json", required=True, help="Path to a decision_canon JSON payload")

    validate_parser = subparsers.add_parser(
        "interactive-validate",
        help="Mark an existing vault artifact as validated",
    )
    validate_parser.add_argument("--path", required=True, help="Vault path")
    validate_parser.add_argument("--json", required=True, help="Path to a state change JSON payload")

    reject_parser = subparsers.add_parser(
        "interactive-reject",
        help="Mark an existing vault artifact as rejected",
    )
    reject_parser.add_argument("--path", required=True, help="Vault path")
    reject_parser.add_argument("--json", required=True, help="Path to a state change JSON payload")

    consistency_parser = subparsers.add_parser(
        "interactive-consistency-check",
        help="Run a non-persistent consistency check over an artifact payload",
    )
    consistency_parser.add_argument("--path", required=True, help="Vault path")
    consistency_parser.add_argument("--json", required=True, help="Path to an artifact_payload JSON payload")

    create_note_parser = subparsers.add_parser(
        "interactive-create-note",
        help="Create a vault note from an artifact_payload after consistency verification",
    )
    create_note_parser.add_argument("--path", required=True, help="Vault path")
    create_note_parser.add_argument("--json", required=True, help="Path to an artifact_payload JSON payload")

    update_note_parser = subparsers.add_parser(
        "interactive-update-note",
        help="Update a vault note from an artifact_payload after consistency verification",
    )
    update_note_parser.add_argument("--path", required=True, help="Vault path")
    update_note_parser.add_argument("--json", required=True, help="Path to an artifact_payload JSON payload")

    extract_voice_parser = subparsers.add_parser(
        "interactive-extract-voice",
        help="Bootstrap project voice from existing manuscript chapters",
    )
    extract_voice_parser.add_argument("--path", required=True, help="Vault path")
    _add_chapter_selection_arguments(extract_voice_parser)

    extract_characters_parser = subparsers.add_parser(
        "interactive-extract-characters",
        help="Bootstrap character notes from existing manuscript chapters",
    )
    extract_characters_parser.add_argument("--path", required=True, help="Vault path")
    _add_chapter_selection_arguments(extract_characters_parser)

    extract_canon_parser = subparsers.add_parser(
        "interactive-extract-canon",
        help="Bootstrap canon proposals from existing manuscript chapters",
    )
    extract_canon_parser.add_argument("--path", required=True, help="Vault path")
    _add_chapter_selection_arguments(extract_canon_parser)

    extract_timeline_parser = subparsers.add_parser(
        "interactive-extract-timeline",
        help="Bootstrap provisional timeline notes from existing manuscript chapters",
    )
    extract_timeline_parser.add_argument("--path", required=True, help="Vault path")
    _add_chapter_selection_arguments(extract_timeline_parser)

    args = parser.parse_args()

    if args.command == "init-vault":
        path = bootstrap_vault(args.path, title=args.title, force=args.force)
        print(path)
        return

    if args.command == "validate-vault":
        errors = validate_vault(args.path)
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
        return

    if args.command in {"write-note", "update-note"}:
        path = write_or_update_note(
            args.path,
            note_type=args.type,
            slug=args.slug,
            title=args.title,
            body=_read_body(args),
            status=args.status,
            metadata=_parse_metadata(args.meta),
        )
        print(path)
        return

    if args.command == "export-context":
        print(export_context(args.path, args.artifact))
        return

    if args.command == "ingest-context":
        payload = load_ingest_payload(args.json)
        print(json.dumps([str(path) for path in ingest_digested_context(args.path, payload)], indent=2))
        return

    if args.command == "import-existing-chapters":
        print(
            json.dumps(
                [
                    str(path)
                    for path in import_existing_chapters(
                        args.path,
                        args.source_dir,
                        pattern=args.pattern,
                        status=args.status,
                        source_label=args.source_label,
                    )
                ],
                indent=2,
            )
        )
        return

    if args.command == "interactive-decide":
        print(json.dumps(decide(args.path, _load_json_payload(args.json)), indent=2))
        return

    if args.command == "interactive-validate":
        print(json.dumps(validate(args.path, _load_json_payload(args.json)), indent=2))
        return

    if args.command == "interactive-reject":
        print(json.dumps(reject(args.path, _load_json_payload(args.json)), indent=2))
        return

    if args.command == "interactive-consistency-check":
        print(json.dumps(consistency_check(args.path, _load_json_payload(args.json)), indent=2))
        return

    if args.command == "interactive-create-note":
        print(json.dumps(create_note(args.path, _load_json_payload(args.json)), indent=2))
        return

    if args.command == "interactive-update-note":
        print(json.dumps(update_note(args.path, _load_json_payload(args.json)), indent=2))
        return

    if args.command == "interactive-extract-voice":
        print(
            json.dumps(
                extract_voice(
                    args.path,
                    chapter_ids=args.chapter_id,
                    chapter_from=args.chapter_from,
                    chapter_to=args.chapter_to,
                ),
                indent=2,
            )
        )
        return

    if args.command == "interactive-extract-characters":
        print(
            json.dumps(
                extract_characters(
                    args.path,
                    chapter_ids=args.chapter_id,
                    chapter_from=args.chapter_from,
                    chapter_to=args.chapter_to,
                ),
                indent=2,
            )
        )
        return

    if args.command == "interactive-extract-canon":
        print(
            json.dumps(
                extract_canon(
                    args.path,
                    chapter_ids=args.chapter_id,
                    chapter_from=args.chapter_from,
                    chapter_to=args.chapter_to,
                ),
                indent=2,
            )
        )
        return

    if args.command == "interactive-extract-timeline":
        print(
            json.dumps(
                extract_timeline(
                    args.path,
                    chapter_ids=args.chapter_id,
                    chapter_from=args.chapter_from,
                    chapter_to=args.chapter_to,
                ),
                indent=2,
            )
        )
        return

    if args.command.startswith("interactive-"):
        adapter = VaultProjectAdapter(args.path)
        if args.command == "interactive-world":
            print(json.dumps(build_world_context(adapter), indent=2))
            return
        if args.command == "interactive-find":
            print(json.dumps(build_find_context(adapter, args.query), indent=2))
            return
        if args.command == "interactive-load-context":
            print(
                json.dumps(
                    build_load_context(
                        adapter,
                        artifacts=args.artifact,
                        scene_ids=args.scene_id,
                        chapter_ids=args.chapter_id,
                    ),
                    indent=2,
                )
            )
            return
        if args.command == "interactive-scene-context":
            print(json.dumps(build_scene_context(adapter, args.scene_id), indent=2))
            return
        if args.command == "interactive-chapter-context":
            print(json.dumps(build_chapter_context(adapter, args.chapter_id), indent=2))
            return


if __name__ == "__main__":
    main()
