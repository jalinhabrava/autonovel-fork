# Semantic Contract Boundaries

## Purpose

TextifAI is not only an application runtime. It is a semantic ingestion and knowledge graph pipeline.

Because of that, some code changes can alter downstream meaning, artifact shape, review semantics, vault projections, or replay compatibility even when tests pass.

This document distinguishes normal operational/runtime changes from semantic contract changes.

## Runtime / Operational Changes

These changes do not intentionally alter semantic meaning, generated artifact contracts, persisted vault structure, replay contracts, or review semantics.

Examples:

- logging
- CLI messaging
- docs
- viewer layout
- internal refactors that preserve outputs
- performance improvements that preserve deterministic artifacts
- non-semantic UX changes

These changes may use normal validation tiers depending on touched files.

## Semantic Contract Changes

Semantic contract changes alter how TextifAI represents, names, emits, validates, replays, or persists semantic knowledge and downstream artifacts.

Examples:

- entity schema changes
- relationship schema changes
- canonical naming logic
- slug generation
- chapter id generation
- source mention extraction
- confidence/review state logic
- resolver behavior
- VaERL invariants
- Obsidian note layout
- generated filenames
- `obsidian_import.json` structure
- `99_System` artifacts
- replay input/output contracts
- review queue shape
- primary note synthesis
- downstream replay behavior

These require explicit user approval before editing.

## Required Plan for Semantic Contract Changes

Before editing, Codex must provide:

- exact contract being changed
- current behavior
- proposed behavior
- affected files
- affected generated artifacts
- backwards compatibility risk
- migration need, if any
- validation plan
- rollback plan

## Required Validation for Semantic Contract Changes

Unless explicitly waived, validation must include:

- targeted tests if available
- replay or downstream validation
- invariant validation
- artifact diff or snapshot comparison when possible
- `git diff` review
- explicit note of expected output changes

Semantic contract changes should use fixture baselines or an explicit artifact diff strategy whenever possible. See `docs/operations/safe-fixtures-and-baselines.md`.

## Prohibited Without Approval

- silent schema changes
- silent filename changes
- silent slug changes
- silent canonicalization changes
- deleting or regenerating `runs/` or `vault/` outputs
- changing persisted note format without migration note

## Handoff Requirement

Every semantic contract change handoff must include:

- `SEMANTIC CONTRACT CHANGES: YES`
- changed contract
- validation performed
- expected downstream impact
- known compatibility risk
