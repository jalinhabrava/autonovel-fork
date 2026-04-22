from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textifai.bootstrap.source_reader import build_source_document_inventory
from textifai.obsidian.json_import import import_json_to_vault
from textifai.import_review.structured_bootstrap_v1 import (
    NovelBootstrapV1Config,
    _extract_title_entity_hints,
    _promote_recurring_chapter_entities,
    _promote_title_hint_entities,
    _stabilize_character_entities_with_title_hints,
    assemble_obsidian_import,
    _build_global_normalization_batches,
    build_canonical_entity_map,
    run_structured_bootstrap_v1,
)


class _StructuredBootstrapFakeProvider:
    def generate(self, request):
        if request.task == "bootstrap_global_normalization":
            return type(
                "_Response",
                (),
                {
                    "text": json.dumps(
                        {
                            "work": {
                                "title": "Test Novel",
                                "language": "es",
                                "normalization_notes": ["global pass ok"],
                            },
                            "entities": [
                                {
                                    "canonical_name": "Sera",
                                    "entity_kind": "character",
                                    "preferred_slug": "sera",
                                    "aliases": ["Serelyne"],
                                    "summary": "Princesa con una magia inestable.",
                                    "key_facts": ["Huye del castillo."],
                                    "relationships": [],
                                    "chapter_refs": ["ch_001"],
                                    "source_mentions": ["Sera", "Serelyne"],
                                    "confidence": 0.95,
                                    "review_state": "canonical",
                                },
                                {
                                    "canonical_name": "Thiseia",
                                    "entity_kind": "place",
                                    "preferred_slug": "thiseia",
                                    "aliases": [],
                                    "summary": "Reino relevante para la historia.",
                                    "key_facts": ["Contiene el castillo real."],
                                    "relationships": [],
                                    "chapter_refs": ["ch_001", "ch_002"],
                                    "source_mentions": ["Thiseia"],
                                    "confidence": 0.91,
                                    "review_state": "canonical",
                                },
                            ],
                            "merge_plan": [
                                {
                                    "canonical_name": "Sera",
                                    "merged_surfaces": ["Sera", "Serelyne"],
                                    "reason": "same character",
                                    "confidence": 0.95,
                                }
                            ],
                        },
                        ensure_ascii=False,
                    )
                },
            )()
        chapter_id = "ch_001"
        if "CHAPTER_ID:" in request.messages[0].content:
            for line in request.messages[0].content.splitlines():
                if line.startswith("CHAPTER_ID:"):
                    chapter_id = line.split(":", 1)[1].strip()
                    break
        return type(
            "_Response",
            (),
            {
                "text": json.dumps(
                    {
                        "work": {"title": "Test Novel", "language": "es"},
                        "chapters": [
                            {
                                "chapter_id": chapter_id,
                                "chapter_title_original": f"{chapter_id} title",
                                "chapter_title_canonical": f"{chapter_id} title",
                                "sequence_index": 1 if chapter_id == "ch_001" else 2,
                                "chapter_summary": "Sera actúa en Thiseia.",
                                "chapter_text_markdown": "Sera viaja por Thiseia.",
                                "characters": [
                                    {
                                        "surface": "Sera",
                                        "canonical": "Sera",
                                        "facts": ["Aparece activamente en el capítulo."],
                                        "confidence": 0.95,
                                    }
                                ],
                                "places": [
                                    {
                                        "surface": "Thiseia",
                                        "canonical": "Thiseia",
                                        "facts": ["Es el marco del capítulo."],
                                        "confidence": 0.9,
                                    }
                                ],
                                "concepts": [],
                                "events": [],
                                "relations": [],
                                "unresolved_mentions": [],
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
            },
        )()


class StructuredBootstrapV1Tests(unittest.TestCase):
    def test_build_canonical_entity_map_reduces_global_payload(self):
        canonical_map = build_canonical_entity_map(
            {
                "entities": [
                    {
                        "canonical_name": "Sera",
                        "entity_kind": "character",
                        "aliases": ["Serelyne"],
                        "summary": "Princesa",
                        "key_facts": ["Uno", "Dos", "Tres", "Cuatro", "Cinco"],
                        "review_state": "canonical",
                        "confidence": 0.9,
                    }
                ]
            }
        )
        self.assertEqual(canonical_map[0]["canonical_name"], "Sera")
        self.assertEqual(len(canonical_map[0]["key_facts"]), 4)

    def test_assemble_obsidian_import_enriches_chapter_refs(self):
        assembled = assemble_obsidian_import(
            global_data={
                "work": {"title": "Test", "language": "es"},
                "entities": [
                    {
                        "canonical_name": "Sera",
                        "entity_kind": "character",
                        "summary": "Princesa",
                        "aliases": [],
                        "key_facts": [],
                        "relationships": [],
                        "chapter_refs": [],
                        "source_mentions": [],
                        "confidence": 0.9,
                        "review_state": "canonical",
                    }
                ],
            },
            chapter_outputs=[
                {
                    "chapter_id": "ch_001",
                    "sequence_index": 1,
                    "characters": [{"surface": "Sera", "canonical": "Sera", "facts": [], "confidence": 0.9}],
                    "places": [],
                    "concepts": [],
                    "relations": [],
                }
            ],
        )
        self.assertEqual(assembled["entities"][0]["chapter_refs"], ["ch_001"])
        self.assertEqual(assembled["entities"][0]["source_mentions"], ["Sera"])

    def test_recurring_chapter_entities_can_be_promoted_when_global_canon_misses_them(self):
        promoted = _promote_recurring_chapter_entities(
            global_entities=[],
            chapter_outputs=[
                {
                    "chapter_id": "ch_001",
                    "characters": [{"surface": "Sera", "canonical": "Sera", "facts": ["Princesa aislada."], "confidence": 0.95}],
                    "places": [],
                    "concepts": [],
                    "events": [],
                    "relations": [],
                },
                {
                    "chapter_id": "ch_002",
                    "characters": [{"surface": "Sera", "canonical": "Sera", "facts": ["Su magia es inestable."], "confidence": 0.94}],
                    "places": [],
                    "concepts": [],
                    "events": [],
                    "relations": [],
                },
            ],
        )
        names = [item["canonical_name"] for item in promoted]
        self.assertIn("Sera", names)

    def test_title_entity_hints_capture_explicit_named_focus(self):
        self.assertEqual(
            _extract_title_entity_hints("Episodio 1: La magia Rota y la herencia silenciosa de Sera"),
            ["Sera"],
        )
        self.assertEqual(
            _extract_title_entity_hints("Episodio 3: El ritual del humo de Ren· Parte 1"),
            ["Ren"],
        )

    def test_title_hint_entities_can_promote_missing_focal_identity(self):
        promoted = _promote_title_hint_entities(
            global_entities=[],
            chapter_outputs=[
                {
                    "chapter_id": "ch_002",
                    "chapter_title_original": "Episodio 1: La magia rota y la herencia silenciosa de Sera",
                    "chapter_summary": "Sera decide abandonar el castillo.",
                    "characters": [{"surface": "Ren", "canonical": "Ren", "facts": ["Su magia es inestable."], "confidence": 0.9}],
                },
                {
                    "chapter_id": "ch_003",
                    "chapter_title_original": "Episodio 2: La huída y el límite de la forma de Sera",
                    "chapter_summary": "Sera escapa del castillo.",
                    "characters": [{"surface": "Ren", "canonical": "Ren", "facts": ["Huye hacia el bosque."], "confidence": 0.9}],
                },
            ],
        )
        names = [item["canonical_name"] for item in promoted]
        self.assertIn("Sera", names)

    def test_stabilize_character_entities_filters_title_conflicted_refs(self):
        stabilized = _stabilize_character_entities_with_title_hints(
            [
                {
                    "canonical_name": "Ren",
                    "entity_kind": "character",
                    "summary": "Ren mezcla hechos de otra protagonista.",
                    "aliases": [],
                    "key_facts": ["Hecho contaminado."],
                    "relationships": [],
                    "chapter_refs": ["ch_002", "ch_004", "ch_005"],
                    "source_mentions": ["Ren"],
                    "confidence": 0.95,
                    "review_state": "canonical",
                }
            ],
            [
                {
                    "chapter_id": "ch_002",
                    "chapter_title_original": "Episodio 1: La magia rota y la herencia silenciosa de Sera",
                    "chapter_summary": "Sera se enfrenta al castillo.",
                    "characters": [{"surface": "Ren", "canonical": "Ren", "facts": ["Hecho contaminado."], "confidence": 0.9}],
                },
                {
                    "chapter_id": "ch_004",
                    "chapter_title_original": "Episodio 3: El ritual del humo de Ren Parte 1",
                    "chapter_summary": "Ren participa en el ritual.",
                    "characters": [{"surface": "Ren", "canonical": "Ren", "facts": ["Participa en un ritual cargado de tensión."], "confidence": 0.95}],
                },
                {
                    "chapter_id": "ch_005",
                    "chapter_title_original": "Episodio 4: El ritual del humo de Ren Parte 2",
                    "chapter_summary": "Ren protege la campanilla.",
                    "characters": [{"surface": "Ren", "canonical": "Ren", "facts": ["Protege la campanilla durante un ataque."], "confidence": 0.95}],
                },
            ],
            language="es",
        )
        ren = stabilized[0]
        self.assertEqual(ren["chapter_refs"], ["ch_004", "ch_005"])
        self.assertNotIn("Hecho contaminado.", ren["key_facts"])
        self.assertIn("Ren", ren["summary"])

    def test_global_normalization_batches_split_chapters_by_budget(self):
        chapter = type("_Chapter", (), {})
        chapters = []
        for idx in range(3):
            item = chapter()
            item.title = f"Chapter {idx + 1}"
            item.text = "x" * 4000
            chapters.append(item)
        batches = _build_global_normalization_batches(
            work_title="Test Novel",
            language="es",
            chapters=chapters,
            config=NovelBootstrapV1Config(
                provider_name="lmstudio",
                model="qwen/qwen3.5-9b",
                global_batch_input_token_budget=2500,
                global_batch_prompt_overhead_tokens=200,
            ),
        )
        batches, audit = batches
        self.assertGreaterEqual(len(batches), 2)
        self.assertEqual(batches[0][0]["sequence_index"], 1)
        self.assertEqual(audit["batch_count"], len(batches))

    def test_json_import_filters_numeric_empty_primaries_and_marks_system_and_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_json = Path(tmp) / "obsidian_import.json"
            vault_root = Path(tmp) / "vault"
            source_json.write_text(
                json.dumps(
                    {
                        "work": {"title": "Test", "language": "es"},
                        "chapters": [
                            {
                                "chapter_id": "ch_001",
                                "chapter_title_original": "Episodio 1: Inicio",
                                "chapter_title_canonical": "Episodio 1: Inicio",
                                "sequence_index": 1,
                                "chapter_summary": "Resumen",
                                "chapter_text_markdown": "Texto",
                                "characters": [],
                                "places": [],
                                "concepts": [],
                                "events": [],
                                "relations": [],
                                "unresolved_mentions": [],
                            }
                        ],
                        "entities": [
                            {
                                "canonical_name": "1",
                                "entity_kind": "character",
                                "summary": "",
                                "key_facts": [],
                                "relationships": [],
                                "aliases": [],
                                "chapter_refs": [],
                                "source_mentions": [],
                                "confidence": 0.2,
                                "review_state": "canonical",
                            },
                            {
                                "canonical_name": "Sera",
                                "entity_kind": "character",
                                "summary": "Protagonista.",
                                "key_facts": ["Huye del castillo."],
                                "relationships": [],
                                "aliases": ["Serelyne"],
                                "chapter_refs": ["ch_001"],
                                "source_mentions": ["Sera"],
                                "confidence": 0.95,
                                "review_state": "canonical",
                            },
                            {
                                "canonical_name": "Figura Dudosa",
                                "entity_kind": "character",
                                "summary": "Mencion incierta.",
                                "key_facts": [],
                                "relationships": [],
                                "aliases": [],
                                "chapter_refs": [],
                                "source_mentions": [],
                                "confidence": 0.4,
                                "review_state": "review",
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            audit = import_json_to_vault(source_json=source_json, vault_root=vault_root)
            self.assertEqual(audit["primary_count"], 1)
            self.assertEqual(audit["review_primary_count"], 1)
            self.assertEqual(audit["skipped_primary_count"], 1)
            self.assertTrue((vault_root / "03_Characters/Profiles/sera.md").exists())
            self.assertTrue((vault_root / "90_Review/figura_dudosa.md").exists())
            self.assertFalse((vault_root / "03_Characters/Profiles/1.md").exists())
            manifest = (vault_root / "01_Project/import_manifest.md").read_text(encoding="utf-8")
            self.assertIn("#system", manifest)
            chapter_note = next((vault_root / "04_Story/Chapters").glob("*.md")).read_text(encoding="utf-8")
            self.assertIn("#chapter", chapter_note)
            self.assertIn("## Resumen", chapter_note)

    def test_json_import_preserves_existing_system_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_json = Path(tmp) / "obsidian_import.json"
            vault_root = Path(tmp) / "vault"
            (vault_root / "99_System").mkdir(parents=True, exist_ok=True)
            (vault_root / "99_System" / "global_batch_plan_audit.json").write_text('{"ok": true}', encoding="utf-8")
            source_json.write_text(
                json.dumps(
                    {
                        "work": {"title": "Test", "language": "es"},
                        "chapters": [],
                        "entities": [
                            {
                                "canonical_name": "Sera",
                                "entity_kind": "character",
                                "summary": "Protagonista.",
                                "key_facts": ["Huye del castillo."],
                                "relationships": [],
                                "aliases": [],
                                "chapter_refs": [],
                                "source_mentions": [],
                                "confidence": 0.95,
                                "review_state": "canonical",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            import_json_to_vault(source_json=source_json, vault_root=vault_root)
            self.assertTrue((vault_root / "99_System" / "global_batch_plan_audit.json").exists())

    def test_run_structured_bootstrap_v1_writes_json_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_root = Path(tmp) / "source"
            vault_root = Path(tmp) / "vault"
            source_root.mkdir(parents=True, exist_ok=True)
            vault_root.mkdir(parents=True, exist_ok=True)
            (source_root / "novel.md").write_text(
                (
                    "# 1 Arrival at Thiseia\n\n"
                    "Sera despierta en Thiseia y observa el castillo mientras piensa en su destino inmediato.\n\n"
                    "# 2 Escape from the Castle\n\n"
                    "Sera huye del castillo y atraviesa Thiseia con miedo, determinación y una decisión duradera.\n"
                ),
                encoding="utf-8",
            )
            inventory = build_source_document_inventory(source_root)

            with patch("textifai.import_review.structured_bootstrap_v1.get_text_provider_config_error", return_value=None), patch(
                "textifai.import_review.structured_bootstrap_v1.get_text_provider",
                return_value=_StructuredBootstrapFakeProvider(),
            ):
                result = run_structured_bootstrap_v1(
                    vault_root,
                    inventory=inventory,
                    config=NovelBootstrapV1Config(provider_name="lmstudio", model="qwen/qwen3.5-9b"),
                )

            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result.chapter_count, 2)
            self.assertTrue(Path(result.global_normalization_path).exists())
            self.assertTrue(Path(result.global_batch_audit_path).exists())
            self.assertTrue(Path(result.canonical_entity_map_path).exists())
            self.assertTrue(Path(result.obsidian_import_path).exists())
            chapter_files = sorted(Path(result.chapter_outputs_dir).glob("*.json"))
            self.assertEqual(len(chapter_files), 2)


if __name__ == "__main__":
    unittest.main()
