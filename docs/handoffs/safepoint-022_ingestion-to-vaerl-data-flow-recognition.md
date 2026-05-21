# Ingestion-to-VaERL Data Flow Recognition

## Scope

Phase 1.3.A was a recognition-only pass over the active TextifAI semantic ingestion rail.

Included inspection:

- CLI entrypoints in `scripts/textifai.py`, `textifai/cli.py`, and `textifai/obsidian/cli.py`.
- Vault/bootstrap orchestration in `textifai/obsidian/setup.py`.
- Structured ingestion, replay, normalization, entity resolution, cleanup, reconciliation, import assembly, invariants, and review queue generation in `textifai/import_review/**` and `textifai/vaerl/**`.
- Obsidian materialization and read surfaces in `textifai/obsidian/json_import.py`, `textifai/obsidian/parser.py`, and `textifai/obsidian/bridge_reader.py`.
- Existing tests and operations docs relevant to semantic contracts, validation surfaces, and safe fixtures.

Not included:

- No runtime behavior changes.
- No ingestion logic changes.
- No VaERL logic changes.
- No canonicalization/reconciliation logic changes.
- No prompt/template changes.
- No schema changes.
- No generated artifact changes.
- No `runs/**` or `vault/**` writes.

## Entry Points

### Primary wrapper

- `scripts/textifai.py`
  - Delegates directly to `textifai.obsidian.cli.run_cli`.
  - Preferred product CLI for the active TextifAI rail.

### Product CLI wrapper

- `textifai/cli.py`
  - Defaults to Obsidian `start` when no args are provided.
  - Delegates `start`, `init`, `status`, `inspect`, `ask`, `provider`, and `configure-provider` to the Obsidian CLI.
  - Keeps separate `doctor` and `chat` flows.

### Active Obsidian/TextifAI CLI

- `textifai/obsidian/cli.py`
  - `start`: interactive guided setup; can call init-like flow and provider setup.
  - `init`: initializes vault or imports existing source material.
  - `status`: readiness inspection.
  - `inspect`: snapshot/readiness/import state/VaERL index inspection.
  - `validate-vaerl`: evaluates semantic invariants against a `99_System` directory and optional vault.
  - `replay-downstream`: replays downstream semantic stages from frozen `global_normalization.json` and `chapter_outputs/`.
  - `review-queue`: reads and filters `review_queue.json`.
  - `ask`: author-facing query against prepared vault context.
  - `viewer`: launches internal local runs/vaults viewer.
  - `provider` / `configure-provider`: provider readiness/configuration.

### Commands that can write artifacts

- `init` with `--source-root` or `--use-vault-root-as-source`
  - Can write vault scaffolding, `99_System` semantic artifacts, imported Markdown notes, bridge plugin files, source extraction audit, and bootstrap progress log.
- `validate-vaerl`
  - Reads `obsidian_import.json`; writes `semantic_invariants_audit.json` by default unless `--output` is redirected.
- `replay-downstream`
  - Reads frozen input `99_System`; writes replay output root with downstream artifacts and audits.
- `ask`
  - Existing tests show trace/preview persistence can occur.
- `viewer`
  - Can execute ingestion jobs through wizard endpoints from Phase 1.2, writing only dedicated `runs/web_ingestion/**` job metadata/log/output when user submits a job.

### Read-only or mostly read-only commands

- `status`
  - Readiness and provider readiness inspection.
- `inspect`
  - Reads vault/snapshot/VaERL index state.
- `review-queue`
  - Reads `review_queue.json`, filters by type/severity/limit.
- `viewer --help`, `init --help`, `validate-vaerl --help`, `replay-downstream --help`, `review-queue --help`
  - Read-only help inspection.

### Source/vault/language/model/provider controls

- `init`
  - `--vault-root`
  - `--project-title`
  - `--source-root`
  - `--use-vault-root-as-source`
  - `--primary-language`
  - `--working-language`
  - `--build-bridge-plugin`
  - `--skip-plugin-install`
  - `--plugin-repo-root`
  - `--importer-preference`
- `validate-vaerl`
  - `--system-root`
  - `--vault-root`
  - `--required-primary`
  - `--language`
  - count/quality thresholds
  - `--language-validator`
  - `--output`
- `replay-downstream`
  - `--input-system`
  - `--output-root`
  - `--language`
  - `--prose-language-validator`
  - `--prose-language-validation-mode`
  - `--auxiliary-document`
  - `--auxiliary-hint`
  - `--auxiliary-provider`
  - `--auxiliary-model`
- Provider/model environment and config
  - `AUTONOVEL_BOOTSTRAP_PROVIDER`
  - `AUTONOVEL_BOOTSTRAP_MODEL`
  - `TEXTIFAI_BOOTSTRAP_MAX_CHAPTERS`
  - runtime environment provider settings from provider onboarding.

## Pipeline Stage Map

### 1. Project setup / intake

- Inputs:
  - `vault_root`, optional `source_root`, project title, language hints, provider/model configuration.
- Key files/functions:
  - `textifai/obsidian/setup.py`
  - `ObsidianProjectSetupConfig`
  - `prepare_obsidian_project(...)`
  - `bootstrap_vault(...)`
  - `discover_importable_source_paths(...)`
  - `build_source_document_inventory(...)`
  - `read_source_documents(...)`
- Outputs:
  - Vault scaffolding when needed.
  - `99_System/source_extraction_audit.json`.
  - `99_System/bootstrap_progress.jsonl`.
- Semantic risk:
  - Source selection and inventory are the first loss boundary.
  - Wrong `source_root` or language hints propagate through every downstream artifact.
- Validation available:
  - `tests/test_textifai_obsidian_setup.py`.
  - `uv run python scripts/textifai.py init --help`.
- Known fragility:
  - Real ingestion can write vault/runs and call provider; must be fixture-gated before core changes.

### 2. Source discovery

- Inputs:
  - Source directory or vault-as-source.
- Key files/functions:
  - `textifai/bootstrap/source_reader.py`.
  - `discover_importable_source_paths(...)`.
  - `build_source_document_inventory(...)`.
  - `read_source_documents(...)`.
- Outputs:
  - Source inventory used by setup and audit.
  - Extracted text map keyed by source document.
- Semantic risk:
  - PDF/derived extraction loss, encoding issues, source ordering, and mixed content kinds can degrade later chapterization.
- Validation available:
  - Derived source tests in `tests/test_textifai_derived_source_extractors.py`.
- Known fragility:
  - Source extraction audit stores preview text; avoid private real data in committed fixtures.

### 3. Chapterization

- Inputs:
  - Source document text and metadata.
- Key files/functions:
  - `textifai/import_review/chapterizer.py`.
  - `detect_story_chapters(...)`.
  - Title/TOC/page marker heuristics.
- Outputs:
  - Detected chapters with IDs, title, slug, page ranges, char ranges, confidence, heading signals, sequence index.
- Semantic risk:
  - Bad segmentation causes downstream chapter refs, source evidence, sequence, and narrative state to drift.
  - False Roman numeral/title detection can split prose incorrectly.
- Validation available:
  - `tests/test_textifai_chapterizer.py`.
- Known fragility:
  - Chapter detection is heuristic and highly sensitive to source formatting.

### 4. Novel index generation

- Inputs:
  - Detected chapters.
- Key files/functions:
  - `build_novel_index(...)` in `textifai/import_review/structured_bootstrap_v1.py`.
- Outputs:
  - `novel_index.json`.
- Semantic risk:
  - Metadata-only index is deterministic, but wrong chapter metadata creates stable-looking downstream errors.
- Validation available:
  - `tests/test_textifai_structured_bootstrap_v1.py`.

### 5. Global normalization

- Inputs:
  - `novel_index.json`, selected chapter text, provider/model plan.
- Key files/functions:
  - `build_global_normalization_pass1(...)`.
  - `_run_global_normalization(...)`.
  - `_build_global_normalization_pass2_artifact(...)`.
  - `build_ambiguous_entity_queue(...)`.
  - language validators in `structured_bootstrap_v1.py`.
- Outputs:
  - `global_normalization_pass1.json`.
  - `ambiguous_entity_queue.json`.
  - `selective_normalization_trace.jsonl`.
  - `selective_normalization_metrics.json`.
  - `global_normalization_pass2.json`.
  - `global_normalization.json`.
  - `global_batch_audit.json`.
  - `model_plan_audit.json`.
  - `llm_call_ledger.jsonl`.
- Semantic risk:
  - Language contamination, over-broad global entities, missed recurring entities, weak aliases, and model routing failures.
- Validation available:
  - Structured bootstrap tests cover pass1 selection, language validation, prompt language policy, model plan guardrails, and deterministic metadata.
- Known fragility:
  - This is LLM-sensitive; fixture harness should isolate downstream deterministic stages before changing extraction prompts.

### 6. Canonical entity map

- Inputs:
  - `global_normalization.json`.
- Key files/functions:
  - `build_canonical_entity_map(...)`.
- Outputs:
  - `canonical_entity_map.json`.
- Semantic risk:
  - Map becomes guardrail for chapter extraction; wrong canonical choices can over-merge, under-merge, or hide specific names behind descriptors.
- Validation available:
  - Structured bootstrap tests around canonical map size/reduction and chapter prompt usage.

### 7. Chapter extraction

- Inputs:
  - Detected chapters, `canonical_entity_map.json`, title parse signals, global context.
- Key files/functions:
  - Chapter extraction prompts and reduction prompts in `structured_bootstrap_v1.py`.
  - `_extract_chapter_payload_with_retries(...)`.
  - chunk/reduction path for large chapters.
- Outputs:
  - `chapter_outputs/*.json`.
  - `chapter_extraction_audit.json`.
  - `chapters_enriched.json`.
- Semantic risk:
  - Chapter-local noise, missing durable facts, weak evidence, unstable `unresolved_mentions`, bad `chapter_refs`, and title-entity hallucination.
- Validation available:
  - Structured bootstrap tests cover prompt constraints, chapter refs, assembly enrichment, and incomplete extraction audit.
- Known fragility:
  - LLM extraction prompt is central and high-risk; do not alter without snapshots.

### 8. Entity resolution

- Inputs:
  - Chapter entities and chapter metadata.
- Key files/functions:
  - `textifai/import_review/entity_cluster_resolution.py`.
  - `resolve_entity_clusters(...)`.
  - `normalize_entity_text(...)`.
  - `normalize_entity_key(...)`.
- Outputs:
  - `resolved_entities.json`.
  - `entity_clusters_audit.json`.
  - `entity_resolution_audit.json`.
  - `gender_signal_audit.json`.
  - `semantic_context_probe_audit.json`.
  - `semantic_context_probe_trace.jsonl`.
- Semantic risk:
  - Over-merge, under-merge, alias pollution, descriptor/pronoun canonicals, weak confidence, and missing source mentions.
- Validation available:
  - `tests/test_textifai_structured_bootstrap_v1.py`.
  - `tests/test_textifai_entity_resolution.py`.
- Known fragility:
  - Resolution is one of the highest semantic-quality leverage points and needs edge fixtures before behavioral changes.

### 9. Cleanup

- Inputs:
  - `resolved_entities.json`, chapter outputs.
- Key files/functions:
  - `textifai/import_review/entity_cleanup.py`.
  - `cleanup_resolved_entities(...)`.
- Outputs:
  - Cleaned entity list in memory before final write.
  - `entity_cleanup_audit.json`.
  - `promotion_decisions_audit.json`.
- Semantic risk:
  - Trivial entity filtering can remove important recurring concepts, or keep noise that floods review queue.
- Validation available:
  - Structured bootstrap tests cover cleanup and promotion behavior.

### 10. Pre-VaERL reconciliation

- Inputs:
  - Cleaned entities and chapter outputs.
- Key files/functions:
  - `textifai/import_review/entity_reconciliation.py`.
  - `reconcile_entities_for_vaerl(...)`.
  - `reconcile_primary_relationship_mentions(...)`.
  - `synthesize_primary_note_summaries(...)`.
- Outputs:
  - Final `cleaned_entities.json`.
  - `pre_vaerl_reconciliation_audit.json`.
  - `primary_note_synthesis_audit.json`.
  - Later `obsidian_relationship_reconciliation_audit.json`.
- Semantic risk:
  - Relationship target mismatch, weak summary synthesis, relationship rewrites that hide uncertainty, and target linking by brittle aliases.
- Validation available:
  - Structured bootstrap tests around chapter refs, relationships, synthesis, and relationship reconciliation.
- Known fragility:
  - This is contract-adjacent because it shapes `obsidian_import.json`.

### 11. VaERL conversion / Obsidian import assembly

- Inputs:
  - `global_normalization.json`, `chapter_outputs/*.json`, cleaned/reconciled entities.
- Key files/functions:
  - `assemble_obsidian_import(...)` in `structured_bootstrap_v1.py`.
- Outputs:
  - `obsidian_import.json`.
  - `obsidian_relationship_reconciliation_audit.json`.
  - `e2e_artifact_contract.json`.
- Semantic risk:
  - `review_state`, `note_role`, slugs, wikilinks, relationships, chapter refs, and filenames become downstream contracts.
- Validation available:
  - Structured bootstrap tests around assembly enrichment, slug target usage, generated artifact writes.

### 12. Invariant evaluation

- Inputs:
  - `obsidian_import.json`, optional materialized vault.
- Key files/functions:
  - `textifai/vaerl/invariants.py`.
  - `evaluate_semantic_invariants(...)`.
  - `write_semantic_invariants_audit(...)`.
- Outputs:
  - `semantic_invariants_audit.json`.
- Checks observed:
  - Import existence.
  - Required primaries.
  - Primary count range.
  - Entity slug presence/duplicates.
  - Exact duplicate canonical names.
  - Near-duplicate primary names.
  - Relationship target resolution to primary.
  - Unlinked primary mention limits.
  - Suspicious orphan primaries.
  - Canonical name strength.
  - Optional vault wikilink/placeholder checks.
- Semantic risk:
  - Invariant coverage can miss evidence quality, narrative state consistency, and false-positive review noise.
- Validation available:
  - `uv run python scripts/textifai.py validate-vaerl --help`.
  - VaERL-related tests.

### 13. Review queue generation

- Inputs:
  - `obsidian_import.json`, `semantic_invariants_audit.json`.
- Key files/functions:
  - `textifai/vaerl/review_queue.py`.
  - `write_review_queue(...)`.
- Outputs:
  - `review_queue.json`.
- Semantic risk:
  - Queue can be noisy if severity/reasons are too broad, or weak if uncertain merges lack actionable evidence.
- Validation available:
  - `uv run python scripts/textifai.py review-queue --help`.
  - Structured bootstrap and viewer tests exercise queue consumption/counting.

### 14. Obsidian markdown/vault materialization

- Inputs:
  - `obsidian_import.json`.
- Key files/functions:
  - `textifai/obsidian/json_import.py`.
  - `import_json_to_vault(...)`.
  - `write_note(...)`.
  - `validate_vault(...)`.
- Outputs:
  - Canonical primary Markdown notes.
  - Chapter notes.
  - Chapter summary notes.
  - `99_System/json_import_audit.json`.
- Semantic risk:
  - Note filenames, frontmatter aliases, tags, wikilinks, and relationship text can diverge from JSON contract.
- Validation available:
  - `tests/test_textifai_obsidian_setup.py`.
  - `tests/test_textifai_obsidian_integration.py`.
  - `docs/VAULT_SCHEMA.md`.

### 15. VaERL vault index / resolver

- Inputs:
  - Materialized vault Markdown or Obsidian bridge snapshot.
- Key files/functions:
  - `textifai/vaerl/index.py`.
  - `build_vault_index(...)`.
  - `textifai/vaerl/resolver.py`.
  - `resolve_text_against_vault(...)`.
  - `textifai/vaerl/matching.py`.
- Outputs:
  - In-memory `VaultIndexEntry` list and resolution results.
- Semantic risk:
  - Alias/project-confirmed alias matching and staging exclusion can change author-facing query behavior.
- Validation available:
  - `tests/test_textifai_vaerl_resolver.py`.
  - `tests/test_textifai_vaerl_contracts.py`.
  - `tests/test_textifai_obsidian_integration.py`.

### 16. Downstream replay

- Inputs:
  - Frozen input `99_System` containing `global_normalization.json` and `chapter_outputs/`.
  - Optional auxiliary documents.
- Key files/functions:
  - `run_semantic_ingestion_replay(...)` in `structured_bootstrap_v1.py`.
  - `textifai/import_review/auxiliary_ingestion.py`.
- Outputs:
  - Replayed downstream artifacts in a separate output root.
  - `semantic_replay_audit.json`.
  - Optional auxiliary source/chunk/extraction/enrichment artifacts.
- Semantic risk:
  - Good slice for deterministic downstream validation, but still writes output and must use safe fixtures/output roots.
- Validation available:
  - `uv run python scripts/textifai.py replay-downstream --help`.

## Artifact Map

| Artifact | Generator | Consumers | Contract role | Replayable | Risk if changed |
| --- | --- | --- | --- | --- | --- |
| `source_extraction_audit.json` | `prepare_obsidian_project` / `_write_source_extraction_audit` | humans/debug surfaces | audit/debug | yes | medium; may expose source previews and source selection behavior |
| `bootstrap_progress.jsonl` | setup progress appender | humans/debug surfaces | runtime audit | partial | low/medium; operational diagnostics |
| `model_plan_audit.json` | structured bootstrap model plan | humans/debug | audit/debug | yes | low/medium; affects provider diagnostics |
| `novel_index.json` | `build_novel_index` | global normalization, audits | critical upstream contract | no, input-derived | high; chapter IDs/metadata anchor later artifacts |
| `global_normalization_pass1.json` | pass1 builder | selective global normalization | contract-adjacent/debug | yes | medium; selection frontier |
| `ambiguous_entity_queue.json` | `build_ambiguous_entity_queue` | pass2/global debug | debug/quality | yes | medium; ambiguity visibility |
| `selective_normalization_trace.jsonl` | global normalization batching | humans/debug | debug/audit | yes | low/medium |
| `selective_normalization_metrics.json` | global normalization metrics | humans/debug | debug/audit | yes | low/medium |
| `global_normalization_pass2.json` | global LLM/pass2 artifact | compatibility assembly | critical semantic artifact | no provider-free | high |
| `global_normalization.json` | structured bootstrap | canonical map, replay input | critical compatibility frontier | input to replay | high |
| `global_batch_audit.json` | global batching | humans/debug | audit/debug | yes | medium |
| `canonical_entity_map.json` | `build_canonical_entity_map` | chapter extraction | critical extraction contract | yes from global | high; controls canonical guardrails |
| `chapter_outputs/*.json` | chapter extraction | resolution, assembly, replay input | critical semantic artifact | input to replay | high |
| `chapter_extraction_audit.json` | structured bootstrap | humans/debug | audit/debug | yes | medium |
| `chapters_enriched.json` | structured bootstrap | resolution context/debug | contract-adjacent | yes | medium |
| `resolved_entities.json` | `resolve_entity_clusters` | cleanup/reconciliation | critical intermediate | yes from replay input | high |
| `entity_clusters_audit.json` | resolver | humans/debug | audit/debug | yes | medium |
| `entity_resolution_audit.json` | resolver | humans/debug | audit/debug | yes | medium |
| `gender_signal_audit.json` | resolver/probe path | humans/debug | audit/debug | yes | low/medium |
| `semantic_context_probe_audit.json` | semantic context probe | humans/debug/viewer | diagnostic only | yes | medium; identifies contamination/merge candidates |
| `semantic_context_probe_trace.jsonl` | semantic context probe | humans/debug | diagnostic trace | yes | low/medium |
| `cleaned_entities.json` | cleanup + reconciliation + synthesis | assembly, invariants indirectly | critical intermediate | yes | high |
| `entity_cleanup_audit.json` | cleanup | humans/debug | audit/debug | yes | medium |
| `promotion_decisions_audit.json` | cleanup/promotion | humans/debug | audit/debug | yes | medium |
| `pre_vaerl_reconciliation_audit.json` | pre-VaERL reconciliation | humans/debug/viewer | audit/debug, contract-adjacent | yes | high if reconciliation policy changes |
| `primary_note_synthesis_audit.json` | primary note synthesis | humans/debug/viewer | audit/debug, contract-adjacent | yes | medium/high |
| `obsidian_relationship_reconciliation_audit.json` | relationship reconciliation | humans/debug/viewer | audit/debug, contract-adjacent | yes | high if relationship semantics change |
| `obsidian_import.json` | `assemble_obsidian_import` | Obsidian importer, VaERL invariants, viewer | critical public artifact contract | yes from replay | very high |
| `e2e_artifact_contract.json` | structured bootstrap | validation/debug | contract inventory | yes | medium |
| `playbook_boundary_audit.json` | structured bootstrap | diagnostics | audit/debug | yes | medium |
| `run_limits_audit.json` | structured bootstrap/replay | diagnostics | audit/debug | yes | low/medium |
| `run_comparability_manifest.json` | structured bootstrap/replay | viewer/compare | debug/compare contract | yes | medium/high for compare UX |
| `semantic_invariants_audit.json` | VaERL invariants | review queue, viewer, humans | critical validation artifact | yes | high |
| `review_queue.json` | review queue writer | CLI/viewer/humans | critical author-action artifact | yes | high |
| `semantic_replay_audit.json` | replay path | humans/debug | replay audit | yes | medium |
| `json_import_audit.json` | `import_json_to_vault` | humans/setup result | vault materialization audit | yes from import | medium |
| Markdown notes | `import_json_to_vault` | Obsidian, VaERL index, author flows | user-visible materialized contract | yes from import | very high |

## Contract Boundaries

Changes likely requiring Tier 3 semantic contract review:

- `obsidian_import.json` shape:
  - work metadata
  - entity list structure
  - `canonical_name`
  - `entity_kind`
  - `preferred_slug`
  - `aliases`
  - `key_facts`
  - `relationships`
  - `chapter_refs`
  - `source_mentions`
  - `review_state`
  - `confidence`
  - note role and visibility fields.
- Entity naming/slugs:
  - slug determinism
  - filename derivation
  - same-kind duplicate slug policy
  - cross-kind ontological collision handling.
- Relationship shape:
  - relationship `type`
  - `target`
  - evidence fields
  - whether target must resolve to primary.
- Review state/confidence:
  - canonical vs review/pending behavior.
  - thresholds that determine primary note materialization and review queue severity.
- Chapter refs/source mentions:
  - chapter ID format.
  - chapter order/sequence.
  - evidence/source mention retention.
- Review queue shape:
  - `schema_version`.
  - item fields.
  - `review_type`.
  - severity.
  - reason/actionability text.
- Invariant outputs:
  - check names.
  - pass/warn/fail statuses.
  - metrics used by viewer and QA surfaces.
- Obsidian materialization:
  - note paths.
  - frontmatter keys.
  - aliases/project-confirmed aliases.
  - tags.
  - wikilink format.
- VaERL assumptions:
  - resolver threshold and ambiguity margin.
  - match sources.
  - staging exclusion.
  - vault index entry fields.
- Replay/comparability:
  - replay input requirements.
  - `run_comparability_manifest.json` contents.
  - stable artifact inventory.

Lower-risk changes:

- Documentation-only recognition.
- New tests/fixtures that snapshot existing behavior without changing it.
- Read-only validation wrappers.
- Diagnostics that do not alter generated artifacts.

## Quality Degradation Points

- Input/chapter segmentation:
  - Source extraction can lose structure.
  - Chapterizer can split prose as headings or miss chapter boundaries.
  - Wrong chapter IDs become stable bad references.
- Language contamination:
  - Global normalization and chapter extraction must keep explanatory prose in work language while preserving names/titles.
  - Existing tests show this is already a known concern.
- Over-extraction:
  - Chapter extraction may emit local/trivial entities that later flood cleanup/review.
- Under-extraction:
  - Recurring but subtle entities can be missed if global selective sampling or chapter extraction filters too aggressively.
- Bad aliases:
  - Aliases from source mentions, descriptors, or titles can pollute canonical identity.
- Over-merge:
  - Similar names or title/descriptive aliases can collapse distinct entities.
- Under-merge:
  - Repeated entity variants can remain as separate review/noisy entities.
- Unstable slugs:
  - Display names, canonical candidates, and title-derived names feed filenames, wikilinks, and compare surfaces.
- Weak confidence/review state:
  - Borderline entities may be promoted or held with insufficient evidence.
- Relationship target mismatch:
  - Relationship targets may not resolve to canonical primaries.
  - Reconciliation adds `related_to` links only under explicit mention policy, but target matching remains brittle.
- Missing evidence:
  - Key facts and relationships can lack strong source mentions/chapter refs.
- Bad chapter refs:
  - Chapter refs generated in extraction or enriched during assembly can be incomplete or wrong.
- Review queue noise:
  - Queue quality depends on upstream review states and invariant checks; broad warnings can become low-signal.
- Obsidian materialization mismatch:
  - JSON contract can diverge from Markdown filenames/frontmatter/wikilinks.
- VaERL invariant gaps:
  - Current checks cover duplicates, relationships, counts, canonical strength, wikilinks, and orphan/unlinked signals.
  - They do not fully prove evidence quality, narrative state consistency, or author usefulness.

## Test / Fixture Gaps

Existing relevant tests:

- `tests/test_textifai_chapterizer.py`
  - Chapter boundary heuristics, multiline titles, Roman numeral false positives.
- `tests/test_textifai_structured_bootstrap_v1.py`
  - Large coverage of structured bootstrap helpers, deterministic index, normalization selection, language validation, canonical map, assembly, artifact writes, audits, slug targets, and incomplete extraction.
- `tests/test_textifai_vaerl_resolver.py`
  - Resolver matching, alias use, ambiguity, staging exclusion, primary priority, title token matching.
- `tests/test_textifai_vaerl_contracts.py`
  - VaERL dataclass contract shapes.
- `tests/test_textifai_import_review_contracts.py`
  - Import review contract catalogs and promotion shapes.
- `tests/test_textifai_obsidian_setup.py`
  - Setup/init behavior, wrapper entrypoints, readiness, plugin handling, ask trace persistence.
- `tests/test_textifai_obsidian_integration.py`
  - Markdown reader, bridge snapshot fallback, VaERL index from snapshot/markdown, reliability.
- `tests/test_textifai_web_viewer.py`
  - Viewer consumption of artifacts, review queue counts, wizard/job history/triage QA surfaces.
- `tests/test_textifai_derived_source_extractors.py`
  - Derived source extraction format detection.

Fixture gaps:

- No committed minimal end-to-end synthetic novel fixture observed for safe ingestion/VaERL snapshots.
- No approved baseline directory for `novel_index.json`, `global_normalization.json`, `chapter_outputs/*.json`, `resolved_entities.json`, `cleaned_entities.json`, `obsidian_import.json`, invariants, and review queue together.
- No small semantic edge fixture focused on alias collisions, over/under merge, descriptor canonicals, and relationship target mismatch.
- No dedicated VaERL fixture that isolates resolver/review queue behavior from LLM extraction.
- No Obsidian import fixture with expected Markdown filenames/frontmatter/wikilinks as stable snapshots.
- No replay baseline fixture that can run downstream deterministic stages without provider calls into temp output.

Recommended fixture classes already align with `docs/operations/safe-fixtures-and-baselines.md`:

- Minimal Novel Fixture.
- Semantic Edge Fixture.
- VaERL Fixture.
- Obsidian Import Fixture.
- Replay Baseline Fixture.

## Monolith / Refactor Risks

- `textifai/import_review/structured_bootstrap_v1.py`
  - Very large central file.
  - Owns prompts, config/result dataclasses, global normalization, chapter extraction, replay, artifact writes, audits, assembly, and multiple validation helpers.
  - High regression risk from broad edits.
  - First safe work should add external fixtures/snapshot tests rather than refactor internals.
- `textifai/import_review/entity_cluster_resolution.py`
  - High semantic leverage; handles merge identity, aliases, confidence, title/descriptor heuristics.
  - Needs semantic edge fixtures before behavior changes.
- `textifai/import_review/entity_cleanup.py`
  - Noise reduction/promotion policy can change primary counts and review queue shape.
  - Requires baseline metrics before tuning thresholds.
- `textifai/import_review/entity_reconciliation.py`
  - Directly impacts VaERL readiness and relationship targets.
  - Contract-adjacent.
- `textifai/vaerl/invariants.py`
  - Check names/statuses are consumed by viewer/QA surfaces.
  - Any status semantics change should be Tier 3.
- `textifai/vaerl/review_queue.py`
  - Author-action surface.
  - Noise/signal changes require fixture baselines.
- `textifai/obsidian/json_import.py`
  - User-visible vault materialization.
  - Filenames, wikilinks, frontmatter, and note layout are product contracts.
- `textifai/obsidian/setup.py`
  - Coordinates writes to vault and plugin.
  - Avoid using it for tests unless all outputs are temp dirs and provider calls mocked.

Zones not safe to touch without fixtures:

- Extraction prompts.
- Canonicalization/alias merge rules.
- Review state promotion thresholds.
- Relationship reconciliation policy.
- Obsidian note path/frontmatter/wikilink generation.
- Invariant status/check naming.

## Validation Surface

Safe read-only commands executed in this phase:

- `git status --short`
- `git log --oneline --grep='^safepoint-[0-9]\\{3\\}' -n 30`
- `codegraph status .`
- `uv run python scripts/textifai.py init --help`
- `uv run python scripts/textifai.py viewer --help`
- `uv run python scripts/textifai.py validate-vaerl --help`
- `uv run python scripts/textifai.py replay-downstream --help`
- `uv run python scripts/textifai.py review-queue --help`

Safe optional tests available:

- `uv run python -m unittest -v tests.test_textifai_web_viewer`
  - Viewer/job tests only; no real ingestion.

Validation commands not run because this is recognition-only and must not write artifacts:

- Real `init` ingestion.
- Real `replay-downstream`.
- Real `validate-vaerl` without redirected output.
- Provider-backed bootstrap/extraction.
- OnT runs.

## Recommended Core Improvement Roadmap

1. Phase 1.3.B — Safe Minimal Fixture Harness
   - Create tiny synthetic source fixture and temp-output test harness.
   - No provider calls.
   - Establish safe directories and baseline update policy.

2. Phase 1.3.C — Artifact Contract Snapshot Tests
   - Snapshot contract-relevant fields across minimal fixture artifacts.
   - Cover `obsidian_import.json`, review queue, invariants, slugs, chapter refs, relationships, and note paths.

3. Phase 1.3.D — Replay Baseline Harness
   - Use frozen `global_normalization.json` + `chapter_outputs/` fixture to replay deterministic downstream stages into temp dirs.
   - Make downstream iteration cheaper and safer.

4. Phase 1.3.E — Entity Extraction Noise Measurement
   - Add metrics around primary/review/noise entities before tuning behavior.
   - Detect trivial local entities and missing recurring entities without changing prompts yet.

5. Phase 1.3.F — Canonicalization/Alias Stability Improvements
   - Target one small alias/slug stability issue backed by semantic edge fixture.
   - Avoid broad resolver rewrites.

6. Phase 1.3.G — Review Queue Signal Quality
   - Improve actionability/severity after fixture baselines exist.
   - Measure false positives and high-priority review density.

7. Phase 1.3.H — Evidence/Source Span Plan
   - Design stronger evidence/source span retention.
   - Do not change artifact schema until Tier 3 contract plan is approved.

8. Phase 1.3.I — Narrative State Extraction Design
   - Recognize state/temporal facts and how they should flow to VaERL without corrupting canonical identity.

## Recommended First Implementation Slice

Recommended next phase:

`Phase 1.3.B — Safe Minimal Fixture Harness`

Why:

- Highest safety/impact ratio.
- Enables future core improvements without relying on real/private runs.
- Does not require semantic contract changes.
- Can be implemented with temp dirs and small committed fixture inputs.
- Prepares artifact snapshot tests, replay baselines, VaERL fixture tests, and Obsidian import fixture tests.
- Reduces risk before touching `structured_bootstrap_v1.py`, entity resolution, cleanup, or reconciliation behavior.

Suggested scope:

- Create `tests/fixtures/textifai/minimal_novel/` with 2-3 tiny synthetic chapters.
- Add helper for temp output roots that never writes real `runs/**` or `vault/**`.
- Add one smoke/snapshot test for deterministic source/chapter/index flow if provider-free.
- Document fixture update policy and expected future baselines.
- Do not call providers.
- Do not generate real vault/runs.

## Files Changed

- `docs/handoffs/safepoint-022_ingestion-to-vaerl-data-flow-recognition.md`

## Validation Performed

- `git status --short`
- `git log --oneline --grep='^safepoint-[0-9]\\{3\\}' -n 30`
- `codegraph status .`
- `uv run python scripts/textifai.py init --help`
- `uv run python scripts/textifai.py viewer --help`
- `uv run python scripts/textifai.py validate-vaerl --help`
- `uv run python scripts/textifai.py replay-downstream --help`
- `uv run python scripts/textifai.py review-queue --help`

No real ingestion, replay, provider call, OnT run, `runs/**` write, or `vault/**` write was performed.

## Semantic Contract Changes: NO

No semantic contract changed.

## Runtime Changes: NO

No runtime behavior changed.

## Write-back: NO

No write-back behavior changed.

## Generated Artifacts: NO

No generated artifacts were created or modified.

## Next Suggested Phase

Phase 1.3.B — Safe Minimal Fixture Harness.
