# TextifAI

TextifAI is a Semantic Story Engine for authors.

It turns manuscripts, lore notes, character sheets, future plans, and editorial corrections into a durable semantic model that can support writing, continuity, review, querying, and later author-facing chat.

TextifAI began as work inside an AutoNovel fork. The project now has its own product direction and identity. The original AutoNovel lineage remains credited because it provided useful historical pipeline ideas, but the active product is TextifAI.

## Why TextifAI Exists

Long fiction projects are hard to keep coherent.

Authors accumulate:

- chapters
- rewrites
- character sheets
- lore documents
- future plans
- contradictions
- unresolved notes
- memories that live only in the author's head

Most AI writing tools treat that material as either a long prompt, a flat document search index, or a static Codex. TextifAI takes a different route: it builds and maintains a semantic layer that the author can inspect, correct, replay, and use.

## What TextifAI Is Not

TextifAI is not just:

- another AI editor
- a Codex generator
- a Story Bible generator
- a chat over Markdown
- an Obsidian importer
- a prompt wrapper around a whole novel
- a fully autonomous writing agent

Those can all be views or workflows on top of TextifAI, but they are not the core.

## The Core Idea

TextifAI is built around VaERL: the Vault-aware Entity Resolution Layer.

VaERL is the semantic source of truth. It stores and exposes:

- chapters and summaries
- canonical entities
- aliases and source mentions
- relationships
- facts and relationship facts
- review states
- confidence
- tags and entity kinds
- unresolved or ambiguous material
- audit and replay metadata

Everything else should be a projection over VaERL:

- Codex View
- Story Bible View
- Review Queue
- Editor View
- Query Layer
- future free author chat

The LLM can synthesize, explain, summarize, and suggest. It does not silently own canon.

## ECC And VaERL

TextifAI uses two high-level ideas:

- ECC: editorial/context understanding of what the author is asking or importing.
- VaERL: grounded semantic resolution against the project vault and semantic artifacts.

ECC helps understand the task. VaERL anchors the task to the story's known entities, chapters, facts, review state, and evidence.

Together they let TextifAI answer questions such as:

- "What does Sera know before this event?"
- "Where have I already hinted at the Báculo?"
- "Does this chapter contradict the current canon?"
- "Which unresolved entities need author review?"
- "Can this lore document enrich the current story graph?"

## Current Product Shape

The active TextifAI rail can:

- ingest a novel from Markdown
- split chapters
- build deterministic structural indexes
- run semantic extraction and normalization
- resolve entities into canonical primaries and review candidates
- import the result into an Obsidian-style vault
- replay downstream semantic compilation from frozen artifacts
- ingest auxiliary author documents as a separate enrichment rail
- run Phase 1 semantic invariants over VaERL/vault outputs

This is currently local-first and developer-facing. The product direction is broader: TextifAI should become a semantic workbench for long-form fiction, not merely an import script.

## Why It Is Different

TextifAI is designed around these principles:

- VaERL is source of truth.
- Views are projections over VaERL.
- LLMs synthesize; they do not own canon.
- Review state and uncertainty stay visible.
- Author corrections should feed back into VaERL.
- Markdown is a first-class output.
- Replayability matters.
- Grounding beats giant prompts.

This makes TextifAI closer to a semantic story operating system than to a single editor pane.

## Documentation Map

- [Semantic Story Engine Roadmap](docs/TEXTIFAI_SEMANTIC_STORY_ENGINE_ROADMAP.md): technical-product vision and phase roadmap.
- [Architecture](docs/ARCHITECTURE.md): current low-level system architecture, entrypoints, pipeline, modules, and artifacts.
- [Bootstrap V1 Flow](docs/BOOTSTRAP_V1_FLOW.md): detailed active bootstrap/import flow.
- [Vault Schema](docs/VAULT_SCHEMA.md): vault layout, metadata, and artifact layout.
- [E2E Semantic Diagnosis Rules](docs/e2e_semantic_diagnosis_rules.md): diagnostic playbook for semantic ingestion runs.
- [Novel Index And Selective Normalization](docs/NOVEL_INDEX_AND_SELECTIVE_NORMALIZATION.md): metadata-first normalization design notes.

## Quick Start

```bash
cp .env.example .env
uv sync
```

Start the active TextifAI CLI:

```bash
uv run python scripts/textifai.py start
```

Bootstrap a vault from existing source material:

```bash
uv run python scripts/textifai.py init \
  --vault-root <vault-root> \
  --source-root <source-root>
```

Replay downstream semantic compilation from frozen artifacts:

```bash
uv run python scripts/textifai.py replay-downstream \
  --input-system <run>/99_System \
  --output-root <new-replay-run> \
  --language es
```

Validate Phase 1 VaERL invariants:

```bash
uv run python scripts/textifai.py validate-vaerl \
  --system-root <run>/99_System \
  --vault-root <materialized-vault> \
  --required-primary Ren \
  --required-primary Sera
```

## Current Boundary

TextifAI is usable today as a local semantic ingestion and vault compilation system. The next product layers are Codex View, Review Queue actions, Story Bible synthesis, Query Layer, free author chat, and eventually a Markdown editor.

See the roadmap for the current phase gates.

## Historical Credit

TextifAI grew out of experimentation in an AutoNovel fork and still preserves some legacy AutoNovel scripts and documents for reference. The active product rail is now TextifAI.

