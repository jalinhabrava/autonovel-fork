# SP-122C Entity fiche writeback UI fix

## Root cause
- Save button gating required `loadedHash`.
- Entity card payload did not expose fiche `content_hash`.
- Result: `canSave` stayed false after edits.

## Fixes
- Added `markdown.content_hash` in `textifai/web_viewer/entity_card.py` from note file hash.
- Preserved author-facing editable body as note body only (no generated structured duplication).
- Added mini MDXEditor toolbar in fiche editor surface (`UndoRedo`, emphasis, block type, lists, link).

## Ren data hydration audit
- Structured cards remain outside MDX body.
- Aliases/relationships/evidence/backlinks/outgoing/local graph still rendered from VM fields.
- If data absent, cards show no-data states; no forced duplication in MDX.

## Runtime and visual proof
- Validated backend+UI contract via targeted unittest suites.
- React bundle rebuilt via `bash scripts/dev/textifai_react_build.sh`.
- Manual screenshot capture pending user runtime session.

## Non-goals preserved
- No semantic mutation.
- No VaERL write-back.
- No Graph regeneration.
- No Review regeneration.
