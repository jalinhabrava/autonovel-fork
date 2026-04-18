# Architecture Notes

These notes describe the current TextifAI core as a layered system built on top of a vault-backed source of truth.

## Architectural Principles

### Core Is Agnostic To Narrative Domain

The core must not assume fantasy, magic, ritual, or any other specific setting. The vault used in tests or fixtures may contain those examples, but they are only examples.

The product logic should remain reusable for different genres and universes.

### Resolution Is Conservative

When the system cannot resolve an input safely, it should prefer:

- candidates
- ambiguity
- clarification

over false certainty.

### No Duplicate Retrieval

Resolution, context assembly, and editorial preparation are related but not the same job.

- VaERL resolves and anchors mentions against the vault
- Context Engine assembles context packs
- editorial layers transform the request into structured outputs

We should not rebuild retrieval logic independently in each layer.

### Vault Is The Source Of Truth

The vault owns the durable project knowledge:

- notes
- metadata
- links
- backlinks
- canonical artifacts
- document structure

TextifAI adds interpretation, workflow control, and structured outputs on top of that knowledge.

## Layer Model

The current core is organized as:

1. **CCE**
2. **VaERL**
3. **Editorial Structuring**
4. **Narration Prep**
5. **Context Engine**
6. **LLM Stage**

This is a pipeline of responsibilities, not just a list of packages.

## CCE

Conversational Context Extraction reads the user input and infers the request shape.

CCE is responsible for:

- detecting request intent
- identifying follow-up behavior
- extracting narrative signals
- extracting editorial signals
- identifying likely target types

CCE does not resolve against the vault by itself. It prepares the request for later anchoring.

## VaERL

Vault-aware Entity Resolution Layer (VaERL) is the anchor against the vault.

VaERL separates:

- detected mentions
- candidate entities
- final resolution
- confidence
- related artifact suggestions

It uses the vault structure conservatively:

- titles
- slugs
- aliases
- frontmatter metadata
- links
- backlinks
- artifact type

VaERL should not become semantic retrieval or fuzzy guesswork in the core. Its job is controlled anchoring.

## Editorial Structuring

Editorial structuring converts the interpreted request into usable intermediate results.

Current contracts include:

- `StoryFacts`
- `BeatOutline`
- `RevisionIntent`
- `EditorialStructuringResult`

This layer answers questions like:

- what happened
- what should change
- what should be preserved
- what structure is useful before narration

It must distinguish:

- explicit input from the author
- inferred editorial material from the system

That distinction is important because the system should not mix author facts and system inference invisibly.

## Narration Prep

Narration prep prepares context for narration later.

It does not narrate yet.

It can be built from:

- `BeatOutline`
- `StoryFacts`
- `RevisionIntent`
- a prior editorial result

Narration prep should collect only the context that is actually needed:

- voice
- canon
- continuity
- character anchors
- language constraints

## Context Engine

The Context Engine assembles a structured `context_pack`.

It is intentionally separate from VaERL:

- VaERL decides what an input refers to
- Context Engine decides what context should be assembled and how much should be rendered

The separation keeps the system explainable and avoids duplicated retrieval logic.

## LLM Stage

The LLM stage comes after the system has already decided:

- what the request is
- what it refers to
- what context should be shown
- what structure should be preserved

This keeps the model from having to solve everything from scratch.

## What The Vault Contributes

The vault contributes:

- durable artifacts
- canonical links
- structured notes
- metadata
- backlinks
- source-of-truth project memory

## What TextifAI Contributes

TextifAI contributes:

- request interpretation
- conservative resolution
- structured editorial outputs
- context selection
- workflow control
- persistence and validation primitives

The key point is that TextifAI is not the memory. It is the layer that reasons over the memory.

## Current Boundaries And Non-Goals

Not part of the current core:

- embeddings
- semantic retrieval
- fuzzy overreach in resolution
- GUI
- LibreChat
- MCP
- automatic narration as the primary end-state
- a fully autonomous editorial loop

These may exist later, but they should not be treated as current core assumptions.

## Core OSS And Future Premium

The open core currently includes:

- terminal runtime
- CCE
- VaERL
- editorial structuring
- narration prep
- Context Engine
- vault-backed persistence

A future premium or private layer, if any, should sit above this core and reuse the same principles rather than redefining them.

## Repo Organization Direction

The codebase should read as a product core plus supporting infrastructure:

- `textifai/` for product/runtime logic
- `context_engine/` for deterministic context assembly
- `interactive/` for internal vault and context operations
- `vault/` for storage and schema
- `providers/` for inference backends
- `stores/` for project storage abstraction
- `scripts/` for operational entrypoints

That layout keeps the architecture explainable without forcing premature abstraction.
