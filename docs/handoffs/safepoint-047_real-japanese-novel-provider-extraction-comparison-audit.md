# Real Japanese Novel Provider Extraction Comparison Audit

## Product Reading
TextifAI ya validó downstream útil con mini-fixture japonés real provider-free. Esta fase audita mitad previa: calidad de extracción estilo provider usando prompt/schema explícito y sample manual comparable contra replay curado, sin integrar provider calls automáticas en tests.

## Scope
- Crear prompt/schema narrativo LLM v1.
- Crear provider sample manual estilo ChatGPT para ch_017–ch_019.
- Crear checklist comparativo y gap report.
- Añadir tests provider-free para sample/comparación.
- Sin runtime changes, schema changes, chunking implementation o write-back.

## Files Changed
- `docs/operations/llm-narrative-extraction-prompt-v1.md`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/provider_samples/README.md`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/provider_samples/chatgpt_style_extraction_ch_017_019.json`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/expected/provider_comparison_checklist.json`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/expected/provider_extraction_gap_report.json`
- `tests/test_textifai_real_novel_jp_provider_sample_contracts.py`
- `tests/test_textifai_real_novel_jp_provider_comparison_audit.py`
- `docs/handoffs/safepoint-047_real-japanese-novel-provider-extraction-comparison-audit.md`

## Prompt v1 Created
Se añadió prompt operativo reutilizable para narrativa autoral (capítulos, notas, worldbuilding, magic-system, lore desordenado), con JSON estricto y guardrails de incertidumbre/suppression/no canon mutation.

## Provider Sample Created
Se añadió sample manual:
- `sample_type`: `manual_chatgpt_style_provider_sample`
- `provider_calls`: `false`
- `for_tests`: `true`
- `not_canon_approval`: `true`

Cubre entidades, objetos, lugares, lore, eventos, relaciones, review_suggestions y suppression_candidates para ch_017–ch_019.

## Comparison Checklist
Se añadió checklist comparativo con:
- must/should coverage
- false positive risks
- pronoun/object/lore/relationship/event guards
- shape compatibility
- qualitative usefulness score (`usable` / `partially_usable` / `not_usable`)
- non-negotiable failures

## Gap Report
Se añadió gap report inicial con:
- `what_matched_curated`
- `what_was_missing`
- `what_was_weaker_than_curated`
- `prompt_improvement_notes`
- `downstream_risk_notes`
- `author_review_notes`
- `overall_assessment`

## What Matched Curated Replay
- Main entities retained (`レン`, `セラ`, `ベルド/オヤジ`).
- `ベル` retained as durable key artifact.
- `エルサリエル` retained as destination.
- Ren/Sera linked magic retained.
- `王者と杖` and `繋がった力` retained.
- Beld death/aftermath retained as event/facts.

## What Was Missing / Weaker
- Alias certainty (`オヤジ`↔`ベルド`) still needs human review.
- Event normalization is weaker than curated replay in some linkage details.
- Role mapping (`王者`/`杖`) remains intentionally unresolved.

## Prompt Improvement Notes
- Ask explicitly for role/lore vs literal-object disambiguation.
- Require stricter participant/object/place linkage per event.
- Require explicit alias uncertainty tagging for alternative surfaces.

## Provider-free Test Guarantee
- No provider calls in tests.
- Sample is static/manual JSON.
- Tests only parse/compare artifacts.

## IP / Privacy Constraints
- No full chapter dumps.
- No full novel content committed.
- Only short spans/excerpts and structured sample data.

## Tests Added / Updated
Added:
- `tests/test_textifai_real_novel_jp_provider_sample_contracts.py`
- `tests/test_textifai_real_novel_jp_provider_comparison_audit.py`

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_real_novel_jp_provider_sample_contracts`
- `uv run python -m unittest -v tests.test_textifai_real_novel_jp_provider_comparison_audit`
- `uv run python -m unittest -v tests.test_textifai_real_novel_jp_mini_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_real_novel_jp_mini_replay_baseline`
- `uv run python -m unittest -v tests.test_textifai_real_novel_jp_mini_usefulness_contracts`
- `uv run python -m unittest -v tests.test_textifai_web_viewer`
- `node --check textifai/web_viewer/static/app.js`
- `uv run python scripts/textifai.py replay-downstream --help`
- `uv run python scripts/textifai.py viewer --help`
- `git status --short`
- `git diff --stat`

## Data Written
- Prompt doc
- Provider sample + comparison artifacts
- Tests + handoff
- No runtime output artifacts committed

## Safety Constraints
- No provider/API calls in tests.
- No runtime/schema changes.
- No write-back.
- No writes to `runs/**` or `vault/**`.
- No chunking implementation.

## Known Limitations
- Sample is manual LLM-style, not automatic provider output.
- Assessment is qualitative and controlled, not full production extraction benchmark.
- Chunking effects not audited in this phase.

## Future Extensions
- Add second/third provider-style samples for consistency comparisons.
- Add stricter schema-compatibility scoring dimensions.

## Next Chunking Audit
Siguiente fase debe auditar chunking para:
- chapter/title-based splitting en novelas estructuradas,
- splitting de notas autorales desordenadas,
- worldbuilding/magic-system notes,
- token budget estimation,
- overlap policy,
- context preservation,
- anti-overlong chunks,
- per-chunk metadata/provenance.

## Semantic Contract Changes
NO

## Runtime Changes
NO

## Generated Artifacts
Provider sample/checklist/gap report only.

## Provider Calls
NO

## Write-back
NO

## Branch
`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
Phase 1.3.M-c — Authorial Source Chunking Audit (Structured Chapters + Messy Notes).
