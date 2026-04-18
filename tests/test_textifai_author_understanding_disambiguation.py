import unittest

from textifai.author_understanding.disambiguation import disambiguate_targets
from textifai.editorial_intent.contracts import CandidateTarget


class TextifAIAuthorUnderstandingDisambiguationTests(unittest.TestCase):
    def test_disambiguation_prefers_single_clear_target(self):
        result = disambiguate_targets(
            [
                CandidateTarget(target_id="memory_ritual", target_type="lore", confidence=0.94),
                CandidateTarget(target_id="ritual_notes", target_type="lore", confidence=0.6),
            ]
        )
        self.assertFalse(result.requires_user_confirmation)
        self.assertIsNotNone(result.preferred_target)
        self.assertEqual(result.preferred_target.target_id, "memory_ritual")

    def test_disambiguation_requires_confirmation_for_competing_targets(self):
        result = disambiguate_targets(
            [
                CandidateTarget(target_id="ritual_notes", target_type="lore", confidence=0.84),
                CandidateTarget(target_id="memory_ritual", target_type="lore", confidence=0.81),
            ]
        )
        self.assertTrue(result.requires_user_confirmation)
        self.assertIsNone(result.preferred_target)


if __name__ == "__main__":
    unittest.main()
