# Branch & Milestone Workflow

## Purpose

TextifAI entra en fases sensibles de ingestion/VaERL. `main` no debe ser zona de experimentación directa.

Objetivo de esta política:

- mantener `main` estable y usable
- aislar trabajo de fase/hito en ramas dedicadas
- conservar trazabilidad por safepoint + handoff
- reducir riesgo al tocar contratos semánticos, replay y calidad VaERL

## Branch Roles

### `main`

- rama estable de referencia
- integra solo hitos cerrados y validados
- debe permanecer en estado usable

### Phase / milestone branches

- rama de trabajo activa por objetivo coherente
- recibe safepoints incrementales
- puede concentrar iteración técnica sin romper estabilidad de `main`

### Emergency / hotfix branches

- solo para correcciones urgentes sobre estado estable
- alcance mínimo
- validación rápida y merge controlado

## Recommended Active Branch

Rama recomendada para núcleo actual:

- `phase-1.3-ingestion-vaerl-hardening`

Uso esperado:

- phases 1.3.D+ (replay baseline, contracts, canonicalization, aliases, review queue quality, evidence/source handling, narrative state)

## Safepoint Policy

- safepoints pequeños y coherentes
- commit por iteración aprobada
- push por safepoint
- handoff versionado en `docs/handoffs/**`
- stage solo archivos de scope
- no stagear outputs/generated artifacts/secrets/local tooling state

## Merge Policy

- merge a `main` solo al cerrar hito coherente
- antes de merge:
  - validación acordada ejecutada
  - handoff de cierre del hito
  - revisión de scope y riesgos
- evitar merges parciales de experimentos no estabilizados

## Milestone Tag Policy

Tags opcionales al cierre de hito estable.

Ejemplos:

- `milestone-001-ingestion-vaerl-foundation`
- `milestone-002-narrative-harness-query-layer`

Regla:

- tag solo cuando la rama de hito ya fue integrada y validada

## Untracked Local Tooling Policy

Estado observado localmente:

- `.codegraph/` → estado local de tooling/indexado
- `.superpowers/` → estado local de tooling
- `package.json` (root) → archivo local no trazado
- `package-lock.json` (root) → archivo local no trazado

Política:

- `.codegraph/`:
  - tratar como estado local
  - no stagear, no commitear
  - mantener fuera de scope de safepoints
- `.superpowers/`:
  - tratar como estado local
  - no stagear, no commitear
  - mantener fuera de scope de safepoints
- `package.json` / `package-lock.json` en root:
  - no stagear ni commitear sin decisión explícita
  - primero confirmar si son tooling accidental o necesidad real de repo
  - si se decide ignorar/versionar, hacerlo en fase aparte con aprobación explícita

## Current Decision

Decisión actual de operación:

- crear/usar rama activa `phase-1.3-ingestion-vaerl-hardening`
- mantener `main` como base estable
- no modificar `.gitignore` en esta fase
- no borrar untracked persistentes locales

