# Deterministic Chapter Manifest + Project-owned Evidence Store + EntityCard Runtime Fix

## Product Reading
TextifAI is author-first. VaERL is semantic source of truth. Markdown is editable author substrate. React/Tailwind is the main product face.

## Scope
SP-111 creates chapter manifest, evidence store, source map, and fixes EntityCard runtime wiring.

## Files Changed
- `textifai/import_review/source_structure.py`
- `textifai/import_review/evidence_store.py`
- `textifai/web_viewer/project_reader.py`
- `tests/test_textifai_source_structure_chapter_manifest.py`
- `tests/fixtures/textifai/source_structure_chapter_manifest/expected/*.json`
- `docs/handoffs/safepoint-111_source-structure-chapter-evidence.md`

## SP110 Context
SP-110 added EntityCardViewModel, review action model, and evidence modal. Evidence modal showed raw pointers; EntityCard showed 0 relations.

## Source Structure Classifier
Classifies source as chaptered/sectioned/unstructured. Recommends chapter_manifest_first for chaptered sources.

## Deterministic Chapter Splitter
Splits by Prólogo/Episodio/Capítulo/Interludio patterns. Creates Ch_001.md...Ch_020.md.

## Chapter Manifest
`chapters/chapter_manifest.json` with 20 chapters. Each chapter has id, order, title, display_title, markdown_path, char_count.

## Editor Chapter Source
Editor should consume chapter_manifest only. No vault tree, no rglob.

## Unstructured Document Policy
No fake chapters for unstructured sources. Direct chunking pipeline.

## Project-owned Source Map
`evidence/source_map.json` maps chapter_id to markdown_path with aliases.

## Project-owned Evidence Store
`evidence/evidence_index.json` with 70 evidence items linked to chapter markdown.

## Review Evidence Materialization
Evidence refs now include chapter_label, has_text boolean, excerpt when resoluble.

## EntityCard Runtime Wiring Fix
Ren now shows relation_count=15 (not 0). Author Markdown hides frontmatter. Alias classification active.

## Project / Run Status
source_structure: chaptered. chapter_manifest_ready: true. evidence_store_ready: true. safe_to_open_workspace: true.

## Private Decision Handoff
Private handoff path: `docs/handoffs/private/safepoint-111_source-structure-chapter-evidence/decision_handoff_private.md`

## Product Decision
Assessment: `chapter_manifest_ready_evidence_partial_entitycard_fixed`.

## Recommended Next Phase
Run next ingestion only after materializing `source_map.chunks[]` with resolvable chunk/source ranges.

## What Worked
- Chapter manifest with 20 chapters in order.
- Evidence store with 70 items linked to chapter markdown.
- EntityCard runtime now shows relations and classified aliases.
- Evidence modal shows chapter_label.

## What Failed
- Evidence excerpt resolution is partial: `evidence_excerpt_resolved_count=4` via markdown offsets; `source_map_chunks_count=0` blocks full hydration.
- Source splitter found 64 H1 headings in source; only 20 chapters were selected.

## Data Written
Chapter manifest, source map, evidence index in project package. Commit-safe reports only.

## Privacy / Non-committed Output
No source prose or raw provider outputs in commit-safe reports.

## Tests Added / Updated
Added `tests/test_textifai_source_structure_chapter_manifest.py`.

## Validation Performed
Python unit tests pass.

## Safety Constraints
No provider calls. No VaERL write-back. No new ingestion.

## Known Limitations
Evidence excerpt resolution from chunk-level source refs needs improvement.
Next ingestion must materialize `source_map.chunks[]`.

## Future Extensions
Chunk-level evidence resolution, draft persistence, entity picker, source resolution.

## Runtime Changes
Added source_structure and evidence_store modules. Updated review hydration.

## Write-back
No write-back.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
