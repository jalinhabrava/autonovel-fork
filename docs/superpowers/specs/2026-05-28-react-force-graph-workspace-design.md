# React Force Graph Workspace Design

## Context
TextifAI usa React/Tailwind como cara principal. Graph actual en React existe, pero es SVG simple y no alcanza experiencia tipo Obsidian/Quartz. Producto pide equilibrio entre exploración viva y control editorial fuerte, con buena mantenibilidad y rendimiento.

## Goal
Reemplazar superficie actual de Graph por implementación basada en `react-force-graph-2d`, manteniendo datos reales de `/api/projects/<id>/graph`, UI editorial author-facing, y sin legacy fallback.

## Non-Goals
- No provider calls.
- No write-back real a Markdown o VaERL.
- No backend graph rewrite grande.
- No Story Bible rewrite en esta fase.
- No persistencia de layout manual todavía.

## Decision Summary
Se adopta `react-force-graph-2d` como motor único de Graph en shell React.

Razón:
- mejor equilibrio entre UX, rendimiento y mantenibilidad;
- evita rehacer physics/hit-testing/zoom/pan a mano;
- deja a TextifAI enfocar capa editorial e inspector.

## Architecture

### Layer Boundaries
- **GraphDataAdapter**
  - entrada: payload real `/graph`
  - salida: view model para canvas, filtros y inspector
- **GraphUXStore**
  - estado local de selección, búsqueda, filtros, cámara, pin, local graph toggle
- **GraphCanvas**
  - render canvas + interaction loop
- **GraphToolbar**
  - chips/filtros/search/viewport controls
- **GraphInspector**
  - ficha author-facing del nodo seleccionado
- **GraphNodeEditDraftModal**
  - affordance de edición sin write-back real

### Rule
Motor dibuja y simula. TextifAI decide semántica visual, labels, copy, acciones y estados review.

## UX Requirements

### Canvas Interactions
- zoom con rueda/trackpad;
- pan arrastrando fondo;
- drag node para recolocar temporalmente;
- click node selecciona y abre inspector derecho;
- doble click node centra y hace zoom suave;
- click fondo limpia selección si conviene al flujo.

### Toolbar
- filtros/chips: `Todo`, `Capítulos`, `Personajes`, `Lugares`, `Objetos`, `Eventos`, `Conceptos`, `Revisión`;
- búsqueda por label/path;
- toggle `Solo relacionados` para local graph del nodo seleccionado;
- acción `Mostrar todo` / reset viewport;
- opcional: `Ajustar al contenido`.

### Inspector
Mostrar:
- título;
- tipo;
- estado review/status;
- summary excerpt;
- facts preview si existen;
- relationship count / degree;
- note path.

Acciones:
- `Editar`;
- `Abrir en Story Bible` si contrato existe;
- `Ver relacionados`.

### Edit Draft Modal
- abre desde inspector;
- read-only o draft placeholder;
- copy explícito: guardado real llega con SP-106 drafts/patch queue;
- sin fake persistence.

## Visual Direction
- negro sobre blanco, neutral/editorial;
- edges gris claro;
- nodos con paleta sobria por tipo;
- ring negro para nodo seleccionado;
- labels priorizadas para selección, hover o zoom suficiente;
- no shell legacy visible;
- inspector fuerte a derecha.

## Performance Strategy
- usar canvas 2D, no SVG para grafo principal;
- limitar labels visibles para evitar clutter;
- aplicar filtros antes de render;
- desacoplar adapter de render;
- preparar clustering/local graph futuros sin romper API.

## Error Handling
- sin fallback legacy;
- si `/graph` falla, mostrar estado de error React con reintento;
- si payload parcial llega, render mejor esfuerzo + empty states claros.

## File Plan
Crear carpeta:
- `textifai/web_viewer/react_shell/src/graph/`

Archivos:
- `types.ts`
- `GraphDataAdapter.ts`
- `GraphCanvas.tsx`
- `GraphToolbar.tsx`
- `GraphInspector.tsx`
- `GraphNodeEditDraftModal.tsx`

Actualizar:
- `textifai/web_viewer/react_shell/src/App.tsx`
- `textifai/web_viewer/react_shell/src/api.ts` si necesita tipos menores
- tests React de graph/shell/parity

## Dependency Scope
Añadir solo en shell React:
- `react-force-graph-2d`

No tocar root package del repo.

## Testing
Agregar o actualizar tests para verificar:
- Graph no usa `LegacyEmbed` como primary;
- `react-force-graph-2d` importado/usado;
- toolbar/filtros/search presentes;
- inspector derecho presente;
- draft modal de edición presente;
- no provider calls;
- no write-back real;
- package changes limitados a shell React.

## Risks
- integración visual con Tailwind alrededor de canvas;
- labels excesivas pueden degradar UX;
- dataset 20ch real sigue ausente en runtime actual;
- selección/cámara deben sentirse estables para no parecer demo técnica.

## Open Questions Resolved
- fallback legacy: no;
- prioridad: equilibrio entre exploración viva y utilidad editorial;
- deadline/prisa: no;
- preferencia: mejor UX mantenible y con buen rendimiento.

## Implementation Recommendation
Hacer implementación incremental en una fase:
1. añadir dependencia;
2. montar adapter + canvas básico;
3. conectar toolbar/filtros;
4. conectar inspector + draft modal;
5. limpiar tests/handoff.
