from __future__ import annotations

import hashlib
import json
from pathlib import Path

from textifai.bootstrap.contracts import SourceDocumentInventory, SourceDocumentRecord
from textifai.bootstrap.language import detect_language_profile
from vault.schema import VAULT_DIRS


def build_source_document_inventory(
    source_root: str | Path,
    *,
    explicit_paths: list[str | Path] | None = None,
    progress_log_path: str | None = None,
) -> SourceDocumentInventory:
    root = Path(source_root).expanduser().resolve()
    documents: list[SourceDocumentRecord] = []
    warnings: list[str] = []
    if not root.exists():
        return SourceDocumentInventory(
            source_root=str(root),
            documents=[],
            total_documents=0,
            total_bytes=0,
            detected_working_languages=[],
            has_multilingual_material=False,
            warnings=[f"Source root does not exist: {root}"],
        )

    candidate_paths = (
        [Path(path).expanduser().resolve() for path in explicit_paths]
        if explicit_paths is not None
        else sorted(root.rglob("*"))
    )

    for path in candidate_paths:
        if not path.is_file():
            continue
        source_format = _detect_source_format(path)
        if source_format not in {"md", "txt", "docx", "pdf", "doc"}:
            continue
        if _should_skip_path(path):
            continue
        _emit_progress(
            progress_log_path,
            phase="source_inventory",
            event="document_started",
            filename=path.name,
            source_format=source_format,
            size_bytes=path.stat().st_size,
        )
        from textifai.derived_sources.extractors import extract_light_source

        seed = extract_light_source(path)
        text = seed.raw_extracted_text
        if not text.strip() and source_format in {"md", "txt"}:
            text = path.read_text(encoding="utf-8", errors="replace")
        detection = detect_language_profile(text)
        likely_content_kinds = _guess_content_kinds(path, text)
        notes = [f"source_format:{source_format}"]
        extraction_method = None
        extraction_warnings: list[str] = []
        if source_format in {"md", "txt"}:
            extraction_method = "native_text"
        else:
            method_notes = list(seed.metadata.get("method_notes", [])) if isinstance(seed.metadata, dict) else []
            extracted_page_count = int(seed.metadata.get("page_count") or 0) if isinstance(seed.metadata, dict) else 0
            extraction_method = method_notes[0] if method_notes else (
                seed.format_profile.extraction_method if seed.format_profile else None
            )
            extraction_warnings = list(dict.fromkeys([*seed.warnings, *method_notes]))
        if source_format in {"md", "txt"}:
            extracted_page_count = 0
        if detection.has_mixed_language:
            notes.append("mixed_language")
        if likely_content_kinds:
            notes.append(f"likely_{likely_content_kinds[0]}")
        if extraction_method:
            notes.append(f"extraction_method:{extraction_method}")
        if not text.strip():
            notes.append("no_extracted_text")
        source_id = _build_source_id(path, text)
        try:
            relative_path = str(path.relative_to(root))
        except ValueError:
            relative_path = path.name
        documents.append(
            SourceDocumentRecord(
                source_id=source_id,
                path=str(path),
                relative_path=relative_path,
                filename=path.name,
                extension=source_format,
                size_bytes=path.stat().st_size,
                checksum=_checksum(path.read_bytes()),
                dominant_language=detection.dominant_language,
                detected_languages=list(detection.detected_languages),
                has_mixed_language=detection.has_mixed_language,
                likely_content_kinds=likely_content_kinds,
                line_count=len(text.splitlines()) or 0,
                extracted_char_count=len(text),
                extracted_word_count=len(text.split()),
                extracted_page_count=extracted_page_count,
                extraction_method=extraction_method,
                extraction_warnings=extraction_warnings,
                notes=notes,
            )
        )
        _emit_progress(
            progress_log_path,
            phase="source_inventory",
            event="document_extracted",
            filename=path.name,
            source_format=source_format,
            extracted_char_count=len(text),
            extracted_word_count=len(text.split()),
            extracted_page_count=extracted_page_count,
            extraction_method=extraction_method,
            extraction_warnings=extraction_warnings[:10],
        )

    detected_languages = _dedupe(
        [language for record in documents for language in record.detected_languages if language not in {"unknown", "mixed"}]
    )
    has_multilingual_material = (
        len(detected_languages) > 1
        or any(record.has_mixed_language or len(record.detected_languages) > 1 for record in documents)
    )
    total_bytes = sum(record.size_bytes for record in documents)
    if not documents:
        warnings.append("No markdown or text documents were found in the source root.")
    return SourceDocumentInventory(
        source_root=str(root),
        documents=documents,
        total_documents=len(documents),
        total_bytes=total_bytes,
        detected_working_languages=detected_languages,
        has_multilingual_material=has_multilingual_material,
        warnings=warnings,
    )


def read_source_documents(
    inventory: SourceDocumentInventory,
    *,
    progress_log_path: str | None = None,
) -> dict[str, str]:
    texts: dict[str, str] = {}
    for document in inventory.documents:
        texts[document.source_id] = _read_source_text(Path(document.path))
        _emit_progress(
            progress_log_path,
            phase="source_inventory",
            event="document_read",
            source_id=document.source_id,
            filename=document.filename,
            extracted_char_count=len(texts[document.source_id]),
        )
    return texts


def _read_source_text(path: Path) -> str:
    from textifai.derived_sources.extractors import extract_light_source

    seed = extract_light_source(path)
    if seed.raw_extracted_text.strip():
        return seed.raw_extracted_text
    if seed.source_format in {"md", "txt"}:
        return path.read_text(encoding="utf-8", errors="replace")
    return ""


def _build_source_id(path: Path, text: str) -> str:
    digest = hashlib.sha256(f"{path.as_posix()}::{text}".encode("utf-8", errors="replace")).hexdigest()[:10]
    stem = "".join(ch for ch in path.stem.lower() if ch.isalnum())
    prefix = stem[:20] or "source"
    return f"{prefix}_{digest}"


def _checksum(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def _should_skip_path(path: Path) -> bool:
    canonical_vault_roots = {Path(relative).parts[0] for relative in VAULT_DIRS.values()}
    skip_parts = {"99_Import_Staging", ".obsidian", *canonical_vault_roots}
    return any(part in skip_parts for part in path.parts)


def discover_importable_source_paths(source_root: str | Path) -> list[Path]:
    root = Path(source_root).expanduser().resolve()
    if not root.exists():
        return []
    paths: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        source_format = _detect_source_format(path)
        if source_format not in {"md", "txt", "docx", "pdf", "doc"}:
            continue
        if _should_skip_path(path):
            continue
        paths.append(path)
    return paths


def _guess_content_kinds(path: Path, text: str) -> list[str]:
    stem = path.stem.casefold()
    if stem.startswith("scene_") or stem.startswith("scn_"):
        return ["scene"]
    if stem.startswith("chapter_") or stem.startswith("ch_"):
        return ["chapter"]
    return ["mixed_note"]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _detect_source_format(path: Path) -> str:
    suffix = path.suffix.lstrip(".").casefold()
    return suffix if suffix in {"md", "txt", "docx", "pdf", "doc"} else (suffix or "txt")


def _emit_progress(path: str | None, **payload) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
