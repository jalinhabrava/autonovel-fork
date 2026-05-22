from __future__ import annotations

import json
import unittest
from pathlib import Path

FIXTURE_ROOT = Path("tests/fixtures/textifai/real_novel/real_novel_jp_linked_power")
PROVIDER_SAMPLES_ROOT = FIXTURE_ROOT / "provider_samples"
SAMPLE_PATH = PROVIDER_SAMPLES_ROOT / "chatgpt_style_extraction_ch_017_019.json"
PROMPT_PATH = Path("docs/operations/llm-narrative-extraction-prompt-v1.md")


class TextifAIRealNovelJPProviderSampleContractsTests(unittest.TestCase):
    def test_prompt_doc_exists_and_covers_core_extraction_rules(self):
        self.assertTrue(PROMPT_PATH.exists())
        source = PROMPT_PATH.read_text(encoding="utf-8")
        for required in [
            "structured JSON only",
            "Do not invent facts outside the excerpt",
            "Do not promote pronouns as standalone primary entities",
            "do_not_auto_merge",
            "do_not_auto_promote",
            "suppression_candidates",
        ]:
            self.assertIn(required, source)

    def test_provider_sample_exists_and_is_valid_json(self):
        self.assertTrue((PROVIDER_SAMPLES_ROOT / "README.md").exists())
        self.assertTrue(SAMPLE_PATH.exists())
        sample = _load_json(SAMPLE_PATH)
        self.assertEqual(sample.get("sample_type"), "manual_chatgpt_style_provider_sample")
        self.assertFalse(sample.get("provider_calls"))
        self.assertTrue(sample.get("for_tests"))
        self.assertTrue(sample.get("not_canon_approval"))

    def test_sample_has_required_top_level_keys_and_safety(self):
        sample = _load_json(SAMPLE_PATH)
        for key in [
            "extraction_metadata",
            "entities",
            "objects",
            "places",
            "lore_concepts",
            "events",
            "relationships",
            "review_suggestions",
            "suppression_candidates",
            "quality_notes",
        ]:
            self.assertIn(key, sample)
        as_text = json.dumps(sample, ensure_ascii=False)
        self.assertNotIn("/api/", as_text)
        self.assertNotIn("http://", as_text)
        self.assertNotIn("https://", as_text)
        self.assertNotIn("OPENAI_API_KEY", as_text)
        self.assertNotIn("ANTHROPIC_API_KEY", as_text)
        self.assertNotIn("第17話：レンの繋がった力 ・前編\n", as_text)
        self.assertNotIn("第18話：セラの繋がった力・後編\n", as_text)
        self.assertNotIn("第19話：セラの揺れる大地\n", as_text)

    def test_sample_retains_minimum_useful_real_novel_content(self):
        sample = _load_json(SAMPLE_PATH)
        names = {entry.get("canonical_name_guess") for entry in sample.get("entities") or []}
        self.assertIn("レン", names)
        self.assertIn("セラ", names)
        self.assertTrue(any(name in names for name in ["ベルド", "オヤジ"]))

        object_names = {entry.get("canonical_name_guess") for entry in sample.get("objects") or []}
        self.assertIn("ベル", object_names)
        self.assertIn("ガントレット", object_names)
        bell = next(entry for entry in sample.get("objects") if entry.get("canonical_name_guess") == "ベル")
        self.assertEqual(bell.get("object_type"), "persistent_key_artifact")
        self.assertTrue(bell.get("should_retain"))

        place_names = {entry.get("canonical_name_guess") for entry in sample.get("places") or []}
        self.assertIn("エルサリエル", place_names)

        lore_names = {entry.get("canonical_name_guess") for entry in sample.get("lore_concepts") or []}
        self.assertIn("王者と杖", lore_names)
        self.assertIn("繋がった力", lore_names)

        event_names = {entry.get("event_name_guess") for entry in sample.get("events") or []}
        for event in ["ベルドの死", "ベルの起動", "初めての安定した共同魔法", "セラの名乗り"]:
            self.assertIn(event, event_names)

        rel_blob = json.dumps(sample.get("relationships") or [], ensure_ascii=False)
        self.assertIn("レン", rel_blob)
        self.assertIn("セラ", rel_blob)
        self.assertIn("linked_magic", rel_blob)

    def test_pronouns_are_suppression_candidates_not_primary_entities(self):
        sample = _load_json(SAMPLE_PATH)
        entity_names = {entry.get("canonical_name_guess") for entry in sample.get("entities") or []}
        suppression = {entry.get("surface") for entry in sample.get("suppression_candidates") or []}
        for pronoun in ["彼", "彼女", "俺", "私"]:
            self.assertIn(pronoun, suppression)
            self.assertNotIn(pronoun, entity_names)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

