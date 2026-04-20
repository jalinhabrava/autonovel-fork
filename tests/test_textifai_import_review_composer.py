from pathlib import Path
import tempfile
import unittest

import json

from textifai.import_review.composer import _sanitize_aliases, _select_candidate_drafts, discover_primary_candidates
from textifai.import_review.staging_loader import load_staging_import_bundle
from vault.bootstrap import bootstrap_vault
from vault.notes import write_or_update_note
from vault.schema import IMPORT_STAGING_DIRS


class TextifAIImportReviewComposerTests(unittest.TestCase):
    def test_discover_primary_candidates_finds_character_and_place_subjects(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            staging_root = vault_root / IMPORT_STAGING_DIRS["root"]
            manifests = staging_root / "_manifests"
            manifests.mkdir(parents=True, exist_ok=True)

            sera_path = write_or_update_note(
                staging_root,
                note_type="lore",
                slug="sera_raw",
                title="✒️ Nombre: Serélyne Thiseriya d’Aelwen",
                body="### Apodo: Sera\n### Lugar: Thiseia\n",
                status="pending_revision",
                metadata={
                    "canonical_subject": "✒️ Nombre: Serélyne Thiseriya d’Aelwen",
                    "entities": "Serélyne Thiseriya d’Aelwen,Sera,Thiseia",
                    "topics": "sera,voz",
                    "artifact_stage": "candidate_artifact",
                    "semantic_class": "mixed_material",
                },
            )
            veredyn_path = write_or_update_note(
                staging_root,
                note_type="lore",
                slug="veredyn_raw",
                title="Ducado de Veredyn",
                body="Veredyn aparece como lugar y entidad política.\n",
                status="pending_revision",
                metadata={
                    "canonical_subject": "Ducado de Veredyn",
                    "entities": "Veredyn,Ducado de Veredyn,Thiseia",
                    "world_terms": "Veredyn,Thiseia",
                    "artifact_stage": "candidate_artifact",
                    "semantic_class": "world_entity",
                },
            )
            manifest = {
                "plan": {
                    "drafts": [
                        {
                            "draft_id": "sera_draft",
                            "target_path": str(sera_path),
                            "artifact_type": "lore",
                            "slug": "sera_raw",
                            "provenance": {
                                "source_id": "source1",
                                "source_path": "/tmp/source1.md",
                                "source_checksum": "abc",
                                "source_format": "md",
                                "extraction_mode": "native_text",
                                "extraction_confidence": 0.9,
                                "structural_confidence": 0.9,
                                "fragment_ids": ["frag1"],
                                "char_ranges": [{"start": 0, "end": 10}],
                                "import_mode": "literal_copy",
                                "llm_assisted": True,
                                "warnings": [],
                                "loss_risk_flags": [],
                                "notes": [],
                            },
                        },
                        {
                            "draft_id": "veredyn_draft",
                            "target_path": str(veredyn_path),
                            "artifact_type": "lore",
                            "slug": "veredyn_raw",
                            "provenance": {
                                "source_id": "source2",
                                "source_path": "/tmp/source2.md",
                                "source_checksum": "def",
                                "source_format": "md",
                                "extraction_mode": "native_text",
                                "extraction_confidence": 0.9,
                                "structural_confidence": 0.9,
                                "fragment_ids": ["frag2"],
                                "char_ranges": [{"start": 0, "end": 10}],
                                "import_mode": "literal_copy",
                                "llm_assisted": True,
                                "warnings": [],
                                "loss_risk_flags": [],
                                "notes": [],
                            },
                        },
                    ],
                    "coverage_summary": {},
                },
                "warnings": [],
            }
            (manifests / "test-plan.json").write_text(__import__("json").dumps(manifest), encoding="utf-8")

            bundle = load_staging_import_bundle(vault_root, plan_id="test-plan")
            candidates = discover_primary_candidates(bundle, max_candidates=10)
            subject_keys = {candidate.subject_key for candidate in candidates}

            self.assertIn("serélyne_thiseriya_daelwen", subject_keys)
            self.assertIn("ducado_de_veredyn", subject_keys)

    def test_select_candidate_drafts_prefers_direct_subject_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp) / "Vault"
            bootstrap_vault(vault_root, title="Test Project")
            staging_root = vault_root / IMPORT_STAGING_DIRS["root"]
            manifests = staging_root / "_manifests"
            manifests.mkdir(parents=True, exist_ok=True)

            direct_path = write_or_update_note(
                staging_root,
                note_type="character",
                slug="sera_profile",
                title="Sera",
                body="Sera profile.\n",
                status="pending_revision",
                metadata={
                    "canonical_subject": "Sera",
                    "character_refs": "Sera",
                    "artifact_stage": "candidate_artifact",
                    "semantic_class": "character_profile",
                },
            )
            indirect_path = write_or_update_note(
                staging_root,
                note_type="character",
                slug="liora_relation",
                title="Liora",
                body="Liora talks about Sera.\n",
                status="pending_revision",
                metadata={
                    "canonical_subject": "Liora",
                    "character_refs": "Sera,Liora",
                    "artifact_stage": "candidate_artifact",
                    "semantic_class": "character_profile",
                },
            )
            manifest = {
                "plan": {
                    "drafts": [
                        {"draft_id": "sera_profile", "target_path": str(direct_path), "artifact_type": "character"},
                        {"draft_id": "liora_relation", "target_path": str(indirect_path), "artifact_type": "character"},
                    ],
                    "coverage_summary": {},
                },
                "warnings": [],
            }
            (manifests / "test-plan.json").write_text(json.dumps(manifest), encoding="utf-8")

            bundle = load_staging_import_bundle(vault_root, plan_id="test-plan")
            candidate = next(item for item in discover_primary_candidates(bundle, max_candidates=10) if item.display_name == "Sera")
            drafts = [draft for draft in bundle.drafts if draft.draft_id in set(candidate.draft_ids)]
            selected = _select_candidate_drafts(candidate, drafts)

            self.assertEqual(selected[0].draft_id, "sera_profile")

    def test_sanitize_aliases_drops_phrase_like_noise(self):
        cleaned = _sanitize_aliases(
            [
                "Sera",
                "Princesa de Thiseia",
                "Vínculo entre Nushi y humanos",
                "Serélyne",
                "Liora",
            ],
            title="Sera",
            canonical_subject="Sera",
            related_subjects=["Thiseia"],
            blocked_subject_keys={"liora"},
        )

        self.assertEqual(cleaned, ["Princesa de Thiseia", "Serélyne"])


if __name__ == "__main__":
    unittest.main()
