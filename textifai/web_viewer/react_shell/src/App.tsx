import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  Database,
  Eye,
  FileText,
  GitBranch,
  Inbox,
  Maximize2,
  MessageSquareText,
  Network,
  PenLine,
  Plus,
  Search,
  SplitSquareHorizontal,
  Upload,
  X,
} from 'lucide-react';
import {
  CanonEntity,
  GraphPayload,
  GraphNode,
  IngestionConfig,
  IngestionJob,
  ProjectDetail,
  ProjectSummary,
  ReviewItem,
  fetchArtifacts,
  fetchGraph,
  fetchIngestionConfig,
  fetchIngestionJobs,
  fetchNote,
  fetchProjectDetail,
  fetchProjects,
  fetchReviewQueue,
} from './api';
import { mapGraphPayload, filterGraph } from './graph/GraphDataAdapter';
import { GraphCanvas } from './graph/GraphCanvas';
import { GraphToolbar } from './graph/GraphToolbar';
import { GraphInspector } from './graph/GraphInspector';
import { GraphNodeEditDraftModal } from './graph/GraphNodeEditDraftModal';
import { GraphCanvasNode } from './graph/types';

type SectionId = 'hub' | 'ingest' | 'codex' | 'graph' | 'review' | 'editor' | 'story' | 'ask' | 'overview';
type ScreenConfig = { id: SectionId; label: string; icon: React.ComponentType<{ size?: number; className?: string }> };
type DecisionItem = { id: string; title: string; severity: string; source: string; action: string; raw: ReviewItem };
type EditDraft = { title: string; notePath?: string; body: string } | null;

const screens: ScreenConfig[] = [
  { id: 'hub', label: 'Project Hub', icon: BookOpen },
  { id: 'ingest', label: 'Ingestion', icon: Upload },
  { id: 'codex', label: 'Codex / VaERL', icon: Network },
  { id: 'graph', label: 'Graph', icon: GitBranch },
  { id: 'review', label: 'Review Queue', icon: Inbox },
  { id: 'editor', label: 'Editor', icon: PenLine },
  { id: 'story', label: 'Story Bible', icon: FileText },
  { id: 'ask', label: 'Ask Canon', icon: MessageSquareText },
];

const overviewCards: Array<{ id: SectionId; title: string; text: string; icon: ScreenConfig['icon'] }> = [
  { id: 'hub', title: '1. Project Hub', text: 'Abrir proyecto TextifAI completo vía manifest.json; .txtfai queda como dirección futura.', icon: Database },
  { id: 'ingest', title: '2. Ingestion', text: 'Preparar estructura estable de source, artifacts, vault y reportes.', icon: Upload },
  { id: 'codex', title: '3. Codex / VaERL', text: 'Inspeccionar entidades, aliases, hechos, evidencia y estado de revisión.', icon: Network },
  { id: 'graph', title: '4. Graph', text: 'Exploración visual nativa de entidades, capítulos, vínculos y warnings.', icon: GitBranch },
  { id: 'review', title: '5. Review Queue', text: 'Resolver avisos mediante decisiones explícitas del autor.', icon: Inbox },
  { id: 'editor', title: '6. Editor', text: 'Escritura y revisión de capítulos, no fichas primarias.', icon: SplitSquareHorizontal },
  { id: 'story', title: '7. Story Bible', text: 'Wiki Markdown author-facing con backlinks y provenance.', icon: FileText },
  { id: 'ask', title: '8. Ask Canon', text: 'Q&A grounded futuro sobre VaERL, evidencia e incertidumbre.', icon: MessageSquareText },
];

const kindLabels: Record<string, string> = { chapter: 'capítulo', character: 'personaje', concept: 'concepto', event: 'evento', object: 'objeto', place: 'lugar', review: 'revisión' };
const graphPalette: Record<string, string> = { chapter: '#7f7a6a', character: '#111827', concept: '#6b7280', event: '#9a3412', object: '#0f766e', place: '#1d4ed8', review: '#b91c1c' };

function isChapterNote(note: { path?: string; kind?: string; role?: string } | undefined): boolean {
  if (!note) return false;
  const kind = String(note.kind || note.role || '').toLowerCase();
  return kind === 'chapter' || String(note.path || '').toLowerCase().startsWith('chapters/');
}

function isMinimalFixture(project: ProjectSummary | null | undefined): boolean {
  return Boolean(project && (project.chapter_count || 0) > 0 && (project.chapter_count || 0) < 20);
}

function choosePreferredProject(projects: ProjectSummary[]): ProjectSummary | undefined {
  return [...projects].sort((a, b) => {
    const score = (project: ProjectSummary) => {
      const chapters = project.chapter_count || 0;
      const title = `${project.work?.title || ''} ${project.name || ''}`.toLowerCase();
      return (chapters >= 20 ? 10000 : 0) + chapters * 10 + (title.includes('20ch') || title.includes('20 capítulos') ? 50 : 0) + (project.recommended ? 25 : 0);
    };
    return score(b) - score(a);
  })[0];
}

function toDecisionItem(item: ReviewItem, index: number): DecisionItem {
  const source = item.source_entity || 'Entidad origen';
  const target = item.target_entity || 'Entidad relacionada';
  const severity = String(item.severity || 'low');
  const title = source && target ? `${source} / ${target}` : source || target || `Decisión ${index + 1}`;
  return {
    id: `${title}-${index}`,
    title,
    severity,
    source: (item.evidence_refs || []).map((row) => row.chapter_id || row.pointer || 'evidencia').slice(0, 2).join(', ') || 'Evidencia pendiente',
    action: item.recommendation || item.review_type || 'Necesita decisión del autor',
    raw: item,
  };
}

function severityClass(level: string): string {
  const normalized = level.toLowerCase();
  if (normalized === 'high') return 'bg-red-100 text-red-700';
  if (normalized === 'medium') return 'bg-amber-100 text-amber-700';
  return 'bg-neutral-200 text-neutral-700';
}

function legacyUrl(view: 'graph' | 'notes' | 'canon', projectId: string): string {
  return `/index.html?embed=1&view=${encodeURIComponent(view)}&project=${encodeURIComponent(projectId)}`;
}

function Shell({ active, setActive, children }: { active: SectionId; setActive: (id: SectionId) => void; children: React.ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  return (
    <div className="min-h-screen h-screen bg-neutral-100 text-neutral-900 p-2 md:p-4 overflow-hidden">
      <div className="mx-auto w-full max-w-none h-full rounded-3xl bg-white shadow-xl overflow-hidden border border-neutral-200">
        <header className="flex items-center justify-between border-b border-neutral-200 px-5 py-4 bg-neutral-50">
          <button type="button" onClick={() => setActive('overview')} className="text-left">
            <div className="text-xl font-bold tracking-tight">TextifAI</div>
            <div className="text-xs text-neutral-500">Narrative semantic engine · author-facing VaERL workspace</div>
          </button>
          <div className="flex items-center gap-2 text-xs"><StatusChip>Local project</StatusChip><StatusChip>VaERL ready</StatusChip></div>
        </header>
        <div className="grid grid-cols-12 h-[calc(100%-73px)] min-h-0">
          <aside className="col-span-12 md:col-span-2 border-r border-neutral-200 bg-neutral-50 p-3 flex min-h-0 flex-col">
            <SidebarNav active={active} setActive={setActive} />
            <div className="mt-auto pt-4 relative">
              {menuOpen ? <div className="absolute bottom-16 left-0 right-0 z-20 rounded-2xl border border-neutral-200 bg-white p-2 shadow-xl text-sm">
                <button type="button" onClick={() => { setSettingsOpen(true); setMenuOpen(false); }} className="w-full rounded-xl px-3 py-2 text-left hover:bg-neutral-100">Ajustes</button>
                <button type="button" onClick={() => setActive('hub')} className="w-full rounded-xl px-3 py-2 text-left hover:bg-neutral-100">Proyecto / Workspace</button>
                <button type="button" className="w-full rounded-xl px-3 py-2 text-left text-neutral-500" disabled>Dev tools · pendiente</button>
              </div> : null}
              <button type="button" onClick={() => setMenuOpen((value) => !value)} className="w-full rounded-2xl border border-neutral-200 bg-white p-3 text-left hover:bg-neutral-100">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-neutral-900 text-white font-semibold">A</div>
                  <div className="min-w-0 flex-1"><div className="truncate text-sm font-semibold">Autor local</div><div className="text-xs text-neutral-500">Workspace privado</div></div>
                  <ChevronDown size={16} />
                </div>
              </button>
            </div>
          </aside>
          <main className="col-span-12 md:col-span-10 bg-white min-h-0 overflow-y-auto">{children}</main>
        </div>
      </div>
      {settingsOpen ? <SettingsModal onClose={() => setSettingsOpen(false)} /> : null}
    </div>
  );
}

function SettingsModal({ onClose }: { onClose: () => void }) {
  return <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/30 p-4"><div className="w-full max-w-2xl rounded-3xl border border-neutral-200 bg-white shadow-2xl"><div className="flex items-center justify-between border-b border-neutral-200 p-5"><div><h2 className="text-lg font-semibold">Ajustes</h2><p className="text-sm text-neutral-500">Preferencias author-facing. Sin persistencia en SP-105D.</p></div><button type="button" onClick={onClose} className="rounded-full p-2 hover:bg-neutral-100"><X size={18} /></button></div><div className="grid gap-4 p-5 md:grid-cols-2 text-sm">{['Apariencia', 'Idioma', 'Proyecto', 'Dev/debug'].map((title) => <div key={title} className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4"><h3 className="font-semibold">{title}</h3><p className="mt-2 text-neutral-600">Placeholder honesto: guardado de preferencias llega después.</p></div>)}</div></div></div>;
}

function SidebarNav({ active, setActive }: { active: SectionId; setActive: (id: SectionId) => void }) {
  return <><nav className="space-y-1">{screens.map((screen) => { const Icon = screen.icon; const selected = active === screen.id; return <button key={screen.id} onClick={() => setActive(screen.id)} className={`flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left text-sm transition ${selected ? 'bg-neutral-900 text-white' : 'text-neutral-700 hover:bg-neutral-200'}`}><Icon size={17} /><span>{screen.label}</span></button>; })}</nav><div className="mt-5 rounded-3xl bg-white border border-neutral-200 p-4 text-xs text-neutral-500"><b className="text-neutral-900">Local-first</b><br />Abre un proyecto TextifAI completo. Nada de navegación arbitraria por filesystem.</div></>;
}

function StatusChip({ children }: { children: React.ReactNode }) { return <span className="rounded-full border border-neutral-200 bg-white px-3 py-1 text-neutral-600">{children}</span>; }
function Button({ children, variant = 'primary', disabled = false, onClick }: { children: React.ReactNode; variant?: 'primary' | 'secondary'; disabled?: boolean; onClick?: () => void }) { return <button type="button" disabled={disabled} onClick={onClick} className={`rounded-2xl px-4 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50 ${variant === 'primary' ? 'bg-neutral-900 text-white' : 'bg-neutral-100 text-neutral-800 border border-neutral-200'}`}>{children}</button>; }
function Metric({ label, value, note }: { label: string; value: React.ReactNode; note: string }) { return <div className="rounded-3xl border border-neutral-200 bg-white p-5 shadow-sm"><div className="text-xs uppercase tracking-wide text-neutral-500">{label}</div><div className="mt-2 text-3xl font-semibold tracking-tight">{value}</div><p className="mt-2 text-sm text-neutral-500">{note}</p></div>; }
function TopBar({ title, subtitle, actions }: { title: string; subtitle: string; actions?: React.ReactNode }) { return <div className="flex flex-col gap-3 border-b border-neutral-200 bg-neutral-50 p-5 lg:flex-row lg:items-center lg:justify-between"><div><h1 className="text-2xl font-semibold tracking-tight">{title}</h1><p className="mt-1 text-sm text-neutral-500">{subtitle}</p></div><div className="flex flex-wrap gap-2">{actions}</div></div>; }
function ProjectRow({ project, selected, onSelect }: { project: ProjectSummary; selected?: boolean; onSelect: () => void }) { const title = project.work?.title || project.name || 'Proyecto narrativo'; return <button onClick={onSelect} className={`w-full rounded-2xl border p-4 grid grid-cols-12 gap-3 items-center text-left ${selected ? 'bg-neutral-900 text-white border-neutral-900' : 'bg-white border-neutral-200 hover:bg-neutral-50'}`}><div className="col-span-12 md:col-span-7"><div className="font-semibold">{title}</div><div className={`text-xs ${selected ? 'text-neutral-300' : 'text-neutral-500'}`}>{project.kind || 'workspace'} · {project.work?.language || 'idioma pendiente'}</div></div><div className="col-span-4 md:col-span-2 text-sm">{project.chapter_count || 0} capítulos</div><div className="col-span-4 md:col-span-2 text-sm">{project.graph_summary?.node_count || 0} nodos</div><div className="col-span-4 md:col-span-1 text-sm">{isMinimalFixture(project) ? 'dev fixture' : 'real'}</div></button>; }

function DecisionCard({ item, selected, onSelect }: { item: DecisionItem; selected?: boolean; onSelect: () => void }) { return <button onClick={onSelect} className={`w-full rounded-3xl border p-4 text-left ${selected ? 'border-neutral-900 bg-neutral-50' : 'border-neutral-200 bg-white hover:bg-neutral-50'}`}><div className="flex items-center justify-between gap-3"><h3 className="font-semibold">{item.title}</h3><span className={`rounded-full px-2 py-1 text-xs ${severityClass(item.severity)}`}>{item.severity}</span></div><p className="mt-2 text-sm text-neutral-600">{item.action}</p><p className="mt-3 text-xs text-neutral-500">Evidencia: {item.source}</p></button>; }
function EntityRecordTable({ entities, selectedKey, onSelect }: { entities: CanonEntity[]; selectedKey: string; onSelect: (key: string) => void }) { return <div className="overflow-hidden rounded-3xl border border-neutral-200"><div className="grid grid-cols-12 bg-neutral-100 px-4 py-3 text-xs uppercase tracking-wide text-neutral-500"><span className="col-span-5">Entidad</span><span className="col-span-2">Tipo</span><span className="col-span-2">Confianza</span><span className="col-span-3">Estado</span></div>{entities.slice(0, 18).map((entity) => { const key = entity.preferred_slug || entity.canonical_name || ''; const active = key === selectedKey; return <button key={key} onClick={() => onSelect(key)} className={`w-full grid grid-cols-12 px-4 py-3 text-sm border-t border-neutral-200 items-center text-left ${active ? 'bg-neutral-50' : 'bg-white hover:bg-neutral-50'}`}><span className="col-span-5 font-medium">{entity.canonical_name || key}</span><span className="col-span-2 text-neutral-500">{entity.entity_kind || 'entity'}</span><span className="col-span-2 text-neutral-500">{entity.confidence ?? '—'}</span><span className="col-span-3 text-neutral-500">{entity.review_state || 'ready'}</span></button>; })}</div>; }
function InspectorCard({ entity }: { entity: CanonEntity | undefined }) { if (!entity) return <div className="rounded-3xl border border-neutral-200 p-5 text-sm text-neutral-500">Selecciona un record para abrir inspector.</div>; return <div className="rounded-3xl border border-neutral-200 bg-neutral-50 p-5"><div className="text-xs uppercase tracking-wide text-neutral-500">Inspector</div><h2 className="mt-2 text-xl font-semibold">{entity.canonical_name}</h2><p className="mt-3 text-sm leading-6 text-neutral-600">{entity.summary || 'Sin resumen author-facing disponible todavía.'}</p><div className="mt-4 flex flex-wrap gap-2">{(entity.aliases || []).slice(0, 6).map((alias) => <span key={alias} className="rounded-full bg-white border border-neutral-200 px-3 py-1 text-xs">{alias}</span>)}</div><Button variant="secondary">Editar ficha · draft</Button></div>; }
function LegacyEmbed({ title, src }: { title: string; src: string }) { return <div className="rounded-3xl border border-neutral-200 bg-white p-3 shadow-sm"><div className="mb-3 text-xs uppercase tracking-wide text-neutral-500">{title}</div><iframe title={title} src={src} className="h-[620px] w-full rounded-2xl border border-neutral-200 bg-white" /></div>; }

function OverviewBoard({ setActive }: { setActive: (id: SectionId) => void }) { return <section><TopBar title="TextifAI Workspace" subtitle="Local-first ahora; SaaS-ready después. VaERL manda, Markdown se edita." actions={<Button onClick={() => setActive('hub')}>Abrir proyecto</Button>} /><div className="grid grid-cols-12 gap-5 p-5">{overviewCards.map((card) => { const Icon = card.icon; return <button key={card.id} onClick={() => setActive(card.id)} className="col-span-12 rounded-3xl border border-neutral-200 bg-white p-5 text-left shadow-sm hover:bg-neutral-50 md:col-span-6 xl:col-span-3"><div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-neutral-900 text-white"><Icon size={18} /></div><h3 className="mt-4 font-semibold">{card.title}</h3><p className="mt-2 text-sm leading-6 text-neutral-500">{card.text}</p></button>; })}</div></section>; }

function NativeGraphSurface({ graph, selectedNodeId, setSelectedNodeId, setEditDraft }: { graph: GraphPayload | null; selectedNodeId: string; setSelectedNodeId: (id: string) => void; setEditDraft: (draft: EditDraft) => void }) {
  const [kindFilter, setKindFilter] = useState('all');
  const nodes = graph?.nodes || [];
  const edges = graph?.edges || [];
  const kinds = Array.from(new Set(nodes.map((node) => String(node.display_kind || node.kind || 'note'))));
  const visibleNodes = nodes.filter((node) => kindFilter === 'all' || String(node.display_kind || node.kind || 'note') === kindFilter);
  const visibleIds = new Set(visibleNodes.map((node) => node.id));
  const visibleEdges = edges.filter((edge) => visibleIds.has(String(edge.source)) && visibleIds.has(String(edge.target)));
  const selected = nodes.find((node) => node.id === selectedNodeId) || visibleNodes[0];
  const positioned = visibleNodes.map((node, index) => { const angle = (index / Math.max(visibleNodes.length, 1)) * Math.PI * 2; const ring = 180 + (index % 3) * 35; return { ...node, x: 380 + Math.cos(angle) * ring, y: 260 + Math.sin(angle) * ring }; });
  const byId = new Map(positioned.map((node) => [node.id, node]));
  return <div className="grid grid-cols-12 gap-5 p-5"><aside className="col-span-12 xl:col-span-2 rounded-3xl border border-neutral-200 bg-neutral-50 p-4"><h2 className="font-semibold">Filtros</h2><div className="mt-4 flex flex-wrap gap-2 xl:block xl:space-y-2">{['all', ...kinds].map((kind) => <button key={kind} onClick={() => setKindFilter(kind)} className={`rounded-2xl px-3 py-2 text-sm xl:w-full xl:text-left ${kindFilter === kind ? 'bg-neutral-900 text-white' : 'bg-white border border-neutral-200 text-neutral-700'}`}>{kind === 'all' ? 'Todo' : kindLabels[kind] || kind}</button>)}</div></aside><div className="col-span-12 xl:col-span-7 rounded-3xl border border-neutral-200 bg-neutral-50 p-4"><div className="mb-3 flex items-center justify-between"><div><h2 className="font-semibold">Grafo VaERL</h2><p className="text-sm text-neutral-500">SVG React nativo sobre `/graph`. Sin iframe legacy como primary.</p></div><StatusChip>{visibleNodes.length} nodos</StatusChip></div><svg viewBox="0 0 760 520" className="h-[560px] w-full rounded-2xl bg-white border border-neutral-200">{visibleEdges.map((edge) => { const source = byId.get(String(edge.source)); const target = byId.get(String(edge.target)); if (!source || !target) return null; return <line key={edge.id || `${edge.source}-${edge.target}`} x1={source.x} y1={source.y} x2={target.x} y2={target.y} stroke="#d4d4d4" strokeWidth="1.5" />; })}{positioned.map((node) => { const kind = String(node.display_kind || node.kind || 'note'); const active = selected?.id === node.id; return <g key={node.id} onClick={() => setSelectedNodeId(node.id || '')} className="cursor-pointer"><circle cx={node.x} cy={node.y} r={active ? 16 : Number(node.radius || 11)} fill={graphPalette[kind] || '#525252'} stroke={active ? '#111827' : '#ffffff'} strokeWidth={active ? 4 : 2} /><text x={node.x + 18} y={node.y + 4} fontSize="12" fill="#171717">{node.label || node.id}</text></g>; })}</svg></div><GraphInspector node={selected} setEditDraft={setEditDraft} /></div>;
}

function GraphInspector({ node, setEditDraft }: { node?: GraphNode; setEditDraft: (draft: EditDraft) => void }) {
  if (!node) return <aside className="col-span-12 xl:col-span-3 rounded-3xl border border-neutral-200 p-5 text-sm text-neutral-500">Selecciona un nodo.</aside>;
  const kind = String(node.display_kind || node.kind || 'note');
  return <aside className="col-span-12 xl:col-span-3 rounded-3xl border border-neutral-200 bg-white p-5 shadow-sm"><div className="text-xs uppercase tracking-wide text-neutral-500">Ficha del nodo</div><h2 className="mt-2 text-xl font-semibold">{node.label || node.id}</h2><div className="mt-2 flex flex-wrap gap-2"><span className="rounded-full bg-neutral-100 px-3 py-1 text-xs">{kindLabels[kind] || kind}</span><span className="rounded-full bg-neutral-100 px-3 py-1 text-xs">{node.review_state || node.status || 'sin estado'}</span></div><p className="mt-4 text-sm leading-6 text-neutral-600">{node.summary_excerpt || 'Sin resumen hidratado para este nodo.'}</p><div className="mt-4 grid gap-2 text-sm"><div className="rounded-2xl bg-neutral-50 border border-neutral-200 p-3">Relaciones: {node.relationship_count ?? node.degree ?? 0}</div><div className="rounded-2xl bg-neutral-50 border border-neutral-200 p-3">Nota: {node.note_path || node.canonical_note_path || 'pendiente'}</div></div><div className="mt-5 flex flex-wrap gap-2"><Button onClick={() => setEditDraft({ title: `Editar ${node.label || node.id}`, notePath: node.note_path || node.canonical_note_path, body: 'Draft local/read-only. Guardar cambios llegará con SP-106 drafts/patch queue.' })}>Editar</Button><Button variant="secondary">Abrir ficha</Button></div></aside>;
}

export function App() {
  const [active, setActive] = useState<SectionId>('overview');
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [projectDetail, setProjectDetail] = useState<ProjectDetail | null>(null);
  const [ingestionConfig, setIngestionConfig] = useState<IngestionConfig | null>(null);
  const [ingestionJobs, setIngestionJobs] = useState<IngestionJob[]>([]);
  const [selectedEntityKey, setSelectedEntityKey] = useState<string>('');
  const [reviewQuery, setReviewQuery] = useState('');
  const [reviewSeverity, setReviewSeverity] = useState('all');
  const [selectedDecisionId, setSelectedDecisionId] = useState<string>('');
  const [editorNotePath, setEditorNotePath] = useState<string>('');
  const [editorMarkdown, setEditorMarkdown] = useState<string>('');
  const [editorFullscreen, setEditorFullscreen] = useState(false);
  const [graphPayload, setGraphPayload] = useState<GraphPayload | null>(null);
  const [selectedGraphNodeId, setSelectedGraphNodeId] = useState<string>('');
  const [graphKindFilter, setGraphKindFilter] = useState<string>('all');
  const [graphQuery, setGraphQuery] = useState('');
  const [graphRelatedOnly, setGraphRelatedOnly] = useState(false);
  const [graphEditNodeId, setGraphEditNodeId] = useState<string | null>(null);
  const [artifactsCount, setArtifactsCount] = useState<number>(0);
  const [editDraft, setEditDraft] = useState<EditDraft>(null);
  const [error, setError] = useState<string>('');

  const selectedProject = useMemo(() => projects.find((project) => project.project_id === selectedProjectId) || null, [projects, selectedProjectId]);
  const selectedEntity = useMemo(() => (projectDetail?.canon?.primaries || []).find((entity) => (entity.preferred_slug || entity.canonical_name || '') === selectedEntityKey), [projectDetail, selectedEntityKey]);
  const chapterNotes = useMemo(() => (projectDetail?.notes || []).filter(isChapterNote), [projectDetail]);
  const allDecisions = useMemo(() => (projectDetail?.canon?.review_queue?.items || []).map(toDecisionItem), [projectDetail]);
  const visibleDecisions = useMemo(() => { const query = reviewQuery.trim().toLowerCase(); return allDecisions.filter((item) => { if (reviewSeverity !== 'all' && item.severity.toLowerCase() !== reviewSeverity) return false; if (!query) return true; return item.title.toLowerCase().includes(query) || item.action.toLowerCase().includes(query) || String(item.raw.review_type || '').toLowerCase().includes(query); }); }, [allDecisions, reviewQuery, reviewSeverity]);
  const selectedDecision = useMemo(() => visibleDecisions.find((item) => item.id === selectedDecisionId) || visibleDecisions[0] || null, [visibleDecisions, selectedDecisionId]);

  useEffect(() => { void loadInitial(); }, []);
  useEffect(() => { if (selectedProjectId) void loadProjectContext(selectedProjectId); }, [selectedProjectId]);
  useEffect(() => { if (selectedProjectId && editorNotePath) void loadEditorNote(selectedProjectId, editorNotePath); }, [selectedProjectId, editorNotePath]);

  async function loadInitial() { try { const [projectList, config, jobs] = await Promise.all([fetchProjects(), fetchIngestionConfig(), fetchIngestionJobs()]); setProjects(projectList); setIngestionConfig(config); setIngestionJobs(jobs); const preferred = choosePreferredProject(projectList); if (preferred) setSelectedProjectId(preferred.project_id); } catch (err) { setError(String(err)); } }
  async function loadProjectContext(projectId: string) { try { const [detail, graph, reviewQueue, artifacts] = await Promise.all([fetchProjectDetail(projectId), fetchGraph(projectId), fetchReviewQueue(projectId), fetchArtifacts(projectId)]); setProjectDetail({ ...detail, canon: { ...detail.canon, review_queue: reviewQueue } }); setGraphPayload(graph || null); setArtifactsCount((artifacts.artifacts || []).length); const firstEntity = detail.canon?.primaries?.[0]; if (firstEntity) setSelectedEntityKey(firstEntity.preferred_slug || firstEntity.canonical_name || ''); const firstNode = graph?.nodes?.[0]; if (firstNode?.id) setSelectedGraphNodeId(firstNode.id); const firstChapter = detail.notes?.find(isChapterNote); if (firstChapter?.path) setEditorNotePath(firstChapter.path); } catch (err) { setError(String(err)); } }
  async function loadEditorNote(projectId: string, notePath: string) { try { const payload = await fetchNote(projectId, notePath); setEditorMarkdown(String(payload.markdown || 'Sin contenido de capítulo disponible.')); } catch (_err) { setEditorMarkdown('Sin contenido de capítulo disponible.'); } }

  const warningsVisible = visibleDecisions.length;
  const graphVm = useMemo(() => mapGraphPayload(graphPayload), [graphPayload]);
  const filteredGraph = useMemo(() => filterGraph(graphVm, graphKindFilter, graphQuery, graphRelatedOnly ? selectedGraphNodeId : null), [graphVm, graphKindFilter, graphQuery, graphRelatedOnly, selectedGraphNodeId]);
  const selectedGraphNode = useMemo(() => (selectedGraphNodeId ? filteredGraph.byId[selectedGraphNodeId] || null : null), [filteredGraph, selectedGraphNodeId]);
  const graphEditNode = useMemo(() => (graphEditNodeId ? filteredGraph.byId[graphEditNodeId] || null : null), [filteredGraph, graphEditNodeId]);
  const graphStats = { nodes: filteredGraph.nodes.length, edges: filteredGraph.edges.length };
  let content: React.ReactNode = null;

  if (active === 'overview') content = <OverviewBoard setActive={setActive} />;
  if (active === 'hub') content = <section><TopBar title="Project Hub" subtitle="Abrir o reanudar proyecto TextifAI completo. El runtime real 20ch se prefiere si existe." actions={<><Button>New ingestion</Button><Button variant="secondary">Open .txtfai / manifest</Button></>} /><div className="p-5 grid grid-cols-12 gap-5"><div className="col-span-12 lg:col-span-8 space-y-4"><div className="rounded-3xl border border-neutral-200 p-5 bg-neutral-50"><div className="flex items-center justify-between"><div><h2 className="font-semibold text-lg">Workspaces disponibles</h2><p className="text-sm text-neutral-500">Datos reales desde /api/projects. Se evita seleccionar fixture 2ch si hay base 20ch.</p></div><Search size={18} className="text-neutral-500" /></div><div className="mt-4 space-y-3">{projects.map((project) => <ProjectRow key={project.project_id} project={project} selected={project.project_id === selectedProjectId} onSelect={() => setSelectedProjectId(project.project_id)} />)}</div>{isMinimalFixture(selectedProject) ? <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"><AlertTriangle size={16} className="inline" /> Proyecto reducido detectado: no usar como base UX final si runtime 20ch existe.</div> : null}</div></div><aside className="col-span-12 lg:col-span-4 space-y-4"><Metric label="Contrato" value="manifest.json" note="Un archivo abre el bundle completo." /><Metric label="Futuro" value=".txtfai" note="Formato empaquetado de workspace." /><div className="rounded-3xl border border-neutral-200 p-5"><h3 className="font-semibold">Salud del proyecto</h3><div className="mt-4 space-y-3 text-sm"><div className="flex items-center gap-2"><CheckCircle2 size={16} /> Capítulos indexados: {projectDetail?.overview?.chapters_processed ?? 0}</div><div className="flex items-center gap-2"><CheckCircle2 size={16} /> VaERL/artifacts: {artifactsCount}</div><div className="flex items-center gap-2"><AlertTriangle size={16} /> Warnings visibles: {warningsVisible}</div></div></div></aside></div></section>;
  if (active === 'ingest') content = <section><TopBar title="Ingestion" subtitle="Crear proyecto TextifAI local-first sin provider calls en esta fase." actions={<Button variant="secondary" disabled>Run ingestion disabled</Button>} /><div className="p-5 grid grid-cols-12 gap-5"><div className="col-span-12 lg:col-span-7 rounded-3xl border border-neutral-200 p-5"><h2 className="font-semibold">Source setup</h2><p className="mt-2 text-sm text-neutral-600">Después de generar proyecto, abrir `manifest.json`. `.txtfai` queda como dirección futura.</p><div className="mt-5 grid gap-3 text-sm md:grid-cols-2"><div className="rounded-2xl bg-neutral-50 border border-neutral-200 p-4">Source root</div><div className="rounded-2xl bg-neutral-50 border border-neutral-200 p-4">Artifacts root</div><div className="rounded-2xl bg-neutral-50 border border-neutral-200 p-4">Vault</div><div className="rounded-2xl bg-neutral-50 border border-neutral-200 p-4">Reports</div></div></div><aside className="col-span-12 lg:col-span-5 space-y-4"><Metric label="Mode" value={ingestionConfig?.mode || 'local'} note={ingestionConfig?.local_only_warning || 'No provider execution.'} /><div className="rounded-3xl border border-neutral-200 bg-neutral-50 p-5"><h2 className="font-semibold">Jobs</h2><div className="mt-3 space-y-2 text-sm">{ingestionJobs.length ? ingestionJobs.map((job) => <div key={job.job_id} className="rounded-xl bg-white border border-neutral-200 px-3 py-2">{job.run_name || job.job_id} · {job.status}</div>) : <div className="text-neutral-500">Sin jobs activos.</div>}</div></div></aside></div></section>;
  if (active === 'codex') content = <section><TopBar title="Codex / VaERL" subtitle="Tabla estructurada sobre source of truth semántico. Primaries se editan aquí, Graph o Story Bible." actions={<><Button variant="secondary">Export selection</Button><Button variant="secondary">Open evidence</Button></>} /><div className="p-5 grid grid-cols-12 gap-5"><div className="col-span-12 lg:col-span-8"><EntityRecordTable entities={projectDetail?.canon?.primaries || []} selectedKey={selectedEntityKey} onSelect={setSelectedEntityKey} /></div><aside className="col-span-12 lg:col-span-4"><InspectorCard entity={selectedEntity} /></aside></div></section>;
  if (active === 'graph') content = (
    <section>
      <TopBar title="Graph" subtitle="Exploración visual author-facing con física viva e inspector editorial." actions={<Button variant="secondary" onClick={() => { setGraphKindFilter('all'); setGraphQuery(''); setGraphRelatedOnly(false); }}>Mostrar todo</Button>} />
      <div className="p-5 grid grid-cols-12 gap-5">
        <aside className="col-span-12 xl:col-span-3">
          <GraphToolbar
            activeKind={graphKindFilter}
            onKindChange={setGraphKindFilter}
            query={graphQuery}
            onQueryChange={setGraphQuery}
            relatedOnly={graphRelatedOnly}
            onRelatedOnlyChange={setGraphRelatedOnly}
            onResetViewport={() => { setGraphKindFilter('all'); setGraphQuery(''); setGraphRelatedOnly(false); }}
          />
        </aside>
        <div className="col-span-12 xl:col-span-6">
          {selectedProjectId ? <GraphCanvas nodes={filteredGraph.nodes} edges={filteredGraph.edges} selectedNodeId={selectedGraphNodeId} onSelectNode={setSelectedGraphNodeId} /> : <div className="rounded-3xl border border-neutral-200 p-5 text-sm text-neutral-500">Selecciona un proyecto para abrir Graph.</div>}
        </div>
        <aside className="col-span-12 xl:col-span-3">
          <GraphInspector node={selectedGraphNode} onEdit={(node: GraphCanvasNode) => setGraphEditNodeId(node.id)} />
        </aside>
      </div>
      <GraphNodeEditDraftModal node={graphEditNode} onClose={() => setGraphEditNodeId(null)} />
    </section>
  );
  if (active === 'review') content = <section><TopBar title="Review Queue" subtitle="Cola de decisiones derivada de warnings reales. Contador = lista visible filtrada." actions={<><Button variant="secondary">Accept</Button><Button variant="secondary">Reject</Button><Button variant="secondary">Merge</Button></>} /><div className="p-5 grid grid-cols-12 gap-5"><div className="col-span-12 lg:col-span-8 space-y-4"><div className="flex gap-3"><input value={reviewQuery} onChange={(event) => setReviewQuery(event.target.value)} className="flex-1 rounded-2xl border border-neutral-300 px-4 py-2 text-sm" placeholder="Buscar decisión..." /><select value={reviewSeverity} onChange={(event) => setReviewSeverity(event.target.value)} className="rounded-2xl border border-neutral-300 px-4 py-2 text-sm"><option value="all">Todas</option><option value="high">Alta</option><option value="medium">Media</option><option value="low">Baja</option></select></div>{visibleDecisions.map((item) => <DecisionCard key={item.id} item={item} selected={selectedDecision?.id === item.id} onSelect={() => setSelectedDecisionId(item.id)} />)}</div><aside className="col-span-12 lg:col-span-4 space-y-4"><Metric label="Pendientes visibles" value={warningsVisible} note="Derivado de misma colección que renderiza la lista." /><div className="rounded-3xl border border-neutral-200 bg-neutral-50 p-5"><h2 className="font-semibold">Decision drawer</h2><p className="mt-2 text-sm text-neutral-600">{selectedDecision?.action || 'Selecciona aviso.'}</p><div className="mt-4 flex flex-wrap gap-2"><Button variant="secondary">Open evidence</Button><Button variant="secondary">Edit canonical label</Button></div></div></aside></div></section>;
  if (active === 'editor') content = <section className={editorFullscreen ? 'fixed inset-0 z-30 bg-white overflow-y-auto' : ''}><TopBar title="Editor" subtitle="Solo capítulos/manuscrito. Fichas primarias viven en Codex, Graph o Story Bible." actions={<><Button onClick={() => setEditDraft({ title: 'Añadir capítulo', body: 'Draft local pendiente de SP-106. No hay persistencia ni write-back en SP-105D.' })}><Plus size={14} className="inline" /> Añadir capítulo</Button><Button variant="secondary" onClick={() => setEditorFullscreen(!editorFullscreen)}><Maximize2 size={14} className="inline" /> {editorFullscreen ? 'Salir fullscreen' : 'Pantalla completa'}</Button></>} /><div className="p-5 grid grid-cols-12 gap-5"><aside className={editorFullscreen ? 'hidden' : 'col-span-12 lg:col-span-3 rounded-3xl border border-neutral-200 bg-neutral-50 p-4'}><h2 className="font-semibold">Capítulos</h2><div className="mt-4 space-y-2 text-sm">{chapterNotes.map((note) => <button key={note.path} onClick={() => setEditorNotePath(note.path)} className={`w-full rounded-xl border px-3 py-2 text-left ${editorNotePath === note.path ? 'bg-neutral-900 text-white border-neutral-900' : 'bg-white border-neutral-200'}`}>{note.name || note.path}</button>)}</div></aside><div className={editorFullscreen ? 'col-span-12 lg:col-span-8' : 'col-span-12 lg:col-span-6'}><div className="rounded-3xl border border-neutral-200 bg-white p-5 min-h-[620px]"><div className="text-xs uppercase text-neutral-500">Editor preview · capítulo real</div><h2 className="mt-2 font-semibold">{editorNotePath || 'Selecciona capítulo'}</h2><pre className="mt-4 whitespace-pre-wrap rounded-2xl bg-neutral-50 p-4 text-sm leading-7 text-neutral-700 max-h-[620px] overflow-auto">{editorMarkdown}</pre></div></div><aside className="col-span-12 lg:col-span-3 space-y-4"><Metric label="Contexto" value="VaERL" note="Panel derecho retenido también en fullscreen." /><div className="rounded-3xl border border-neutral-200 bg-neutral-50 p-5 text-sm text-neutral-600"><div className="rounded-2xl bg-white border border-neutral-200 p-3"><b>Rewrite selection</b><br />Placeholder. Sin LLM.</div><div className="mt-3 rounded-2xl bg-white border border-neutral-200 p-3"><b>Canon risks</b><br />No write-back en esta fase.</div></div></aside></div></section>;
  if (active === 'story') content = <section><TopBar title="Story Bible" subtitle="Wiki Markdown author-facing. Legacy boundary transicional documentado." actions={<><Button variant="secondary">Sync Markdown</Button><Button variant="secondary">Open graph side-by-side</Button></>} /><div className="p-5 grid grid-cols-12 gap-5"><aside className="col-span-12 lg:col-span-3 rounded-3xl border border-neutral-200 bg-neutral-50 p-4"><h2 className="font-semibold">Vault tree</h2><div className="mt-4 space-y-2 text-sm">{(projectDetail?.notes || []).slice(0, 16).map((note) => <div key={note.path} className="rounded-xl bg-white border border-neutral-200 px-3 py-2">{note.name || note.path}</div>)}</div></aside><div className="col-span-12 lg:col-span-9">{selectedProjectId ? <LegacyEmbed title="Story Bible transitional legacy boundary" src={legacyUrl('notes', selectedProjectId)} /> : <div className="rounded-3xl border border-neutral-200 p-5 text-sm text-neutral-500">Selecciona proyecto.</div>}</div></div></section>;
  if (active === 'ask') content = <section><TopBar title="Ask Canon" subtitle="Q&A shell grounded futuro en VaERL, evidencia y review state." actions={<><Button variant="secondary">Open answer history</Button><Button variant="secondary">Check source coverage</Button></>} /><div className="p-5 grid grid-cols-12 gap-5"><div className="col-span-12 lg:col-span-7 rounded-3xl border border-neutral-200 p-5 min-h-[560px] flex flex-col"><div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4 text-sm text-neutral-500">Pregunta: “¿Qué sabe Sera antes del capítulo 6?”</div><div className="mt-5 rounded-3xl border border-neutral-200 p-5 bg-white shadow-sm"><div className="font-semibold">Respuesta grounded</div><p className="mt-3 text-sm leading-7">Placeholder. No se genera canon sin backend de evidencia.</p></div><div className="mt-auto pt-5 flex gap-2"><input className="flex-1 rounded-2xl border border-neutral-300 px-4 py-3 text-sm" placeholder="Pregunta sobre canon, continuidad o capítulos..." /><Button variant="secondary" disabled>Enviar</Button></div></div><aside className="col-span-12 lg:col-span-5 space-y-4"><Metric label="Grounding" value="Evidence-first" note="Sin claims no soportados." /></aside></div></section>;

  return <Shell active={active} setActive={setActive}><motion.div key={active} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.18 }}>{content}</motion.div>{error ? <div className="mx-5 mb-5 rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}{editDraft ? <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"><div className="w-full max-w-2xl rounded-3xl border border-neutral-200 bg-white shadow-2xl"><div className="flex items-center justify-between border-b border-neutral-200 p-5"><div><h2 className="font-semibold">{editDraft.title}</h2><p className="text-sm text-neutral-500">{editDraft.notePath || 'nuevo draft local'}</p></div><button onClick={() => setEditDraft(null)} className="rounded-full p-2 hover:bg-neutral-100"><X size={18} /></button></div><div className="p-5"><textarea readOnly value={editDraft.body} className="h-48 w-full rounded-2xl border border-neutral-200 bg-neutral-50 p-4 text-sm" /><p className="mt-3 text-sm text-neutral-500">Guardar cambios llega con drafts/patch queue. No write-back en SP-105D.</p></div></div></div> : null}</Shell>;
}

export default App;
