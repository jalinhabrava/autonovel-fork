# SP-150 — pronoun/coreference review hydration hardening

## Problem summary

SP-149 left review hydration vulnerable to noisy pronoun-like queue items. Viewer received repeated low-context cards, generic titles, and weak evidence surfacing for unresolved references.

## Root cause

- Hydration treated pronoun-like items one-by-one.
- Evidence resolution stayed card-local and did not surface explicit failure state.
- Candidate plumbing allowed empty context, which made cards look under-specified.
- Generic title/reason strings hid chapter and excerpt context already present in artifacts.

## Hydration fix

- Backend hydration now groups repeated pronoun-like items by normalized pronoun plus chapter.
- Representative grouped item keeps `grouped_review_item_ids`, `occurrence_count`, evidence refs, and chapter context.
- Title/reason now prefer chapter-aware wording instead of generic fallback text.
- Evidence diagnostics now expose `metadata.evidence_resolution` with:
  - `resolved`
  - `missing_source_map`
  - `missing_chunk`
  - `unavailable`

## Dedupe/grouping strategy

- Only pronoun-like hydration items are deduped.
- Group key: normalized target label + chapter identity.
- First hydrated item stays representative.
- Later duplicates merge into representative by:
  - incrementing `occurrence_count`
  - appending grouped ids
  - preserving unique evidence refs
  - upgrading evidence state to `resolved` when any duplicate resolves excerpt text

## Evidence surfacing

- Hydration uses existing `evidence/evidence_index.json` and `evidence/source_map.json`.
- When chunk resolution succeeds, grouped item keeps excerpt-bearing evidence and chapter label.
- When resolution fails, item stays renderable and explains failure state through `metadata.evidence_resolution` and hydrated reason text.
- Missing source map no longer crashes hydration path.

## No-fake-candidate rule

- Pronoun-like items never invent candidate entities during hydration.
- Existing `candidate_entities` pass through as context only.
- Empty candidate list stays empty.
- No synthetic fallback candidate is introduced.

## Explicitly deferred

- Full coreference resolution
- Provider prompt or schema changes
- Second-pass LLM coreference
- User actions such as retry, ignore, resolve
- Review Queue redesign
