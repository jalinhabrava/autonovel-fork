import unittest

from textifai.editorial.contracts import BeatItem, BeatOutline, EditorialStructuringResult, StoryFactItem, StoryFacts
from textifai.followthrough.contracts import (
    FollowThroughResult,
    NarrationRequest,
    ReviewReadyPackage,
    ValidatedStructuringState,
)


class TextifAIFollowThroughContractTests(unittest.TestCase):
    def test_validated_structuring_state_requires_supported_validation_status(self):
        source_result = _make_structuring_result()
        state = ValidatedStructuringState(
            source_result_kind="beat_outline",
            source_structuring_result=source_result,
            validation_status="validated",
            validated_by_user=True,
            ready_for_narration_prep=True,
            ready_for_review_handoff=True,
        )
        self.assertEqual(state.validation_status, "validated")
        with self.assertRaises(ValueError):
            ValidatedStructuringState(
                source_result_kind="beat_outline",
                source_structuring_result=source_result,
                validation_status="invalid_status",
                validated_by_user=True,
            )

    def test_narration_request_enforces_closed_catalogs(self):
        source_result = _make_structuring_result()
        state = ValidatedStructuringState(
            source_result_kind="beat_outline",
            source_structuring_result=source_result,
            validation_status="validated",
            validated_by_user=True,
            ready_for_narration_prep=True,
        )
        request = NarrationRequest(
            source_kind="beat_outline",
            validated_structuring_state=state,
            target_language="ja",
            voice_mode="inherit_project_voice",
            continuity_scope="scene_only",
            canon_mode="validated_only",
        )
        self.assertEqual(request.voice_mode, "inherit_project_voice")
        with self.assertRaises(ValueError):
            NarrationRequest(
                source_kind="beat_outline",
                validated_structuring_state=state,
                target_language="ja",
                voice_mode="too_open",
                continuity_scope="scene_only",
                canon_mode="validated_only",
            )

    def test_review_ready_package_enforces_review_focus_catalog(self):
        source_result = _make_structuring_result()
        state = ValidatedStructuringState(
            source_result_kind="beat_outline",
            source_structuring_result=source_result,
            validation_status="validated_with_notes",
            validated_by_user=True,
            validation_notes=["needs tone pass"],
            validated_story_facts=source_result.story_facts,
            validated_beat_outline=source_result.beat_outline,
            validated_revision_intent=source_result.revision_intent,
            ready_for_narration_prep=True,
            ready_for_review_handoff=True,
        )
        package = ReviewReadyPackage(
            source_kind="beat_outline",
            validated_structuring_state=state,
            narration_prep=None,
            review_focus=["structure", "tone"],
            preserve_constraints=["preserve_validated_canon"],
            related_artifacts=["lore:memory_ritual"],
            open_questions=["Does this preserve the core conflict?"],
        )
        self.assertIn("tone", package.review_focus)
        with self.assertRaises(ValueError):
            ReviewReadyPackage(
                source_kind="beat_outline",
                validated_structuring_state=state,
                narration_prep=None,
                review_focus=["too_broad"],
            )

    def test_followthrough_result_requires_closed_next_step(self):
        source_result = _make_structuring_result()
        state = ValidatedStructuringState(
            source_result_kind="beat_outline",
            source_structuring_result=source_result,
            validation_status="validated",
            validated_by_user=True,
            ready_for_narration_prep=True,
        )
        result = FollowThroughResult(
            validated_structuring_state=state,
            narration_request=None,
            narration_prep=None,
            review_ready_package=None,
            next_recommended_step="prepare_narration",
            ready_for_user_confirmation=True,
        )
        self.assertEqual(result.next_recommended_step, "prepare_narration")
        with self.assertRaises(ValueError):
            FollowThroughResult(
                validated_structuring_state=state,
                narration_request=None,
                narration_prep=None,
                review_ready_package=None,
                next_recommended_step="do_something_else",
                ready_for_user_confirmation=True,
            )


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
