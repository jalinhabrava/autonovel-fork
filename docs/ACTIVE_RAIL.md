# Active Rail

## Canonical Product

The canonical product in this repository is the TextifAI semantic ingestion and Obsidian/VaERL pipeline.

TextifAI work should center on semantic ingestion, VaERL, Obsidian import/export, author-facing inspection, review queues, replayability, and semantic validation.

## Canonical Entrypoints

Canonical TextifAI entrypoints are:

- `scripts/textifai.py`
- `textifai/obsidian/cli.py`

These entrypoints represent the active product rail for setup, ingestion, replay, inspection, VaERL validation, provider checks, review queues, and the internal viewer.

## Legacy / Historical Rail

The legacy AutoNovel drafting pipeline is preservation-only unless explicitly requested.

Legacy / historical entrypoints and areas include:

- `run_pipeline.py`
- `scripts/foundation/*`
- `scripts/drafting/*`
- `scripts/revision/*`

These files may remain useful as historical reference, but they are not the default place for new TextifAI work.

## Working Rule

Unless explicitly stated, new work MUST target the TextifAI rail only.

Legacy AutoNovel rail is preservation-only.

## Warning

Do not mix TextifAI semantic pipeline work with AutoNovel drafting pipeline work.

A change to TextifAI ingestion, VaERL, Obsidian, semantic replay, or author-facing semantic workflows must not silently alter legacy drafting, revision, or foundation-generation behavior.
