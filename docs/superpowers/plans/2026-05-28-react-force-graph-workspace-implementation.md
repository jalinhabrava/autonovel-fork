# React Force Graph Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar Graph React actual por experiencia nativa con `react-force-graph-2d`, filtros editoriales, inspector derecho y draft modal sin write-back.

**Architecture:** Motor único `react-force-graph-2d` para render/interacción. Capa TextifAI separa adapter de datos, estado UX e inspector author-facing. Sin fallback legacy; errores de `/graph` se gestionan en React con retry.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, `react-force-graph-2d`, unittest Python para contratos de UI textual.

---

## File Structure (responsabilidad por archivo)

- `textifai/web_viewer/react_shell/src/graph/types.ts`
  - Tipos de nodo/arista/view-model para canvas e inspector.
- `textifai/web_viewer/react_shell/src/graph/GraphDataAdapter.ts`
  - Mapea payload `/graph` a estructura renderizable y filtrable.
- `textifai/web_viewer/react_shell/src/graph/GraphToolbar.tsx`
  - Chips de filtro, búsqueda, toggles de viewport/local graph.
- `textifai/web_viewer/react_shell/src/graph/GraphCanvas.tsx`
  - Render `ForceGraph2D`, zoom/pan/drag/click/double-click.
- `textifai/web_viewer/react_shell/src/graph/GraphInspector.tsx`
  - Inspector author-facing de nodo seleccionado.
- `textifai/web_viewer/react_shell/src/graph/GraphNodeEditDraftModal.tsx`
  - Modal de edición draft read-only/no write-back.
- `textifai/web_viewer/react_shell/src/App.tsx`
  - Integración pantalla Graph y wiring de estado.
- `textifai/web_viewer/react_shell/src/api.ts`
  - Ajustes menores de tipos si faltan campos.
- `tests/test_textifai_react_force_graph_workspace.py`
  - Tests de contrato de UI Graph nativa.
- `tests/test_textifai_react_workspace_real_project.py`
  - Ajustes de regresión SP-105D.

---

### Task 1: Añadir tests de contrato Graph nativo

**Files:**
- Create: `tests/test_textifai_react_force_graph_workspace.py`
- Modify: `tests/test_textifai_react_workspace_real_project.py`

- [ ] **Step 1: Write the failing test**

```python
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP = REPO / 'textifai/web_viewer/react_shell/src/App.tsx'
GRAPH_CANVAS = REPO / 'textifai/web_viewer/react_shell/src/graph/GraphCanvas.tsx'
GRAPH_TOOLBAR = REPO / 'textifai/web_viewer/react_shell/src/graph/GraphToolbar.tsx'
GRAPH_INSPECTOR = REPO / 'textifai/web_viewer/react_shell/src/graph/GraphInspector.tsx'
GRAPH_MODAL = REPO / 'textifai/web_viewer/react_shell/src/graph/GraphNodeEditDraftModal.tsx'
PKG = REPO / 'textifai/web_viewer/react_shell/package.json'

class TextifAIReactForceGraphWorkspaceTests(unittest.TestCase):
    def test_graph_uses_force_graph_library(self):
        self.assertTrue(GRAPH_CANVAS.exists())
        text = GRAPH_CANVAS.read_text(encoding='utf-8')
        self.assertIn("from 'react-force-graph-2d'", text)
        self.assertIn('ForceGraph2D', text)

    def test_graph_no_legacy_embed_primary(self):
        app = APP.read_text(encoding='utf-8')
        graph_start = app.index("if (active === 'graph')")
        graph_end = app.index("if (active === 'review')")
        graph_block = app[graph_start:graph_end]
        self.assertNotIn('LegacyEmbed', graph_block)

    def test_toolbar_filters_and_search_exist(self):
        text = GRAPH_TOOLBAR.read_text(encoding='utf-8')
        for label in ['Todo', 'Capítulos', 'Personajes', 'Lugares', 'Objetos', 'Eventos', 'Conceptos', 'Revisión', 'Solo relacionados']:
            self.assertIn(label, text)
        self.assertIn('Buscar nodo', text)

    def test_inspector_and_edit_draft_modal_exist(self):
        inspector = GRAPH_INSPECTOR.read_text(encoding='utf-8')
        modal = GRAPH_MODAL.read_text(encoding='utf-8')
        self.assertIn('Ficha del nodo', inspector)
        self.assertIn('Editar', inspector)
        self.assertIn('SP-106', modal)
        self.assertIn('No write-back', modal)

    def test_dependency_scope_shell_only(self):
        package = json.loads(PKG.read_text(encoding='utf-8'))
        self.assertIn('react-force-graph-2d', package['dependencies'])

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest -v tests.test_textifai_react_force_graph_workspace`
Expected: `FAIL` por archivos/componentes aún no creados.

- [ ] **Step 3: Commit test-first checkpoint**

```bash
git add tests/test_textifai_react_force_graph_workspace.py tests/test_textifai_react_workspace_real_project.py
git commit -m "test: add force graph workspace contract tests"
```

---

### Task 2: Añadir dependencia del motor de grafo

**Files:**
- Modify: `textifai/web_viewer/react_shell/package.json`
- Modify: `textifai/web_viewer/react_shell/package-lock.json`

- [ ] **Step 1: Install dependency**

Run: `cd textifai/web_viewer/react_shell && npm install react-force-graph-2d`
Expected: `package.json` y `package-lock.json` del shell actualizados.

- [ ] **Step 2: Verify dependency scope**

Run: `rg -n "react-force-graph-2d" textifai/web_viewer/react_shell/package.json package.json`
Expected: hit solo en package del shell React.

- [ ] **Step 3: Commit dependency scope**

```bash
git add textifai/web_viewer/react_shell/package.json textifai/web_viewer/react_shell/package-lock.json
git commit -m "build: add react-force-graph-2d in react shell only"
```

---

### Task 3: Implementar tipos y adapter de datos

**Files:**
- Create: `textifai/web_viewer/react_shell/src/graph/types.ts`
- Create: `textifai/web_viewer/react_shell/src/graph/GraphDataAdapter.ts`

- [ ] **Step 1: Add graph domain types**

```ts
// textifai/web_viewer/react_shell/src/graph/types.ts
export type GraphKind = 'chapter' | 'character' | 'concept' | 'event' | 'object' | 'place' | 'review' | 'note';

export type GraphCanvasNode = {
  id: string;
  label: string;
  kind: GraphKind;
  reviewState: string;
  notePath: string;
  summaryExcerpt: string;
  relationshipCount: number;
  degree: number;
  color: string;
};

export type GraphCanvasEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
};

export type GraphViewModel = {
  nodes: GraphCanvasNode[];
  edges: GraphCanvasEdge[];
  kinds: GraphKind[];
  byId: Record<string, GraphCanvasNode>;
};
```

- [ ] **Step 2: Add adapter with filter helpers**

```ts
// textifai/web_viewer/react_shell/src/graph/GraphDataAdapter.ts
import { GraphPayload } from '../api';
import { GraphCanvasEdge, GraphCanvasNode, GraphKind, GraphViewModel } from './types';

const DEFAULT_KIND: GraphKind = 'note';

export function mapGraphPayload(payload: GraphPayload | null | undefined): GraphViewModel {
  const rawNodes = payload?.nodes || [];
  const rawEdges = payload?.edges || [];

  const nodes: GraphCanvasNode[] = rawNodes
    .filter((node) => Boolean(node.id))
    .map((node) => {
      const kind = normalizeKind(String(node.display_kind || node.kind || DEFAULT_KIND));
      return {
        id: String(node.id),
        label: String(node.label || node.id || ''),
        kind,
        reviewState: String(node.review_state || node.status || 'unknown'),
        notePath: String(node.note_path || node.canonical_note_path || ''),
        summaryExcerpt: String(node.summary_excerpt || ''),
        relationshipCount: Number(node.relationship_count || node.degree || 0),
        degree: Number(node.degree || node.canonical_degree || 0),
        color: pickColor(kind),
      };
    });

  const edges: GraphCanvasEdge[] = rawEdges
    .filter((edge) => edge.source && edge.target)
    .map((edge) => ({
      id: String(edge.id || `${edge.source}-${edge.target}`),
      source: String(edge.source),
      target: String(edge.target),
      label: String(edge.label || edge.type || ''),
    }));

  const byId = Object.fromEntries(nodes.map((node) => [node.id, node]));
  const kinds = Array.from(new Set(nodes.map((node) => node.kind)));
  return { nodes, edges, kinds, byId };
}

export function filterGraph(vm: GraphViewModel, kind: string, query: string, relatedTo: string | null): GraphViewModel {
  const normalizedQuery = query.trim().toLowerCase();
  const kindFiltered = vm.nodes.filter((node) => (kind === 'all' ? true : node.kind === kind));
  const searchFiltered = kindFiltered.filter((node) => {
    if (!normalizedQuery) return true;
    return node.label.toLowerCase().includes(normalizedQuery) || node.notePath.toLowerCase().includes(normalizedQuery);
  });

  const visibleIds = new Set(searchFiltered.map((node) => node.id));
  if (relatedTo && visibleIds.has(relatedTo)) {
    const neighborIds = new Set<string>([relatedTo]);
    vm.edges.forEach((edge) => {
      if (edge.source === relatedTo) neighborIds.add(edge.target);
      if (edge.target === relatedTo) neighborIds.add(edge.source);
    });
    const relatedNodes = searchFiltered.filter((node) => neighborIds.has(node.id));
    const relatedIds = new Set(relatedNodes.map((node) => node.id));
    const relatedEdges = vm.edges.filter((edge) => relatedIds.has(edge.source) && relatedIds.has(edge.target));
    return { ...vm, nodes: relatedNodes, edges: relatedEdges, byId: Object.fromEntries(relatedNodes.map((n) => [n.id, n])) };
  }

  const edges = vm.edges.filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target));
  return { ...vm, nodes: searchFiltered, edges, byId: Object.fromEntries(searchFiltered.map((n) => [n.id, n])) };
}

function normalizeKind(kind: string): GraphKind {
  const value = kind.toLowerCase();
  if (['chapter', 'character', 'concept', 'event', 'object', 'place', 'review'].includes(value)) return value as GraphKind;
  return DEFAULT_KIND;
}

function pickColor(kind: GraphKind): string {
  const palette: Record<GraphKind, string> = {
    chapter: '#7f7a6a',
    character: '#111827',
    concept: '#6b7280',
    event: '#9a3412',
    object: '#0f766e',
    place: '#1d4ed8',
    review: '#b91c1c',
    note: '#525252',
  };
  return palette[kind];
}
```

- [ ] **Step 3: Run adapter-focused test subset**

Run: `uv run python -m unittest -v tests.test_textifai_react_force_graph_workspace::TextifAIReactForceGraphWorkspaceTests.test_graph_uses_force_graph_library`
Expected: aún `FAIL` (faltan componentes), pero types/adapter compilan luego en build.

- [ ] **Step 4: Commit adapter layer**

```bash
git add textifai/web_viewer/react_shell/src/graph/types.ts textifai/web_viewer/react_shell/src/graph/GraphDataAdapter.ts
git commit -m "feat: add graph view-model types and adapter"
```

---

### Task 4: Implementar toolbar + inspector + draft modal

**Files:**
- Create: `textifai/web_viewer/react_shell/src/graph/GraphToolbar.tsx`
- Create: `textifai/web_viewer/react_shell/src/graph/GraphInspector.tsx`
- Create: `textifai/web_viewer/react_shell/src/graph/GraphNodeEditDraftModal.tsx`

- [ ] **Step 1: Implement toolbar component**

```tsx
// textifai/web_viewer/react_shell/src/graph/GraphToolbar.tsx
import React from 'react';

const CHIP_LABELS = [
  { id: 'all', label: 'Todo' },
  { id: 'chapter', label: 'Capítulos' },
  { id: 'character', label: 'Personajes' },
  { id: 'place', label: 'Lugares' },
  { id: 'object', label: 'Objetos' },
  { id: 'event', label: 'Eventos' },
  { id: 'concept', label: 'Conceptos' },
  { id: 'review', label: 'Revisión' },
];

export function GraphToolbar(props: {
  activeKind: string;
  onKindChange: (kind: string) => void;
  query: string;
  onQueryChange: (value: string) => void;
  relatedOnly: boolean;
  onRelatedOnlyChange: (value: boolean) => void;
  onResetViewport: () => void;
}) {
  return (
    <div className="rounded-3xl border border-neutral-200 bg-neutral-50 p-4 space-y-3">
      <div className="flex flex-wrap gap-2">
        {CHIP_LABELS.map((chip) => (
          <button
            key={chip.id}
            type="button"
            onClick={() => props.onKindChange(chip.id)}
            className={`rounded-2xl px-3 py-1.5 text-sm ${props.activeKind === chip.id ? 'bg-neutral-900 text-white' : 'bg-white border border-neutral-200 text-neutral-700'}`}
          >
            {chip.label}
          </button>
        ))}
      </div>
      <input
        value={props.query}
        onChange={(event) => props.onQueryChange(event.target.value)}
        placeholder="Buscar nodo"
        className="w-full rounded-2xl border border-neutral-300 bg-white px-3 py-2 text-sm"
      />
      <div className="flex items-center justify-between">
        <label className="text-sm text-neutral-700 flex items-center gap-2">
          <input type="checkbox" checked={props.relatedOnly} onChange={(event) => props.onRelatedOnlyChange(event.target.checked)} />
          Solo relacionados
        </label>
        <button type="button" onClick={props.onResetViewport} className="rounded-2xl border border-neutral-200 bg-white px-3 py-1.5 text-sm">
          Mostrar todo
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Implement inspector + modal components**

```tsx
// textifai/web_viewer/react_shell/src/graph/GraphInspector.tsx
import React from 'react';
import { GraphCanvasNode } from './types';

export function GraphInspector({ node, onEdit }: { node: GraphCanvasNode | null; onEdit: (node: GraphCanvasNode) => void }) {
  if (!node) return <aside className="rounded-3xl border border-neutral-200 bg-white p-5 text-sm text-neutral-500">Ficha del nodo: selecciona un nodo.</aside>;
  return (
    <aside className="rounded-3xl border border-neutral-200 bg-white p-5 shadow-sm">
      <div className="text-xs uppercase tracking-wide text-neutral-500">Ficha del nodo</div>
      <h2 className="mt-2 text-xl font-semibold">{node.label}</h2>
      <div className="mt-2 text-sm text-neutral-600">{node.kind} · {node.reviewState}</div>
      <p className="mt-3 text-sm text-neutral-600">{node.summaryExcerpt || 'Sin resumen disponible.'}</p>
      <div className="mt-4 space-y-2 text-sm">
        <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-2">Relaciones: {node.relationshipCount}</div>
        <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-2">Ruta: {node.notePath || 'sin nota'}</div>
      </div>
      <button type="button" onClick={() => onEdit(node)} className="mt-4 rounded-2xl bg-neutral-900 px-4 py-2 text-sm text-white">Editar</button>
    </aside>
  );
}
```

```tsx
// textifai/web_viewer/react_shell/src/graph/GraphNodeEditDraftModal.tsx
import React from 'react';
import { GraphCanvasNode } from './types';

export function GraphNodeEditDraftModal({ node, onClose }: { node: GraphCanvasNode | null; onClose: () => void }) {
  if (!node) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="w-full max-w-2xl rounded-3xl border border-neutral-200 bg-white shadow-2xl">
        <div className="border-b border-neutral-200 p-5">
          <h3 className="font-semibold">Editar {node.label}</h3>
          <p className="text-sm text-neutral-500">Draft local. Guardado real llega en SP-106.</p>
        </div>
        <div className="p-5">
          <textarea readOnly className="h-52 w-full rounded-2xl border border-neutral-200 bg-neutral-50 p-3 text-sm" value={`No write-back\n\nRuta: ${node.notePath || 'sin nota'}`} />
          <button type="button" onClick={onClose} className="mt-4 rounded-2xl border border-neutral-200 px-4 py-2 text-sm">Cerrar</button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit UI side components**

```bash
git add textifai/web_viewer/react_shell/src/graph/GraphToolbar.tsx textifai/web_viewer/react_shell/src/graph/GraphInspector.tsx textifai/web_viewer/react_shell/src/graph/GraphNodeEditDraftModal.tsx
git commit -m "feat: add graph toolbar inspector and edit draft modal"
```

---

### Task 5: Implementar canvas `react-force-graph-2d`

**Files:**
- Create: `textifai/web_viewer/react_shell/src/graph/GraphCanvas.tsx`

- [ ] **Step 1: Implement force graph canvas**

```tsx
// textifai/web_viewer/react_shell/src/graph/GraphCanvas.tsx
import React, { useMemo, useRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { GraphCanvasEdge, GraphCanvasNode } from './types';

type GraphCanvasProps = {
  nodes: GraphCanvasNode[];
  edges: GraphCanvasEdge[];
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
};

export function GraphCanvas({ nodes, edges, selectedNodeId, onSelectNode }: GraphCanvasProps) {
  const fgRef = useRef<any>(null);
  const graphData = useMemo(() => ({ nodes: nodes.map((n) => ({ ...n })), links: edges.map((e) => ({ ...e })) }), [nodes, edges]);

  return (
    <div className="rounded-3xl border border-neutral-200 bg-white p-2 h-[640px]">
      <ForceGraph2D
        ref={fgRef}
        graphData={graphData}
        linkColor={() => '#d4d4d4'}
        linkWidth={1.1}
        nodeRelSize={6}
        nodeCanvasObject={(node: any, ctx, globalScale) => {
          const selected = node.id === selectedNodeId;
          ctx.beginPath();
          ctx.arc(node.x, node.y, selected ? 8 : 6, 0, 2 * Math.PI, false);
          ctx.fillStyle = node.color || '#525252';
          ctx.fill();
          if (selected) {
            ctx.lineWidth = 2;
            ctx.strokeStyle = '#111827';
            ctx.stroke();
          }
          const showLabel = selected || globalScale > 1.6;
          if (showLabel) {
            ctx.font = `${selected ? 13 : 11}px Inter, system-ui, sans-serif`;
            ctx.fillStyle = '#171717';
            ctx.fillText(String(node.label || node.id), node.x + 10, node.y + 3);
          }
        }}
        onNodeClick={(node: any) => onSelectNode(String(node.id))}
        onBackgroundClick={() => onSelectNode(null)}
        onNodeDragEnd={(node: any) => {
          node.fx = node.x;
          node.fy = node.y;
        }}
        onNodeRightClick={(node: any) => {
          if (!fgRef.current) return;
          fgRef.current.centerAt(node.x, node.y, 450);
          fgRef.current.zoom(2.2, 450);
        }}
      />
    </div>
  );
}
```

- [ ] **Step 2: Quick compile check**

Run: `cd textifai/web_viewer/react_shell && npm run build`
Expected: `built in ...` sin errores TS/Vite.

- [ ] **Step 3: Commit graph canvas**

```bash
git add textifai/web_viewer/react_shell/src/graph/GraphCanvas.tsx
git commit -m "feat: add force graph 2d canvas with core interactions"
```

---

### Task 6: Integrar GraphScreen en `App.tsx` y eliminar embed legacy

**Files:**
- Modify: `textifai/web_viewer/react_shell/src/App.tsx`

- [ ] **Step 1: Add imports and graph state wiring**

```tsx
import { mapGraphPayload, filterGraph } from './graph/GraphDataAdapter';
import { GraphCanvas } from './graph/GraphCanvas';
import { GraphToolbar } from './graph/GraphToolbar';
import { GraphInspector } from './graph/GraphInspector';
import { GraphNodeEditDraftModal } from './graph/GraphNodeEditDraftModal';
```

```tsx
const [graphKindFilter, setGraphKindFilter] = useState('all');
const [graphQuery, setGraphQuery] = useState('');
const [graphRelatedOnly, setGraphRelatedOnly] = useState(false);
const [graphEditNodeId, setGraphEditNodeId] = useState<string | null>(null);

const graphVm = useMemo(() => mapGraphPayload(graphPayload), [graphPayload]);
const filteredGraph = useMemo(
  () => filterGraph(graphVm, graphKindFilter, graphQuery, graphRelatedOnly ? selectedGraphNodeId : null),
  [graphVm, graphKindFilter, graphQuery, graphRelatedOnly, selectedGraphNodeId]
);
const selectedGraphNode = useMemo(() => (selectedGraphNodeId ? filteredGraph.byId[selectedGraphNodeId] || null : null), [filteredGraph, selectedGraphNodeId]);
const graphEditNode = useMemo(() => (graphEditNodeId ? filteredGraph.byId[graphEditNodeId] || null : null), [filteredGraph, graphEditNodeId]);
```

- [ ] **Step 2: Replace `active === 'graph'` block**

```tsx
if (active === 'graph') {
  content = (
    <section>
      <TopBar
        title="Graph"
        subtitle="Exploración visual author-facing con física viva e inspector editorial."
        actions={<Button variant="secondary">Contexto local</Button>}
      />
      <div className="p-5 grid grid-cols-12 gap-5">
        <aside className="col-span-12 xl:col-span-3">
          <GraphToolbar
            activeKind={graphKindFilter}
            onKindChange={setGraphKindFilter}
            query={graphQuery}
            onQueryChange={setGraphQuery}
            relatedOnly={graphRelatedOnly}
            onRelatedOnlyChange={setGraphRelatedOnly}
            onResetViewport={() => {
              setGraphKindFilter('all');
              setGraphQuery('');
              setGraphRelatedOnly(false);
            }}
          />
        </aside>
        <div className="col-span-12 xl:col-span-6">
          <GraphCanvas
            nodes={filteredGraph.nodes}
            edges={filteredGraph.edges}
            selectedNodeId={selectedGraphNodeId}
            onSelectNode={setSelectedGraphNodeId}
          />
        </div>
        <div className="col-span-12 xl:col-span-3">
          <GraphInspector node={selectedGraphNode} onEdit={(node) => setGraphEditNodeId(node.id)} />
        </div>
      </div>
      <GraphNodeEditDraftModal node={graphEditNode} onClose={() => setGraphEditNodeId(null)} />
    </section>
  );
}
```

- [ ] **Step 3: Delete legacy graph embedding path**

Remove:
```tsx
<LegacyEmbed title="Graph legacy dev fallback" ... />
```

- [ ] **Step 4: Commit integration**

```bash
git add textifai/web_viewer/react_shell/src/App.tsx
git commit -m "feat: integrate native force graph screen and remove legacy graph embed"
```

---

### Task 7: Validación completa + tests de regresión

**Files:**
- Modify: `tests/test_textifai_react_workspace_real_project.py` (si assertion cambia)

- [ ] **Step 1: Run Graph-specific tests**

Run:
```bash
uv run python -m unittest -v tests.test_textifai_react_force_graph_workspace
uv run python -m unittest -v tests.test_textifai_react_workspace_real_project
```
Expected: `OK`.

- [ ] **Step 2: Run required regressions**

Run:
```bash
uv run python -m unittest -v tests.test_textifai_react_ui_target_parity
uv run python -m unittest -v tests.test_textifai_review_workspace_cleanup
uv run python -m unittest -v tests.test_textifai_product_ux_architecture
uv run python -m unittest -v tests.test_textifai_author_workspace_stabilization
uv run python -m unittest -v tests.test_textifai_viewer_graph_architecture
```
Expected: `OK`.

- [ ] **Step 3: Build + endpoint checks**

Run:
```bash
cd textifai/web_viewer/react_shell && npm run build
cd /home/david/projects/autonovel-fork
curl -fsS http://127.0.0.1:8872/ >/tmp/sp105e_root.html
curl -fsS http://127.0.0.1:8872/api/projects >/tmp/sp105e_projects.json
```
Expected: sin errores; runtime sigue vivo.

- [ ] **Step 4: Commit validation-compatible test updates**

```bash
git add tests/test_textifai_react_workspace_real_project.py tests/test_textifai_react_ui_target_parity.py tests/test_textifai_react_force_graph_workspace.py
git commit -m "test: validate native force graph workspace contracts"
```

---

### Task 8: Handoff y cierre de fase

**Files:**
- Create: `docs/handoffs/safepoint-105e_react-force-graph-workspace.md`
- Create: `tests/fixtures/textifai/react_force_graph_workspace/expected/*.json`
- Create (gitignored): `docs/handoffs/private/safepoint-105e_react-force-graph-workspace/decision_handoff_private.md`

- [ ] **Step 1: Write commit-safe reports**

Create JSON reports with:
- graph engine selected;
- legacy graph removed from primary;
- filters/search/inspector/edit affordance;
- no provider calls;
- no write-back.

- [ ] **Step 2: Write public handoff**

Include:
- Product reading
- Scope
- Files changed
- SP105D context
- Force graph architecture
- UX interactions
- Validation
- Product decision
- Branch

- [ ] **Step 3: Commit handoff package**

```bash
git add docs/handoffs/safepoint-105e_react-force-graph-workspace.md tests/fixtures/textifai/react_force_graph_workspace/expected
git commit -m "safepoint-105e react force graph workspace"
```

- [ ] **Step 4: Final push**

Run:
```bash
git push origin phase-1.3-ingestion-vaerl-hardening
```
Expected: branch pushed.

---

## Self-Review Checklist

- Spec coverage: cubierto (motor único, sin fallback legacy, UX tipo Obsidian/Quartz, inspector, draft modal, rendimiento, no write-back).
- Placeholder scan: no hay `TBD`/`TODO`; instrucciones operativas concretas.
- Type consistency: `GraphViewModel`, `GraphCanvasNode`, `GraphCanvasEdge`, `GraphPayload` consistentes entre adapter/canvas/inspector.
