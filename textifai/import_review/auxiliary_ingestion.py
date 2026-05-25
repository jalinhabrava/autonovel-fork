from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from providers.text_provider import TextGenerationRequest, TextMessage
from textifai.author_understanding.normalization import extract_json_payload
from textifai.import_review.entity_cluster_resolution import normalize_entity_key, normalize_entity_text
from textifai.import_review.entity_reconciliation import reconcile_entities_for_vaerl


@dataclass(frozen=True)
class AuxiliaryDocumentInput:
    path: str
    author_hint: str = ""


AUXILIARY_EXTRACTION_PROMPT = """You are extracting structured author-knowledge from an auxiliary document.

This is NOT necessarily a novel chapter.
The document may be messy, incomplete, informal, fragmented, or written as notes, lists, drafts, character sheets, worldbuilding notes, outlines, future plans, or author reminders.

WORK LANGUAGE RULES

The working language for all generated prose fields is: {WORK_LANGUAGE}.
Generate all summaries, facts, relationship facts, notes, and explanatory prose in {WORK_LANGUAGE}.
Do not translate proper names, canonical names, place names, faction names, object names, or titles.

AUTHOR DOCUMENT HINT

{AUTHOR_HINT_BLOCK}

Use the author-provided hint as guidance when present, but do not treat it as guaranteed truth.
If no author hint was provided, infer the document purpose from the content itself.
The document may still contain reliable character sheets, worldbuilding notes, lore, future plot plans, relationship notes, or other useful author material.
If the content clearly states facts, entities, relationships, or plans, extract them normally.
Only mark items as uncertain when the content itself is ambiguous or contradictory.

TASK

Extract structured author-knowledge from the auxiliary chunk.
Prioritize durable, high-signal information that is useful for an author's VaERL knowledge base.
Do not attempt to exhaustively transcribe every bullet or sentence.
Prefer fewer reliable entities/facts over many weak or repetitive ones.
As a practical ceiling per chunk, return at most 35 declared_entities, 40 declared_relationships, and 15 planned_events.
Return ONLY valid JSON.
Do not include markdown fences.
Do not invent missing facts.
Preserve uncertainty explicitly.

Allowed entity_kind values:
- character
- place
- faction
- concept
- object
- creature
- event

Allowed narrative_status values:
- observed
- planned
- backstory
- speculative
- uncertain

Schema:

{{
  "chunk_id": "...",
  "document_role": "character_sheets | world_lore | outline | timeline | mixed_notes | unknown_auxiliary",
  "document_role_confidence": 0.0,
  "declared_entities": [
    {{
      "canonical_name": "...",
      "entity_kind": "character",
      "entity_subkind": "",
      "aliases": ["..."],
      "summary": "...",
      "facts": ["..."],
      "narrative_status": "planned",
      "confidence": 0.0,
      "uncertainty": ""
    }}
  ],
  "declared_relationships": [
    {{
      "source": "...",
      "target": "...",
      "type": "familial | conflict | authority | dependency | located_in | uses | member_of | related_to | planned",
      "facts": ["..."],
      "narrative_status": "planned",
      "confidence": 0.0,
      "uncertainty": ""
    }}
  ],
  "planned_events": [
    {{
      "canonical_name": "...",
      "summary": "...",
      "facts": ["..."],
      "narrative_status": "planned",
      "confidence": 0.0,
      "uncertainty": ""
    }}
  ],
  "backstory_items": [
    {{
      "subject": "...",
      "facts": ["..."],
      "confidence": 0.0,
      "uncertainty": ""
    }}
  ],
  "uncertain_notes": ["..."]
}}

AUXILIARY CHUNK METADATA

source_id: {SOURCE_ID}
chunk_id: {CHUNK_ID}
filename: {FILENAME}
heading_path: {HEADING_PATH}
document_title_hint: {TITLE_HINT}

CHUNK TEXT

{CHUNK_TEXT}
"""


def ingest_auxiliary_documents(
    *,
    system_root: Path,
    entities: list[dict[str, Any]],
    auxiliary_documents: list[AuxiliaryDocumentInput],
    language: str,
    provider: Any,
    provider_name: str | None = None,
    model: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    aux_root = system_root / "auxiliary_chunks"
    extraction_root = system_root / "auxiliary_extractions"
    aux_root.mkdir(parents=True, exist_ok=True)
    extraction_root.mkdir(parents=True, exist_ok=True)

    docs = [_build_auxiliary_document_record(item) for item in auxiliary_documents]
    chunks: list[dict[str, Any]] = []
    extractions: list[dict[str, Any]] = []
    extraction_errors: list[dict[str, Any]] = []

    for doc in docs:
        doc_chunks = _chunk_auxiliary_document(doc)
        chunks.extend(doc_chunks)

    persisted_docs = [{key: value for key, value in doc.items() if key != "text"} for doc in docs]
    (system_root / "auxiliary_source_index.json").write_text(
        json.dumps(
            {
                "schema_version": "textifai.auxiliary_source_index.v1",
                "document_count": len(persisted_docs),
                "documents": persisted_docs,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    for chunk in chunks:
        (aux_root / f"{chunk['chunk_id']}.json").write_text(json.dumps(chunk, ensure_ascii=False, indent=2), encoding="utf-8")
        prompt = _build_auxiliary_extraction_prompt(chunk=chunk, language=language)
        result, error = _extract_auxiliary_chunk(
            provider=provider,
            prompt=prompt,
            chunk=chunk,
            provider_name=provider_name,
            model=model,
        )
        if result is not None:
            extractions.append(result)
            (extraction_root / f"{chunk['chunk_id']}.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        elif error is not None:
            extraction_errors.append(error)
            (extraction_root / f"{chunk['chunk_id']}.error.json").write_text(
                json.dumps(error, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    enriched_entities, enrichment_audit = _apply_auxiliary_extractions(
        entities=entities,
        extractions=extractions,
    )
    enriched_entities, reconciliation_audit = reconcile_entities_for_vaerl(entities=enriched_entities, language=language)

    audit = {
        "schema_version": "textifai.auxiliary_enrichment.v1",
        "document_count": len(docs),
        "chunk_count": len(chunks),
        "extraction_count": len(extractions),
        "extraction_error_count": len(extraction_errors),
        "documents": persisted_docs,
        "extraction_errors": extraction_errors,
        **enrichment_audit,
        "post_auxiliary_reconciliation": reconciliation_audit,
    }
    (system_root / "auxiliary_enrichment_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return enriched_entities, audit


def _build_auxiliary_document_record(item: AuxiliaryDocumentInput) -> dict[str, Any]:
    path = Path(item.path).expanduser().resolve()
    text = path.read_text(encoding="utf-8", errors="replace")
    author_hint = normalize_entity_text(item.author_hint)
    title_hint = normalize_entity_text(path.stem)
    source_id = _source_id(path, text)
    hint_status = "provided" if author_hint else "missing"
    return {
        "source_id": source_id,
        "path": str(path),
        "filename": path.name,
        "title_hint": title_hint,
        "author_hint": author_hint,
        "author_hint_status": hint_status,
        "fallback_title_hint_used": not bool(author_hint),
        "content_hash": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest(),
        "char_count": len(text),
        "word_count": len(text.split()),
        "heading_count": len(re.findall(r"(?m)^#{1,6}\s+", text)),
        "has_markdown_headings": bool(re.search(r"(?m)^#{1,6}\s+", text)),
        "text": text,
    }


def _source_id(path: Path, text: str) -> str:
    digest = hashlib.sha256(f"{path.as_posix()}::{text}".encode("utf-8", errors="replace")).hexdigest()[:10]
    stem = "".join(ch for ch in path.stem.lower() if ch.isalnum())[:20] or "auxiliary"
    return f"{stem}_{digest}"


def _chunk_auxiliary_document(doc: dict[str, Any]) -> list[dict[str, Any]]:
    text = str(doc.get("text") or "")
    sections = _split_markdown_sections(text)
    if not sections:
        sections = _split_paragraph_sections(text)
    sections = _pack_auxiliary_sections(sections, max_chars=200000)
    chunks: list[dict[str, Any]] = []
    for index, section in enumerate(sections, start=1):
        section_start = int(section.get("char_start", 0) or 0)
        for part_index, part_record in enumerate(_window_text_with_spans(section["text"], max_chars=200000, overlap_chars=1500), start=1):
            part = part_record["text"]
            char_start = section_start + int(part_record["char_start"])
            char_end = section_start + int(part_record["char_end"])
            chunk_id = f"{doc['source_id']}_chunk_{index:03d}_{part_index:02d}"
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "source_id": doc["source_id"],
                    "filename": doc["filename"],
                    "path": doc["path"],
                    "author_hint": doc["author_hint"],
                    "author_hint_status": doc["author_hint_status"],
                    "title_hint": doc["title_hint"],
                    "heading_path": section["heading_path"],
                    "chunk_kind": section["kind"],
                    "text": part,
                    "char_start": char_start,
                    "char_end": char_end,
                    "char_count": len(part),
                    "source_span": {
                        "source_id": doc["source_id"],
                        "char_start": char_start,
                        "char_end": char_end,
                    },
                }
            )
    return chunks


def _extract_auxiliary_chunk(
    *,
    provider: Any,
    prompt: str,
    chunk: dict[str, Any],
    provider_name: str | None,
    model: str | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    last_error: dict[str, Any] | None = None
    for attempt in range(1, 3):
        response_text = ""
        try:
            response = provider.generate(
                TextGenerationRequest(
                    task="auxiliary_source_extraction",
                    provider_name=provider_name,
                    model=model,
                    messages=[TextMessage(role="user", content=prompt)],
                    max_tokens=12000,
                    temperature=0.1,
                    response_format={"type": "json_object"},
                )
            )
            response_text = response.text or ""
            extracted_payload = extract_json_payload(response_text)
            if not isinstance(extracted_payload, dict):
                raise ValueError("response did not contain a valid JSON object")
            return _normalize_auxiliary_extraction(extracted_payload, chunk=chunk), None
        except Exception as exc:  # noqa: BLE001 - audit must preserve failed chunks.
            last_error = {
                "chunk_id": chunk["chunk_id"],
                "source_id": chunk["source_id"],
                "attempt_count": attempt,
                "failure_type": exc.__class__.__name__,
                "failure_reason": str(exc),
                "response_excerpt": response_text[:500],
                "response_sha256": hashlib.sha256(response_text.encode("utf-8", errors="replace")).hexdigest()
                if response_text
                else None,
            }
    return None, last_error


def _pack_auxiliary_sections(sections: list[dict[str, Any]], *, max_chars: int) -> list[dict[str, Any]]:
    if not sections:
        return []
    packed: list[dict[str, Any]] = []
    bucket: list[dict[str, Any]] = []
    bucket_size = 0

    def flush() -> None:
        nonlocal bucket, bucket_size
        if not bucket:
            return
        packed.append(
            {
                "heading_path": [item["heading_path"] for item in bucket if item.get("heading_path")],
                "text": "\n\n".join(str(item.get("text") or "").strip() for item in bucket if str(item.get("text") or "").strip()),
                "kind": "packed_heading_sections" if len(bucket) > 1 else bucket[0].get("kind", "heading_section"),
                "char_start": min(int(item.get("char_start", 0) or 0) for item in bucket),
                "char_end": max(int(item.get("char_end", 0) or 0) for item in bucket),
            }
        )
        bucket = []
        bucket_size = 0

    for section in sections:
        section_text = str(section.get("text") or "").strip()
        if not section_text:
            continue
        section_size = len(section_text)
        if bucket and bucket_size + section_size > max_chars:
            flush()
        if section_size > max_chars:
            packed.append(section)
            continue
        bucket.append(section)
        bucket_size += section_size
    flush()
    return packed


def _split_markdown_sections(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    line_starts = _line_start_offsets(text)
    heading_indices = [i for i, line in enumerate(lines) if re.match(r"^#{1,6}\s+", line)]
    if not heading_indices:
        return []
    sections: list[dict[str, Any]] = []
    current_path: list[str] = []
    for pos, start in enumerate(heading_indices):
        end = heading_indices[pos + 1] if pos + 1 < len(heading_indices) else len(lines)
        char_start = line_starts[start]
        char_end = line_starts[end] if end < len(line_starts) else len(text)
        heading_line = lines[start]
        level = len(heading_line) - len(heading_line.lstrip("#"))
        heading = normalize_entity_text(heading_line.lstrip("#").strip())
        current_path = current_path[: max(level - 1, 0)]
        current_path.append(heading)
        body = "\n".join(lines[start:end]).strip()
        if body:
            sections.append({"heading_path": list(current_path), "text": body, "kind": "heading_section", "char_start": char_start, "char_end": char_end})
    return sections


def _split_paragraph_sections(text: str) -> list[dict[str, Any]]:
    paragraphs = [(match.group(0).strip(), match.start(), match.end()) for match in re.finditer(r"(?s)(?:^|\n\s*\n)(.*?)(?=\n\s*\n|$)", text) if match.group(0).strip()]
    if not paragraphs:
        return [{"heading_path": [], "text": text.strip(), "kind": "plain_text_window", "char_start": 0, "char_end": len(text)}] if text.strip() else []
    sections: list[dict[str, Any]] = []
    bucket: list[str] = []
    size = 0
    bucket_start = 0
    bucket_end = 0
    for paragraph, start, end in paragraphs:
        if bucket and size + len(paragraph) > 4500:
            sections.append({"heading_path": [], "text": "\n\n".join(bucket), "kind": "paragraph_group", "char_start": bucket_start, "char_end": bucket_end})
            bucket = []
            size = 0
            bucket_start = start
        if not bucket:
            bucket_start = start
        bucket.append(paragraph)
        size += len(paragraph)
        bucket_end = end
    if bucket:
        sections.append({"heading_path": [], "text": "\n\n".join(bucket), "kind": "paragraph_group", "char_start": bucket_start, "char_end": bucket_end})
    return sections

def _line_start_offsets(text: str) -> list[int]:
    starts = [0]
    for match in re.finditer("\n", text):
        starts.append(match.end())
    starts.append(len(text))
    return starts


def _window_text(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    return [item["text"] for item in _window_text_with_spans(text, max_chars=max_chars, overlap_chars=overlap_chars)]

def _window_text_with_spans(text: str, *, max_chars: int, overlap_chars: int) -> list[dict[str, Any]]:
    text = text.strip()
    if len(text) <= max_chars:
        return [{"text": text, "char_start": 0, "char_end": len(text)}] if text else []
    chunks: list[dict[str, Any]] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        part = text[start:end].strip()
        left_trim = len(text[start:end]) - len(text[start:end].lstrip())
        chunks.append({"text": part, "char_start": start + left_trim, "char_end": start + left_trim + len(part)})
        if end == len(text):
            break
        start = max(end - overlap_chars, start + 1)
    return chunks


def _build_auxiliary_extraction_prompt(*, chunk: dict[str, Any], language: str) -> str:
    hint = normalize_entity_text(chunk.get("author_hint") or "")
    if hint:
        hint_block = hint
    else:
        hint_block = (
            "No author hint was provided. Use the document title/filename and the chunk content as fallback context. "
            "Do not penalize clear facts solely because the author hint is missing."
        )
    return AUXILIARY_EXTRACTION_PROMPT.format(
        WORK_LANGUAGE=language or "unknown",
        AUTHOR_HINT_BLOCK=hint_block,
        SOURCE_ID=chunk["source_id"],
        CHUNK_ID=chunk["chunk_id"],
        FILENAME=chunk["filename"],
        HEADING_PATH=json.dumps(chunk.get("heading_path") or [], ensure_ascii=False),
        TITLE_HINT=chunk.get("title_hint") or "",
        CHUNK_TEXT=chunk.get("text") or "",
    )


def _normalize_auxiliary_extraction(payload: dict[str, Any], *, chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": chunk["chunk_id"],
        "source_id": chunk["source_id"],
        "filename": chunk["filename"],
        "heading_path": chunk.get("heading_path") or [],
        "author_hint": chunk.get("author_hint") or "",
        "author_hint_status": chunk.get("author_hint_status") or "missing",
        "document_role": str(payload.get("document_role") or "unknown_auxiliary").strip() or "unknown_auxiliary",
        "document_role_confidence": _float(payload.get("document_role_confidence"), default=0.0),
        "declared_entities": [_normalize_declared_entity(item, chunk=chunk) for item in payload.get("declared_entities") or [] if isinstance(item, dict)],
        "declared_relationships": [
            _normalize_declared_relationship(item, chunk=chunk) for item in payload.get("declared_relationships") or [] if isinstance(item, dict)
        ],
        "planned_events": [_normalize_planned_event(item, chunk=chunk) for item in payload.get("planned_events") or [] if isinstance(item, dict)],
        "backstory_items": list(payload.get("backstory_items") or []),
        "uncertain_notes": [normalize_entity_text(item) for item in payload.get("uncertain_notes") or [] if normalize_entity_text(item)],
    }


def _normalize_declared_entity(item: dict[str, Any], *, chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "canonical_name": normalize_entity_text(item.get("canonical_name") or ""),
        "entity_kind": _normalize_kind(item.get("entity_kind")),
        "entity_subkind": normalize_entity_text(item.get("entity_subkind") or ""),
        "aliases": _strings(item.get("aliases") or []),
        "summary": normalize_entity_text(item.get("summary") or ""),
        "facts": _strings(item.get("facts") or item.get("key_facts") or []),
        "narrative_status": _normalize_status(item.get("narrative_status")),
        "confidence": _float(item.get("confidence"), default=0.0),
        "uncertainty": normalize_entity_text(item.get("uncertainty") or ""),
        "source_refs": [_source_ref(chunk)],
    }


def _normalize_declared_relationship(item: dict[str, Any], *, chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": normalize_entity_text(item.get("source") or item.get("from") or ""),
        "target": normalize_entity_text(item.get("target") or item.get("to") or ""),
        "type": normalize_entity_text(item.get("type") or "related_to") or "related_to",
        "facts": _strings(item.get("facts") or []),
        "narrative_status": _normalize_status(item.get("narrative_status")),
        "confidence": _float(item.get("confidence"), default=0.0),
        "uncertainty": normalize_entity_text(item.get("uncertainty") or ""),
        "source_refs": [_source_ref(chunk)],
    }


def _normalize_planned_event(item: dict[str, Any], *, chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "canonical_name": normalize_entity_text(item.get("canonical_name") or ""),
        "entity_kind": "event",
        "entity_subkind": "historical",
        "aliases": [],
        "summary": normalize_entity_text(item.get("summary") or ""),
        "facts": _strings(item.get("facts") or []),
        "narrative_status": _normalize_status(item.get("narrative_status") or "planned"),
        "confidence": _float(item.get("confidence"), default=0.0),
        "uncertainty": normalize_entity_text(item.get("uncertainty") or ""),
        "source_refs": [_source_ref(chunk)],
    }


def _source_ref(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": chunk["source_id"],
        "chunk_id": chunk["chunk_id"],
        "filename": chunk["filename"],
        "heading_path": chunk.get("heading_path") or [],
        "char_start": int(chunk.get("char_start", 0) or 0),
        "char_end": int(chunk.get("char_end", 0) or 0),
        "source_origin": "auxiliary",
    }


def _normalize_kind(value: Any) -> str:
    kind = str(value or "").strip().casefold()
    return kind if kind in {"character", "place", "faction", "concept", "object", "creature", "event"} else "concept"


def _normalize_status(value: Any) -> str:
    status = str(value or "").strip().casefold()
    return status if status in {"observed", "planned", "backstory", "speculative", "uncertain"} else "planned"


def _strings(values: Any) -> list[str]:
    if not isinstance(values, list):
        values = [values]
    out: list[str] = []
    for value in values:
        text = normalize_entity_text(value)
        if text and text not in out:
            out.append(text)
    return out


def _float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _apply_auxiliary_extractions(
    *,
    entities: list[dict[str, Any]],
    extractions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output = [dict(entity) for entity in entities]
    created_entities: list[dict[str, Any]] = []
    enriched_entities: list[dict[str, Any]] = []
    planned_relationships: list[dict[str, Any]] = []
    unmatched_items: list[dict[str, Any]] = []

    def rebuild_index() -> dict[str, int]:
        index: dict[str, int] = {}
        for idx, entity in enumerate(output):
            for value in [entity.get("canonical_name") or "", *(entity.get("aliases") or []), *(entity.get("source_mentions") or [])]:
                key = normalize_entity_key(value)
                if key and key not in index:
                    index[key] = idx
        return index

    entity_index = rebuild_index()
    for extraction in extractions:
        for declared in [*(extraction.get("declared_entities") or []), *(extraction.get("planned_events") or [])]:
            name = declared.get("canonical_name") or ""
            if not name:
                continue
            key = normalize_entity_key(name)
            match_idx = entity_index.get(key)
            if match_idx is None:
                for alias in declared.get("aliases") or []:
                    match_idx = entity_index.get(normalize_entity_key(alias))
                    if match_idx is not None:
                        break
            if match_idx is not None:
                _enrich_existing_entity(output[match_idx], declared)
                enriched_entities.append({"canonical_name": output[match_idx].get("canonical_name") or "", "auxiliary_name": name})
            elif float(declared.get("confidence") or 0.0) >= 0.65 and not declared.get("uncertainty"):
                new_entity = _new_auxiliary_entity(declared)
                output.append(new_entity)
                created_entities.append({"canonical_name": new_entity["canonical_name"], "entity_kind": new_entity["entity_kind"]})
                entity_index = rebuild_index()
            else:
                unmatched_items.append({"kind": "entity", "canonical_name": name, "reason": "low_confidence_or_uncertain"})

    entity_index = rebuild_index()
    for extraction in extractions:
        for relationship in extraction.get("declared_relationships") or []:
            source_key = normalize_entity_key(relationship.get("source") or "")
            target_key = normalize_entity_key(relationship.get("target") or "")
            source_idx = entity_index.get(source_key)
            target_idx = entity_index.get(target_key)
            if source_idx is None or target_idx is None:
                unmatched_items.append(
                    {
                        "kind": "relationship",
                        "source": relationship.get("source") or "",
                        "target": relationship.get("target") or "",
                        "reason": "unresolved_endpoint",
                    }
                )
                continue
            rel = {
                "target": output[target_idx].get("canonical_name") or relationship.get("target") or "",
                "type": relationship.get("type") or "related_to",
                "facts": relationship.get("facts") or [],
                "narrative_status": relationship.get("narrative_status") or "planned",
                "source_origin": "auxiliary",
                "source_refs": relationship.get("source_refs") or [],
            }
            existing = list(output[source_idx].get("relationships") or [])
            existing.append(rel)
            output[source_idx]["relationships"] = existing
            output[source_idx]["entity_origin"] = _merge_origin(output[source_idx].get("entity_origin"))
            planned_relationships.append(
                {
                    "source": output[source_idx].get("canonical_name") or "",
                    "target": rel["target"],
                    "type": rel["type"],
                    "narrative_status": rel["narrative_status"],
                }
            )

    return output, {
        "created_entities": created_entities,
        "enriched_entities": enriched_entities,
        "planned_relationships": planned_relationships,
        "unmatched_items": unmatched_items,
        "created_entity_count": len(created_entities),
        "enriched_entity_count": len(enriched_entities),
        "planned_relationship_count": len(planned_relationships),
        "unmatched_item_count": len(unmatched_items),
    }


def _enrich_existing_entity(entity: dict[str, Any], declared: dict[str, Any]) -> None:
    entity["aliases"] = _merge_strings(entity.get("aliases") or [], declared.get("aliases") or [])
    entity["key_facts"] = _merge_strings(entity.get("key_facts") or [], declared.get("facts") or [])
    entity["auxiliary_facts"] = _merge_strings(entity.get("auxiliary_facts") or [], declared.get("facts") or [])
    entity["source_refs"] = [*(entity.get("source_refs") or []), *(declared.get("source_refs") or [])]
    entity["entity_origin"] = _merge_origin(entity.get("entity_origin"))
    entity["narrative_statuses"] = _merge_strings(entity.get("narrative_statuses") or [], [declared.get("narrative_status") or "planned"])
    summary = normalize_entity_text(declared.get("summary") or "")
    if summary:
        entity["auxiliary_summary"] = summary


def _new_auxiliary_entity(declared: dict[str, Any]) -> dict[str, Any]:
    name = declared.get("canonical_name") or ""
    return {
        "canonical_name": name,
        "canonical_candidate": name,
        "entity_kind": declared.get("entity_kind") or "concept",
        "entity_subkind": declared.get("entity_subkind") or "",
        "preferred_slug": normalize_entity_key(name).replace(" ", "_") or "auxiliary_entity",
        "aliases": declared.get("aliases") or [],
        "summary": declared.get("summary") or "",
        "key_facts": declared.get("facts") or [],
        "auxiliary_facts": declared.get("facts") or [],
        "relationships": [],
        "chapter_refs": [],
        "source_mentions": [name],
        "source_refs": declared.get("source_refs") or [],
        "confidence": float(declared.get("confidence") or 0.0),
        "entity_origin": "auxiliary_declared",
        "narrative_statuses": [declared.get("narrative_status") or "planned"],
        "review_state": "canonical",
        "promotion_status": "promoted_canonical",
        "note_role": "primary",
        "naming_quality": "proper_name" if (declared.get("entity_kind") == "character" and len(name.split()) <= 4) else "descriptor",
        "needs_review": bool(declared.get("uncertainty")),
        "graph_exclude": False,
        "retrieval_exclude": False,
    }


def _merge_origin(value: Any) -> str:
    current = str(value or "").strip()
    if current == "auxiliary_declared":
        return "auxiliary_declared"
    return "mixed"


def _merge_strings(left: list[Any], right: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in [*left, *right]:
        text = normalize_entity_text(value)
        key = normalize_entity_key(text)
        if text and key not in seen:
            seen.add(key)
            out.append(text)
    return out
