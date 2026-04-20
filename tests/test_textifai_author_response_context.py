from pathlib import Path
import tempfile
import unittest

from textifai.author_response.context import build_response_context
from textifai.editorial_intent.contracts import CandidateTarget, EditorialIntent
from vault.bootstrap import bootstrap_vault
from vault.schema import note_frontmatter


class TextifAIAuthorResponseContextTests(unittest.TestCase):
    def test_build_response_context_falls_back_to_supporting_note_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            (vault_root / "99_Import_Staging" / "mixed").mkdir(parents=True, exist_ok=True)
            (vault_root / "99_Import_Staging" / "mixed" / "sera_profile.md").write_text(
                note_frontmatter(
                    "mixed_note",
                    "✒️ Nombre: Serélyne Thiseriya d’Aelwen",
                    slug="serelyne_thiseriya",
                    character_refs="Sera",
                )
                + "\n\n### Apodo: Sera\n\nSera keeps a hard edge over buried subtext.\n",
                encoding="utf-8",
            )

            context = build_response_context(
                vault_root=vault_root,
                editorial_intent=EditorialIntent(
                    request_type="editorial_revision",
                    confidence=0.8,
                    candidate_targets=[CandidateTarget(target_id="Sera", target_type="character", confidence=0.56)],
                    followup_mode="prefer_candidate_targets",
                ),
                entity_results=[],
            )

            self.assertTrue(context)
            self.assertEqual(context[0]["artifact_id"], "serelyne_thiseriya")
            self.assertIn("fallback_search", context[0]["source"])


if __name__ == "__main__":
    unittest.main()
