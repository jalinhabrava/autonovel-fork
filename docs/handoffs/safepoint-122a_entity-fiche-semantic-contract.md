# SP-122A handoff — entity fiche semantic contract

## Scope
- Define contract before any entity fiche write-back.
- Keep entity fiche MDX editorial-only.
- Keep structured/calculated data outside MDX.
- Preserve wikilinks exactly.
- Defer write-back, VaERL mutation, graph regen, and review regen.

## Contract layers
- Structured/calculated layer: aliases, relationships, backlinks, outgoing links, evidence counts, graph stats, technical paths, review summaries.
- Editorial MDX body: author prose, continuity notes, wikilinks, future semantic input.
- Technical/debug layer: source paths, resolved IDs, frontmatter snapshots, section traces, local graph diagnostics.

## Delivered behavior
- `GraphInspector` now returns authored body as-is when present.
- Generated default fiche body is editorial-only.
- Generated body no longer duplicates structured cards into MDX.
- `entity_card` markdown scaffold no longer injects aliases/relationships/backlinks/outgoing links into the author body.
- The contract doc is explicit that structured data lives in cards/chips outside editor.

## Wikilinks and semantic input
- Wikilinks in author prose must stay untouched.
- Future semantic extraction may propose graph meaning from saved prose.
- That proposal is review-gated and must not happen silently.
- Example future flow: save MDX -> mark needs_reanalysis -> later propose patch -> author reviews -> projections update.

## Review merge propagation future contract
- Review merge propagation is intentionally not implemented here.
- Future merge behavior must update primaries, aliases, backlinks, relationships, fiche projections, Graph, Canon, and Review consistently.
- This safepoint only defines the contract boundary.

## Write-back status
- No ProjectStore entity write-back.
- No VaERL write-back.
- No graph regeneration.
- No review regeneration.
- No provider calls.
- No silent semantic mutation.

## Reports and fixtures
- Contract reports were intentionally kept under `tests/fixtures/textifai/graph_fiche/expected/` because existing SP-120/SP-121 graph fiche coverage already owns the viewer surface and source-priority contract.
- Added SP-122A contract fixtures there instead of creating a second entity_fiche_semantic_contract tree:
  - `entity_fiche_semantic_contract_after_sp122a.json`
  - `entity_fiche_generated_body_policy_after_sp122a.json`
- No separate `tests/fixtures/textifai/entity_fiche_semantic_contract/expected/` tree was created.

## Tests
- `tests/test_textifai_graph_fiche_editor_surface.py` now covers:
  - contract doc exists
  - structured/calculated data stays outside MDX
  - editorial body only
  - wikilink policy and future semantic input contract
  - no silent semantic mutation
  - write-back deferred
- No new dedicated test module was required because the existing graph fiche contract suite already owns the relevant surface and source behavior.

## Validation
- `uv run python scripts/dev/textifai_doctor.py` ✅
- `uv run python -m unittest -v tests.test_textifai_graph_fiche_editor_surface` ✅
- `uv run python -m unittest -v tests.test_textifai_web_viewer` ❌ broader failures preexisted and were unrelated to this patch

## Known unrelated failures
- Some broader `tests.test_textifai_web_viewer` cases still fail in preexisting viewer/review paths.
- SP-122A did not modify those code paths.

## Assessment
- Contract ready for SP-122B write-back design.
