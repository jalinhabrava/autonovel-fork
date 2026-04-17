from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

from adapters.vault_adapter import VaultProjectAdapter
from interactive.chapter_selection import chapter_ids_for, chapter_path_strings, normalize_chapter_id, select_chapter_records
from interactive.persistence_commands import create_note, get_existing_artifact_status, update_note
from interactive.query import extract_summary, infer_characters, parse_frontmatter, strip_frontmatter


CHARACTER_STOPWORDS = {
    "Chapter",
    "The",
    "And",
    "But",
    "For",
    "When",
    "Then",
    "This",
    "That",
    "There",
    "They",
    "Their",
    "Because",
    "Before",
    "After",
    "He",
    "She",
    "His",
    "Her",
    "You",
    "Your",
    "Our",
    "We",
    "I",
}

CANON_MARKERS = ("always", "never", "must", "cannot", "can't", "only", "requires", "forbidden", "cost", "limit")


def extract_voice(
    vault_root: str | Path,
    *,
    chapter_ids: list[str] | None = None,
    chapter_from: int | None = None,
    chapter_to: int | None = None,
) -> dict:
    adapter = VaultProjectAdapter(vault_root)
    records = select_chapter_records(adapter, chapter_ids=chapter_ids, chapter_from=chapter_from, chapter_to=chapter_to)
    if not records:
        raise ValueError("No chapters available for extract-voice.")

    body = _build_project_voice_body(records)
    payload = {
        "type": "artifact_payload",
        "artifact_kind": "root_artifact",
        "artifact_type": "voice",
        "entity_id": "voice",
        "title": "Project Voice",
        "body": body,
        "state": _state_for_records(records, threshold=2),
        "metadata": {
            "voice_layer": "project",
            "bootstrap_mode": "partial_manuscript_extraction",
            "chapter_paths": ",".join(chapter_path_strings(records)),
        },
        "origin": {
            "source": "manuscript_bootstrap",
            "chapter_ids": chapter_ids_for(records),
        },
    }
    return _bootstrap_persist(vault_root, payload)


def extract_characters(
    vault_root: str | Path,
    *,
    chapter_ids: list[str] | None = None,
    chapter_from: int | None = None,
    chapter_to: int | None = None,
) -> list[dict]:
    adapter = VaultProjectAdapter(vault_root)
    records = select_chapter_records(adapter, chapter_ids=chapter_ids, chapter_from=chapter_from, chapter_to=chapter_to)
    if not records:
        raise ValueError("No chapters available for extract-characters.")

    entities = _extract_character_candidates(records)
    results: list[dict] = []
    for name, evidence in entities.items():
        slug = _slugify(name)
        body = _build_character_body(name, evidence["chapter_ids"], evidence["signals"])
        payload = {
            "type": "artifact_payload",
            "artifact_kind": "note",
            "artifact_type": "character",
            "entity_id": slug,
            "title": name,
            "body": body,
            "state": "pending_revision" if len(evidence["chapter_ids"]) >= 2 else "proposed",
            "metadata": {
                "bootstrap_mode": "manuscript_character_extraction",
                "evidence_count": evidence["count"],
            },
            "origin": {
                "source": "manuscript_bootstrap",
                "chapter_ids": sorted(evidence["chapter_ids"]),
            },
        }
        results.append(_bootstrap_persist(vault_root, payload))
    return results


def extract_canon(
    vault_root: str | Path,
    *,
    chapter_ids: list[str] | None = None,
    chapter_from: int | None = None,
    chapter_to: int | None = None,
) -> list[dict]:
    adapter = VaultProjectAdapter(vault_root)
    records = select_chapter_records(adapter, chapter_ids=chapter_ids, chapter_from=chapter_from, chapter_to=chapter_to)
    if not records:
        raise ValueError("No chapters available for extract-canon.")

    proposals = _extract_canon_candidates(records)
    results: list[dict] = []
    for proposal in proposals:
        payload = {
            "type": "artifact_payload",
            "artifact_kind": "note",
            "artifact_type": "decision",
            "entity_id": proposal["entity_id"],
            "title": proposal["title"],
            "body": proposal["body"],
            "state": "pending_revision" if len(proposal["chapter_ids"]) >= 2 else "proposed",
            "metadata": {
                "bootstrap_mode": "manuscript_canon_extraction",
                "canon_source": "extracted_proposal",
                "evidence_count": len(proposal["evidence"]),
            },
            "origin": {
                "source": "manuscript_bootstrap",
                "chapter_ids": proposal["chapter_ids"],
            },
        }
        results.append(_bootstrap_persist(vault_root, payload))
    return results


def extract_timeline(
    vault_root: str | Path,
    *,
    chapter_ids: list[str] | None = None,
    chapter_from: int | None = None,
    chapter_to: int | None = None,
) -> list[dict]:
    adapter = VaultProjectAdapter(vault_root)
    records = select_chapter_records(adapter, chapter_ids=chapter_ids, chapter_from=chapter_from, chapter_to=chapter_to)
    if not records:
        raise ValueError("No chapters available for extract-timeline.")

    results: list[dict] = []
    for record in records:
        chapter_id = str(record["id"])
        summary = extract_summary(record["text"], f"Provisional event derived from {chapter_id}.")
        payload = {
            "type": "artifact_payload",
            "artifact_kind": "note",
            "artifact_type": "lore",
            "entity_id": f"timeline_{chapter_id}",
            "title": f"Timeline Event {chapter_id.upper()}",
            "body": (
                "# Provisional Timeline Note\n\n"
                "This timeline artifact is a provisional lore-backed event extracted from manuscript chapters.\n"
                "It is not yet the definitive timeline model.\n\n"
                f"## Source Chapter\n\n- {chapter_id}\n\n"
                f"## Extracted Event\n\n{summary}\n"
            ),
            "state": "proposed",
            "metadata": {
                "bootstrap_mode": "manuscript_timeline_extraction",
                "timeline_model": "provisional_lore_note",
            },
            "origin": {
                "source": "manuscript_bootstrap",
                "chapter_ids": [chapter_id],
            },
        }
        results.append(_bootstrap_persist(vault_root, payload))
    return results


def _bootstrap_persist(vault_root: str | Path, payload: dict) -> dict:
    existing_status = get_existing_artifact_status(vault_root, payload)
    if existing_status is None:
        return create_note(vault_root, payload)

    if existing_status == "proposed":
        return update_note(vault_root, payload)

    if payload["artifact_kind"] == "root_artifact":
        return {
            "type": payload["type"],
            "status": "skipped",
            "state": payload["state"],
            "artifact_kind": payload["artifact_kind"],
            "target_type": payload["artifact_type"],
            "target_id": payload["entity_id"],
            "reason": f"existing_{existing_status}_root_artifact_requires_manual_review",
        }

    proposal_payload = _fork_bootstrap_proposal(payload, existing_status=existing_status)
    return create_note(vault_root, proposal_payload)


def _fork_bootstrap_proposal(payload: dict, *, existing_status: str) -> dict:
    chapter_ids = payload.get("origin", {}).get("chapter_ids", [])
    suffix = "_".join(normalize_chapter_id(chapter_id) for chapter_id in chapter_ids[:2]) or "bootstrap"
    forked = dict(payload)
    forked["entity_id"] = f"{payload['entity_id']}__bootstrap__{suffix}".lower()
    forked["title"] = f"{payload['title']} (Bootstrap Proposal)"
    forked["state"] = "proposed"
    metadata = dict(payload.get("metadata", {}))
    metadata["derived_from_existing_status"] = existing_status
    forked["metadata"] = metadata
    return forked


def _build_project_voice_body(records: list[dict]) -> str:
    text = "\n".join(strip_frontmatter(record["text"]) for record in records)
    sentence_lengths = [len(sentence.split()) for sentence in re.split(r"[.!?]+", text) if sentence.strip()]
    avg_sentence = round(sum(sentence_lengths) / len(sentence_lengths), 1) if sentence_lengths else 0

    first_person = len(re.findall(r"\bI\b|\bwe\b", text))
    close_third = len(re.findall(r"\bhe\b|\bshe\b|\bthey\b", text.lower()))
    narration_mode = "close third person" if close_third >= first_person else "first person leaning"

    sensory_words = [word for word in ("salt", "stone", "light", "shadow", "heat", "cold", "touch") if word in text.lower()]
    beat_pattern = "balanced cadence" if avg_sentence < 18 else "longer lyrical cadence"
    chapter_ids = chapter_ids_for(records)

    return (
        "# Project Voice\n\n"
        "## Preset Reference\n\n"
        "- selected_preset: none\n"
        "- preset_status: not_configured_yet\n\n"
        "## Project Overrides\n\n"
        f"- inferred narration mode: {narration_mode}\n"
        f"- average sentence length across sampled chapters: {avg_sentence} words\n"
        f"- observed beat pattern: {beat_pattern}\n\n"
        "## Manuscript Signals\n\n"
        f"- extracted from chapters: {', '.join(chapter_ids)}\n"
        f"- sensory anchors observed: {', '.join(sorted(set(sensory_words))) or 'none explicit'}\n"
        "- use these signals as project-level overrides, not as a final preset definition\n"
    )


def _extract_character_candidates(records: list[dict]) -> dict[str, dict]:
    counts: Counter[str] = Counter()
    chapter_map: dict[str, set[str]] = defaultdict(set)
    signals: dict[str, list[str]] = defaultdict(list)

    for record in records:
        chapter_id = str(record["id"])
        body = strip_frontmatter(record["text"])
        names = re.findall(r"\b[A-Z][a-z]{2,}\b", body)
        local_counts = Counter(name for name in names if name not in CHARACTER_STOPWORDS)
        for name, count in local_counts.items():
            counts[name] += count
            chapter_map[name].add(chapter_id)
            signals[name].append(extract_summary(body, f"{name} appears in {chapter_id}."))

    selected = {}
    for name, count in counts.most_common(8):
        if count < 2:
            continue
        selected[name] = {
            "count": count,
            "chapter_ids": chapter_map[name],
            "signals": signals[name][:3],
        }
    return selected


def _build_character_body(name: str, chapter_ids: set[str], signals: list[str]) -> str:
    evidence_lines = "\n".join(f"- {chapter_id}" for chapter_id in sorted(chapter_ids))
    signal_lines = "\n".join(f"- {signal}" for signal in signals if signal)
    voice_hint = "dialogue/register still provisional; refine after editorial review"
    return (
        f"# {name}\n\n"
        "## Role\n\n"
        "Provisional character profile extracted from manuscript chapters.\n\n"
        "## Evidence\n\n"
        f"{evidence_lines}\n\n"
        "## Observed Signals\n\n"
        f"{signal_lines or '- limited evidence collected'}\n\n"
        "## Character Voice Layer\n\n"
        f"- {voice_hint}\n"
    )


def _extract_canon_candidates(records: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for record in records:
        chapter_id = str(record["id"])
        body = strip_frontmatter(record["text"])
        sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", body) if sentence.strip()]
        for sentence in sentences:
            lowered = sentence.lower()
            if not any(marker in lowered for marker in CANON_MARKERS):
                continue
            key = _slugify(re.sub(r"[^a-z0-9 ]+", "", lowered)[:60])
            entry = grouped.setdefault(
                key,
                {
                    "entity_id": f"canon_{key}"[:80],
                    "title": f"Canon Proposal: {sentence[:60]}",
                    "claim": sentence,
                    "chapter_ids": [],
                    "evidence": [],
                },
            )
            if chapter_id not in entry["chapter_ids"]:
                entry["chapter_ids"].append(chapter_id)
            entry["evidence"].append(f"{chapter_id}: {sentence}")

    proposals: list[dict] = []
    for entry in grouped.values():
        body = (
            "# Extracted Canon Proposal\n\n"
            "This note is a proposed canon artifact extracted from manuscript chapters.\n"
            "It is not a validated canon decision.\n\n"
            "## Claim\n\n"
            f"{entry['claim']}\n\n"
            "## Evidence\n\n"
            + "\n".join(f"- {item}" for item in entry["evidence"][:4])
            + "\n\n## Traceability\n\n"
            + "\n".join(f"- {chapter_id}" for chapter_id in entry["chapter_ids"])
        )
        proposals.append(
            {
                "entity_id": entry["entity_id"],
                "title": entry["title"],
                "body": body,
                "chapter_ids": entry["chapter_ids"],
                "evidence": entry["evidence"],
            }
        )
    return proposals


def _state_for_records(records: list[dict], *, threshold: int) -> str:
    return "pending_revision" if len(records) >= threshold else "proposed"


def _slugify(value: str) -> str:
    value = value.strip().lower().replace(" ", "_")
    return "".join(ch for ch in value if ch.isalnum() or ch in {"_", "-"}).strip("_") or "artifact"
