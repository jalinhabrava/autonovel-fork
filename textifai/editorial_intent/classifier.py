from __future__ import annotations

from dataclasses import asdict

from textifai.author_understanding.contracts import AuthorIntentInterpretation
from textifai.editorial_intent.contracts import CandidateTarget, EditorialIntent
from textifai.vaerl.contracts import EntityHint


def classify_editorial_intent(
    *,
    raw_text: str,
    recognized_intent_name: str,
    entity_results,
    narrative_signals,
    state=None,
    author_understanding: AuthorIntentInterpretation | None = None,
) -> EditorialIntent | None:
    candidate_targets = _candidate_targets_from_entities(entity_results)
    if author_understanding and author_understanding.disambiguation is not None:
        candidate_targets = _dedupe_targets(candidate_targets + list(author_understanding.disambiguation.candidate_targets))

    multi_target = _is_multi_target_request(candidate_targets, author_understanding, narrative_signals, state, recognized_intent_name)
    resolved_target = _resolve_target(candidate_targets, author_understanding)
    preserve_constraints, editorial_goals = _editorial_guidance(narrative_signals, author_understanding)
    if author_understanding is not None:
        preserve_constraints = _dedupe(preserve_constraints + _normalize_signal_list(author_understanding.preserve_signals))
        author_goals = [goal for goal in _normalize_signal_list(author_understanding.author_goal_signals) if goal != "mixed_request"]
        author_changes = [goal for goal in _normalize_signal_list(author_understanding.change_signals) if goal != "mixed_request"]
        editorial_goals = _dedupe(editorial_goals + author_goals + author_changes)

    followup_mode = _followup_mode(candidate_targets, state, recognized_intent_name, author_understanding)
    author_request_type = _author_understanding_request_type(author_understanding)
    entity_hints = _entity_hints_from_author_understanding(author_understanding)
    semantic_basis = _semantic_basis(author_understanding, recognized_intent_name, narrative_signals)
    narrative_source_text = _narrative_source_text(raw_text, author_understanding, author_request_type)
    use_fallback = author_request_type is None

    if author_request_type == "validation_request" and recognized_intent_name == "unknown" and not candidate_targets:
        return None

    if recognized_intent_name in {"inspect_scene", "inspect_chapter"} and len(candidate_targets) <= 1 and not (author_understanding is not None and author_understanding.has_mixed_request):
        return None
    if recognized_intent_name == "consistency_check" and len(candidate_targets) <= 1:
        return None
    if recognized_intent_name == "consistency_check" and len(candidate_targets) >= 2:
        return _build_intent(
            request_type="mixed_editorial_request",
            confidence=max(0.78, author_understanding.confidence if author_understanding is not None else 0.0),
            semantic_basis=semantic_basis,
            target_scope=_target_scope(candidate_targets, state),
            resolved_target=resolved_target,
            multi_target=multi_target,
            candidate_targets=candidate_targets,
            entity_hints=entity_hints,
            followup_mode=followup_mode,
            preserve_constraints=preserve_constraints,
            editorial_goals=_dedupe(editorial_goals + ["structure_scene"]),
            narrative_source_text=narrative_source_text,
            author_understanding=author_understanding,
        )

    if author_request_type == "validation_request" or (use_fallback and recognized_intent_name == "validate_structure"):
        validation_followup_mode = followup_mode
        if validation_followup_mode == "none":
            validation_followup_mode = "reuse_recent_target" if state and state.last_target_id else "require_clarification"
        return _build_intent(
            request_type="validation_request",
            confidence=0.9,
            semantic_basis=semantic_basis,
            target_scope=_target_scope(candidate_targets, state),
            resolved_target=resolved_target,
            multi_target=multi_target,
            candidate_targets=candidate_targets,
            entity_hints=entity_hints,
            followup_mode=validation_followup_mode,
            preserve_constraints=preserve_constraints,
            editorial_goals=_dedupe(editorial_goals + ["structure_scene"]),
            narrative_source_text=None,
            followthrough_action="validate_structure",
            author_understanding=author_understanding,
        )

    if author_request_type == "narration_preparation" or (use_fallback and recognized_intent_name == "prepare_narration"):
        request_type = "narration_preparation"
        if author_understanding is not None and author_understanding.has_mixed_request:
            request_type = "mixed_editorial_request"
        elif _is_structured_content_request(candidate_targets, narrative_signals, state):
            request_type = "mixed_editorial_request"
        return _build_intent(
            request_type=request_type,
            confidence=0.82,
            semantic_basis=semantic_basis,
            target_scope=_target_scope(candidate_targets, state),
            resolved_target=resolved_target,
            multi_target=multi_target,
            candidate_targets=candidate_targets,
            entity_hints=entity_hints,
            followup_mode=followup_mode,
            preserve_constraints=preserve_constraints,
            editorial_goals=_dedupe(editorial_goals + ["prepare_for_narration"]),
            narrative_source_text=narrative_source_text,
            followthrough_action="prepare_narration" if request_type == "narration_preparation" else None,
            author_understanding=author_understanding,
        )

    if author_request_type == "review_handoff" or (use_fallback and recognized_intent_name == "prepare_review"):
        return _build_intent(
            request_type="review_handoff",
            confidence=0.84,
            semantic_basis=semantic_basis,
            target_scope=_target_scope(candidate_targets, state),
            resolved_target=resolved_target,
            multi_target=multi_target,
            candidate_targets=candidate_targets,
            entity_hints=entity_hints,
            followup_mode=followup_mode,
            preserve_constraints=preserve_constraints,
            editorial_goals=editorial_goals,
            narrative_source_text=None,
            followthrough_action="prepare_review",
            author_understanding=author_understanding,
        )

    if author_request_type == "structured_followup" or (
        use_fallback and _followup_is_structured(candidate_targets, state, recognized_intent_name, author_understanding)
    ):
        structured_followup_mode = followup_mode if followup_mode != "none" else "require_clarification"
        return _build_intent(
            request_type="structured_followup",
            confidence=0.8,
            semantic_basis=semantic_basis,
            target_scope=_target_scope(candidate_targets, state),
            resolved_target=resolved_target,
            multi_target=multi_target,
            candidate_targets=candidate_targets,
            entity_hints=entity_hints,
            followup_mode=structured_followup_mode,
            preserve_constraints=preserve_constraints,
            editorial_goals=editorial_goals,
            narrative_source_text=None,
            followthrough_action="resume_followup",
            author_understanding=author_understanding,
        )

    if (
        author_request_type == "contextual_followup"
        or (
            use_fallback
            and recognized_intent_name not in {"inspect_scene", "inspect_chapter", "consistency_check"}
            and followup_mode in {"reuse_recent_target", "prefer_candidate_targets"}
            and not _is_structured_content_request(candidate_targets, narrative_signals, state)
        )
    ):
        return _build_intent(
            request_type="contextual_followup",
            confidence=0.74,
            semantic_basis=semantic_basis,
            target_scope=_target_scope(candidate_targets, state),
            resolved_target=resolved_target,
            multi_target=multi_target,
            candidate_targets=candidate_targets,
            entity_hints=entity_hints,
            followup_mode=followup_mode,
            preserve_constraints=preserve_constraints,
            editorial_goals=editorial_goals,
            narrative_source_text=None,
            author_understanding=author_understanding,
        )

    if author_request_type == "mixed_request" or (
        use_fallback and author_understanding is not None and author_understanding.has_mixed_request and len(candidate_targets) >= 2
    ):
        return _build_intent(
            request_type="mixed_editorial_request",
            confidence=0.81,
            semantic_basis=semantic_basis,
            target_scope=_target_scope(candidate_targets, state),
            resolved_target=resolved_target,
            multi_target=multi_target,
            candidate_targets=candidate_targets,
            entity_hints=entity_hints,
            followup_mode=followup_mode,
            preserve_constraints=preserve_constraints,
            editorial_goals=editorial_goals,
            narrative_source_text=narrative_source_text,
            author_understanding=author_understanding,
        )

    if author_request_type == "structuring_request" or (
        use_fallback
        and recognized_intent_name not in {"inspect_scene", "inspect_chapter", "consistency_check"}
        and _is_structured_content_request(candidate_targets, narrative_signals, state)
    ):
        return _build_intent(
            request_type="structuring_request",
            confidence=0.8,
            semantic_basis=semantic_basis,
            target_scope=_target_scope(candidate_targets, state),
            resolved_target=resolved_target,
            multi_target=multi_target,
            candidate_targets=candidate_targets,
            entity_hints=entity_hints,
            followup_mode=followup_mode,
            preserve_constraints=preserve_constraints,
            editorial_goals=_dedupe(editorial_goals + ["structure_scene"]),
            narrative_source_text=narrative_source_text,
            author_understanding=author_understanding,
        )

    if author_request_type == "editorial_revision" or (
        use_fallback
        and recognized_intent_name not in {"inspect_scene", "inspect_chapter", "consistency_check"}
        and narrative_signals is not None
        and bool(narrative_signals.issue_types)
    ):
        return _build_intent(
            request_type="editorial_revision",
            confidence=0.79,
            semantic_basis=semantic_basis,
            target_scope=_target_scope(candidate_targets, state),
            resolved_target=resolved_target,
            multi_target=multi_target,
            candidate_targets=candidate_targets,
            entity_hints=entity_hints,
            followup_mode=followup_mode,
            preserve_constraints=preserve_constraints,
            editorial_goals=editorial_goals,
            narrative_source_text=None,
            author_understanding=author_understanding,
        )

    if author_request_type == "narrative_facts" or (
        use_fallback
        and recognized_intent_name == "editorial_structuring"
        and _is_structured_content_request(candidate_targets, narrative_signals, state)
    ):
        return _build_intent(
            request_type="narrative_facts",
            confidence=0.72,
            semantic_basis=semantic_basis,
            target_scope=_target_scope(candidate_targets, state),
            resolved_target=resolved_target,
            multi_target=multi_target,
            candidate_targets=candidate_targets,
            entity_hints=entity_hints,
            followup_mode=followup_mode,
            preserve_constraints=preserve_constraints,
            editorial_goals=_dedupe(editorial_goals + ["extract_story_facts"]),
            narrative_source_text=narrative_source_text or raw_text,
            author_understanding=author_understanding,
        )

    return None


def _build_intent(
    *,
    request_type: str,
    confidence: float,
    semantic_basis: str,
    target_scope: str | None,
    resolved_target: CandidateTarget | None,
    multi_target: bool,
    candidate_targets: list[CandidateTarget],
    entity_hints: list[EntityHint],
    followup_mode: str,
    preserve_constraints: list[str],
    editorial_goals: list[str],
    narrative_source_text: str | None,
    author_understanding: AuthorIntentInterpretation | None,
    followthrough_action: str | None = None,
) -> EditorialIntent:
    metadata = {
        "narrative_source_text": narrative_source_text,
        "multi_target": multi_target,
        "followthrough_action": followthrough_action,
        "author_understanding": asdict(author_understanding) if author_understanding is not None else None,
    }
    return EditorialIntent(
        request_type=request_type,
        confidence=confidence,
        semantic_basis=semantic_basis,
        target_scope=target_scope,
        resolved_target_type=None if multi_target else (resolved_target.target_type if resolved_target else None),
        resolved_target_id=None if multi_target else (resolved_target.target_id if resolved_target else None),
        candidate_targets=candidate_targets,
        entity_hints=entity_hints,
        followup_mode=followup_mode,
        preserve_constraints=preserve_constraints,
        editorial_goals=editorial_goals,
        metadata=metadata,
    )


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


def _is_multi_target_request(
    candidate_targets: list[CandidateTarget],
    author_understanding: AuthorIntentInterpretation | None,
    narrative_signals,
    state,
    recognized_intent_name: str,
) -> bool:
    if author_understanding is not None and author_understanding.has_mixed_request and len(candidate_targets) >= 2:
        return True
    if len(candidate_targets) >= 2:
        return True
    if narrative_signals is not None and len(getattr(narrative_signals, "mentioned_entities", []) or []) >= 2:
        return True
    if recognized_intent_name in {"editorial_structuring", "structured_followup"} and state is not None and state.last_target_id and len(candidate_targets) >= 1:
        return True
    return False


def _followup_mode(
    candidate_targets: list[CandidateTarget],
    state,
    recognized_intent_name: str,
    author_understanding: AuthorIntentInterpretation | None = None,
) -> str:
    if author_understanding is not None and author_understanding.disambiguation is not None:
        if author_understanding.disambiguation.requires_user_confirmation and not author_understanding.disambiguation.preferred_target:
            return "require_clarification"
        if author_understanding.disambiguation.preferred_target is not None:
            return "prefer_candidate_targets"
    if candidate_targets and candidate_targets[0].confidence >= 0.75:
        return "prefer_candidate_targets"
    if state and state.last_target_id and recognized_intent_name in {"unknown", "validate_artifact", "reject_artifact"}:
        return "reuse_recent_target"
    return "none"


def _followup_is_structured(
    candidate_targets: list[CandidateTarget],
    state,
    recognized_intent_name: str,
    author_understanding: AuthorIntentInterpretation | None,
) -> bool:
    if author_understanding is not None and author_understanding.has_mixed_request:
        return True
    if len(candidate_targets) >= 2:
        return True
    if recognized_intent_name in {"structured_followup", "editorial_structuring"} and state and state.last_target_id:
        return True
    return False


def _is_structured_content_request(
    candidate_targets: list[CandidateTarget],
    narrative_signals,
    state,
) -> bool:
    if narrative_signals is not None and bool(getattr(narrative_signals, "issue_types", []) or getattr(narrative_signals, "mentioned_entities", [])):
        return True
    if state and state.last_target_id and len(candidate_targets) >= 2:
        return True
    return False


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


def _semantic_basis(author_understanding: AuthorIntentInterpretation | None, recognized_intent_name: str, narrative_signals) -> str:
    if author_understanding is not None:
        return "author_understanding_validated"
    if narrative_signals is not None and bool(getattr(narrative_signals, "issue_types", [])):
        return "narrative_signals"
    if recognized_intent_name and recognized_intent_name != "unknown":
        return "recognized_intent"
    return "surface_fallback"


def _narrative_source_text(
    raw_text: str,
    author_understanding: AuthorIntentInterpretation | None,
    author_request_type: str | None,
) -> str | None:
    if author_understanding is not None:
        if author_understanding.narrative_content_text is not None:
            return author_understanding.narrative_content_text
        if author_understanding.meta_instruction_text is not None and not author_understanding.narrative_content_text:
            return None
    if author_request_type in {"narrative_facts", "structuring_request", "mixed_request"}:
        return raw_text.strip() or None
    return None


def _entity_hints_from_author_understanding(author_understanding: AuthorIntentInterpretation | None) -> list[EntityHint]:
    if author_understanding is None:
        return []
    hints = list(author_understanding.entity_hints)
    if hints:
        return _dedupe_entity_hints(hints)
    if author_understanding.disambiguation is None:
        return []
    return _dedupe_entity_hints(
        [
            EntityHint(
                hint_text=f"{target.target_type}:{target.target_id}",
                normalized_hint=target.target_id,
                hint_kind="semantic_target",
                hint_source="author_understanding",
                confidence=target.confidence,
                supported_by_author_understanding=True,
                candidate_target_id=target.target_id,
                candidate_target_type=target.target_type,
            )
            for target in author_understanding.disambiguation.candidate_targets
        ]
    )


def _dedupe_entity_hints(hints: list[EntityHint]) -> list[EntityHint]:
    seen: dict[tuple[str, str | None, str | None], EntityHint] = {}
    for hint in hints:
        key = (hint.normalized_hint, hint.candidate_target_id, hint.candidate_target_type)
        if key not in seen or hint.confidence > seen[key].confidence:
            seen[key] = hint
    return sorted(seen.values(), key=lambda item: (item.confidence, item.hint_kind, item.normalized_hint), reverse=True)


def _normalize_signal_list(values: list[str]) -> list[str]:
    return _dedupe([str(value).strip() for value in values if str(value).strip()])


def _editorial_guidance(narrative_signals, author_understanding: AuthorIntentInterpretation | None) -> tuple[list[str], list[str]]:
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
    if "clarity_issue" in issue_types or "continuity_issue" in issue_types:
        goals.append("clarify_motivation")
    if author_understanding is not None:
        goals = _dedupe(goals + _normalize_signal_list(author_understanding.author_goal_signals))
        preserve_constraints = _dedupe(preserve_constraints + _normalize_signal_list(author_understanding.preserve_signals))
    return (_dedupe(preserve_constraints), _dedupe(goals))


def _target_scope(candidate_targets: list[CandidateTarget], state) -> str | None:
    if candidate_targets:
        return candidate_targets[0].target_type
    if state and state.last_target_type:
        return state.last_target_type
    return None


def _has_recent_anchor(state) -> bool:
    return bool(state and state.last_target_id)


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
