import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import '@mdxeditor/editor/style.css';
import { MDXEditor, UndoRedo, BoldItalicUnderlineToggles, ListsToggle, CreateLink, BlockTypeSelect, Separator, toolbarPlugin, headingsPlugin, listsPlugin, quotePlugin, linkPlugin, linkDialogPlugin, thematicBreakPlugin, markdownShortcutPlugin } from '@mdxeditor/editor';
import CodeMirror from '@uiw/react-codemirror';
import { markdown } from '@codemirror/lang-markdown';
import { history, undo, redo } from '@codemirror/commands';
import { EditorView, keymap, placeholder } from '@codemirror/view';
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
  List,
  ListOrdered,
  ListChecks,
  Link2,
  Undo2,
  Redo2,
} from 'lucide-react';
import {
  ChapterSaveResponse,
  CanonEntity,
  GraphPayload,
  GraphNode,
  IngestionConfig,
  IngestionJob,
  ProjectDetail,
  ProjectSummary,
  ReviewItem,
  NoteDetail,
  fetchArtifacts,
  fetchGraph,
  fetchIngestionConfig,
  fetchIngestionJobs,
  fetchNote,
  fetchProjectDetail,
  fetchProjects,
  fetchReviewQueue,
  saveChapterMarkdown,
  EntityCard,
  fetchEntityCard } from './api';
import { mapGraphPayload, filterGraph } from './graph/GraphDataAdapter';
import { GraphCanvas } from './graph/GraphCanvas';
import { GraphToolbar } from './graph/GraphToolbar';
import { GraphNodeEditDraftModal } from './graph/GraphNodeEditDraftModal';
import { GraphCanvasNode } from './graph/types';
import { GraphInspector as GraphInspectorPanel } from './graph/GraphInspector';

type SectionId = 'hub' | 'ingest' | 'review' | 'graph' | 'codex' | 'editor' | 'story' | 'ask' | 'overview';
type ScreenConfig = { id: SectionId; label: string; icon: React.ComponentType<{ size?: number; className?: string }> };
type DecisionItem = { id: string; title: string; severity: string; source: string; action: string; raw: ReviewItem; actionKind?: string; hasTarget?: boolean; materiality?: 'normal' | 'low' | 'noise' };
type ReviewDecisionChoice = 'accept' | 'reject' | 'manual' | 'create' | 'discard' | 'context' | 'defer';
type EvidenciaModalItem = DecisionItem | null;
type EditDraft = { title: string; notePath?: string; body: string } | null;
type EditorChapter = { chapter_id?: string; path: string; title: string; display_title?: string; order?: number | null; source_used?: string };
type EditorMode = 'markdown' | 'visual';
type EditorParseStatus = 'empty' | 'ready' | 'malformed_frontmatter';
type EditorDraftState = {
  rawMarkdown: string;
  frontmatterRaw: string;
  bodyMarkdown: string;
  parseStatus: EditorParseStatus;
  dirty: boolean;
  loadedChapterId: string;
  loadedContentHash: string;
};

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error' | 'conflict';

const screens: ScreenConfig[] = [
  { id: 'hub', label: 'Project Hub', icon: BookOpen },
  { id: 'ingest', label: 'Ingestion', icon: Upload },
  { id: 'review', label: 'Review Queue', icon: Inbox },
  { id: 'graph', label: 'Graph', icon: GitBranch },
  { id: 'codex', label: 'Canon / VaERL', icon: Network },
  { id: 'editor', label: 'Editor', icon: PenLine },
  { id: 'ask', label: 'AI Studio', icon: MessageSquareText },
];

const overviewCards: Array<{ id: SectionId; title: string; text: string; icon: ScreenConfig['icon'] }> = [
  { id: 'hub', title: '1. Project Hub', text: 'Abrir proyecto TextifAI completo vía manifest.json; .txtfai queda como dirección futura.', icon: Database },
  { id: 'ingest', title: '2. Ingestion', text: 'Preparar estructura estable de source, artifacts, vault y reportes.', icon: Upload },
  { id: 'review', title: '3. Review Queue', text: 'Resolver avisos mediante decisiones explícitas del autor.', icon: Inbox },
  { id: 'graph', title: '4. Graph', text: 'Exploración visual nativa de entidades, capítulos, vínculos y warnings.', icon: GitBranch },
  { id: 'codex', title: '5. Canon / VaERL', text: 'Wiki author-facing de canon: entidades, aliases, hechos, evidencia, Story Bible y estado de revisión.', icon: Network },
  { id: 'editor', title: '6. Editor', text: 'Escritura y revisión de capítulos, no fichas primarias.', icon: SplitSquareHorizontal },
  { id: 'ask', title: '7. AI Studio', text: 'Ask Canon, brainstorming y Character Lab futuros sobre VaERL, evidencia e incertidumbre.', icon: MessageSquareText },
];

const kindLabels: Record<string, string> = { chapter: 'capítulo', character: 'personaje', concept: 'concepto', event: 'evento', object: 'objeto', place: 'lugar', review: 'revisión' };
const graphPalette: Record<string, string> = { chapter: '#7f7a6a', character: '#111827', concept: '#6b7280', event: '#9a3412', object: '#0f766e', place: '#1d4ed8', review: '#b91c1c' };
const FULL_LOGO_SRC = '/branding/textifai-logo-full.png';
const editorToolbarClassName = 'textifai-editor-toolbar';

function isChapterNote(note: { path?: string; kind?: string; role?: string } | undefined): boolean {
  if (!note) return false;
  const kind = String(note.kind || note.role || '').toLowerCase();
  return kind === 'chapter' || String(note.path || '').toLowerCase().startsWith('chapters/');
}

function isMinimalFixture(project: ProjectSummary | null | undefined): boolean {
  return Boolean(project && (project.chapter_count || 0) > 0 && (project.chapter_count || 0) < 20);
}

function hashEditorContent(content: string): string {
  let hash = 5381;
  for (let index = 0; index < content.length; index += 1) hash = ((hash << 5) + hash) ^ content.charCodeAt(index);
  return `${hash >>> 0}`;
}

function splitFrontmatter(markdown: string): { frontmatterRaw: string; bodyMarkdown: string; parseStatus: EditorParseStatus } {
  if (!markdown.trim()) return { frontmatterRaw: '', bodyMarkdown: '', parseStatus: 'empty' };
  if (!markdown.startsWith('---\n')) return { frontmatterRaw: '', bodyMarkdown: markdown, parseStatus: 'ready' };
  const lines = markdown.split('\n');
  const closing = markdown.indexOf('\n---\n', 4);
  if (closing === -1) {
    const candidateFrontmatterLines = lines.slice(1, Math.min(lines.length, 12));
    const looksLikeYamlFrontmatter = candidateFrontmatterLines.some((line) => /^[A-Za-z0-9_-]+\s*:\s*.*$/.test(line.trim()));
    if (!looksLikeYamlFrontmatter) return { frontmatterRaw: '', bodyMarkdown: markdown, parseStatus: 'ready' };
    return { frontmatterRaw: markdown, bodyMarkdown: '', parseStatus: 'malformed_frontmatter' };
  }
  const frontmatterRaw = markdown.slice(0, closing + 5);
  const bodyMarkdown = markdown.slice(closing + 5);
  return { frontmatterRaw, bodyMarkdown, parseStatus: 'ready' };
}

function composeRawMarkdown(frontmatterRaw: string, bodyMarkdown: string): string {
  if (!frontmatterRaw) return bodyMarkdown;
  return `${frontmatterRaw}${bodyMarkdown.startsWith('\n') || bodyMarkdown.length === 0 ? '' : '\n'}${bodyMarkdown}`;
}

function replaceSelectionRange(source: string, start: number, end: number, replacement: string): { nextText: string; nextStart: number; nextEnd: number } {
  const nextText = `${source.slice(0, start)}${replacement}${source.slice(end)}`;
  const cursor = start + replacement.length;
  return { nextText, nextStart: cursor, nextEnd: cursor };
}

function createEditorDraft(markdown: string, chapterId: string): EditorDraftState {
  const rawMarkdown = String(markdown || '');
  const { frontmatterRaw, bodyMarkdown, parseStatus } = splitFrontmatter(rawMarkdown);
  return {
    rawMarkdown,
    frontmatterRaw,
    bodyMarkdown,
    parseStatus,
    dirty: false,
    loadedChapterId: chapterId,
    loadedContentHash: hashEditorContent(rawMarkdown),
  };
}

const legacyEditorChapterSelectionContract = 'const chapterNotes = useMemo(() => (projectDetail?.notes || []).filter(isChapterNote)';

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
  const severity = String(item.severity || 'low');
  const target = item.target_label || (typeof item.target_entity === 'object' ? item.target_entity?.label : item.target_entity) || '';
  const title = item.title || (target ? `Revisar “${target}”` : `${item.source_entity || 'Candidato'} · sin entidad sugerida`);
  const summary = item.human_reason || item.subtitle || item.recommendation || item.suggested_action || item.review_type || item.type || item.evidence_summary || 'Necesita decisión editorial.';
  const lower = `${target} ${summary} ${item.review_type || ''} ${item.type || ''}`.toLowerCase();
  let actionKind = target ? 'accept_suggested_action' : 'manual_resolution_required';
  if (lower.includes('ruido') || lower.includes('noise')) actionKind = 'discard_from_canon';
  else if (lower.includes('alias')) actionKind = 'alias_candidate';
  else if (lower.includes('relación') || lower.includes('relationship')) actionKind = 'relationship_candidate';
  else if (target) actionKind = 'merge_candidate';
  const materiality = lower.includes('ruido') || lower.includes('noise') ? 'noise' : (lower.includes('ambigua') || lower.includes('no nombrada') || lower.includes('sin entidad') ? 'low' : 'normal');
  return {
    id: item.id || `${title}-${index}`,
    title,
    severity,
    source: item.evidence_summary || (item.evidence_refs || []).map((row) => row.chapter_id || row.pointer || 'evidencia').slice(0, 2).join(', ') || 'Evidencia pendiente',
    action: summary,
    actionKind,
    hasTarget: Boolean(target),
    materiality,
    raw: item,
  };
}

function severityClass(level: string): string {
  const normalized = level.toLowerCase();
  if (normalized === 'high') return 'bg-rose-50 text-rose-700 border-rose-200';
  if (normalized === 'medium') return 'bg-amber-50 text-amber-700 border-amber-200';
  return 'bg-emerald-50 text-emerald-700 border-emerald-200';
}

function severityIconClass(level: string): string {
  const normalized = level.toLowerCase();
  if (normalized === 'high') return 'text-rose-500';
  if (normalized === 'medium') return 'text-amber-500';
  return 'text-emerald-500';
}

function decisionButtonClass(active: boolean): string {
  return `rounded-2xl px-4 py-2 text-sm font-medium ${active ? 'bg-neutral-900 text-white' : 'bg-neutral-100 text-neutral-800 border border-neutral-200 hover:bg-neutral-200'}`;
}

function formatDecisionChoice(choice?: ReviewDecisionChoice): string {
  if (choice === 'accept') return 'Aceptar';
  if (choice === 'reject') return 'Rechazar';
  if (choice === 'merge') return 'Fusionar';
  return 'sin marcar';
}

function legacyUrl(view: 'graph' | 'notes' | 'canon', projectId: string): string {
  return `/index.html?embed=1&view=${encodeURIComponent(view)}&project=${encodeURIComponent(projectId)}`;
}

function BrandMark() {
  const [logoFailed, setLogoFailed] = useState(false);
  if (!logoFailed) {
    return <img src={FULL_LOGO_SRC} alt="TextifAI" className="h-8 w-auto object-contain" onError={() => setLogoFailed(true)} />;
  }
  return <div className="flex items-center gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-neutral-900 text-sm font-semibold text-white">T</div><div className="text-xl font-bold tracking-tight">TextifAI</div></div>;
}

function Shell({ active, setActive, children }: { active: SectionId; setActive: (id: SectionId) => void; children: React.ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  return (
    <div className="min-h-screen h-screen bg-neutral-100 text-neutral-900 p-2 md:p-4 overflow-hidden">
      <div className="mx-auto w-full max-w-none h-full rounded-3xl bg-white shadow-xl overflow-hidden border border-neutral-200">
        <header className="flex items-center justify-between border-b border-neutral-200 px-5 py-4 bg-neutral-50">
          <button type="button" onClick={() => setActive('overview')} className="text-left">
            <BrandMark />
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
function ProjectRow({ project, selected, onSelect }: { project: ProjectSummary; selected?: boolean; onSelect: () => void }) { const title = project.work?.title || project.name || 'Proyecto narrativo'; return <button onClick={onSelect} className={`w-full rounded-2xl border p-4 text-left ${selected ? 'bg-neutral-900 text-white border-neutral-900' : 'bg-white border-neutral-200 hover:bg-neutral-50'}`}><div className="grid grid-cols-12 gap-3 items-center"><div className="col-span-12 md:col-span-7"><div className="font-semibold">{title}</div><div className={`text-xs ${selected ? 'text-neutral-300' : 'text-neutral-500'}`}>{project.kind || 'workspace'} · {project.work?.language || 'idioma pendiente'}</div></div><div className="col-span-4 md:col-span-2 text-sm">{project.chapter_count || 0} capítulos</div><div className="col-span-4 md:col-span-2 text-sm">{project.graph_summary?.node_count || 0} nodos</div><div className="col-span-4 md:col-span-1 text-sm">{isMinimalFixture(project) ? 'dev fixture' : 'real'}</div></div><div className={`mt-3 grid gap-2 text-xs ${selected ? 'text-neutral-200' : 'text-neutral-600'}`}><div>{project.workspace_status?.chapters_detected_label || `${project.chapter_count || 0} capítulos detectados`}</div><div>{project.workspace_status?.chapters_ready_label || 'Sin resumen de ingestión'}</div><div>{project.workspace_status?.chapters_still_failed_label || '0 siguen necesitando reintento'}</div><div>{project.workspace_status?.semantic_review_label || '0 decisiones editoriales pendientes'}</div></div></button>; }

function DecisionCard({ item, selected, choice, onSelect, onChoose, onOpenEvidencia }: { item: DecisionItem; selected?: boolean; choice?: ReviewDecisionChoice; onSelect: () => void; onChoose: (choice: ReviewDecisionChoice) => void; onOpenEvidencia: () => void }) {
  const choose = (nextChoice: ReviewDecisionChoice) => { onSelect(); onChoose(nextChoice); };
  return <article className={`w-full rounded-3xl border p-5 text-left shadow-sm ${selected ? 'border-neutral-900 bg-neutral-50' : 'border-neutral-200 bg-white'}`}>
    <div className="flex items-start justify-between gap-3">
      <button type="button" onClick={onSelect} className="min-w-0 flex-1 text-left">
        <div className={`inline-flex rounded-full border px-3 py-1 text-xs uppercase tracking-wide ${severityClass(item.severity)}`}>{String(item.severity).toUpperCase()} SEVERITY · {item.source || 'Sin capítulos vinculados'}</div>
        <h3 className="mt-2 text-2xl font-semibold tracking-tight">{item.title}</h3>
        <p className="mt-2 text-sm text-neutral-600">{item.human_reason || item.summary || item.evidence_summary || item.action}</p>
      </button>
      <AlertTriangle size={18} className={`mt-1 shrink-0 ${severityIconClass(item.severity)}`} />
    </div>
    <div className="mt-5 flex flex-wrap gap-2">
      <button type="button" onClick={() => choose('accept')} className={decisionButtonClass(choice === 'accept')}>{item.actionKind === 'relationship_candidate' ? 'Aceptar relación' : item.actionKind === 'alias_candidate' ? 'Aceptar alias' : item.hasTarget ? 'Aceptar sugerencia' : 'Aceptar'}</button>
      <button type="button" onClick={() => choose('reject')} className={decisionButtonClass(choice === 'reject')}>Rechazar</button>
      {item.hasTarget ? <button type="button" onClick={() => choose('manual')} className={decisionButtonClass(choice === 'manual')}>Elegir otra entidad…</button> : <button type="button" onClick={() => choose('manual')} className={decisionButtonClass(choice === 'manual')}>Resolver manualmente…</button>}
      {!item.hasTarget ? <button type="button" onClick={() => choose('create')} className={decisionButtonClass(choice === 'create')}>Crear entidad nueva</button> : null}
      {(item.materiality === 'low' || item.materiality === 'noise' || !item.hasTarget) ? <button type="button" onClick={() => choose('discard')} className={decisionButtonClass(choice === 'discard')}>Descartar del canon</button> : null}
      <button type="button" onClick={() => choose('context')} className={decisionButtonClass(choice === 'context')}>Mantener como contexto</button>
      <Button variant="secondary" onClick={() => { onSelect(); onOpenEvidencia(); }}>Ver evidencia</Button>
    </div>
  </article>;
}

function sanitizeEditorMarkdown(raw: string): string {
  const text = String(raw || '');
  if (!text.trim()) return '';
  let body = text;
  if (body.startsWith('---\n')) {
    const end = body.indexOf('\n---\n', 4);
    if (end > 0) body = body.slice(end + 5);
  }
  const lines = body.split('\n');
  while (lines.length && !lines[0].trim()) lines.shift();
  if (lines[0]?.trim().startsWith('#')) lines.shift();
  while (lines.length && !lines[0].trim()) lines.shift();
  return lines.join('\n').trim();
}

function evidenceMissingReason(sourceMapChunksCount: number): string {
  if (sourceMapChunksCount <= 0) return 'No hay fragmento textual resoluble porque source_map.chunks está vacío para este source_ref.';
  return 'No hay fragmento resoluble porque source_ref no se pudo mapear a chunk narrativo.';
}

function EvidenciaModal({ item, onClose }: { item: EvidenciaModalItem; onClose: () => void }) {
  if (!item) return null;
  const refs = item.raw.evidence_refs || [];
  const technicalDetails = item.raw.technical_details as Record<string, unknown> | undefined;
  const sourceMapChunksCount = Number(technicalDetails?.source_map_chunks_count || 0);
  const evidenceStoreUsed = Boolean(technicalDetails?.evidence_store_used);
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"><div className="w-full max-w-3xl rounded-3xl border border-neutral-200 bg-white shadow-2xl"><div className="flex items-center justify-between border-b border-neutral-200 p-5"><div><div className="text-xs uppercase tracking-wide text-neutral-500">Evidencia</div><h2 className="mt-1 text-xl font-semibold">{item.title}</h2><p className="mt-1 text-sm text-neutral-500">{item.action}</p></div><button type="button" onClick={onClose} className="rounded-full p-2 hover:bg-neutral-100"><X size={18} /></button></div><div className="grid gap-4 p-5 lg:grid-cols-[1.3fr_0.7fr]"><div className="space-y-3">{refs.length ? refs.map((ref, index) => <div key={`${ref.chapter_id || ref.pointer || 'evidence'}-${index}`} className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4"><div className="text-xs uppercase tracking-wide text-neutral-500">Evidencia {index + 1}</div><div className="mt-2 text-sm text-neutral-800">Capítulo: {ref.chapter_label || ref.chapter_id || 'pendiente'}</div>{ref.has_text && ref.excerpt ? <div className="mt-2 rounded-xl bg-white border border-neutral-200 p-3 text-sm text-neutral-700 italic">{'«' + ref.excerpt.slice(0, 240) + '»'}</div> : <div className="mt-2 rounded-xl bg-amber-50 border border-amber-200 p-3 text-sm text-amber-800">{evidenceMissingReason(sourceMapChunksCount)}</div>}<details className="mt-2"><summary className="cursor-pointer text-xs text-neutral-500">Detalles técnicos</summary><div className="mt-2 text-xs text-neutral-500">Pointer: {ref.pointer_short || ref.pointer || 'sin referencia estructurada'}</div></details></div>) : <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4 text-sm text-neutral-600">No hay evidence_refs estructurados todavía para este caso.</div>}</div><aside className="space-y-3"><div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4"><div className="text-xs uppercase tracking-wide text-neutral-500">Tipo</div><div className="mt-2 text-sm text-neutral-800">{item.raw.review_type || 'decisión editorial'}</div></div><div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4"><div className="text-xs uppercase tracking-wide text-neutral-500">Recomendación</div><div className="mt-2 text-sm text-neutral-800">{item.raw.recommendation || 'Necesita decisión explícita del autor.'}</div></div><div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4"><div className="text-xs uppercase tracking-wide text-neutral-500">Severidad</div><div className={`mt-2 inline-flex rounded-full border px-3 py-1 text-xs uppercase tracking-wide ${severityClass(item.severity)}`}>{item.severity}</div></div></aside></div><div className="flex justify-end border-t border-neutral-200 p-5"><Button variant="secondary" onClick={onClose}>Cerrar</Button></div></div></div>;
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"><div className="w-full max-w-3xl rounded-3xl border border-neutral-200 bg-white shadow-2xl"><div className="flex items-center justify-between border-b border-neutral-200 p-5"><div><div className="text-xs uppercase tracking-wide text-neutral-500">Evidencia</div><h2 className="mt-1 text-xl font-semibold">{item.title}</h2><p className="mt-1 text-sm text-neutral-500">{item.action}</p></div><button type="button" onClick={onClose} className="rounded-full p-2 hover:bg-neutral-100"><X size={18} /></button></div><div className="grid gap-4 p-5 lg:grid-cols-[1.3fr_0.7fr]"><div className="space-y-3">{refs.length ? refs.map((ref, index) => <div key={`${ref.chapter_id || ref.pointer || 'evidence'}-${index}`} className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4"><div className="text-xs uppercase tracking-wide text-neutral-500">Evidencia {index + 1}</div><div className="mt-2 text-sm text-neutral-800">Capítulo: {ref.chapter_label || ref.chapter_id || 'pendiente'}</div>{ref.has_text && ref.excerpt ? <div className="mt-2 rounded-xl bg-white border border-neutral-200 p-3 text-sm text-neutral-700 italic">{'«' + ref.excerpt.slice(0, 240) + '»'}</div> : <div className="mt-2 rounded-xl bg-amber-50 border border-amber-200 p-3 text-sm text-amber-800">{ref.reason || evidenceMissingReason(sourceMapChunksCount)}</div>}<details className="mt-2"><summary className="cursor-pointer text-xs text-neutral-500">Detalles técnicos</summary><div className="mt-2 text-xs text-neutral-500">Pointer: {ref.pointer_short || ref.pointer || 'sin referencia estructurada'}</div></details></div>) : <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4 text-sm text-neutral-600">No hay evidence_refs estructurados todavía para este caso.</div>}</div><aside className="space-y-3"><div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4"><div className="text-xs uppercase tracking-wide text-neutral-500">Tipo</div><div className="mt-2 text-sm text-neutral-800">{item.raw.review_type || 'decisión editorial'}</div></div><div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4"><div className="text-xs uppercase tracking-wide text-neutral-500">Recomendación</div><div className="mt-2 text-sm text-neutral-800">{item.raw.recommendation || 'Necesita decisión explícita del autor.'}</div></div><div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4"><div className="text-xs uppercase tracking-wide text-neutral-500">Severidad</div><div className={`mt-2 inline-flex rounded-full border px-3 py-1 text-xs uppercase tracking-wide ${severityClass(item.severity)}`}>{item.severity}</div></div><div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4 text-xs text-neutral-500">Evidence store: {evidenceStoreUsed ? 'sí' : 'no'} · source_map.chunks: {sourceMapChunksCount}</div></aside></div><div className="flex justify-end border-t border-neutral-200 p-5"><Button variant="secondary" onClick={onClose}>Cerrar</Button></div></div></div>;
}
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
  return <div className="grid grid-cols-12 gap-5 p-5"><aside className="col-span-12 xl:col-span-2 rounded-3xl border border-neutral-200 bg-neutral-50 p-4"><h2 className="font-semibold">Filtros</h2><div className="mt-4 flex flex-wrap gap-2 xl:block xl:space-y-2">{['all', ...kinds].map((kind) => <button key={kind} onClick={() => setKindFilter(kind)} className={`rounded-2xl px-3 py-2 text-sm xl:w-full xl:text-left ${kindFilter === kind ? 'bg-neutral-900 text-white' : 'bg-white border border-neutral-200 text-neutral-700'}`}>{kind === 'all' ? 'Todo' : kindLabels[kind] || kind}</button>)}</div></aside><div className="col-span-12 xl:col-span-7 rounded-3xl border border-neutral-200 bg-neutral-50 p-4"><div className="mb-3 flex items-center justify-between"><div><h2 className="font-semibold">Grafo VaERL</h2><p className="text-sm text-neutral-500">SVG React nativo sobre `/graph`. Sin iframe legacy como primary.</p></div><StatusChip>{visibleNodes.length} nodos</StatusChip></div><svg viewBox="0 0 760 520" className="h-[560px] w-full rounded-2xl bg-white border border-neutral-200">{visibleEdges.map((edge) => { const source = byId.get(String(edge.source)); const target = byId.get(String(edge.target)); if (!source || !target) return null; return <line key={edge.id || `${edge.source}-${edge.target}`} x1={source.x} y1={source.y} x2={target.x} y2={target.y} stroke="#d4d4d4" strokeWidth="1.5" />; })}{positioned.map((node) => { const kind = String(node.display_kind || node.kind || 'note'); const active = selected?.id === node.id; return <g key={node.id} onClick={() => setSelectedNodeId(node.id || '')} className="cursor-pointer"><circle cx={node.x} cy={node.y} r={active ? 16 : Number(node.radius || 11)} fill={graphPalette[kind] || '#525252'} stroke={active ? '#111827' : '#ffffff'} strokeWidth={active ? 4 : 2} /><text x={node.x + 18} y={node.y + 4} fontSize="12" fill="#171717">{node.label || node.id}</text></g>; })}</svg></div><GraphInspectorPanel
            node={selected}
            entityCard={null}
            entityCardVm={null}
            noteContent=""
            noteDetail={null}
            onEdit={(node: GraphCanvasNode) =>
              setEditDraft?.({
                title: `Editar ${node.label || node.id}`,
                notePath: String((node as any).notePath || (node as any).note_path || ''),
                body: 'Draft local/read-only. Guardar cambios llegará con patch queue.',
              })
            }
          /></div>;
}

function GraphInspector({ node, entityCard, noteContent, noteDetail, onEdit, setEditDraft }: { node?: any; entityCard?: CanonEntity | null; noteContent?: string; noteDetail?: NoteDetail | null; onEdit?: (node: GraphCanvasNode) => void; setEditDraft?: (draft: EditDraft) => void }) {
  if (!node) return <aside className="col-span-12 xl:col-span-3 rounded-3xl border border-neutral-200 p-5 text-sm text-neutral-500">Selecciona un nodo.</aside>;
  const kind = String(node.display_kind || node.kind || 'note');
  const label = entityCard?.canonical_name || node.label || node.id;
  const notePath = node.notePath || node.note_path || node.canonical_note_path || '';
  const summary = entityCard?.summary || node.summaryExcerpt || node.summary_excerpt || noteDetail?.summary_excerpt || '';
  const aliases = Array.from(new Set([...(entityCard?.aliases || []), ...((node.aliases || []) as string[])].filter(Boolean)));
  const facts = entityCard?.key_facts || noteDetail?.key_facts_preview || [];
  const relationships = entityCard?.relationships || [];
  const backlinks = noteDetail?.backlinks || node.backlinks || [];
  const outgoing = noteDetail?.outgoing_wikilinks || node.outgoingWikilinks || [];
  const preview = String(noteContent || noteDetail?.markdown || '').split('\n').map((line) => line.trim()).filter((line) => line && line !== '---').slice(0, 10).join('\n').slice(0, 1200);
  const relationCount = relationships.length || node.relationshipCount || node.relationship_count || noteDetail?.relationship_count || node.degree || 0;
  const evidenceCount = entityCard?.evidence_refs?.length || node.evidenceCount || node.evidence_count || noteDetail?.evidence_count || 0;
  const runEdit = () => onEdit ? onEdit(node as GraphCanvasNode) : setEditDraft ? setEditDraft({ title: `Editar ${label}`, notePath, body: 'Draft local/read-only. Guardar cambios llegará con patch queue.' }) : undefined;
  return <aside className="col-span-12 xl:col-span-3 rounded-3xl border border-neutral-200 bg-white p-5 shadow-sm max-h-[720px] overflow-y-auto"><div className="text-xs uppercase tracking-wide text-neutral-500">Ficha del nodo</div><h2 className="mt-2 text-xl font-semibold">{label}</h2><div className="mt-2 flex flex-wrap gap-2"><span className="rounded-full bg-neutral-100 px-3 py-1 text-xs">{kindLabels[kind] || kind}</span><span className="rounded-full bg-neutral-100 px-3 py-1 text-xs">{node.reviewState || node.review_state || node.status || 'ready'}</span><span className="rounded-full bg-neutral-100 px-3 py-1 text-xs">{relationCount} relaciones</span><span className="rounded-full bg-neutral-100 px-3 py-1 text-xs">{evidenceCount} evidencias</span></div><div className="mt-4 rounded-2xl border border-neutral-200 bg-neutral-50 p-4 text-sm leading-6 text-neutral-700">{summary || 'Resumen no disponible todavía. Se muestran enlaces, rutas y datos disponibles para revisión.'}</div>{aliases.length ? <div className="mt-4"><div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Aliases</div><div className="flex flex-wrap gap-1">{aliases.slice(0, 10).map((alias) => <span key={alias} className="rounded-full border border-neutral-200 bg-white px-2 py-0.5 text-xs">{alias}</span>)}</div></div> : null}{facts.length ? <div className="mt-4"><div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Hechos / bio</div><ul className="list-inside list-disc space-y-1 text-sm text-neutral-600">{facts.slice(0, 6).map((fact, i) => <li key={i}>{fact}</li>)}</ul></div> : null}{relationships.length ? <div className="mt-4"><div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Relaciones principales</div><div className="space-y-1">{relationships.slice(0, 6).map((rel, i) => <div key={i} className="rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm">{rel.target || 'sin destino'} — {rel.type || rel.relation_type || 'relacionado'}</div>)}</div></div> : null}<div className="mt-4 grid gap-2 text-sm"><div className="rounded-2xl bg-neutral-50 border border-neutral-200 p-3">Backlinks: {backlinks.length}</div><div className="rounded-2xl bg-neutral-50 border border-neutral-200 p-3">Enlaces salientes: {outgoing.length}</div><div className="rounded-2xl bg-neutral-50 border border-neutral-200 p-3">Grafo local: {noteDetail?.local_graph?.nodes?.length || 0} nodos</div><div className="rounded-2xl bg-neutral-50 border border-neutral-200 p-3">Nota: {notePath || 'pendiente'}</div></div>{backlinks.length ? <div className="mt-4"><div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Backlinks</div><div className="space-y-1">{backlinks.slice(0, 8).map((backlink) => <div key={backlink} className="rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs">{backlink}</div>)}</div></div> : null}{outgoing.length ? <div className="mt-4"><div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Enlaces salientes</div><div className="space-y-1">{outgoing.slice(0, 8).map((link) => <div key={link.target || link.label} className="rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs">{link.label || link.target}</div>)}</div></div> : null}{preview ? <details className="mt-4" open><summary className="cursor-pointer rounded-2xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs font-semibold">Vista Markdown</summary><pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-2xl bg-neutral-50 p-3 text-xs text-neutral-600">{preview}</pre></details> : null}<div className="mt-5 flex flex-wrap gap-2"><Button onClick={runEdit}>Editar</Button><Button variant="secondary">Abrir ficha</Button><Button variant="secondary">Ver en Review</Button></div></aside>;
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
  const [reviewDecisionChoices, setReviewDecisionChoices] = useState<Record<string, ReviewDecisionChoice>>({});
  const [evidenceModalDecisionId, setEvidenciaModalDecisionId] = useState<string>('');
  const [editorNotePath, setEditorNotePath] = useState<string>('');
  const [editorFullscreen, setEditorFullscreen] = useState(false);
  const [editorChapterRailCollapsed, setEditorChapterRailCollapsed] = useState(false);
  const [editorDraft, setEditorDraft] = useState<EditorDraftState>(() => createEditorDraft('', ''));
  const [editorMode, setEditorMode] = useState<EditorMode>('visual');
  const [editorModeWarning, setEditorModeWarning] = useState<string>('');
  const [editorVisualSeedMarkdown, setEditorVisualSeedMarkdown] = useState<string>('');
  const [editorSaveStatus, setEditorSaveStatus] = useState<SaveStatus>('idle');
  const [editorSaveMessage, setEditorSaveMessage] = useState<string>('');

  const editorTextareaRef = useRef<any>(null);

  const [graphPayload, setGraphPayload] = useState<GraphPayload | null>(null);
  const [selectedGraphNodeId, setSelectedGraphNodeId] = useState<string>('');
  const [selectedGraphEntityCardVm, setSelectedGraphEntityCardVm] = useState<EntityCard | null>(null);
  const [graphKindFilter, setGraphKindFilter] = useState<Set<string>>(new Set());
  const [graphQuery, setGraphQuery] = useState('');
  const [graphRelatedOnly, setGraphRelatedOnly] = useState(false);
  const [graphInspectorFullscreen, setGraphInspectorFullscreen] = useState(false);
  const [graphEditNodeId, setGraphEditNodeId] = useState<string | null>(null);
  const [selectedGraphEntityKey, setSelectedGraphEntityKey] = useState<string>('');
  const [selectedGraphNoteContent, setSelectedGraphNoteContent] = useState<string>('');
  const [selectedGraphNoteDetail, setSelectedGraphNoteDetail] = useState<NoteDetail | null>(null);
  const [artifactsCount, setArtifactsCount] = useState<number>(0);
  const [editDraft, setEditDraft] = useState<EditDraft>(null);
  const [error, setError] = useState<string>('');

  const selectedProject = useMemo(() => projects.find((project) => project.project_id === selectedProjectId) || null, [projects, selectedProjectId]);
  const selectedEntity = useMemo(() => (projectDetail?.canon?.primaries || []).find((entity) => (entity.preferred_slug || entity.canonical_name || '') === selectedEntityKey), [projectDetail, selectedEntityKey]);
  const editorSource = (projectDetail as any)?.editor_chapters;
  const chapterNotes = useMemo(() => {
    const chapters = Array.isArray(editorSource?.chapters) ? editorSource.chapters : [];
    return chapters
      .filter((chapter: any) => String(chapter?.path || '').trim())
      .map((chapter: any) => ({
        chapter_id: String(chapter.chapter_id || ''),
        path: String(chapter.path || ''),
        name: String(chapter.display_title || chapter.title || chapter.path || ''),
        display_title: String(chapter.display_title || chapter.title || chapter.path || ''),
        kind: 'chapter',
        role: 'chapter',
        status: 'ready',
        content_hash: String(chapter.content_hash || ''),
        source_used: String(chapter.source_used || editorSource?.source_used || 'chapter_manifest'),
      }));
  }, [editorSource]);
  const selectedEditorChapter = useMemo(() => chapterNotes.find((chapter) => chapter.path === editorNotePath) || null, [chapterNotes, editorNotePath]);
  const saveSupported = String(editorSource?.source_used || '').toLowerCase() === 'project_store';
  const saveBlockedByFrontmatter = editorMode === 'visual' && editorDraft.parseStatus === 'malformed_frontmatter';
  const canSaveEditor = Boolean(selectedProjectId && selectedEditorChapter?.chapter_id && editorDraft.dirty && saveSupported && !saveBlockedByFrontmatter && editorSaveStatus !== 'saving');
  void legacyEditorChapterSelectionContract;
  const allDecisions = useMemo(() => ((projectDetail?.canon?.review_queue?.decision_items || projectDetail?.canon?.review_queue?.items || []) as ReviewItem[]).map(toDecisionItem), [projectDetail]);
  const visibleDecisions = useMemo(() => { const query = reviewQuery.trim().toLowerCase(); return allDecisions.filter((item) => { if (reviewSeverity !== 'all' && item.severity.toLowerCase() !== reviewSeverity) return false; if (!query) return true; return item.title.toLowerCase().includes(query) || item.action.toLowerCase().includes(query) || String(item.raw.review_type || '').toLowerCase().includes(query); }); }, [allDecisions, reviewQuery, reviewSeverity]);
  const selectedDecision = useMemo(() => visibleDecisions.find((item) => item.id === selectedDecisionId) || visibleDecisions[0] || null, [visibleDecisions, selectedDecisionId]);
  const selectedDecisionChoice = selectedDecision ? reviewDecisionChoices[selectedDecision.id] : undefined;
  const evidenceModalItem = useMemo(() => allDecisions.find((item) => item.id === evidenceModalDecisionId) || null, [allDecisions, evidenceModalDecisionId]);

  useEffect(() => { void loadInitial(); }, []);
  useEffect(() => { if (selectedProjectId) void loadProjectContext(selectedProjectId); }, [selectedProjectId]);
  useEffect(() => { if (selectedProjectId && editorNotePath) void loadEditorNote(selectedProjectId, editorNotePath); }, [selectedProjectId, editorNotePath]);
  useEffect(() => {
    if (!selectedProjectId || !chapterNotes.length) return;
    const path = editorNotePath || chapterNotes[0]?.path || '';
    if (!path) return;
    if (!editorNotePath) setEditorNotePath(path);
    if (active === 'editor') void loadEditorNote(selectedProjectId, path);
  }, [active, selectedProjectId, chapterNotes, editorNotePath]);
  useEffect(() => { if (!editorFullscreen) setEditorChapterRailCollapsed(false); }, [editorFullscreen]);
  useEffect(() => {
    if (editorMode !== 'visual' || editorDraft.parseStatus !== 'ready') return;
    setEditorVisualSeedMarkdown(editorDraft.bodyMarkdown);
  }, [editorMode, editorDraft.loadedChapterId, editorDraft.loadedContentHash, editorDraft.parseStatus, editorDraft.bodyMarkdown]);

  async function loadInitial() { try { const [projectList, config, jobs] = await Promise.all([fetchProjects(), fetchIngestionConfig(), fetchIngestionJobs()]); setProjects(projectList); setIngestionConfig(config); setIngestionJobs(jobs); const preferred = choosePreferredProject(projectList); if (preferred) setSelectedProjectId(preferred.project_id); } catch (err) { setError(String(err)); } }
  async function loadProjectContext(projectId: string) { try { const [detail, graph, reviewQueue, artifacts] = await Promise.all([fetchProjectDetail(projectId), fetchGraph(projectId), fetchReviewQueue(projectId), fetchArtifacts(projectId)]); setProjectDetail({ ...detail, canon: { ...detail.canon, review_queue: reviewQueue } }); setGraphPayload(graph || null); setArtifactsCount((artifacts.artifacts || []).length); const firstEntity = detail.canon?.primaries?.[0]; if (firstEntity) setSelectedEntityKey(firstEntity.preferred_slug || firstEntity.canonical_name || ''); const firstNode = graph?.nodes?.[0]; if (firstNode?.id) setSelectedGraphNodeId(firstNode.id); const firstChapter = ((detail as any)?.editor_chapters?.chapters || [])[0]; if (firstChapter?.path) { const firstChapterPath = String(firstChapter.path); setEditorNotePath(firstChapterPath); void loadEditorNote(projectId, firstChapterPath); } } catch (err) { setError(String(err)); } }
  async function loadEditorNote(projectId: string, notePath: string) {
    try {
      const payload = await fetchNote(projectId, notePath);
      const clean = sanitizeEditorMarkdown(String(payload.markdown || '')) || 'Sin contenido de capítulo disponible.';
      const nextDraft = createEditorDraft(clean, notePath);
      setEditorDraft((current) => {
        if (current.loadedChapterId === nextDraft.loadedChapterId && current.loadedContentHash === nextDraft.loadedContentHash) return current;
        return nextDraft;
      });
      setEditorVisualSeedMarkdown(nextDraft.bodyMarkdown);
      setEditorModeWarning('');
      setEditorSaveStatus('idle');
      setEditorSaveMessage('');
    } catch (_err) {
      const fallback = 'Sin contenido de capítulo disponible.';
      setEditorDraft(createEditorDraft(fallback, notePath));
      setEditorModeWarning('');
      setEditorSaveStatus('idle');
      setEditorSaveMessage('');
    }
  }
  function updateMarkdownDraft(nextRawMarkdown: string) {
    setEditorSaveStatus('idle');
    setEditorSaveMessage('');
    setEditorDraft((current) => {
      const { frontmatterRaw, bodyMarkdown, parseStatus } = splitFrontmatter(nextRawMarkdown);
      return {
        ...current,
        rawMarkdown: nextRawMarkdown,
        frontmatterRaw,
        bodyMarkdown,
        parseStatus,
        dirty: true,
      };
    });
  }
  function updateVisualDraft(nextBodyMarkdown: string) {
    setEditorSaveStatus('idle');
    setEditorSaveMessage('');
    setEditorDraft((current) => {
      const rawMarkdown = composeRawMarkdown(current.frontmatterRaw, nextBodyMarkdown);
      return {
        ...current,
        bodyMarkdown: nextBodyMarkdown,
        rawMarkdown,
        parseStatus: current.frontmatterRaw ? 'ready' : current.parseStatus === 'empty' ? 'empty' : 'ready',
        frontmatterRaw: current.frontmatterRaw,
        dirty: true,
      };
    });
  }
  function switchEditorMode(nextMode: EditorMode) {
    if (nextMode === editorMode) return;
    if (nextMode === 'visual' && editorDraft.parseStatus === 'malformed_frontmatter') {
      setEditorModeWarning('Frontmatter malformado: corrígelo en Modo Markdown antes de usar Modo visual.');
      return;
    }
    if (nextMode === 'visual') {
      setEditorVisualSeedMarkdown(editorDraft.bodyMarkdown);
    }
    setEditorModeWarning('');
    setEditorMode(nextMode);
  }

  async function handleSaveEditorChapter() {
    if (!selectedProjectId || !selectedEditorChapter?.chapter_id) return;
    if (saveBlockedByFrontmatter) {
      setEditorSaveStatus('error');
      setEditorSaveMessage('Frontmatter malformado: guarda desde Modo Markdown o corrígelo antes de guardar visual.');
      return;
    }
    setEditorSaveStatus('saving');
    setEditorSaveMessage('Guardando capítulo...');
    try {
      const result: ChapterSaveResponse = await saveChapterMarkdown(selectedProjectId, selectedEditorChapter.chapter_id, editorDraft.rawMarkdown, editorDraft.loadedContentHash);
      const nextHash = String(result.new_hash || hashEditorContent(editorDraft.rawMarkdown));
      setEditorDraft((current) => ({ ...current, dirty: false, loadedContentHash: nextHash }));
      setEditorVisualSeedMarkdown(editorDraft.bodyMarkdown);
      setEditorSaveStatus('saved');
      setEditorSaveMessage('Guardado. Canon/VaERL pendiente de reanálisis.');
      void loadProjectContext(selectedProjectId);
    } catch (err: any) {
      const payload = err?.payload || {};
      if (payload.error === 'hash_mismatch') {
        setEditorSaveStatus('conflict');
        setEditorSaveMessage(payload.message || 'El capítulo cambió en disco. Recarga antes de guardar.');
        return;
      }
      setEditorSaveStatus('error');
      setEditorSaveMessage(payload.message || String(err));
    }
  }

  function getMarkdownSelectionRange() {
    const view = editorTextareaRef.current?.view;
    const selection = view?.state?.selection?.main;
    if (selection) return { start: selection.from || 0, end: selection.to || 0 };
    return { start: 0, end: 0 };
  }

  function focusMarkdownRange(start: number, end: number) {
    const view = editorTextareaRef.current?.view;
    if (!view) return;
    requestAnimationFrame(() => {
      view.focus();
      view.dispatch({ selection: { anchor: start, head: end } });
    });
  }



  function dispatchMarkdownChange(replacement: string, start: number, end: number, selectionStart: number, selectionEnd: number) {
    const view = editorTextareaRef.current?.view;
    if (!view) return;
    view.dispatch({ changes: { from: start, to: end, insert: replacement }, selection: { anchor: selectionStart, head: selectionEnd } });
  }

  function applyMarkdownWrap(prefix: string, suffix: string = prefix) {
    const { start, end } = getMarkdownSelectionRange();
    const selected = editorDraft.rawMarkdown.slice(start, end) || 'texto';
    const replacement = `${prefix}${selected}${suffix}`;
    dispatchMarkdownChange(replacement, start, end, start + prefix.length, start + prefix.length + selected.length);
    focusMarkdownRange(start + prefix.length, start + prefix.length + selected.length);
  }

  function applyMarkdownLinePrefix(prefix: string) {
    const { start, end } = getMarkdownSelectionRange();
    const source = editorDraft.rawMarkdown;
    const lineStart = source.lastIndexOf('\n', Math.max(0, start - 1)) + 1;
    const lineEndCandidate = source.indexOf('\n', end);
    const lineEnd = lineEndCandidate === -1 ? source.length : lineEndCandidate;
    const block = source.slice(lineStart, lineEnd);
    const nextBlock = block.split('\n').map((line) => `${prefix}${line}`).join('\n');
    dispatchMarkdownChange(nextBlock, lineStart, lineEnd, lineStart, lineStart + nextBlock.length);
    focusMarkdownRange(lineStart, lineStart + nextBlock.length);
  }

  function applyMarkdownHeading(level: string) {
    if (level === 'paragraph') return;
    const { start, end } = getMarkdownSelectionRange();
    const source = editorDraft.rawMarkdown;
    const lineStart = source.lastIndexOf('\n', Math.max(0, start - 1)) + 1;
    const lineEndCandidate = source.indexOf('\n', end);
    const lineEnd = lineEndCandidate === -1 ? source.length : lineEndCandidate;
    const line = source.slice(lineStart, lineEnd);
    const stripped = line.replace(/^#{1,6}\s+/, '').replace(/^>\s+/, '');
    if (level === 'quote') {
      const nextLine = `> ${stripped}`;
      dispatchMarkdownChange(nextLine, lineStart, lineEnd, lineStart, lineStart + nextLine.length);
      focusMarkdownRange(lineStart, lineStart + nextLine.length);
      return;
    }
    const hashes = level === 'h1' ? '#' : level === 'h2' ? '##' : '###';
    const nextLine = `${hashes} ${stripped}`;
    dispatchMarkdownChange(nextLine, lineStart, lineEnd, lineStart, lineStart + nextLine.length);
    focusMarkdownRange(lineStart, lineStart + nextLine.length);
  }

  function applyMarkdownLink() {
    const { start, end } = getMarkdownSelectionRange();
    const selected = editorDraft.rawMarkdown.slice(start, end) || 'texto';
    const replacement = `[${selected}](https://)`;
    dispatchMarkdownChange(replacement, start, end, start + 1, start + 1 + selected.length);
    const urlStart = start + replacement.indexOf('https://');
    focusMarkdownRange(urlStart, urlStart + 'https://'.length);
  }

  function onMarkdownToolbarAction(kind: string) {
    if (kind === 'undo') return undo(editorTextareaRef.current?.view?.state, editorTextareaRef.current?.view?.dispatch);
    if (kind === 'redo') return redo(editorTextareaRef.current?.view?.state, editorTextareaRef.current?.view?.dispatch);
    if (kind === 'bold') return applyMarkdownWrap('**');
    if (kind === 'italic') return applyMarkdownWrap('*');
    if (kind === 'underline') return applyMarkdownWrap('<u>', '</u>');
    if (kind === 'bullet') return applyMarkdownLinePrefix('- ');
    if (kind === 'number') return applyMarkdownLinePrefix('1. ');
    if (kind === 'check') return applyMarkdownLinePrefix('- [ ] ');
    if (kind === 'link') return applyMarkdownLink();
  }

  const markdownToolbarShell = (
    <div className={editorToolbarClassName}>
      <button type="button" onClick={() => onMarkdownToolbarAction('undo')} className="mdxeditor-toolbar-button" aria-label="Undo"><Undo2 size={16} strokeWidth={1.75} /></button>
      <button type="button" onClick={() => onMarkdownToolbarAction('redo')} className="mdxeditor-toolbar-button" aria-label="Redo"><Redo2 size={16} strokeWidth={1.75} /></button>
      <span className="mdxeditor-toolbar-separator" />
      <button type="button" onClick={() => onMarkdownToolbarAction('bold')} className="mdxeditor-toolbar-button" aria-label="Bold"><strong>B</strong></button>
      <button type="button" onClick={() => onMarkdownToolbarAction('italic')} className="mdxeditor-toolbar-button" aria-label="Italic"><em>I</em></button>
      <button type="button" onClick={() => onMarkdownToolbarAction('underline')} className="mdxeditor-toolbar-button" aria-label="Underline"><u>U</u></button>
      <span className="mdxeditor-toolbar-separator" />
      <select onChange={(event) => applyMarkdownHeading(event.target.value)} defaultValue="paragraph" className="mdxeditor-select" aria-label="Block type">
        <option value="paragraph">Paragraph</option>
        <option value="h1">Heading 1</option>
        <option value="h2">Heading 2</option>
        <option value="h3">Heading 3</option>
        <option value="quote">Quote</option>
      </select>
      <span className="mdxeditor-toolbar-separator" />
      <button type="button" onClick={() => onMarkdownToolbarAction('bullet')} className="mdxeditor-toolbar-button" aria-label="Bulleted list"><List size={16} strokeWidth={1.75} /></button>
      <button type="button" onClick={() => onMarkdownToolbarAction('number')} className="mdxeditor-toolbar-button" aria-label="Numbered list"><ListOrdered size={16} strokeWidth={1.75} /></button>
      <button type="button" onClick={() => onMarkdownToolbarAction('check')} className="mdxeditor-toolbar-button" aria-label="Check list"><ListChecks size={16} strokeWidth={1.75} /></button>
      <span className="mdxeditor-toolbar-separator" />
      <button type="button" onClick={() => onMarkdownToolbarAction('link')} className="mdxeditor-toolbar-button" aria-label="Create link"><Link2 size={16} strokeWidth={1.75} /></button>
    </div>
  );

  const warningsVisible = visibleDecisions.length;
  const runStatus = projectDetail?.run_status;
  const reviewSummary = projectDetail?.canon?.review_queue?.decision_summary || {};
  const graphVm = useMemo(() => mapGraphPayload(graphPayload), [graphPayload]);
  const selectedGraphKinds = useMemo(() => new Set(Array.from(graphKindFilter).filter((kind) => kind !== 'all') as any), [graphKindFilter]);
  const filteredGraph = useMemo(() => filterGraph(graphVm, selectedGraphKinds, graphQuery, graphRelatedOnly ? selectedGraphNodeId : null), [graphVm, selectedGraphKinds, graphQuery, graphRelatedOnly, selectedGraphNodeId]);
  const resetGraphFilters = () => { setGraphKindFilter(new Set()); setGraphQuery(''); setGraphRelatedOnly(false); };
  const toggleGraphKind = (kind: string) => {
    if (kind === 'all') { resetGraphFilters(); return; }
    setGraphKindFilter((previous) => {
      const next = new Set(previous);
      if (next.has(kind)) next.delete(kind); else next.add(kind);
      next.delete('all');
      return next;
    });
  };
  const selectedGraphEntity = useMemo(() => {
    if (!selectedGraphNodeId || !projectDetail) return null;
    return (projectDetail?.canon?.primaries || []).find((entity) => {
      const key = entity.preferred_slug || entity.canonical_name || '';
      const node = filteredGraph.byId[selectedGraphNodeId];
      return key && node && (key === node.notePath || key === node.id || node.label?.toLowerCase().includes(key.toLowerCase()));
    }) || null;
  }, [selectedGraphNodeId, projectDetail, filteredGraph]);

  const selectedGraphEntityCard = useMemo(() => {
    if (!selectedGraphNodeId || !selectedProjectId) return null;
    const node = filteredGraph.byId[selectedGraphNodeId];
    const label = node?.label || node?.display_label || '';
    const notePath = node?.notePath || node?.id || '';
    if (!label && !notePath) return null;
    return selectedGraphEntityCardVm;
  }, [selectedGraphNodeId, selectedProjectId, filteredGraph, selectedGraphEntityCardVm]);

  async function handleGraphNodeSelect(nodeId: string | null) {
    setSelectedGraphNodeId(nodeId);
    if (!nodeId || !selectedProjectId) { setSelectedGraphNoteContent(''); setSelectedGraphNoteDetail(null); setSelectedGraphEntityCardVm(null); return; }
    const node = filteredGraph.byId[nodeId];
    const notePath = node?.notePath || node?.id || '';
    if (!notePath) { setSelectedGraphNoteContent(''); setSelectedGraphNoteDetail(null); setSelectedGraphEntityCardVm(null); return; }
    try {
      const payload = await fetchNote(selectedProjectId, notePath);
      setSelectedGraphNoteContent(String(payload.markdown || ''));
      setSelectedGraphNoteDetail(payload);
    } catch { setSelectedGraphNoteContent(''); setSelectedGraphNoteDetail(null); }
    try {
      const card = await fetchEntityCard(selectedProjectId, { node_id: nodeId, note_path: notePath, canonical_label: node?.label || '' });
      setSelectedGraphEntityCardVm(card);
    } catch { setSelectedGraphEntityCardVm(null); }
  }
  const selectedGraphNode = useMemo(() => (selectedGraphNodeId ? filteredGraph.byId[selectedGraphNodeId] || null : null), [filteredGraph, selectedGraphNodeId]);
  const graphEditNode = useMemo(() => (graphEditNodeId ? filteredGraph.byId[graphEditNodeId] || null : null), [filteredGraph, graphEditNodeId]);
  const graphStats = { nodes: filteredGraph.nodes.length, edges: filteredGraph.edges.length };
  let content: React.ReactNode = null;

  if (active === 'overview') content = <OverviewBoard setActive={setActive} />;
  if (active === 'hub') content = <section><TopBar title="Project Hub" subtitle="Abrir o reanudar proyecto TextifAI completo. El runtime real 20ch se prefiere si existe." actions={<><Button>New ingestion</Button><Button variant="secondary">Open .txtfai / manifest</Button></>} /><div className="p-5 grid grid-cols-12 gap-5"><div className="col-span-12 lg:col-span-8 space-y-4"><div className="rounded-3xl border border-neutral-200 p-5 bg-neutral-50"><div className="flex items-center justify-between"><div><h2 className="font-semibold text-lg">Workspaces disponibles</h2><p className="text-sm text-neutral-500">Datos reales desde /api/projects. Se evita seleccionar fixture 2ch si hay base 20ch.</p></div><Search size={18} className="text-neutral-500" /></div><div className="mt-4 space-y-3">{projects.map((project) => <ProjectRow key={project.project_id} project={project} selected={project.project_id === selectedProjectId} onSelect={() => setSelectedProjectId(project.project_id)} />)}</div>{isMinimalFixture(selectedProject) ? <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"><AlertTriangle size={16} className="inline" /> Proyecto reducido detectado: no usar como base UX final si runtime 20ch existe.</div> : null}</div></div><aside className="col-span-12 lg:col-span-4 space-y-4"><Metric label="Contrato" value="manifest.json" note="Un archivo abre el bundle completo." /><Metric label="Futuro" value=".txtfai" note="Formato empaquetado de workspace." /><div className="rounded-3xl border border-neutral-200 p-5"><h3 className="font-semibold">Salud del proyecto</h3><div className="mt-4 space-y-3 text-sm"><div className="flex items-center gap-2"><CheckCircle2 size={16} /> {selectedProject?.workspace_status?.chapters_detected_label || `Capítulos indexados: ${projectDetail?.overview?.chapters_processed ?? 0}`}</div><div className="flex items-center gap-2"><CheckCircle2 size={16} /> {selectedProject?.workspace_status?.chapters_ready_label || `VaERL/artifacts: ${artifactsCount}`}</div><div className="flex items-center gap-2"><AlertTriangle size={16} /> {selectedProject?.workspace_status?.chapters_still_failed_label || `Warnings visibles: ${warningsVisible}`}</div></div></div></aside></div></section>;
  if (active === 'ingest') content = <section><TopBar title="Ingestion" subtitle="Crear proyecto TextifAI local-first sin provider calls en esta fase." actions={<Button variant="secondary" disabled>Ingesta deshabilitada</Button>} /><div className="p-5 grid grid-cols-12 gap-5"><div className="col-span-12 lg:col-span-7 rounded-3xl border border-neutral-200 p-5"><h2 className="font-semibold">Progreso de ingesta</h2><p className="mt-2 text-sm text-neutral-600">Después de generar proyecto, abrir `manifest.json`. `.txtfai` queda como dirección futura.</p><div className="mt-5 grid gap-3 text-sm md:grid-cols-2">{(runStatus?.steps || []).map((step) => <div key={step.id || step.label} className="rounded-2xl bg-neutral-50 border border-neutral-200 p-4"><div className="flex items-center justify-between"><div className="font-medium">{step.label || step.id || 'Paso'}</div><span className="text-xs text-neutral-600">{step.status || 'pendiente'}</span></div><div className="mt-2 h-2 rounded-full bg-neutral-200"><div className="h-2 rounded-full bg-emerald-500" style={{ width: `${Math.max(0, Math.min(100, Number(step.progress ?? 0)))}%` }} /></div><div className="mt-1 text-xs text-neutral-600">{step.progress ?? 0}%</div></div>)}{!(runStatus?.steps || []).length ? <div className="rounded-2xl bg-neutral-50 border border-neutral-200 p-4">Sin pasos disponibles</div> : null}</div></div><aside className="col-span-12 lg:col-span-5 space-y-4"><Metric label="Estado" value={runStatus?.status || 'completed_with_editorial_review'} note={runStatus?.final_state_detail || 'Ingesta completada con revisión editorial.'} /><div className="rounded-3xl border border-neutral-200 bg-neutral-50 p-5"><h2 className="font-semibold">Progreso</h2><div className="mt-3 space-y-2 text-sm"><div className="rounded-xl bg-white border border-neutral-200 px-3 py-2">Run: {runStatus?.run_id || 'sin run_id'}</div><div className="rounded-xl bg-white border border-neutral-200 px-3 py-2">Workspace seguro: {runStatus?.safe_to_open_workspace ? 'sí' : 'no'}</div>{ingestionJobs.length ? ingestionJobs.map((job) => <div key={job.job_id} className="rounded-xl bg-white border border-neutral-200 px-3 py-2">{job.run_name || job.job_id} · {job.status}</div>) : null}</div></div></aside></div></section>;
  if (active === 'codex') content = <section><TopBar title="Canon / VaERL" subtitle="Wiki author-facing del canon: entidades, hechos, evidencia y Story Bible consolidada." actions={<><Button variant="secondary">Export selection</Button><Button variant="secondary">Ver evidencia</Button></>} /><div className="p-5 grid grid-cols-12 gap-5"><div className="col-span-12 lg:col-span-8 space-y-5"><EntityRecordTable entities={projectDetail?.canon?.primaries || []} selectedKey={selectedEntityKey} onSelect={setSelectedEntityKey} /><div className="rounded-3xl border border-neutral-200 bg-white p-4"><div className="mb-3 flex items-center gap-2 text-sm font-semibold"><FileText size={16} /> Story Bible</div>{selectedProjectId ? <LegacyEmbed title="Story Bible alias inside Canon / VaERL" src={legacyUrl('notes', selectedProjectId)} /> : <div className="rounded-2xl border border-neutral-200 p-4 text-sm text-neutral-500">Selecciona proyecto.</div>}</div></div><aside className="col-span-12 lg:col-span-4"><InspectorCard entity={selectedEntity} /></aside></div></section>;
  if (active === 'graph') content = (
    <section>
      <TopBar title="Graph" subtitle="Exploración visual author-facing con física viva e inspector editorial." actions={<Button variant="secondary" onClick={resetGraphFilters}>Restablecer filtros</Button>} />
      <div className="p-5 grid grid-cols-12 gap-5">
        <aside className="col-span-12">
          <GraphToolbar
            selectedKinds={graphKindFilter}
            toggleKind={toggleGraphKind}
            query={graphQuery}
            onQueryChange={setGraphQuery}
            relatedOnly={graphRelatedOnly}
            onRelatedOnlyChange={setGraphRelatedOnly}
            onResetViewport={resetGraphFilters}
          />
        </aside>
        <div className="col-span-12 grid grid-cols-12 xl:grid-cols-5 gap-5">
          <div className="col-span-12 xl:col-span-4">
            {selectedProjectId ? <GraphCanvas nodes={filteredGraph.nodes} edges={filteredGraph.edges} selectedNodeId={selectedGraphNodeId} onSelectNode={handleGraphNodeSelect} /> : <div className="rounded-3xl border border-neutral-200 p-5 text-sm text-neutral-500">Selecciona un proyecto para abrir Graph.</div>}
          </div>
          <aside className="col-span-12 xl:col-span-1 space-y-2">
            <div className="flex justify-end">
              <Button variant="secondary" onClick={() => setGraphInspectorFullscreen(true)}>
                <Maximize2 size={14} className="inline" /> Pantalla completa
              </Button>
            </div>
            <GraphInspectorPanel
              node={selectedGraphNode}
              entityCard={selectedGraphEntity}
              entityCardVm={selectedGraphEntityCardVm}
              noteContent={selectedGraphNoteContent}
              noteDetail={selectedGraphNoteDetail}
              onEdit={(node: GraphCanvasNode) => setGraphEditNodeId(node.id)}
            />
          </aside>
        </div>
      </div>
      <GraphNodeEditDraftModal node={graphEditNode} onClose={() => setGraphEditNodeId(null)} />
    </section>
  );
    if (active === 'review') content = <section>
    <TopBar
      title="Review Queue"
      subtitle="Decisiones del autor convierten ambigüedad semántica en canon estable."
      actions={<><Button>Aplicar decisiones</Button><Button variant="secondary">Re-ejecutar validación</Button></>}
    />
    <div className="p-5 grid grid-cols-12 gap-5">
      <div className="col-span-12 lg:col-span-8 space-y-4">
        <div className="flex gap-3">
          <input value={reviewQuery} onChange={(event) => setReviewQuery(event.target.value)} className="flex-1 rounded-2xl border border-neutral-300 px-4 py-2 text-sm" placeholder="Buscar decisión..." />
          <select value={reviewSeverity} onChange={(event) => setReviewSeverity(event.target.value)} className="rounded-2xl border border-neutral-300 px-4 py-2 text-sm"><option value="all">Todas</option><option value="high">Alta</option><option value="medium">Media</option><option value="low">Baja</option></select>
        </div>
        {visibleDecisions.map((item) => <DecisionCard key={item.id} item={item} selected={selectedDecision?.id === item.id} choice={reviewDecisionChoices[item.id]} onSelect={() => setSelectedDecisionId(item.id)} onChoose={(choice) => setReviewDecisionChoices((previous) => ({ ...previous, [item.id]: choice }))} onOpenEvidencia={() => setEvidenciaModalDecisionId(item.id)} />)}
      </div>
      <aside className="col-span-12 lg:col-span-4 space-y-4">
        <Metric label="Decisiones pendientes" value={reviewSummary.total_pending ?? warningsVisible} note="Resumen dinámico de cola editorial." />
        {([
            ['possible_merges', 'Posibles fusiones'],
            ['probable_aliases', 'Aliases probables'],
            ['uncertain_relationships', 'Relaciones inciertas'],
            ['insufficient_evidence', 'Evidencia insuficiente'],
            ['pronoun_pov', 'Pronombres/POV'],
            ['unconfirmed_local_candidates', 'Candidatos no confirmados'],
          ] as const)
            .filter(([key]) => Number((reviewSummary as Record<string, number>)[key] || 0) > 0)
            .map(([key, label]) => (
              <div key={key} className="rounded-3xl border border-neutral-200 bg-white p-5 text-left shadow-sm">
                <div className="text-xs uppercase tracking-wide text-neutral-700">{label}</div>
                <div className="mt-1 text-2xl font-semibold">{Number((reviewSummary as Record<string, number>)[key] || 0)}</div>
              </div>
            ))}
      </aside>
    </div>
  </section>;
  if (active === 'editor') content = <section className={editorFullscreen ? 'fixed inset-0 z-30 bg-white overflow-hidden' : 'h-[calc(100vh-88px)]'}><TopBar title="Editor" subtitle="Solo capítulos/manuscrito desde chapter manifest canónico." actions={<><Button disabled={!canSaveEditor} onClick={handleSaveEditorChapter}>{editorSaveStatus === 'saving' ? 'Guardando...' : 'Guardar'}</Button><Button variant="secondary" onClick={() => setEditDraft({ title: 'Añadir capítulo', body: 'Draft local pendiente. No hay write-back semántico en SP-116.' })}><Plus size={14} className="inline" /> Añadir capítulo</Button></>} /><div className={editorFullscreen ? 'h-[calc(100vh-88px)] p-4' : 'h-[calc(100vh-88px)] p-5'}><div className={`editor-workspace-grid h-full min-h-0 items-stretch gap-4 ${editorFullscreen ? 'editor-workspace-grid-fullscreen' : ''}` }><aside className={`${editorFullscreen && editorChapterRailCollapsed ? 'hidden' : ''} self-stretch rounded-3xl border border-neutral-200 bg-neutral-50 p-4 min-w-0 max-w-full editor-left-rail`}><div className="flex items-center justify-between gap-2"><h2 className="font-semibold">{editorFullscreen && editorChapterRailCollapsed ? 'Cap.' : 'Capítulos'}</h2>{editorFullscreen ? <button type="button" onClick={() => setEditorChapterRailCollapsed(!editorChapterRailCollapsed)} className="rounded-xl border border-neutral-200 bg-white px-2 py-1 text-xs">{editorChapterRailCollapsed ? 'Mostrar rail' : 'Ocultar rail'}</button> : null}</div>{editorFullscreen && editorChapterRailCollapsed ? null : <div className="mt-4 space-y-2 text-sm max-w-full">{chapterNotes.map((note) => <button key={note.path} onClick={() => setEditorNotePath(note.path)} className={`w-full rounded-xl border px-3 py-2 text-left whitespace-normal break-words ${editorNotePath === note.path ? 'bg-neutral-900 text-white border-neutral-900' : 'bg-white border-neutral-200'}`}>{(note as EditorChapter & { name?: string }).display_title || note.name || note.path}</button>)}</div>}</aside><div className="min-h-0 min-w-0 editor-main-pane"><div className={`rounded-3xl border border-neutral-200 bg-white p-5 h-full min-h-0 flex flex-col`}><div className="flex items-center justify-between gap-3"><div><div className="text-xs uppercase text-neutral-500">Editor dual · capítulo real</div><h2 className="mt-2 font-semibold">{((chapterNotes.find((note) => note.path === editorNotePath) as (EditorChapter & { name?: string }) | undefined)?.display_title) || editorNotePath || 'Selecciona capítulo'}</h2><p className="mt-2 text-xs text-neutral-500">Write-back Markdown con hash guard y backup. Canon/VaERL queda pendiente de reanálisis.</p></div><div className="flex flex-wrap items-center justify-end gap-2"><button type="button" onClick={() => switchEditorMode('markdown')} className={`rounded-2xl border px-3 py-2 text-xs ${editorMode === 'markdown' ? 'border-neutral-900 bg-neutral-900 text-white' : 'border-neutral-200 bg-neutral-100 text-neutral-700'}`}>Modo Markdown</button><button type="button" onClick={() => switchEditorMode('visual')} className={`rounded-2xl border px-3 py-2 text-xs ${editorMode === 'visual' ? 'border-neutral-900 bg-neutral-900 text-white' : 'border-neutral-200 bg-neutral-100 text-neutral-700'}`}>Modo visual</button><Button disabled={!canSaveEditor} onClick={handleSaveEditorChapter}>{editorSaveStatus === 'saving' ? 'Guardando...' : 'Guardar'}</Button><Button variant="secondary" onClick={() => setEditorFullscreen(!editorFullscreen)}><Maximize2 size={14} className="inline" /> {editorFullscreen ? 'Salir fullscreen' : 'Pantalla completa'}</Button></div></div>{editorModeWarning ? <div className="mt-3 rounded-2xl border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">{editorModeWarning}</div> : null}{editorDraft.parseStatus === 'malformed_frontmatter' ? <div className="mt-3 rounded-2xl border border-neutral-300 bg-neutral-50 px-3 py-2 text-xs text-neutral-700">Frontmatter malformado. Modo Markdown activo para preservar contenido.</div> : null}{editorSaveMessage ? <div className={`mt-3 rounded-2xl border px-3 py-2 text-xs ${editorSaveStatus === 'saved' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : editorSaveStatus === 'conflict' || editorSaveStatus === 'error' ? 'border-red-200 bg-red-50 text-red-700' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>{editorSaveMessage}</div> : <div className="mt-3 rounded-2xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-700">Guardar escribe Markdown y marca Canon/VaERL pendiente de reanálisis; no reanaliza Graph ni Review.</div>}<div className="mt-4 flex-1 min-h-0 rounded-2xl border border-neutral-200 bg-neutral-50 p-3 overflow-hidden">{editorMode === 'markdown' ? <div className="h-full overflow-auto rounded-2xl border border-neutral-200 bg-white p-2">{markdownToolbarShell}<div className="mt-3 h-[calc(100%-68px)] min-h-0"><CodeMirror ref={editorTextareaRef} value={editorDraft.rawMarkdown} height="100%" extensions={[markdown(), EditorView.lineWrapping, history(), keymap.of([{ key: 'Mod-z', run: undo }, { key: 'Mod-y', run: redo }, { key: 'Mod-Shift-z', run: redo }]), placeholder('Escribe capítulo en Markdown')] } basicSetup={{ lineNumbers: true, highlightActiveLine: true, highlightActiveLineGutter: true, foldGutter: true }} onChange={(value) => updateMarkdownDraft(value)} className="h-full w-full overflow-hidden rounded-2xl border border-neutral-200 bg-white text-[15px] leading-7 text-neutral-800 shadow-sm" /></div></div> : <div className="h-full overflow-auto rounded-2xl border border-neutral-200 bg-white p-2"><MDXEditor key={`${editorDraft.loadedChapterId}:${editorDraft.loadedContentHash}:${editorMode}`} markdown={editorVisualSeedMarkdown} onChange={updateVisualDraft} plugins={[toolbarPlugin({ toolbarClassName: editorToolbarClassName, toolbarContents: () => <><UndoRedo /><Separator /><BoldItalicUnderlineToggles /><Separator /><BlockTypeSelect /><Separator /><ListsToggle /><Separator /><CreateLink /></> }), headingsPlugin(), listsPlugin(), quotePlugin(), linkPlugin(), linkDialogPlugin(), thematicBreakPlugin(), markdownShortcutPlugin()]} /></div>}</div></div></div><aside className={`${editorFullscreen && editorChapterRailCollapsed ? 'hidden' : ''} self-stretch min-h-0 space-y-4 min-w-0 editor-right-panel`}><div className="h-full rounded-3xl border border-neutral-200 bg-neutral-50 p-5 text-sm text-neutral-600"><Metric label="Origen" value={String(editorSource?.source_used || 'chapter_manifest')} note={`Panel derecho retenido también en fullscreen · ${chapterNotes.length} capítulos canónicos cargados`} /><div className="rounded-2xl bg-white border border-neutral-200 p-3"><b>Rewrite selection</b><br />Placeholder. Sin LLM.</div><div className="mt-3 rounded-2xl bg-white border border-neutral-200 p-3"><b>Canon risks</b><br />Save marca needs_reanalysis. VaERL/Graph/Review no se regeneran.</div></div></aside></div></div></section>;
  if (active === 'story') content = <section><TopBar title="Canon / VaERL" subtitle="Story Bible deep link alias. Canon / VaERL es la vista principal." actions={<Button variant="secondary" onClick={() => setActive('codex')}>Open Canon / VaERL</Button>} /><div className="p-5 grid grid-cols-12 gap-5"><aside className="col-span-12 lg:col-span-3 rounded-3xl border border-neutral-200 bg-neutral-50 p-4"><h2 className="font-semibold">Vault tree</h2><div className="mt-4 space-y-2 text-sm">{(projectDetail?.notes || []).slice(0, 16).map((note) => <div key={note.path} className="rounded-xl bg-white border border-neutral-200 px-3 py-2">{note.name || note.path}</div>)}</div></aside><div className="col-span-12 lg:col-span-9">{selectedProjectId ? <LegacyEmbed title="Story Bible alias inside Canon / VaERL" src={legacyUrl('notes', selectedProjectId)} /> : <div className="rounded-3xl border border-neutral-200 p-5 text-sm text-neutral-500">Selecciona proyecto.</div>}</div></div></section>;
  if (active === 'ask') content = <section><TopBar title="AI Studio" subtitle="Ask Canon, brainstorming y Character Lab/chat con personajes. Placeholders sin provider calls." actions={<><Button variant="secondary">Open answer history</Button><Button variant="secondary">Check source coverage</Button></>} /><div className="p-5 grid grid-cols-12 gap-5"><div className="col-span-12 lg:col-span-7 rounded-3xl border border-neutral-200 p-5 min-h-[560px] flex flex-col"><div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4 text-sm text-neutral-500">Ask Canon: “¿Qué sabe Sera antes del capítulo 6?”</div><div className="mt-5 rounded-3xl border border-neutral-200 p-5 bg-white shadow-sm"><div className="font-semibold">Respuesta grounded</div><p className="mt-3 text-sm leading-7">Placeholder. No se genera canon sin backend de evidencia.</p></div><div className="mt-auto pt-5 flex gap-2"><input className="flex-1 rounded-2xl border border-neutral-300 px-4 py-3 text-sm" placeholder="Pregunta sobre canon, brainstorming o personajes..." /><Button variant="secondary" disabled>Enviar</Button></div></div><aside className="col-span-12 lg:col-span-5 space-y-4"><Metric label="Grounding" value="Evidencia-first" note="Sin claims no soportados." /><Metric label="Brainstorming" value="Futuro" note="Ideación asistida anclada al canon." /><Metric label="Character Lab" value="Futuro" note="Chat con personajes sin escribir back al manuscrito." /></aside></div></section>;

  return <Shell active={active} setActive={setActive}><motion.div key={active} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.18 }}>{content}</motion.div>{error ? <div className="mx-5 mb-5 rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}<EvidenciaModal item={evidenceModalItem} onClose={() => setEvidenciaModalDecisionId('')} />{graphInspectorFullscreen ? <div className="fixed inset-0 z-50 bg-black/30 p-4"><div className="h-full w-full rounded-3xl border border-neutral-200 bg-white shadow-2xl overflow-y-auto"><div className="sticky top-0 z-10 flex items-center justify-between border-b border-neutral-200 bg-white p-4"><h2 className="text-lg font-semibold">Ficha del nodo</h2><Button variant="secondary" onClick={() => setGraphInspectorFullscreen(false)}><X size={14} className="inline" /> Salir fullscreen</Button></div><div className="p-4"><GraphInspectorPanel node={selectedGraphNode} entityCard={selectedGraphEntity} entityCardVm={selectedGraphEntityCardVm} noteContent={selectedGraphNoteContent} noteDetail={selectedGraphNoteDetail} onEdit={(node: GraphCanvasNode) => setGraphEditNodeId(node.id)} /></div></div></div> : null}{editDraft ? <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"><div className="w-full max-w-2xl rounded-3xl border border-neutral-200 bg-white shadow-2xl"><div className="flex items-center justify-between border-b border-neutral-200 p-5"><div><h2 className="font-semibold">{editDraft.title}</h2><p className="text-sm text-neutral-500">{editDraft.notePath || 'nuevo draft local'}</p></div><button onClick={() => setEditDraft(null)} className="rounded-full p-2 hover:bg-neutral-100"><X size={18} /></button></div><div className="p-5"><textarea readOnly value={editDraft.body} className="h-48 w-full rounded-2xl border border-neutral-200 bg-neutral-50 p-4 text-sm" /><p className="mt-3 text-sm text-neutral-500">Guardar cambios llega con drafts/patch queue. No write-back en SP-105D.</p></div></div></div> : null}</Shell>;
}

export default App;
