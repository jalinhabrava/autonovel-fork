from __future__ import annotations

from dataclasses import asdict

from textifai.author_understanding.contracts import AuthorIntentInterpretation
from textifai.editorial_intent.contracts import CandidateTarget, EditorialIntent


def classify_editorial_intent(
    *,
    raw_text: str,
    recognized_intent_name: str,
    entity_results,
    narrative_signals,
    state=None,
    author_understanding: AuthorIntentInterpretation | None = None,
) -> EditorialIntent | None:
    lowered = raw_text.casefold().strip()
    candidate_targets = _candidate_targets_from_entities(entity_results)
    if author_understanding and author_understanding.disambiguation is not None:
        candidate_targets = _dedupe_targets(
            candidate_targets + list(author_understanding.disambiguation.candidate_targets)
        )
    multi_target = _is_multi_target_request(lowered, candidate_targets) or (
        author_understanding is not None and author_understanding.has_mixed_request and len(candidate_targets) >= 2
    )
    resolved_target = None
    if not multi_target:
        resolved_target = _resolve_target(candidate_targets, author_understanding)
        if resolved_target is None:
            resolved_target = next((item for item in candidate_targets if item.confidence >= 0.9), None)
    preserve_constraints, editorial_goals = _editorial_guidance(lowered, narrative_signals)
    if author_understanding is not None:
        preserve_constraints = _dedupe(preserve_constraints + _normalize_signal_list(author_understanding.preserve_signals))
        author_goals = [goal for goal in _normalize_signal_list(author_understanding.author_goal_signals) if goal != "mixed_request"]
        author_changes = [goal for goal in _normalize_signal_list(author_understanding.change_signals) if goal != "mixed_request"]
        editorial_goals = _dedupe(
            editorial_goals
            + author_goals
            + author_changes
        )
    followup_mode = _followup_mode(
        lowered,
        candidate_targets,
        state,
        recognized_intent_name=recognized_intent_name,
        author_understanding=author_understanding,
    )
    author_request_type = _author_understanding_request_type(author_understanding)
    narrative_source_text = _narrative_source_text(raw_text, author_understanding)

    if author_request_type == "validation_request" or _is_validation_request(lowered):
        validation_followup_mode = followup_mode
        if validation_followup_mode == "none":
            validation_followup_mode = "reuse_recent_target" if state and state.last_target_id else "require_clarification"
        return EditorialIntent(
            request_type="validation_request",
            confidence=0.9,
            target_scope=_target_scope(candidate_targets, state),
            resolved_target_type=None if multi_target else (resolved_target.target_type if resolved_target else None),
            resolved_target_id=None if multi_target else (resolved_target.target_id if resolved_target else None),
            candidate_targets=candidate_targets,
            followup_mode=validation_followup_mode,
            preserve_constraints=preserve_constraints,
            editorial_goals=_dedupe(editorial_goals + ["structure_scene"]),
            metadata={
                "narrative_source_text": None,
                "multi_target": multi_target,
                "followthrough_action": "validate_structure",
                "author_understanding": asdict(author_understanding) if author_understanding is not None else None,
            },
        )

    if author_request_type == "narration_preparation" or _is_narration_preparation(lowered):
        request_type = "narration_preparation"
        if author_understanding is not None and author_understanding.has_mixed_request:
            request_type = "mixed_editorial_request"
        elif _is_structuring_request(lowered):
            request_type = "mixed_editorial_request"
        return EditorialIntent(
            request_type=request_type,
            confidence=0.82,
            target_scope=_target_scope(candidate_targets, state),
            resolved_target_type=None if multi_target else (resolved_target.target_type if resolved_target else None),
            resolved_target_id=None if multi_target else (resolved_target.target_id if resolved_target else None),
            candidate_targets=candidate_targets,
            followup_mode=followup_mode,
            preserve_constraints=preserve_constraints,
            editorial_goals=_dedupe(editorial_goals + ["prepare_for_narration"]),
            metadata={
                "narrative_source_text": narrative_source_text,
                "multi_target": multi_target,
                "followthrough_action": "prepare_narration" if request_type == "narration_preparation" else None,
                "author_understanding": asdict(author_understanding) if author_understanding is not None else None,
            },
        )

    if author_request_type == "review_handoff" or _is_review_handoff(lowered):
        return EditorialIntent(
            request_type="review_handoff",
            confidence=0.84,
            target_scope=_target_scope(candidate_targets, state),
            resolved_target_type=None if multi_target else (resolved_target.target_type if resolved_target else None),
            resolved_target_id=None if multi_target else (resolved_target.target_id if resolved_target else None),
            candidate_targets=candidate_targets,
            followup_mode=followup_mode,
            preserve_constraints=preserve_constraints,
            editorial_goals=_dedupe(editorial_goals),
            metadata={
                "narrative_source_text": None,
                "multi_target": multi_target,
                "followthrough_action": "prepare_review",
                "author_understanding": asdict(author_understanding) if author_understanding is not None else None,
            },
        )

    if author_request_type == "structured_followup" or _is_structured_followup(lowered):
        structured_followup_mode = followup_mode if followup_mode != "none" else "require_clarification"
        return EditorialIntent(
            request_type="structured_followup",
            confidence=0.8,
            target_scope=_target_scope(candidate_targets, state),
            resolved_target_type=None if multi_target else (resolved_target.target_type if resolved_target else None),
            resolved_target_id=None if multi_target else (resolved_target.target_id if resolved_target else None),
            candidate_targets=candidate_targets,
            followup_mode=structured_followup_mode,
            preserve_constraints=preserve_constraints,
            editorial_goals=_dedupe(editorial_goals),
            metadata={
                "narrative_source_text": None,
                "multi_target": multi_target,
                "followthrough_action": "resume_followup",
                "author_understanding": asdict(author_understanding) if author_understanding is not None else None,
            },
        )

    if (
        (author_request_type == "contextual_followup" and recognized_intent_name not in {"inspect_scene", "inspect_chapter"})
        or (
            _is_followup_only(lowered)
            and not (
                _is_structuring_request(lowered)
                or _is_editorial_revision(lowered, narrative_signals)
                or _is_narration_preparation(lowered)
            )
        )
    ):
        return EditorialIntent(
            request_type="contextual_followup",
            confidence=0.74,
            target_scope=_target_scope(candidate_targets, state),
            resolved_target_type=None if multi_target else (resolved_target.target_type if resolved_target else None),
            resolved_target_id=None if multi_target else (resolved_target.target_id if resolved_target else None),
            candidate_targets=candidate_targets,
            followup_mode=followup_mode,
            preserve_constraints=preserve_constraints,
            editorial_goals=editorial_goals,
            metadata={
                "narrative_source_text": None,
                "multi_target": multi_target,
                "author_understanding": asdict(author_understanding) if author_understanding is not None else None,
            },
        )

    if author_request_type == "mixed_request" or (
        author_understanding is not None and author_understanding.has_mixed_request and _is_structuring_request(lowered)
    ):
        return EditorialIntent(
            request_type="mixed_editorial_request",
            confidence=0.81,
            target_scope=_target_scope(candidate_targets, state),
            resolved_target_type=None if multi_target else (resolved_target.target_type if resolved_target else None),
            resolved_target_id=None if multi_target else (resolved_target.target_id if resolved_target else None),
            candidate_targets=candidate_targets,
            followup_mode=followup_mode,
            preserve_constraints=preserve_constraints,
            editorial_goals=_dedupe(editorial_goals),
            metadata={
                "narrative_source_text": narrative_source_text,
                "multi_target": multi_target,
                "author_understanding": asdict(author_understanding) if author_understanding is not None else None,
            },
        )

    if author_request_type == "structuring_request" or _is_structuring_request(lowered):
        return EditorialIntent(
            request_type="structuring_request",
            confidence=0.8,
            target_scope=_target_scope(candidate_targets, state),
            resolved_target_type=None if multi_target else (resolved_target.target_type if resolved_target else None),
            resolved_target_id=None if multi_target else (resolved_target.target_id if resolved_target else None),
            candidate_targets=candidate_targets,
            followup_mode=followup_mode,
            preserve_constraints=preserve_constraints,
            editorial_goals=_dedupe(editorial_goals + ["structure_scene"]),
            metadata={
                "narrative_source_text": narrative_source_text,
                "multi_target": multi_target,
                "author_understanding": asdict(author_understanding) if author_understanding is not None else None,
            },
        )

    if author_request_type == "editorial_revision" or (
        _is_editorial_revision(lowered, narrative_signals)
        and (
            recognized_intent_name not in {"inspect_scene", "inspect_chapter"}
            or any(
                phrase in lowered
                for phrase in (
                    "no me gusta",
                    "quiero que",
                    "suena demasiado",
                    "ordena",
                    "ordénalo",
                    "ordena lo",
                    "ordénalo mejor",
                    "sin que",
                    "no entiendo por qué",
                    "no entiendo por que",
                )
            )
        )
    ):
        return EditorialIntent(
            request_type="editorial_revision",
            confidence=0.79,
            target_scope=_target_scope(candidate_targets, state),
            resolved_target_type=None if multi_target else (resolved_target.target_type if resolved_target else None),
            resolved_target_id=None if multi_target else (resolved_target.target_id if resolved_target else None),
            candidate_targets=candidate_targets,
            followup_mode=followup_mode,
            preserve_constraints=preserve_constraints,
            editorial_goals=editorial_goals,
            metadata={
                "narrative_source_text": None,
                "multi_target": multi_target,
                "author_understanding": asdict(author_understanding) if author_understanding is not None else None,
            },
        )

    if author_request_type == "narrative_facts" or recognized_intent_name == "editorial_structuring" or _looks_like_narrative_facts(lowered):
        return EditorialIntent(
            request_type="narrative_facts",
            confidence=0.72,
            target_scope=_target_scope(candidate_targets, state),
            resolved_target_type=None if multi_target else (resolved_target.target_type if resolved_target else None),
            resolved_target_id=None if multi_target else (resolved_target.target_id if resolved_target else None),
            candidate_targets=candidate_targets,
            followup_mode=followup_mode,
            preserve_constraints=preserve_constraints,
            editorial_goals=_dedupe(editorial_goals + ["extract_story_facts"]),
            metadata={
                "narrative_source_text": narrative_source_text or raw_text,
                "multi_target": multi_target,
                "author_understanding": asdict(author_understanding) if author_understanding is not None else None,
            },
        )
    return None


def _candidate_targets_from_entities(entity_results) -> list[CandidateTarget]:
    targets: list[CandidateTarget] = []
    for item in entity_results:
        if item.resolved and item.resolved_entity_id and item.resolved_entity_type:
            targets.append(
                CandidateTarget(
                    target_id=item.resolved_entity_id,
                    target_type=item.resolved_entity_type,
                    confidence=item.resolution_confidence,
                )
            )
            continue
        if item.candidate_entities:
            top = item.candidate_entities[0]
            targets.append(
                CandidateTarget(
                    target_id=top.artifact_id,
                    target_type=top.artifact_type,
                    confidence=top.confidence,
                )
            )
    return _dedupe_targets(targets)


def _dedupe_targets(targets: list[CandidateTarget]) -> list[CandidateTarget]:
    seen: dict[tuple[str, str], CandidateTarget] = {}
    for target in targets:
        key = (target.target_type, target.target_id)
        if key not in seen or target.confidence > seen[key].confidence:
            seen[key] = target
    return sorted(
        seen.values(),
        key=lambda item: (
            item.confidence,
            1 if item.target_type in {"lore", "decision"} else 0,
        ),
        reverse=True,
    )[:5]


def _is_multi_target_request(lowered: str, candidate_targets: list[CandidateTarget]) -> bool:
    if len(candidate_targets) < 2:
        strong_targets = [target for target in candidate_targets if target.confidence >= 0.85]
        if len(strong_targets) >= 2:
            return True
        if lowered.count("lo del ") >= 2 and any(
            phrase in lowered
            for phrase in (
                "ordena",
                "ordénalo",
                "ordena lo",
                "ordénalo mejor",
                "sin romper el canon",
                "sin romper el",
                "ajusta",
                "reordena",
            )
        ):
            return True
        return False
    strong_targets = [target for target in candidate_targets if target.confidence >= 0.85]
    return len(strong_targets) >= 2


def _followup_mode(
    lowered: str,
    candidate_targets: list[CandidateTarget],
    state,
    *,
    recognized_intent_name: str,
    author_understanding: AuthorIntentInterpretation | None = None,
) -> str:
    if _is_followup_only(lowered):
        if author_understanding is not None and author_understanding.disambiguation is not None:
            if author_understanding.disambiguation.requires_user_confirmation and not author_understanding.disambiguation.preferred_target:
                return "require_clarification"
            if author_understanding.disambiguation.preferred_target is not None:
                return "prefer_candidate_targets"
        if lowered == "esta nota" and state and state.last_target_type in {"lore", "decision"}:
            return "reuse_recent_target"
        if lowered == "esta escena" and state and state.last_target_type == "scene":
            return "reuse_recent_target"
        if lowered in {"este capítulo", "este capitulo"} and state and state.last_target_type == "chapter":
            return "reuse_recent_target"
        if candidate_targets and candidate_targets[0].confidence >= 0.75:
            return "prefer_candidate_targets"
        if state and state.last_target_id:
            return "reuse_recent_target"
        return "require_clarification"
    if recognized_intent_name in {"validate_artifact", "reject_artifact"} and lowered == "esta nota":
        if state and state.last_target_type in {"lore", "decision"}:
            return "reuse_recent_target"
        if candidate_targets and candidate_targets[0].target_type in {"lore", "decision"} and candidate_targets[0].confidence >= 0.8:
            return "prefer_candidate_targets"
        return "require_clarification"
    return "none"


def _author_understanding_request_type(author_understanding: AuthorIntentInterpretation | None) -> str | None:
    if author_understanding is None:
        return None
    request_type = author_understanding.primary_intent_type
    if request_type == "mixed_request":
        return "mixed_request"
    if request_type in {
        "narrative_facts",
        "editorial_revision",
        "structuring_request",
        "narration_preparation",
        "contextual_followup",
        "validation_request",
        "narration_handoff",
        "review_handoff",
        "structured_followup",
    }:
        return request_type
    return None


def _resolve_target(
    candidate_targets: list[CandidateTarget],
    author_understanding: AuthorIntentInterpretation | None,
) -> CandidateTarget | None:
    if author_understanding is not None and author_understanding.disambiguation is not None:
        if author_understanding.disambiguation.preferred_target is not None:
            return author_understanding.disambiguation.preferred_target
    return next((item for item in candidate_targets if item.confidence >= 0.9), None)


def _narrative_source_text(raw_text: str, author_understanding: AuthorIntentInterpretation | None) -> str | None:
    if author_understanding is not None:
        if author_understanding.narrative_content_text is not None:
            return author_understanding.narrative_content_text
        if author_understanding.meta_instruction_text is not None and not author_understanding.narrative_content_text:
            return None
    return _extract_narrative_source_text(raw_text)


def _normalize_signal_list(values: list[str]) -> list[str]:
    return _dedupe([str(value).strip() for value in values if str(value).strip()])


def _editorial_guidance(lowered: str, narrative_signals) -> tuple[list[str], list[str]]:
    preserve_constraints: list[str] = []
    goals: list[str] = []
    issue_types = list((narrative_signals.issue_types if narrative_signals else []) or [])
    if "canon_issue" in issue_types:
        preserve_constraints.append("preserve_validated_canon")
        goals.append("anchor_canon")
    if "character_voice_mismatch" in issue_types:
        preserve_constraints.append("preserve_character_voice")
    if "tone_issue" in issue_types:
        goals.append("align_tone")
    if "motivation_issue" in issue_types:
        goals.append("clarify_motivation")
    if any(phrase in lowered for phrase in ("sin que", "without making")):
        preserve_constraints.append("preserve_character_empathy")
    if any(phrase in lowered for phrase in ("dure más", "dure mas", "last longer", "sostener el conflicto")):
        goals.append("extend_conflict")
        preserve_constraints.append("preserve_scene_conflict")
    return (_dedupe(preserve_constraints), _dedupe(goals))


def _target_scope(candidate_targets: list[CandidateTarget], state) -> str | None:
    if candidate_targets:
        return candidate_targets[0].target_type
    if state and state.last_target_type:
        return state.last_target_type
    return None


def _is_followup_only(lowered: str) -> bool:
    if lowered in {"esta nota", "esta escena", "este capítulo", "este capitulo", "sí, esa", "si, esa", "usa la anterior"}:
        return True
    if lowered.startswith("lo del "):
        return True
    return lowered.startswith("de lo anterior") or lowered.startswith("de la anterior")


def _is_narration_preparation(lowered: str) -> bool:
    return any(
        phrase in lowered
        for phrase in (
            "prepáralo para narrar",
            "preparalo para narrar",
            "prepare it for narration",
            "prepáralo para escribir",
            "preparalo para escribir",
            "versión narrable",
            "version narrable",
            "lista para narrar",
            "déjalo listo para narrar",
            "dejalo listo para narrar",
            "déjalo preparado",
            "dejalo preparado",
            "todavía no lo escribas",
            "todavia no lo escribas",
            "sin cerrarlo todavía",
            "sin cerrarlo todavia",
        )
    )


def _is_validation_request(lowered: str) -> bool:
    return any(
        phrase in lowered
        for phrase in (
            "valido esta estructura",
            "valida esta estructura",
            "validate this structure",
            "valida la estructura",
        )
    )


def _is_review_handoff(lowered: str) -> bool:
    return any(
        phrase in lowered
        for phrase in (
            "déjalo listo para revisión",
            "dejalo listo para revision",
            "prepáralo para revisión",
            "preparalo para revision",
            "listo para revisión",
            "listo para revision",
        )
    )


def _is_structured_followup(lowered: str) -> bool:
    return any(
        phrase in lowered
        for phrase in (
            "prepáralo con esa estructura",
            "preparalo con esa estructura",
            "usa la anterior",
            "sí, esa",
            "si, esa",
            "quédate con",
            "quedate con",
        )
    )


def _is_handoff_request(lowered: str) -> bool:
    return any(
        phrase in lowered
        for phrase in (
            "déjalo listo para narrar",
            "dejalo listo para narrar",
            "preparalo para narrar",
            "prepáralo para narrar",
        )
    )


def _is_structuring_request(lowered: str) -> bool:
    return any(
        phrase in lowered
        for phrase in (
            "ordenar esta escena",
            "ordenar la escena",
            "antes de escribirla",
            "convertirlos en una estructura",
            "estructura clara",
            "beat by beat",
            "beats",
            "ordenar esto",
        )
    )


def _is_editorial_revision(lowered: str, narrative_signals) -> bool:
    return bool(
        any(
            phrase in lowered
            for phrase in (
                "no me gusta",
                "quiero que",
                "sin que",
                "demasiado rápido",
                "demasiado rapido",
                "no entiendo por qué",
                "no entiendo por que",
                "suena demasiado",
                "ordena",
                "ordénalo",
                "ordena lo",
                "ordénalo mejor",
            )
        )
        or (narrative_signals and narrative_signals.issue_types)
    )


def _looks_like_narrative_facts(lowered: str) -> bool:
    return any(token in lowered for token in (",", "luego", "después", "despues", "terminan", "confiesa", "encuentra"))


def _extract_narrative_source_text(raw_text: str) -> str | None:
    text = raw_text.strip()
    lowered = text.casefold()
    meta_prefixes = (
        "estos son los hechos de la escena",
        "necesito ordenar esta escena antes de escribirla",
        "prepáralo para narrar",
        "preparalo para narrar",
    )
    if lowered in meta_prefixes:
        return None
    if lowered.startswith("estos son los hechos de la escena"):
        parts = text.split(";", 1)
        if len(parts) == 2:
            candidate = parts[1].strip()
            lowered_candidate = candidate.casefold()
            if any(
                phrase in lowered_candidate
                for phrase in (
                    "convertirlos en una estructura",
                    "estructura clara",
                    "lista para narrar",
                    "prepararla para narrar",
                    "dejarla lista para narrar",
                )
            ):
                return None
            if _looks_like_narrative_facts(lowered_candidate):
                return candidate or None
            return None
        return None
    if any(
        phrase in lowered
        for phrase in (
            "quiero convertirlos en una estructura",
            "quiero convertirlo en una estructura",
            "quiero convertir esto en una estructura",
            "quiero convertirlo en una estructura clara",
            "quiero convertir esto en una estructura clara",
            "ordénalo mejor",
            "ordena esto",
            "prepararlo para narrar",
            "prepararla para narrar",
        )
    ):
        return None
    return text


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
