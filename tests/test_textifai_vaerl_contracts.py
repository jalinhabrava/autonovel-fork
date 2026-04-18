import unittest

from textifai.vaerl.contracts import (
    EntityCandidate,
    EntityMention,
    EntityResolutionResult,
    RelatedArtifactSuggestion,
    VaultIndexEntry,
)


class TextifAIVaERLContractsTests(unittest.TestCase):
    def test_entity_mention_supports_context_hint(self):
        mention = EntityMention(
            surface_text="esta nota",
            normalized_text="esta_nota",
            mention_kind_hint="note",
            source="contextual_phrase",
            confidence=0.58,
            context_hint="esta nota",
        )
        self.assertEqual(mention.context_hint, "esta nota")

    def test_entity_candidate_supports_path(self):
        candidate = EntityCandidate(
            artifact_id="memory_ritual",
            artifact_type="lore",
            title="Memory Ritual",
            path="/vault/02_World/Lore/memory_ritual.md",
            match_source="title",
            match_reason="exact title match",
            confidence=0.92,
        )
        self.assertTrue(candidate.path.endswith("memory_ritual.md"))

    def test_entity_resolution_result_keeps_related_artifacts_separate(self):
        result = EntityResolutionResult(
            query_text="ritual de memoria",
            mention=EntityMention(
                surface_text="ritual de memoria",
                normalized_text="ritual_de_memoria",
                source="raw_text",
                confidence=0.9,
            ),
            candidate_entities=[
                EntityCandidate(
                    artifact_id="memory_ritual",
                    artifact_type="lore",
                    match_source="alias",
                    match_reason="exact alias match",
                    confidence=0.9,
                )
            ],
            resolved=False,
            resolution_confidence=0.9,
            related_artifacts_suggested=[
                RelatedArtifactSuggestion(
                    artifact_id="magic_costs",
                    artifact_type="decision",
                    relation="linked_canon",
                    confidence=0.72,
                )
            ],
        )
        self.assertEqual(result.candidate_entities[0].artifact_id, "memory_ritual")
        self.assertEqual(result.related_artifacts_suggested[0].artifact_id, "magic_costs")

    def test_vault_index_entry_keeps_light_links_and_backlinks(self):
        entry = VaultIndexEntry(
            artifact_id="memory_ritual",
            artifact_type="lore",
            title="Memory Ritual",
            slug="memory_ritual",
            links=["magic_costs"],
            backlinks=["scene_054_b"],
        )
        self.assertEqual(entry.links, ["magic_costs"])
        self.assertEqual(entry.backlinks, ["scene_054_b"])


if __name__ == "__main__":
    unittest.main()
