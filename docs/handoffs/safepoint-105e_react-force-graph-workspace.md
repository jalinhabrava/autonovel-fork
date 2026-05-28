# React Force Graph Workspace

## Product Reading
TextifAI Graph debe sentirse como workspace narrativo vivo, tipo Obsidian/Quartz, pero con inspector editorial fuerte para autores.

## Scope
- Añadir `react-force-graph-2d` en shell React.
- Crear adapter/view-model de grafo.
- Crear toolbar, canvas, inspector y modal draft.
- Integrar Graph en App sin LegacyEmbed primario.

## Files Changed
- `textifai/web_viewer/react_shell/src/graph/*`
- `textifai/web_viewer/react_shell/src/App.tsx`
- `textifai/web_viewer/react_shell/package.json`
- `textifai/web_viewer/react_shell/package-lock.json`
- `textifai/web_viewer/static/react-shell/*`
- tests y reports SP-105E.

## Architecture
Graph usa `react-force-graph-2d` para física, zoom, pan y canvas. TextifAI mantiene semántica editorial en `GraphDataAdapter`, `GraphToolbar`, `GraphInspector` y modal draft.

## UX
Filtros por tipo, búsqueda, solo relacionados, canvas con nodos/edges, selección, inspector derecho y acción Editar sin write-back.

## Validation
- Build React OK.
- Force graph tests OK.
- Workspace real project tests OK.
- React target parity tests OK.
- Review/product/stabilization/graph regressions OK.

## Safety
No provider calls. No write-back. No backend rewrite. No root package changes.

## Known Limitations
- Runtime real 20ch sigue ausente.
- Bundle supera 500k y pide code-splitting futuro.
- Story Bible sigue legacy boundary.

## Product Decision
`react_force_graph_workspace_ready_for_manual_review`

## Branch
`phase-1.3-ingestion-vaerl-hardening`
