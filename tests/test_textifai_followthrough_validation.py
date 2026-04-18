import unittest

from textifai.editorial.contracts import EditorialStructuringResult
from textifai.editorial.contracts import BeatItem, BeatOutline, StoryFactItem, StoryFacts
from textifai.followthrough.contracts import FollowThroughResult, ValidatedStructuringState
from textifai.followthrough.validation import build_followthrough_result, build_validated_structuring_state, extract_followthrough_state


class TextifAIFollowThroughValidationTests(unittest.TestCase):
    def test_validation_rejects_empty_structuring_material(self):
        empty_result = EditorialStructuringResult(
            entity_resolution_results=[],
            story_facts=None,
            beat_outline=None,
            revision_intent=None,
            narration_prep=None,
            result_kind="mixed",
            ready_for_validation=False,
        )
        state = build_validated_structuring_state(
            empty_result,
            validated_by_user=True,
        )
        self.assertEqual(state.validation_status, "insufficient_structure")
        self.assertFalse(state.ready_for_narration_prep)
        self.assertFalse(state.ready_for_review_handoff)

    def test_validation_marks_structures_as_validated_when_user_confirms(self):
        source_result = _make_structuring_result()
        state = build_validated_structuring_state(
            source_result,
            validated_by_user=True,
            validation_notes=["tone is fine"],
        )
        self.assertEqual(state.validation_status, "validated_with_notes")
        self.assertTrue(state.ready_for_narration_prep)
        self.assertTrue(state.ready_for_review_handoff)
        self.assertEqual(state.validated_story_facts, source_result.story_facts)

    def test_followthrough_result_roundtrips_from_session_payload(self):
        source_result = _make_structuring_result()
        state = build_validated_structuring_state(
            source_result,
            validated_by_user=True,
        )
        result = build_followthrough_result(
            validated_structuring_state=state,
            narration_request=None,
            narration_prep=None,
            review_ready_package=None,
            next_recommended_step="prepare_narration",
            ready_for_user_confirmation=True,
        )
        remembered = {
            "type": "followthrough",
            "data": {
                "validated_structuring_state": _state_to_dict(state),
                "narration_request": None,
                "narration_prep": None,
                "review_ready_package": None,
                "next_recommended_step": result.next_recommended_step,
                "ready_for_user_confirmation": True,
            },
        }
        extracted = extract_followthrough_state(remembered)
        self.assertIsInstance(extracted, ValidatedStructuringState)
        self.assertEqual(extracted.validation_status, "validated")
        self.assertTrue(extracted.ready_for_narration_prep)


def _state_to_dict(state: ValidatedStructuringState) -> dict:
    source = state.source_structuring_result
    return {
        "source_result_kind": state.source_result_kind,
        "source_structuring_result": {
            "entity_resolution_results": [],
            "story_facts": _story_facts_to_dict(source.story_facts),
            "beat_outline": _beat_outline_to_dict(source.beat_outline),
            "revision_intent": _revision_intent_to_dict(source.revision_intent),
            "narration_prep": None,
            "result_kind": source.result_kind,
            "ready_for_validation": source.ready_for_validation,
        },
        "validation_status": state.validation_status,
        "validated_by_user": state.validated_by_user,
        "validation_notes": list(state.validation_notes),
        "validated_story_facts": _story_facts_to_dict(state.validated_story_facts),
        "validated_beat_outline": _beat_outline_to_dict(state.validated_beat_outline),
        "validated_revision_intent": _revision_intent_to_dict(state.validated_revision_intent),
        "ready_for_narration_prep": state.ready_for_narration_prep,
        "ready_for_review_handoff": state.ready_for_review_handoff,
    }


def _story_facts_to_dict(value):
    if value is None:
        return None
    return {
        "source_text": value.source_text,
        "language": value.language,
        "characters_involved": list(value.characters_involved),
        "locations_involved": list(value.locations_involved),
        "objects_involved": list(value.objects_involved),
        "premise": value.premise,
        "core_conflict": value.core_conflict,
        "goals": list(value.goals),
        "constraints": list(value.constraints),
        "canon_constraints": list(value.canon_constraints),
        "explicit_facts": [dict(text=item.text, fact_kind=item.fact_kind, source=item.source) for item in value.explicit_facts],
        "inferred_facts": [dict(text=item.text, fact_kind=item.fact_kind, source=item.source) for item in value.inferred_facts],
        "open_questions": list(value.open_questions),
    }


def _beat_outline_to_dict(value):
    if value is None:
        return None
    return {
        "source_kind": value.source_kind,
        "title": value.title,
        "beats": [
            {
                "index": item.index,
                "summary": item.summary,
                "purpose": item.purpose,
                "characters": list(item.characters),
                "tension_level": item.tension_level,
            }
            for item in value.beats
        ],
        "emotional_arc": list(value.emotional_arc),
        "target_language": value.target_language,
        "continuity_notes": list(value.continuity_notes),
        "canon_checks": list(value.canon_checks),
    }


def _revision_intent_to_dict(value):
    if value is None:
        return None
    return {
        "source_text": value.source_text,
        "target_scope": value.target_scope,
        "issue_types": list(value.issue_types),
        "desired_changes": list(value.desired_changes),
        "must_preserve": list(value.must_preserve),
        "priority": value.priority,
        "target_hint": value.target_hint,
    }


def _make_structuring_result() -> EditorialStructuringResult:
    facts = StoryFacts(
        source_text="Sera llega tarde al puerto.",
        language="es",
        characters_involved=["sera"],
        locations_involved=[],
        objects_involved=[],
        premise="Sera llega tarde al puerto.",
        core_conflict=None,
        goals=["llegar al puerto"],
        constraints=[],
        canon_constraints=["respect_validated_canon"],
        explicit_facts=[StoryFactItem(text="Sera llega tarde al puerto.", fact_kind="event", source="explicit_input")],
        inferred_facts=[],
        open_questions=[],
    )
    outline = BeatOutline(
        source_kind="story_facts",
        title="Sera llega tarde al puerto.",
        beats=[
            BeatItem(
                index=1,
                summary="Sera llega tarde al puerto.",
                purpose="advance_scene",
                characters=["sera"],
                tension_level="low",
            )
        ],
        emotional_arc=["low"],
        target_language="ja",
        continuity_notes=[],
        canon_checks=["respect_validated_canon"],
    )
    return EditorialStructuringResult(
        entity_resolution_results=[],
        story_facts=facts,
        beat_outline=outline,
        revision_intent=None,
        narration_prep=None,
        result_kind="beat_outline",
        ready_for_validation=True,
    )


if __name__ == "__main__":
    unittest.main()
