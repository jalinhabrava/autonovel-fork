from __future__ import annotations

import hashlib
from pathlib import Path

from textifai.bootstrap.contracts import SourceDocumentInventory, SourceDocumentRecord
from textifai.bootstrap.language import detect_language_profile


def build_source_document_inventory(source_root: str | Path) -> SourceDocumentInventory:
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

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        source_format = _detect_source_format(path)
        if source_format not in {"md", "txt", "docx", "pdf", "doc"}:
            continue
        if _should_skip_path(path):
            continue
        text = _read_source_text(path)
        detection = detect_language_profile(text)
        likely_content_kinds = _guess_content_kinds(path, text)
        notes = []
        notes.append(f"source_format:{source_format}")
        if detection.has_mixed_language:
            notes.append("mixed_language")
        if likely_content_kinds:
            notes.append(f"likely_{likely_content_kinds[0]}")
        source_id = _build_source_id(path, text)
        relative_path = str(path.relative_to(root))
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
                notes=notes,
            )
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


def read_source_documents(inventory: SourceDocumentInventory) -> dict[str, str]:
    texts: dict[str, str] = {}
    for document in inventory.documents:
        texts[document.source_id] = _read_source_text(Path(document.path))
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
    return any(part in {"99_Import_Staging", ".obsidian"} for part in path.parts)


def _guess_content_kinds(path: Path, text: str) -> list[str]:
    haystack = " ".join([path.stem, text[:500]]).casefold()
    kinds: list[str] = []
    if any(term in haystack for term in {"chapter", "capítulo", "capitulo"}):
        kinds.append("chapter")
    if any(term in haystack for term in {"character", "personaje", "profile", "bio"}):
        kinds.append("character")
    if any(term in haystack for term in {"lore", "world", "worldbuilding", "mundo", "canon"}):
        kinds.append("lore")
    if any(term in haystack for term in {"scene", "escena"}):
        kinds.append("scene")
    if not kinds:
        kinds.append("mixed_note")
    return _dedupe(kinds)


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
