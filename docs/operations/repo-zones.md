# Repository Zones

This document classifies repository areas by risk and expected approval level.

See also `docs/operations/semantic-contracts.md` for the rule that some files outside the core can still change semantic contracts.

## Critical Core — Explicit Approval Required

These areas define TextifAI semantic behavior, entity resolution, author understanding, contracts, and durable outputs. Touch them only with explicit approval and a validation plan.

- `textifai/import_review/structured_bootstrap_v1.py`
- `textifai/vaerl/**`
- `textifai/author_understanding/**`
- `textifai/editorial_intent/**`
- `textifai/conversation/**`
- `textifai/obsidian/json_import.py`
- `textifai/obsidian/parser.py`
- schema-related files
- invariant-related files
- resolver-related files

Never make semantic contract changes without explicit approval.

Files outside CRITICAL CORE may still cause semantic contract changes if they affect generated artifacts or downstream formats.

## Safe Docs / Operations

These areas are safe for operational documentation, handoffs, planning, and repo workflow notes.

- `docs/**`
- `docs/handoffs/**`
- `docs/operations/**`

Docs can still affect future operator behavior, so keep changes scoped and factual.

## Caution Tooling

These areas can change how users run, inspect, build, or integrate TextifAI. Treat them as tooling-sensitive.

- `scripts/textifai.py`
- `textifai/cli.py`
- `textifai/obsidian/cli.py`
- `textifai/web_viewer/**`
- `integrations/obsidian-textifai-bridge/**`

Changes here may not alter semantic contracts directly, but they can change runtime workflows, commands, integration behavior, or inspection surfaces.

## Preservation Zones

These areas may contain generated artifacts, user data, local state, runtime outputs, or secrets. Never touch preservation zones unless explicitly requested.

- `runs/**`
- `vault/**`
- `archive/**`
- `.textifai/**`
- `typeset/**`
- `results.tsv`
- `state.json`
- `.env`

Never commit secrets.

Never discard, overwrite, normalize, or clean preservation zones without explicit user approval.

If a preservation-zone file is already modified before a task starts, preserve it and report it in the handoff unless the user explicitly says otherwise.
