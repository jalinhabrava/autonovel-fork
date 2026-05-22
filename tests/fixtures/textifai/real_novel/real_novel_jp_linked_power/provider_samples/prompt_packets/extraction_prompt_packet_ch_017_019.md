# Blind Prompt Packet — real_novel_jp_linked_power ch_017_019

## 1. Purpose
You are a narrative analysis extractor for TextifAI.
Your task is to read provided authorial text and return structured JSON only.
You are extracting semantic evidence for downstream author review.

## 2. Rules
- Use only the provided text.
- Do not invent facts outside the excerpt.
- Preserve original surface forms in the source language.
- If source is Japanese, keep Japanese names and surfaces in Japanese.
- Do not continue story prose.
- Do not approve canon.
- Do not merge entities automatically.
- Do not auto-promote candidates.
- Do not promote pronouns as standalone primary entities.
- Mark uncertainty explicitly.
- Distinguish characters, objects, places, lore concepts, events, relationships, review suggestions, suppression candidates.
- Include only short source spans.
- Output valid JSON only.

## 3. Output JSON schema
Return this JSON shape:

```json
{
  "extraction_metadata": {
    "source_language": "",
    "source_title": "",
    "chunk_id": "",
    "chapter_refs": [],
    "extraction_mode": "llm_provider",
    "confidence_overall": "low|medium|high",
    "notes": []
  },
  "entities": [
    {
      "canonical_name_guess": "",
      "entity_kind": "character|group|organization|unknown",
      "aliases": [],
      "source_mentions": [],
      "pronoun_like_mentions": [],
      "roles_or_titles": [],
      "lore_identity_candidates": [],
      "key_facts": [],
      "relationships": [],
      "chapter_refs": [],
      "source_spans": [],
      "confidence": "low|medium|high",
      "uncertainties": [],
      "review_suggestions": []
    }
  ],
  "objects": [
    {
      "canonical_name_guess": "",
      "object_type": "persistent_key_artifact|weapon|tool|temporary_prop|unknown",
      "source_mentions": [],
      "key_facts": [],
      "relationships": [],
      "chapter_refs": [],
      "source_spans": [],
      "confidence": "low|medium|high",
      "should_retain": true,
      "uncertainties": [],
      "review_suggestions": []
    }
  ],
  "places": [
    {
      "canonical_name_guess": "",
      "place_type": "destination|settlement|building|region|unknown",
      "source_mentions": [],
      "key_facts": [],
      "relationships": [],
      "chapter_refs": [],
      "source_spans": [],
      "confidence": "low|medium|high",
      "uncertainties": [],
      "review_suggestions": []
    }
  ],
  "lore_concepts": [
    {
      "canonical_name_guess": "",
      "concept_type": "role_system|magic_system|bond|ritual|faction_lore|unknown",
      "source_mentions": [],
      "key_facts": [],
      "related_entities": [],
      "chapter_refs": [],
      "source_spans": [],
      "confidence": "low|medium|high",
      "uncertainties": [],
      "review_suggestions": []
    }
  ],
  "events": [
    {
      "event_name_guess": "",
      "event_kind": "death|artifact_activation|magic_activation|battle|relationship_moment|revelation|journey|unknown",
      "participants": [],
      "objects": [],
      "places": [],
      "facts": [],
      "chapter_refs": [],
      "source_spans": [],
      "confidence": "low|medium|high",
      "uncertainties": [],
      "review_suggestions": []
    }
  ],
  "relationships": [
    {
      "source": "",
      "target": "",
      "relationship_type": "",
      "evidence": [],
      "chapter_refs": [],
      "confidence": "low|medium|high",
      "uncertainties": [],
      "review_suggestions": []
    }
  ],
  "review_suggestions": [
    {
      "review_type": "alias_merge|role_attach|lore_concept_review|object_retention|relationship_review|event_review|noise_suppression|uncertain_identity",
      "target": "",
      "candidate": "",
      "reason": "",
      "evidence": [],
      "recommended_action": "",
      "confidence": "low|medium|high",
      "do_not_auto_merge": true,
      "do_not_auto_promote": true
    }
  ],
  "suppression_candidates": [
    {
      "surface": "",
      "reason": "pronoun|generic_descriptor|temporary_prop|ephemeral_group|other",
      "should_not_promote": true,
      "evidence": []
    }
  ],
  "quality_notes": {
    "possible_missing_context": [],
    "possible_hallucination_risks": [],
    "schema_fit_notes": [],
    "author_review_needed": []
  }
}
```

## 4. Source chunk payload

- chapter_ref: ch_017
  - 「……エルサリエル。」
  - 「……ベルを。」
  - 「今なら――鳴らせる。」
  - 「……王者と杖は……共に歩む。」
  - ベルが鳴った。
  - 俺が――彼女の魔力を運ぶ道だった。
  - ガントレットが、肘ごと砕けた。

- chapter_ref: ch_018
  - 彼は、境界線であり、流れを導く川だった。
  - 押さえつけるでもなく、止めるでもなく、ただ、私を支えた。
  - 魔法が走った。
  - ただ、私のままで、魔法を使った。

- chapter_ref: ch_019
  - 「……オヤジ……」
  - 「セラ。」
  - 私たちは、まだ、ちゃんと名乗り合ってもいなかった。
  - ひとりにしないために。
  - 後には戻れない。

## 5. Final instruction
Return JSON only.
No markdown.
No explanation outside JSON.
