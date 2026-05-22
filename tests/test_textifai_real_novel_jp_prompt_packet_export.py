from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

FIXTURE_ROOT = Path("tests/fixtures/textifai/real_novel/real_novel_jp_linked_power")
PROMPT_PACKET_ROOT = FIXTURE_ROOT / "provider_samples" / "prompt_packets"
PROMPT_PACKET_MD = PROMPT_PACKET_ROOT / "extraction_prompt_packet_ch_017_019.md"
PROMPT_PACKET_JSON = PROMPT_PACKET_ROOT / "extraction_prompt_packet_ch_017_019.json"

REQUIRED_SCHEMA_KEYS = {
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
}

FORBIDDEN_HINTS = [
    "must detect",
    "must retain",
    "should detect",
    "expected entity",
    "expected object",
    "expected lore",
    "expected event",
    "expected relationship",
    "オヤジ should",
    "ベル should",
    "王者と杖 should",
    "treat オヤジ",
    "retain ベル",
    "linked magic should",
    "Beld death should",
]


class TextifAIRealNovelJPPromptPacketExportTests(unittest.TestCase):
    def test_prompt_packet_files_exist_and_json_flags_are_blind_provider_free(self):
        self.assertTrue((PROMPT_PACKET_ROOT / "README.md").exists())
        self.assertTrue(PROMPT_PACKET_MD.exists())
        self.assertTrue(PROMPT_PACKET_JSON.exists())

        packet = _load_json(PROMPT_PACKET_JSON)
        self.assertEqual(packet.get("sample_type"), "blind_prompt_packet_export")
        self.assertFalse(packet.get("provider_calls"))
        self.assertTrue(packet.get("not_runtime_provider_output"))
        self.assertTrue(packet.get("not_canon_approval"))
        self.assertTrue(packet.get("blind_prompt"))
        self.assertEqual(packet.get("source_language"), "ja")
        self.assertEqual(packet.get("selected_chapters"), ["ch_017", "ch_018", "ch_019"])

    def test_prompt_packet_md_contains_general_instructions_schema_and_source_payload(self):
        source = PROMPT_PACKET_MD.read_text(encoding="utf-8")
        for required in [
            "You are a narrative analysis extractor for TextifAI.",
            "Use only the provided text.",
            "Do not promote pronouns as standalone primary entities.",
            "Output valid JSON only.",
            '"extraction_metadata"',
            '"entities"',
            '"objects"',
            '"places"',
            '"lore_concepts"',
            '"events"',
            '"relationships"',
            '"review_suggestions"',
            '"suppression_candidates"',
            '"quality_notes"',
            "chapter_ref: ch_017",
            "chapter_ref: ch_018",
            "chapter_ref: ch_019",
            "JSON only",
        ]:
            self.assertIn(required, source)

    def test_prompt_packet_json_contains_schema_keys_privacy_and_output_constraints(self):
        packet = _load_json(PROMPT_PACKET_JSON)
        self.assertTrue(REQUIRED_SCHEMA_KEYS.issubset(set(packet.get("output_schema_keys") or [])))
        self.assertTrue(packet.get("privacy_constraints"))
        self.assertTrue(packet.get("expected_output_constraints"))
        self.assertEqual(len(packet.get("source_payload") or []), 3)
        self.assertTrue(all(item.get("chapter_ref") in {"ch_017", "ch_018", "ch_019"} for item in packet.get("source_payload") or []))

    def test_prompt_packet_is_short_safe_and_has_no_provider_or_writeback_instructions(self):
        for path in [PROMPT_PACKET_MD, PROMPT_PACKET_JSON]:
            text = path.read_text(encoding="utf-8")
            self.assertLess(len(text), 30000, path)
            self.assertNotIn("OPENAI_API_KEY", text)
            self.assertNotIn("ANTHROPIC_API_KEY", text)
            self.assertNotIn("https://api.", text)
            self.assertNotIn("/runs/", text)
            self.assertNotIn("/vault/", text)
            self.assertNotRegex(text.casefold(), r"\bwrite[- ]?back\b")
        md_lines = PROMPT_PACKET_MD.read_text(encoding="utf-8").splitlines()
        self.assertLess(len(md_lines), 420)

    def test_anti_leakage_guards_instruction_sections_not_source_payload(self):
        source = PROMPT_PACKET_MD.read_text(encoding="utf-8")
        instruction_text = source.split("## 4. Source chunk payload", 1)[0]
        tail = source.split("## 5. Final instruction", 1)[-1]
        non_payload_text = instruction_text + "\n" + tail
        for forbidden in FORBIDDEN_HINTS:
            self.assertNotIn(forbidden, non_payload_text)

        packet = _load_json(PROMPT_PACKET_JSON)
        non_payload_json = {
            key: value
            for key, value in packet.items()
            if key not in {"source_payload"}
        }
        non_payload_blob = json.dumps(non_payload_json, ensure_ascii=False)
        for forbidden in FORBIDDEN_HINTS:
            self.assertNotIn(forbidden, non_payload_blob)

    def test_prompt_packet_does_not_embed_full_chapters(self):
        source = PROMPT_PACKET_MD.read_text(encoding="utf-8")
        self.assertLess(source.count("chapter_ref:"), 4)
        bullet_like_lines = [line for line in source.splitlines() if re.match(r"^- [「彼私俺ベルガ魔押たひ後]", line)]
        self.assertLessEqual(len(bullet_like_lines), 18)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
