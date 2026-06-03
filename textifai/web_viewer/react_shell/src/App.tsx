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
  Save,
  Sparkles,
  SplitSquareHorizontal,
  Upload,
  Users,
  Share2,
  X,
  List,
  ListOrdered,
  ListChecks,
  Link2,
  Undo2,
  Redo2,
} from 'lucide-react';
import {
  ChapterReanalysisResponse,
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
  saveEntityFicheMarkdown,
  EntityCard,
  fetchEntityCard,
  requestChapterReanalysis } from './api';
import { mapGraphPayload, filterGraph } from './graph/GraphDataAdapter';
import { GraphCanvas } from './graph/GraphCanvas';
import { GraphToolbar } from './graph/GraphToolbar';
import { GraphNodeEditDraftModal } from './graph/GraphNodeEditDraftModal';
import { GraphCanvasNode } from './graph/types';
import { GraphInspector as GraphInspectorPanel } from './graph/GraphInspector';

type DecisionItem = { id: string; title: string; severity: string; source: string; action: string; raw: ReviewItem; actionKind?: string; hasTarget?: boolean; materiality?: 'normal' | 'low' | 'noise' };
type ReviewDecisionChoice = 'accept' | 'reject' | 'manual' | 'create' | 'discard' | 'context' | 'defer';
type EvidenciaModalItem = DecisionItem | null;
type EditDraft = { title: string; notePath?: string; body: string } | null;
type EditorChapter = { chapter_id?: string; path: string; title: string; display_title?: string; order?: number | null; source_used?: string; content_hash?: string };
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

type SaveStatus = 'idle' | 'dirty' | 'saving' | 'saved' | 'error' | 'conflict';

const editorContractStrings = [
  'textifai-editor-toolbar',
  'editor.toolbar.contract',
  'editor.save.dirty',
  'editor.save.saving',
  'editor.save.chapter_saved',
  'editor.save.conflict_message',
  'editor.canon_risks',
  'editor.reanalysis.pending',
  'editor.reanalysis.notice',
  'editor.reanalysis.action',
] as const;

import { t, type UiI18nKey } from './i18n/ui';
import { Button, Metric, TopBar } from './common/ui';
import { AppShell } from './shell/AppShell';
import { screens, type ScreenConfig, type SectionId } from './shell/navigation';
import { ProjectHubView } from './modules/project/ProjectHubView';
import { IngestionView } from './modules/ingestion/IngestionView';
import { ReviewQueueView } from './modules/review/ReviewQueueView';
import { GraphView } from './modules/graph/GraphView';
import { CanonVaerlView } from './modules/canon/CanonVaerlView';
import { EditorView as EditorModuleView } from './modules/editor/EditorView';
import { AIStudioView } from './modules/ai/AIStudioView';
import { StoryAliasView } from './modules/canon/StoryAliasView';

const overviewCards: Array<{ id: SectionId; titleKey: UiI18nKey; textKey: UiI18nKey; icon: ScreenConfig['icon'] }> = [
  { id: 'hub', titleKey: 'overview.project_hub.title', textKey: 'overview.project_hub.text', icon: Database },
  { id: 'ingest', titleKey: 'overview.ingestion.title', textKey: 'overview.ingestion.text', icon: Upload },
  { id: 'review', titleKey: 'overview.review.title', textKey: 'overview.review.text', icon: Inbox },
  { id: 'graph', titleKey: 'overview.graph.title', textKey: 'overview.graph.text', icon: GitBranch },
  { id: 'codex', titleKey: 'overview.codex.title', textKey: 'overview.codex.text', icon: Network },
  { id: 'editor', titleKey: 'overview.editor.title', textKey: 'overview.editor.text', icon: SplitSquareHorizontal },
  { id: 'ask', titleKey: 'overview.ai.title', textKey: 'overview.ai.text', icon: MessageSquareText },
];

const kindLabels: Record<string, string> = { chapter: 'capítulo', character: 'personaje', concept: 'concepto', event: 'evento', object: 'objeto', place: 'lugar', review: 'revisión' };
const graphPalette: Record<string, string> = { chapter: '#7f7a6a', character: '#111827', concept: '#6b7280', event: '#9a3412', object: '#0f766e', place: '#1d4ed8', review: '#b91c1c' };
const FULL_LOGO_SRC = '/branding/textifai-logo-full.png';
const editorToolbarClassName = 'textifai-editor-toolbar';
const markdownToolbarClassName = editorToolbarClassName;

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

function extractFirstH1(markdown: string): string {
  const line = String(markdown || '').split('\n').find((item) => item.startsWith('# '));
  return line ? line.slice(2).trim() : '';
}


function formatRelativeSaveTime(iso: string | null | undefined): string {
  if (!iso) return t('editor.save.not_saved_yet');
  const diffMs = Math.max(0, Date.now() - new Date(iso).getTime());
  const diffSeconds = Math.floor(diffMs / 1000);
  if (diffSeconds < 60) return t('editor.save.saved_since', { value: `${diffSeconds}s` });
  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) return t('editor.save.saved_since', { value: `${diffMinutes}m` });
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return t('editor.save.saved_since', { value: `${diffHours}h` });
  const diffDays = Math.floor(diffHours / 24);
  return t('editor.save.saved_since', { value: `${diffDays}d` });
}
function replaceOrInsertFirstH1(markdown: string, title: string): string {
  const cleanTitle = title.trim();
  if (!cleanTitle) return markdown;
  const source = String(markdown || '');
  const frontmatterEnd = source.startsWith('---\n') ? source.indexOf('\n---\n', 4) : -1;
  const frontmatter = frontmatterEnd >= 0 ? source.slice(0, frontmatterEnd + 5) : '';
  const body = frontmatterEnd >= 0 ? source.slice(frontmatterEnd + 5) : source;
  const lines = body.split('\n');
  const index = lines.findIndex((line) => line.startsWith('# '));
  if (index >= 0) {
    lines[index] = `# ${cleanTitle}`;
    return `${frontmatter}${lines.join('\n')}`;
  }
  return `${frontmatter}# ${cleanTitle}\n${body.startsWith('\n') ? body : `\n${body}`}`;
}

function replaceSelectionRange(source: string, start: number, end: number, replacement: string): { nextText: string; nextStart: number; nextEnd: number } {
  const nextText = `${source.slice(0, start)}${replacement}${source.slice(end)}`;
  const cursor = start + replacement.length;
  return { nextText, nextStart: cursor, nextEnd: cursor };
}

function createEditorDraft(markdown: string, chapterId: string, loadedContentHash?: string): EditorDraftState {
  const rawMarkdown = String(markdown || '');
  const { frontmatterRaw, bodyMarkdown, parseStatus } = splitFrontmatter(rawMarkdown);
  return {
    rawMarkdown,
    frontmatterRaw,
    bodyMarkdown,
    parseStatus,
    dirty: false,
    loadedChapterId: chapterId,
    loadedContentHash: String(loadedContentHash || hashEditorContent(rawMarkdown)),
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
  const title = item.title || (target ? t('review.item.reviewing_target', { target }) : t('review.item.source_with_entity', { source: item.source_entity || t('review.source.candidate') }));
  const summary = item.human_reason || item.subtitle || item.recommendation || item.suggested_action || item.review_type || item.type || item.evidence_summary || t('review.item.needs_decision');
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
    source: item.evidence_summary || (item.evidence_refs || []).map((row) => row.chapter_id || row.pointer || t('review.source.evidence_pending')).slice(0, 2).join(', ') || t('review.source.evidence_pending'),
    action: summary,
    actionKind,
    hasTarget: Boolean(target),
    materiality,
    raw: item,
  };
}

function reviewItemMatchesQuery(item: DecisionItem, query: string): boolean {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return true;
  const rawTarget = item.raw.target_label || (typeof item.raw.target_entity === 'object' ? item.raw.target_entity?.label : item.raw.target_entity) || '';
  const rawSource = item.raw.source_entity || '';
  const haystack = [item.title, item.action, String(item.raw.review_type || ''), String(item.raw.type || ''), String(rawSource), String(rawTarget)].join(' ').toLowerCase();
  return haystack.includes(normalized);
}

function normalizeEntityToken(value: unknown): string {
  return String(value || '').trim().toLowerCase();
}

declare global {
  interface Window {
    __sp123bDebug?: Record<string, unknown>;
    __TEXTIFAI_FICHE_DEBUG__?: Record<string, unknown>;
  }
}

function reviewItemMatchesEntity(item: DecisionItem, entityTokens: Set<string>): boolean {
  if (!entityTokens.size) return true;
  const rawTarget = item.raw.target_label || (typeof item.raw.target_entity === 'object' ? item.raw.target_entity?.label : item.raw.target_entity) || '';
  const rawSource = item.raw.source_entity || '';
  return entityTokens.has(normalizeEntityToken(rawSource)) || entityTokens.has(normalizeEntityToken(rawTarget));
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
  return `rounded-2xl border px-4 py-2 text-sm font-medium ${active ? 'border-txf-surface-soft bg-txf-nav-active text-txf-nav-active-text ring-1 ring-txf-surface-soft/70' : 'border-txf-border bg-txf-surface-soft text-txf-text hover:bg-txf-surface-muted'}`;
}

function formatDecisionChoice(choice?: ReviewDecisionChoice): string {
  if (choice === 'accept') return t('review.accept');
  if (choice === 'reject') return t('review.reject');
  if (choice === 'merge') return t('review.manual');
  return t('review.unmarked');
}

const reviewSeverityLabels = {
  all: 'review.severity.all',
  high: 'review.severity.high',
  medium: 'review.severity.medium',
  low: 'review.severity.low',
} as const;

function formatReviewSeverity(value: keyof typeof reviewSeverityLabels): string {
  return t(reviewSeverityLabels[value]);
}

function legacyUrl(view: 'graph' | 'notes' | 'canon', projectId: string): string {
  return `/index.html?embed=1&view=${encodeURIComponent(view)}&project=${encodeURIComponent(projectId)}`;
}





function ProjectRow({ project, selected, onSelect }: { project: ProjectSummary; selected?: boolean; onSelect: () => void }) { const title = project.work?.title || project.name || t('project.kind.default'); return <button onClick={onSelect} className={`w-full rounded-2xl border p-4 text-left ${selected ? 'bg-txf-nav-active text-txf-nav-active-text border-txf-border-strong' : 'bg-txf-surface border-txf-border hover:bg-txf-surface-soft'}`}><div className="grid grid-cols-12 gap-3 items-center"><div className="col-span-12 md:col-span-7"><div className="font-semibold">{title}</div><div className={`text-xs ${selected ? 'text-txf-surface-soft' : 'text-txf-subtle'}`}>{project.kind || t('project.kind.workspace')} · {project.work?.language || t('project.language.pending')}</div></div><div className="col-span-4 md:col-span-2 text-sm">{t('project.count.chapters', { count: project.chapter_count || 0 })}</div><div className="col-span-4 md:col-span-2 text-sm">{t('project.count.nodes', { count: project.graph_summary?.node_count || 0 })}</div><div className="col-span-4 md:col-span-1 text-sm">{isMinimalFixture(project) ? t('project.fixture.dev') : t('project.fixture.real')}</div></div><div className={`mt-3 grid gap-2 text-xs ${selected ? 'text-txf-surface-soft' : 'text-txf-subtle'}`}><div>{project.workspace_status?.chapters_detected_label || t('project.workspace_status.chapters_detected', { count: project.chapter_count || 0 })}</div><div>{project.workspace_status?.chapters_ready_label || t('project.workspace_status.chapters_ready')}</div><div>{project.workspace_status?.chapters_still_failed_label || t('project.workspace_status.chapters_failed')}</div><div>{project.workspace_status?.semantic_review_label || t('project.workspace_status.semantic_review')}</div></div></button>; }

function DecisionCard({ item, selected, choice, onSelect, onChoose, onOpenEvidencia }: { item: DecisionItem; selected?: boolean; choice?: ReviewDecisionChoice; onSelect: () => void; onChoose: (choice: ReviewDecisionChoice) => void; onOpenEvidencia: () => void }) {
  const choose = (nextChoice: ReviewDecisionChoice) => { onSelect(); onChoose(nextChoice); };
  return <article className={`w-full rounded-3xl border p-5 text-left ${selected ? 'border-txf-border-strong bg-txf-nav-active text-txf-nav-active-text' : 'border-txf-border bg-txf-surface'}`}>
    <div className="flex items-start justify-between gap-3">
      <button type="button" onClick={onSelect} className="min-w-0 flex-1 text-left">
        <div className={`inline-flex rounded-full border px-3 py-1 text-xs uppercase tracking-wide ${severityClass(item.severity)}`}>{String(item.severity).toUpperCase()} {t('review.severity').toUpperCase()} · {item.source || t('review.no_linked_chapters')}</div>
        <h3 className={`mt-2 text-2xl font-semibold tracking-tight ${selected ? 'text-txf-nav-active-text' : ''}`}>{item.title}</h3>
        <p className={`mt-2 text-sm ${selected ? 'text-txf-surface-soft' : 'text-txf-subtle'}`}>{item.human_reason || item.summary || item.evidence_summary || item.action}</p>
      </button>
      <AlertTriangle size={18} className={`mt-1 shrink-0 ${severityIconClass(item.severity)}`} />
    </div>
    <div className="mt-5 flex flex-wrap gap-2">
      <button type="button" onClick={() => choose('accept')} className={decisionButtonClass(choice === 'accept')}>{item.actionKind === 'relationship_candidate' ? t('review.accept_relationship') : item.actionKind === 'alias_candidate' ? t('review.accept_alias') : item.hasTarget ? t('review.accept_suggestion') : t('review.accept')}</button>
      <button type="button" onClick={() => choose('reject')} className={decisionButtonClass(choice === 'reject')}>{t('review.reject')}</button>
      {item.hasTarget ? <button type="button" onClick={() => choose('manual')} className={decisionButtonClass(choice === 'manual')}>{t('review.choose_other_entity')}…</button> : <button type="button" onClick={() => choose('manual')} className={decisionButtonClass(choice === 'manual')}>{t('review.resolve_manually')}…</button>}
      {!item.hasTarget ? <button type="button" onClick={() => choose('create')} className={decisionButtonClass(choice === 'create')}>{t('review.create_entity')}</button> : null}
      {(item.materiality === 'low' || item.materiality === 'noise' || !item.hasTarget) ? <button type="button" onClick={() => choose('discard')} className={decisionButtonClass(choice === 'discard')}>{t('review.discard_canon')}</button> : null}
      <button type="button" onClick={() => choose('context')} className={decisionButtonClass(choice === 'context')}>{t('review.keep_context')}</button>
      <Button variant="secondary" onClick={() => { onSelect(); onOpenEvidencia(); }} className="rounded-2xl border-txf-border bg-txf-surface-soft px-3 py-1.5 font-medium text-txf-action hover:bg-txf-surface-muted">{t('review.view_evidence')}</Button>
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
  if (sourceMapChunksCount <= 0) return t('graph.no_fragment_fallback');
  return t('review.item.no_fragment');
}

function EvidenciaModal({ item, onClose }: { item: EvidenciaModalItem; onClose: () => void }) {
  if (!item) return null;
  const refs = item.raw.evidence_refs || [];
  const technicalDetails = item.raw.technical_details as Record<string, unknown> | undefined;
  const sourceMapChunksCount = Number(technicalDetails?.source_map_chunks_count || 0);
  const evidenceStoreUsed = Boolean(technicalDetails?.evidence_store_used);
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/25 p-4"><div className="w-full max-w-3xl rounded-3xl border border-txf-border bg-txf-surface shadow-txf-floating"><div className="flex items-center justify-between border-b border-txf-border p-5"><div><div className="text-xs uppercase tracking-wide text-txf-subtle">{t('review.evidence')}</div><h2 className="mt-1 text-xl font-semibold">{item.title}</h2><p className="mt-1 text-sm text-txf-subtle">{item.action}</p></div><button type="button" onClick={onClose} className="rounded-full p-2 hover:bg-txf-surface-soft"><X size={18} /></button></div><div className="grid gap-4 p-5 lg:grid-cols-[1.3fr_0.7fr]"><div className="editor-right-panel-scroll space-y-3 pr-1">{refs.length ? refs.map((ref, index) => <div key={`${ref.chapter_id || ref.pointer || 'evidence'}-${index}`} className="rounded-2xl border border-txf-border bg-txf-surface-muted p-4"><div className="text-xs uppercase tracking-wide text-txf-subtle">{t('review.evidence_item', { index: index + 1 })}</div><div className="mt-2 text-sm text-txf-text">{t('review.chapter')}: {ref.chapter_label || ref.chapter_id || t('review.no_structured_reference')}</div>{ref.has_text && ref.excerpt ? <div className="mt-2 rounded-xl bg-txf-surface border border-txf-border p-3 text-sm text-txf-text italic">{'«' + ref.excerpt.slice(0, 240) + '»'}</div> : <div className="mt-2 rounded-xl bg-amber-50 border border-amber-200 p-3 text-sm text-amber-800">{ref.reason || evidenceMissingReason(sourceMapChunksCount)}</div>}<details className="mt-2"><summary className="cursor-pointer text-xs text-txf-subtle">{t('review.technical_details')}</summary><div className="mt-2 text-xs text-txf-subtle">{t('review.pointer')}: {ref.pointer_short || ref.pointer || t('review.no_structured_reference')}</div></details></div>) : <div className="rounded-2xl border border-txf-border bg-txf-surface-muted p-4 text-sm text-txf-subtle">{t('review.no_structured_evidence')}</div>}</div><aside className="editor-right-panel-scroll space-y-3 pr-1"><div className="rounded-2xl border border-txf-border bg-txf-surface-muted p-4"><div className="text-xs uppercase tracking-wide text-txf-subtle">{t('review.decision_type')}</div><div className="mt-2 text-sm text-txf-text">{item.raw.review_type || t('review.editorial_decision')}</div></div><div className="rounded-2xl border border-txf-border bg-txf-surface-muted p-4"><div className="text-xs uppercase tracking-wide text-txf-subtle">{t('review.recommendation')}</div><div className="mt-2 text-sm text-txf-text">{item.raw.recommendation || t('review.needs_author_decision')}</div></div><div className="rounded-2xl border border-txf-border bg-txf-surface-muted p-4"><div className="text-xs uppercase tracking-wide text-txf-subtle">{t('review.severity_label')}</div><div className={`mt-2 inline-flex rounded-full border px-3 py-1 text-xs uppercase tracking-wide ${severityClass(item.severity)}`}>{item.severity}</div></div><div className="rounded-2xl border border-txf-border bg-txf-surface-muted p-4 text-xs text-txf-subtle">{t('review.evidence_store')}: {evidenceStoreUsed ? t('review.yes') : t('review.no')} · source_map.chunks: {sourceMapChunksCount}</div></aside></div><div className="flex justify-end border-t border-txf-border p-5"><Button variant="secondary" onClick={onClose}>{t('common.close')}</Button></div></div></div>;
}
function EntityRecordTable({ entities, selectedKey, onSelect }: { entities: CanonEntity[]; selectedKey: string; onSelect: (key: string) => void }) { return <div className="overflow-hidden rounded-3xl border border-txf-border"><div className="grid grid-cols-12 bg-txf-surface-soft px-4 py-3 text-xs uppercase tracking-wide text-txf-subtle"><span className="col-span-5">{t('review.entity')}</span><span className="col-span-2">{t('review.decision_type')}</span><span className="col-span-2">{t('review.confidence')}</span><span className="col-span-3">{t('review.state')}</span></div>{entities.slice(0, 18).map((entity) => { const key = entity.preferred_slug || entity.canonical_name || ''; const active = key === selectedKey; return <button key={key} onClick={() => onSelect(key)} className={`w-full grid grid-cols-12 px-4 py-3 text-sm border-t border-txf-border items-center text-left ${active ? 'bg-txf-surface-muted' : 'bg-txf-surface hover:bg-txf-surface-soft'}`}><span className="col-span-5 font-medium">{entity.canonical_name || key}</span><span className="col-span-2 text-txf-subtle">{entity.entity_kind || 'entity'}</span><span className="col-span-2 text-txf-subtle">{entity.confidence ?? '—'}</span><span className="col-span-3 text-txf-subtle">{entity.review_state || 'ready'}</span></button>; })}</div>; }
function InspectorCard({ entity }: { entity: CanonEntity | undefined }) { if (!entity) return <div className="rounded-3xl border border-txf-border p-5 text-sm text-txf-subtle">{t('review.inspector.empty')}</div>; return <div className="rounded-3xl border border-txf-border bg-txf-surface-muted p-5"><div className="text-xs uppercase tracking-wide text-txf-subtle">{t('review.inspector.label')}</div><h2 className="mt-2 text-xl font-semibold">{entity.canonical_name}</h2><p className="mt-3 text-sm leading-6 text-txf-subtle">{entity.summary || t('review.inspector.summary_missing')}</p><div className="mt-4 flex flex-wrap gap-2">{(entity.aliases || []).slice(0, 6).map((alias) => <span key={alias} className="rounded-full bg-txf-surface border border-txf-border px-3 py-1 text-xs">{alias}</span>)}</div><Button variant="secondary">{t('review.inspector.edit_draft')}</Button></div>; }
function LegacyEmbed({ title, src }: { title: string; src: string }) { return <div className="rounded-3xl border border-txf-border bg-txf-surface p-3 shadow-txf-card"><div className="mb-3 text-xs uppercase tracking-wide text-txf-subtle">{title}</div><iframe title={title} src={src} className="h-[620px] w-full rounded-2xl border border-txf-border bg-txf-surface" /></div>; }

function OverviewBoard({ setActive }: { setActive: (id: SectionId) => void }) { return <section><TopBar title={t('overview.title')} subtitle={t('overview.subtitle')} actions={<Button onClick={() => setActive('hub')}>{t('overview.open_project')}</Button>} /><div className="grid grid-cols-12 gap-5 p-5">{overviewCards.map((card) => { const Icon = card.icon; return <button key={card.id} onClick={() => setActive(card.id)} className="col-span-12 rounded-3xl border border-txf-border bg-txf-surface p-5 text-left hover:bg-txf-surface-soft md:col-span-6 xl:col-span-3"><div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-txf-nav-active text-txf-nav-active-text"><Icon size={18} /></div><h3 className="mt-4 font-semibold">{t(card.titleKey)}</h3><p className="mt-2 text-sm leading-6 text-txf-subtle">{t(card.textKey)}</p></button>; })}</div></section>; }

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
  return <div className="grid grid-cols-12 gap-5 p-5"><aside className="col-span-12 xl:col-span-2 rounded-3xl border border-txf-border bg-txf-surface-muted p-4"><h2 className="font-semibold">{t('graph.filters_title')}</h2><div className="mt-4 flex flex-wrap gap-2 xl:block xl:space-y-2">{['all', ...kinds].map((kind) => <button key={kind} onClick={() => setKindFilter(kind)} className={`rounded-2xl px-3 py-2 text-sm xl:w-full xl:text-left ${kindFilter === kind ? 'bg-txf-nav-active text-txf-nav-active-text' : 'bg-txf-surface border border-txf-border text-txf-text'}`}>{kind === 'all' ? t('graph.toolbar.filters.all') : kindLabels[kind] || kind}</button>)}</div></aside><div className="col-span-12 xl:col-span-7 rounded-3xl border border-txf-border bg-txf-surface-muted p-4"><div className="mb-3 flex items-center justify-between"><div><h2 className="font-semibold">{t('graph.view.title')}</h2><p className="text-sm text-txf-subtle">{t('graph.view.subtitle')}</p></div><StatusChip>{t('graph.visible_nodes', { count: visibleNodes.length })}</StatusChip></div><svg viewBox="0 0 760 520" className="h-[560px] w-full rounded-2xl bg-txf-surface border border-txf-border">{visibleEdges.map((edge) => { const source = byId.get(String(edge.source)); const target = byId.get(String(edge.target)); if (!source || !target) return null; return <line key={edge.id || `${edge.source}-${edge.target}`} x1={source.x} y1={source.y} x2={target.x} y2={target.y} stroke="#d4d4d4" strokeWidth="1.5" />; })}{positioned.map((node) => { const kind = String(node.display_kind || node.kind || 'note'); const active = selected?.id === node.id; return <g key={node.id} onClick={() => setSelectedNodeId(node.id || '')} className="cursor-pointer"><circle cx={node.x} cy={node.y} r={active ? 16 : Number(node.radius || 11)} fill={graphPalette[kind] || '#525252'} stroke={active ? '#111827' : '#ffffff'} strokeWidth={active ? 4 : 2} /><text x={node.x + 18} y={node.y + 4} fontSize="12" fill="#171717">{node.label || node.id}</text></g>; })}</svg></div><GraphInspectorPanel
            node={selected}
            entityCard={null}
            entityCardVm={null}
            noteContent=""
            noteDetail={null}
            onEdit={(node: GraphCanvasNode) =>
              setEditDraft?.({
                title: t('graph.edit_title', { label: node.label || node.id }),
                notePath: String((node as any).notePath || (node as any).note_path || ''),
                body: t('graph.edit_draft_body'),
              })
            }
          /></div>;
}

function GraphInspector({ node, entityCard, noteContent, noteDetail, onEdit, setEditDraft }: { node?: any; entityCard?: CanonEntity | null; noteContent?: string; noteDetail?: NoteDetail | null; onEdit?: (node: GraphCanvasNode) => void; setEditDraft?: (draft: EditDraft) => void }) {
  if (!node) return <aside className="col-span-12 xl:col-span-3 rounded-3xl border border-txf-border p-5 text-sm text-txf-subtle">{t('graph.inspector.empty_legacy')}</aside>;
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
  const runEdit = () => onEdit ? onEdit(node as GraphCanvasNode) : setEditDraft ? setEditDraft({ title: t('graph.edit_title', { label }), notePath, body: t('graph.edit_draft_body') }) : undefined;
  return <aside className="col-span-12 xl:col-span-3 rounded-3xl border border-txf-border bg-txf-surface p-5 shadow-txf-card max-h-[720px] overflow-y-auto"><div className="text-xs uppercase tracking-wide text-txf-subtle">{t('graph.inspector.title')}</div><h2 className="mt-2 text-xl font-semibold">{label}</h2><div className="mt-2 flex flex-wrap gap-2"><span className="rounded-full bg-txf-surface-soft px-3 py-1 text-xs">{kindLabels[kind] || kind}</span><span className="rounded-full bg-txf-surface-soft px-3 py-1 text-xs">{node.reviewState || node.review_state || node.status || t('graph.review_label')}</span><span className="rounded-full bg-txf-surface-soft px-3 py-1 text-xs">{t('graph.inspector.relations_count', { count: relationCount })}</span><span className="rounded-full bg-txf-surface-soft px-3 py-1 text-xs">{t('graph.inspector.evidence_count', { count: evidenceCount })}</span></div><div className="mt-4 rounded-2xl border border-txf-border bg-txf-surface-muted p-4 text-sm leading-6 text-txf-text">{summary || t('graph.summary_missing')}</div>{aliases.length ? <div className="mt-4"><div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">{t('graph.inspector.aliases_legacy')}</div><div className="flex flex-wrap gap-1">{aliases.slice(0, 10).map((alias) => <span key={alias} className="rounded-full border border-txf-border bg-txf-surface px-2 py-0.5 text-xs">{alias}</span>)}</div></div> : null}{facts.length ? <div className="mt-4"><div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">{t('graph.inspector.facts_bio')}</div><ul className="list-inside list-disc space-y-1 text-sm text-txf-subtle">{facts.slice(0, 6).map((fact, i) => <li key={i}>{fact}</li>)}</ul></div> : null}{relationships.length ? <div className="mt-4"><div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">{t('graph.inspector.main_relations')}</div><div className="space-y-1">{relationships.slice(0, 6).map((rel, i) => <div key={i} className="rounded-xl border border-txf-border bg-txf-surface-muted px-3 py-2 text-sm">{rel.target || t('graph.fiche_entity_fallback')} — {rel.type || rel.relation_type || t('graph.relations')}</div>)}</div></div> : null}<div className="mt-4 grid gap-2 text-sm"><div className="rounded-2xl bg-txf-surface-muted border border-txf-border p-3">{t('graph.backlinks')}: {backlinks.length}</div><div className="rounded-2xl bg-txf-surface-muted border border-txf-border p-3">{t('graph.outgoing_links')}: {outgoing.length}</div><div className="rounded-2xl bg-txf-surface-muted border border-txf-border p-3">{t('graph.local_graph')}: {t('graph.visible_nodes', { count: noteDetail?.local_graph?.nodes?.length || 0 })}</div><div className="rounded-2xl bg-txf-surface-muted border border-txf-border p-3">{t('graph.fiche_note_ref')}: {notePath || t('review.no_structured_reference')}</div></div>{backlinks.length ? <div className="mt-4"><div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">{t('graph.backlinks')}</div><div className="space-y-1">{backlinks.slice(0, 8).map((backlink) => <div key={backlink} className="rounded-xl border border-txf-border bg-txf-surface-muted px-3 py-2 text-xs">{backlink}</div>)}</div></div> : null}{outgoing.length ? <div className="mt-4"><div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">{t('graph.outgoing_links')}</div><div className="space-y-1">{outgoing.slice(0, 8).map((link) => <div key={link.target || link.label} className="rounded-xl border border-txf-border bg-txf-surface-muted px-3 py-2 text-xs">{link.label || link.target}</div>)}</div></div> : null}{preview ? <details className="mt-4" open><summary className="cursor-pointer rounded-2xl border border-txf-border bg-txf-surface-muted px-3 py-2 text-xs font-semibold">{t('graph.markdown_view')}</summary><pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-2xl bg-txf-surface-muted p-3 text-xs text-txf-subtle">{preview}</pre></details> : null}<div className="mt-5 flex flex-wrap gap-2"><Button onClick={runEdit}>{t('graph.edit')}</Button><Button variant="secondary">{t('graph.open_sheet')}</Button><Button variant="secondary">{t('graph.view_review')}</Button></div></aside>;
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
  const [reviewEntityFilterTokens, setReviewEntityFilterTokens] = useState<Set<string>>(new Set());
  const [reviewSeverity, setReviewSeverity] = useState<keyof typeof reviewSeverityLabels>('all');
  const [reviewSeverityOpen, setReviewSeverityOpen] = useState(false);
  const [selectedDecisionId, setSelectedDecisionId] = useState<string>('');
  const [reviewDecisionChoices, setReviewDecisionChoices] = useState<Record<string, ReviewDecisionChoice>>({});
  const [evidenceModalDecisionId, setEvidenciaModalDecisionId] = useState<string>('');
  const [editorNotePath, setEditorNotePath] = useState<string>('');
  const [editorFullscreen, setEditorFullscreen] = useState(false);
  const [editorChapterListOpen, setEditorChapterListOpen] = useState(false);
  const [editorDraft, setEditorDraft] = useState<EditorDraftState>(() => createEditorDraft('', ''));
  const [editorMode, setEditorMode] = useState<EditorMode>('visual');
  const [editorModeWarning, setEditorModeWarning] = useState<string>('');
  const [editorVisualSeedMarkdown, setEditorVisualSeedMarkdown] = useState<string>('');
  const [editorSaveStatus, setEditorSaveStatus] = useState<SaveStatus>('idle');
  const [editorSaveMessage, setEditorSaveMessage] = useState<string>('');
  const [editorLastSavedAt, setEditorLastSavedAt] = useState<string>('');
  const [editorSaveBannerVisible, setEditorSaveBannerVisible] = useState(false);
  const [editorReanalysisStatus, setEditorReanalysisStatus] = useState<'idle' | 'queued' | 'error'>('idle');
  const [editorReanalysisMessage, setEditorReanalysisMessage] = useState<string>('');
  const [editorTitleDrafts, setEditorTitleDrafts] = useState<Record<string, string>>({});
  const [renamingChapterPath, setRenamingChapterPath] = useState<string>('');
  const [renameChapterValue, setRenameChapterValue] = useState<string>('');

  const editorTextareaRef = useRef<any>(null);

  useEffect(() => {
    if (!reviewSeverityOpen) return;
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (target.closest('[data-review-severity-dropdown]')) return;
      setReviewSeverityOpen(false);
    };
    window.addEventListener('pointerdown', handlePointerDown);
    return () => window.removeEventListener('pointerdown', handlePointerDown);
  }, [reviewSeverityOpen]);

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
        display_title: editorTitleDrafts[String(chapter.path || '')] || String(chapter.display_title || chapter.title || chapter.path || ''),
        kind: 'chapter',
        role: 'chapter',
        status: String(chapter.semantic_state || chapter.status || 'ready'),
        semantic_state: String(chapter.semantic_state || chapter.status || ''),
        dirty_state: Boolean(chapter.dirty_state),
        content_hash: String(chapter.content_hash || ''),
        source_used: String(chapter.source_used || editorSource?.source_used || 'chapter_manifest'),
      }));
  }, [editorSource, editorTitleDrafts]);
  const selectedEditorChapter = useMemo(() => chapterNotes.find((chapter) => chapter.path === editorNotePath) || null, [chapterNotes, editorNotePath]);
  const selectedEditorTitle = selectedEditorChapter?.display_title || selectedEditorChapter?.name || editorNotePath || t('editor.chapter_list.empty');
  const selectedEditorTitleValue = editorTitleDrafts[editorNotePath] || selectedEditorTitle;
  const saveSupported = String(editorSource?.source_used || '').toLowerCase() === 'project_store';
  const saveBlockedByFrontmatter = editorMode === 'visual' && editorDraft.parseStatus === 'malformed_frontmatter';
  const canSaveEditor = Boolean(selectedProjectId && selectedEditorChapter?.chapter_id && editorDraft.dirty && saveSupported && !saveBlockedByFrontmatter && editorSaveStatus !== 'saving');
  const selectedEditorSemanticState = String((selectedEditorChapter as any)?.semantic_state || (selectedEditorChapter as any)?.status || '');
  const selectedEditorNeedsReanalysis = editorReanalysisStatus === 'queued' || selectedEditorSemanticState === 'needs_reanalysis' || editorSaveStatus === 'saved';
  const editorSaveStatusText = editorSaveStatus === 'dirty' || editorDraft.dirty ? t('editor.save.dirty') : editorSaveStatus === 'saving' ? t('editor.save.saving') : editorSaveStatus === 'saved' ? (formatRelativeSaveTime(editorLastSavedAt) || t('editor.save.saved')) : editorSaveStatus === 'conflict' ? t('editor.save.conflict') : editorSaveStatus === 'error' ? t('editor.save.error') : '';
  const editorSaveBannerClass = editorSaveStatus === 'saved' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : editorSaveStatus === 'conflict' || editorSaveStatus === 'error' ? 'border-red-200 bg-red-50 text-txf-text' : 'border-amber-200 bg-amber-50 text-amber-800';
  void legacyEditorChapterSelectionContract;
  const allDecisions = useMemo(() => ((projectDetail?.canon?.review_queue?.decision_items || projectDetail?.canon?.review_queue?.items || []) as ReviewItem[]).map(toDecisionItem), [projectDetail]);
  const visibleDecisions = useMemo(() => {
    return allDecisions.filter((item) => {
      if (reviewSeverity !== 'all' && item.severity.toLowerCase() !== reviewSeverity) return false;
      if (!reviewItemMatchesEntity(item, reviewEntityFilterTokens)) return false;
      return reviewItemMatchesQuery(item, reviewQuery);
    });
  }, [allDecisions, reviewQuery, reviewSeverity, reviewEntityFilterTokens]);
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
  useEffect(() => {
    if (editorMode !== 'visual' || editorDraft.parseStatus !== 'ready') return;
    setEditorVisualSeedMarkdown(editorDraft.bodyMarkdown);
  }, [editorMode, editorDraft.loadedChapterId, editorDraft.loadedContentHash, editorDraft.parseStatus, editorDraft.bodyMarkdown]);

  async function loadInitial() { try { const [projectList, config, jobs] = await Promise.all([fetchProjects(), fetchIngestionConfig(), fetchIngestionJobs()]); setProjects(projectList); setIngestionConfig(config); setIngestionJobs(jobs); const preferred = choosePreferredProject(projectList); if (preferred) setSelectedProjectId(preferred.project_id); } catch (err) { setError(String(err)); } }
  async function loadProjectContext(projectId: string) { try { const [detail, graph, reviewQueue, artifacts] = await Promise.all([fetchProjectDetail(projectId), fetchGraph(projectId), fetchReviewQueue(projectId), fetchArtifacts(projectId)]); setProjectDetail({ ...detail, canon: { ...detail.canon, review_queue: reviewQueue } }); setGraphPayload(graph || null); setArtifactsCount((artifacts.artifacts || []).length); const firstEntity = detail.canon?.primaries?.[0]; if (firstEntity) setSelectedEntityKey(firstEntity.preferred_slug || firstEntity.canonical_name || ''); const graphSelect = typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('graph_select')?.trim().toLowerCase() : ''; const selectedFromUrl = graphSelect ? graph?.nodes?.find((node) => [node.label, node.display_label, node.canonical_id, node.id].some((value) => String(value || '').toLowerCase() === graphSelect)) : null; const firstNode = selectedFromUrl || graph?.nodes?.[0]; if (firstNode?.id) setSelectedGraphNodeId(firstNode.id); const firstChapter = ((detail as any)?.editor_chapters?.chapters || [])[0]; if (firstChapter?.path) { const firstChapterPath = String(firstChapter.path); setEditorNotePath(firstChapterPath); void loadEditorNote(projectId, firstChapterPath); } } catch (err) { setError(String(err)); } }
  async function loadEditorNote(projectId: string, notePath: string) {
    try {
      const payload = await fetchNote(projectId, notePath);
      const rawMarkdown = String(payload.markdown || '');
      const chapterMeta = chapterNotes.find((chapter) => chapter.path === notePath) as (EditorChapter | undefined);
      const nextDraft = createEditorDraft(rawMarkdown, notePath, String(chapterMeta?.content_hash || ''));
      const loadedTitle = extractFirstH1(rawMarkdown) || String(chapterMeta?.display_title || chapterMeta?.title || '');
      if (loadedTitle) setEditorTitleDrafts((current) => ({ ...current, [notePath]: loadedTitle }));
      setEditorDraft((current) => {
        if (current.loadedChapterId === nextDraft.loadedChapterId && current.loadedContentHash === nextDraft.loadedContentHash) return current;
        return nextDraft;
      });
      setEditorVisualSeedMarkdown(nextDraft.bodyMarkdown);
      setEditorModeWarning('');
      markEditorDirty();
      setEditorSaveBannerVisible(false);
      setEditorLastSavedAt('');
      setEditorReanalysisStatus('idle');
      setEditorReanalysisMessage('');
    } catch (_err) {
      const fallback = t('editor.no_chapter_content');
      setEditorDraft(createEditorDraft(fallback, notePath));
      setEditorModeWarning('');
      markEditorDirty();
      setEditorSaveBannerVisible(false);
    }
  }
  useEffect(() => {
    if (!editorSaveBannerVisible || editorSaveStatus !== 'saved') return;
    const timer = window.setTimeout(() => setEditorSaveBannerVisible(false), 4000);
    return () => window.clearTimeout(timer);
  }, [editorSaveBannerVisible, editorSaveStatus, editorSaveMessage]);
  function markEditorDirty() {
    setEditorSaveStatus('dirty');
    setEditorSaveMessage(t('editor.save.dirty'));
    setEditorSaveBannerVisible(true);
  }
  function updateMarkdownDraft(nextRawMarkdown: string) {
    markEditorDirty();
    const nextTitle = extractFirstH1(nextRawMarkdown);
    if (nextTitle && editorDraft.loadedChapterId) setEditorTitleDrafts((current) => ({ ...current, [editorDraft.loadedChapterId]: nextTitle }));
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
    markEditorDirty();
    const nextTitle = extractFirstH1(nextBodyMarkdown);
    if (nextTitle && editorDraft.loadedChapterId) setEditorTitleDrafts((current) => ({ ...current, [editorDraft.loadedChapterId]: nextTitle }));
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

  function commitChapterTitleRename(path: string, title: string) {
    const clean = title.trim();
    if (!path || !clean) {
      setRenamingChapterPath('');
      return;
    }
    setEditorTitleDrafts((current) => ({ ...current, [path]: clean }));
    if (path === editorDraft.loadedChapterId) {
      const nextRawMarkdown = replaceOrInsertFirstH1(editorDraft.rawMarkdown, clean);
      const { frontmatterRaw, bodyMarkdown, parseStatus } = splitFrontmatter(nextRawMarkdown);
      setEditorDraft((current) => ({ ...current, rawMarkdown: nextRawMarkdown, frontmatterRaw, bodyMarkdown, parseStatus, dirty: true }));
      setEditorVisualSeedMarkdown(bodyMarkdown);
      markEditorDirty();
    }
    setRenamingChapterPath('');
  }

  async function saveChapterTitleRename(path: string, title: string) {
    const clean = title.trim();
    if (!selectedProjectId || !clean) {
      setRenamingChapterPath('');
      return;
    }
    commitChapterTitleRename(path, clean);
    const chapterMeta = chapterNotes.find((chapter) => chapter.path === path) as (EditorChapter | undefined);
    const chapterId = String(chapterMeta?.chapter_id || '');
    if (!chapterId) return;
    try {
      setEditorSaveStatus('saving');
      setEditorSaveMessage(t('editor.save.saving'));
    setEditorSaveBannerVisible(true);
      let markdown = editorDraft.rawMarkdown;
      let expectedHash = editorDraft.loadedContentHash;
      if (path !== editorDraft.loadedChapterId) {
        const payload = await fetchNote(selectedProjectId, path);
        markdown = String(payload.markdown || '');
        expectedHash = String(chapterMeta?.content_hash || '');
      }
      const nextMarkdown = replaceOrInsertFirstH1(markdown, clean);
      const result = await saveChapterMarkdown(selectedProjectId, chapterId, nextMarkdown, expectedHash, clean);
      if (path === editorDraft.loadedChapterId) {
        setEditorDraft((current) => ({ ...current, rawMarkdown: nextMarkdown, bodyMarkdown: splitFrontmatter(nextMarkdown).bodyMarkdown, dirty: false, loadedContentHash: String(result.new_hash || current.loadedContentHash) }));
      }
      setEditorSaveStatus('saved');
      setEditorLastSavedAt(result.saved_at || new Date().toISOString());
      setEditorSaveMessage(t('editor.save.chapter_saved'));
      setEditorSaveBannerVisible(true);
      setEditorReanalysisStatus('queued');
      setEditorLastSavedAt(String(result.saved_at || new Date().toISOString()));
      void loadProjectContext(selectedProjectId);
    } catch (err: any) {
      const payload = err?.payload || {};
      if (payload.error === 'hash_mismatch') {
        setEditorSaveStatus('conflict');
        setEditorSaveMessage(t('editor.save.conflict_message'));
        setEditorSaveBannerVisible(true);
        return;
      }
      setEditorSaveStatus('error');
      setEditorSaveMessage(`${t('editor.save.error_prefix')} ${payload.message || String(err)}`);
      setEditorSaveBannerVisible(true);
    }
  }

  function updateCurrentChapterTitleDraft(title: string) {
    if (!editorNotePath) return;
    const clean = title;
    setEditorTitleDrafts((current) => ({ ...current, [editorNotePath]: clean }));
    const nextRawMarkdown = replaceOrInsertFirstH1(editorDraft.rawMarkdown, clean.trim() || selectedEditorTitle);
    const { frontmatterRaw, bodyMarkdown, parseStatus } = splitFrontmatter(nextRawMarkdown);
    setEditorDraft((current) => ({ ...current, rawMarkdown: nextRawMarkdown, frontmatterRaw, bodyMarkdown, parseStatus, dirty: true }));
    setEditorVisualSeedMarkdown(bodyMarkdown);
    markEditorDirty();
  }

  async function handleRequestChapterReanalysis() {
    if (!selectedProjectId || !selectedEditorChapter?.chapter_id) return;
    try {
      const result: ChapterReanalysisResponse = await requestChapterReanalysis(selectedProjectId, selectedEditorChapter.chapter_id);
      setEditorReanalysisStatus(result.status === 'queued' ? 'queued' : 'idle');
      setEditorReanalysisMessage(result.message || t('editor.reanalysis.pending_not_implemented'));
    } catch (err: any) {
      const payload = err?.payload || {};
      setEditorReanalysisStatus('error');
      setEditorReanalysisMessage(payload.message || String(err));
    }
  }

  async function handleSaveEditorChapter() {
    if (!selectedProjectId || !selectedEditorChapter?.chapter_id) return;
    if (saveBlockedByFrontmatter) {
      setEditorSaveStatus('error');
      setEditorSaveMessage(t('editor.save.malformed_frontmatter'));
      setEditorSaveBannerVisible(true);
      return;
    }
    setEditorSaveStatus('saving');
    setEditorSaveMessage(t('editor.save.saving'));
    setEditorSaveBannerVisible(true);
    try {
      const result: ChapterSaveResponse = await saveChapterMarkdown(selectedProjectId, selectedEditorChapter.chapter_id, editorDraft.rawMarkdown, editorDraft.loadedContentHash, selectedEditorTitleValue);
      const nextHash = String(result.new_hash || hashEditorContent(editorDraft.rawMarkdown));
      setEditorDraft((current) => ({ ...current, dirty: false, loadedContentHash: nextHash }));
      setEditorVisualSeedMarkdown(editorDraft.bodyMarkdown);
      setEditorSaveStatus('saved');
      setEditorLastSavedAt(result.saved_at || new Date().toISOString());
      setEditorSaveMessage(t('editor.save.chapter_saved'));
      setEditorSaveBannerVisible(true);
      setEditorReanalysisStatus('queued');
      void loadProjectContext(selectedProjectId);
    } catch (err: any) {
      const payload = err?.payload || {};
      if (payload.error === 'hash_mismatch') {
        setEditorSaveStatus('conflict');
        setEditorSaveMessage(t('editor.save.conflict_message'));
        setEditorSaveBannerVisible(true);
        return;
      }
      setEditorSaveStatus('error');
      setEditorSaveMessage(`${t('editor.save.error_prefix')} ${payload.message || String(err)}`);
      setEditorSaveBannerVisible(true);
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
    <div className={markdownToolbarClassName}>
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

  function selectGraphEntityBySelectToken(selectToken: string) {
    const normalizedToken = normalizeEntityToken(selectToken);
    if (!import.meta.env.PROD) {
      window.__TEXTIFAI_FICHE_DEBUG__ = { ...(window.__TEXTIFAI_FICHE_DEBUG__ || {}), last_graph_select_token: selectToken };
    }
    window.__sp123bDebug = {
      ...(window.__sp123bDebug || {}),
      selectToken,
      normalizedToken,
      graphNodeCount: graphVm.nodes.length,
      selectedGraphNodeBefore: selectedGraphNodeId,
    };
    if (!normalizedToken) return false;
    const node = graphVm.nodes.find((candidate) => {
      const values = [candidate.id, candidate.canonical_id, candidate.label, candidate.display_label, candidate.notePath].map(normalizeEntityToken);
      return values.includes(normalizedToken);
    }) || null;
    window.__sp123bDebug = {
      ...(window.__sp123bDebug || {}),
      resolvedNodeId: node?.id || '',
      resolvedNodeLabel: node?.label || '',
      resolvedNodeNotePath: node?.notePath || '',
    };
    if (!node?.id) return false;
    if (active !== 'graph') setActive('graph');
    setGraphKindFilter(new Set());
    setGraphQuery('');
    setGraphRelatedOnly(false);
    setSelectedGraphNodeId(node.id);
    void handleGraphNodeSelect(node.id);
    setGraphInspectorFullscreen(false);
    return true;
  }

  function clearGraphSelectFromUrl() {
    const current = new URL(window.location.href);
    if (!current.searchParams.has('graph_select') && !current.hash.includes('graph_select=')) return;
    current.searchParams.delete('graph_select');
    if (current.hash.includes('graph_select=')) current.hash = current.hash.replace(/([?#&])graph_select=[^&#]*/g, '').replace(/[#&?]$/, '');
    window.history.replaceState(window.history.state, '', `${current.pathname}${current.search}${current.hash}`);
  }

  function handleGraphInternalEntityLinkClick(href: string) {
    const url = new URL(href, window.location.href);
    const hashSelect = href.trim().startsWith('#') ? url.hash.replace(/^#.*graph_select=/, '') : '';
    const selectToken = hashSelect || url.searchParams.get('graph_select') || url.hash.replace(/^#.*graph_select=/, '') || '';
    window.__sp123bDebug = {
      ...(window.__sp123bDebug || {}),
      callbackCalled: true,
      callbackHref: href,
      callbackToken: selectToken,
      urlBefore: window.location.href,
      activeBefore: active,
    };
    if (!selectToken) return;
    if (selectGraphEntityBySelectToken(selectToken)) {
      clearGraphSelectFromUrl();
      window.__sp123bDebug = {
        ...(window.__sp123bDebug || {}),
        callbackResolved: true,
        urlAfter: window.location.href,
      };
    }
  }

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

  useEffect(() => {
    if (!selectedProjectId || !selectedGraphNodeId) return;
    void handleGraphNodeSelect(selectedGraphNodeId);
  }, [selectedProjectId, selectedGraphNodeId]);

  useEffect(() => {
    window.__sp123bDebug = {
      ...(window.__sp123bDebug || {}),
      selectedGraphNodeCurrent: selectedGraphNodeId,
      activeCurrent: active,
    };
  }, [active, selectedGraphNodeId]);

  async function handleSaveGraphEntityFiche(params: { entityId: string; notePath: string; markdown: string; expectedHash: string; canonicalLabel: string }) {
    if (!selectedProjectId) throw new Error('project_required');
    return saveEntityFicheMarkdown(selectedProjectId, params.entityId, params.markdown, params.expectedHash, params.canonicalLabel, params.notePath);
  }

  function handleGraphLocalView(node: GraphCanvasNode) {
    if (!node?.id) return;
    setSelectedGraphNodeId(node.id);
    setGraphRelatedOnly(true);
  }

  function handleOpenGraphReview(entityLabel: string) {
    const tokens = new Set<string>([
      normalizeEntityToken(entityLabel),
      normalizeEntityToken(selectedGraphEntity?.canonical_name),
      normalizeEntityToken(selectedGraphEntity?.preferred_slug),
    ]);
    tokens.delete('');
    setReviewEntityFilterTokens(tokens);
    setReviewQuery('');
    setActive('review');
  }
  const selectedGraphNode = useMemo(() => (selectedGraphNodeId ? filteredGraph.byId[selectedGraphNodeId] || null : null), [filteredGraph, selectedGraphNodeId]);
  const selectedGraphReviewCount = useMemo(() => {
    if (!selectedGraphNode?.label) return 0;
    const tokens = new Set<string>([
      normalizeEntityToken(selectedGraphNode.label),
      normalizeEntityToken(selectedGraphEntity?.canonical_name),
      normalizeEntityToken(selectedGraphEntity?.preferred_slug),
    ]);
    tokens.delete('');
    return allDecisions.filter((item) => reviewItemMatchesEntity(item, tokens)).length;
  }, [allDecisions, selectedGraphEntity?.canonical_name, selectedGraphEntity?.preferred_slug, selectedGraphNode?.label]);
  const graphEditNode = useMemo(() => (graphEditNodeId ? filteredGraph.byId[graphEditNodeId] || null : null), [filteredGraph, graphEditNodeId]);
  const graphStats = { nodes: filteredGraph.nodes.length, edges: filteredGraph.edges.length };
  let content: React.ReactNode = null;

  if (active === 'overview') content = <OverviewBoard setActive={setActive} />;
  if (active === 'hub') content = <ProjectHubView projectRows={projects.map((project) => <ProjectRow key={project.project_id} project={project} selected={project.project_id === selectedProjectId} onSelect={() => setSelectedProjectId(project.project_id)} />)} reducedProjectWarning={isMinimalFixture(selectedProject)} chaptersProcessed={projectDetail?.overview?.chapters_processed ?? 0} artifactsCount={artifactsCount} warningsVisible={warningsVisible} />;
  if (active === 'ingest') content = <IngestionView runStatus={runStatus} ingestionJobs={ingestionJobs} />;
  if (active === 'codex') content = <section><TopBar title={t('codex.title')} subtitle={t('codex.subtitle')} actions={<><Button variant="secondary">{t('codex.export_selection')}</Button><Button variant="secondary">{t('codex.view_evidence')}</Button></>} /><div className="p-5 grid grid-cols-12 gap-5"><div className="col-span-12 lg:col-span-8 space-y-5"><EntityRecordTable entities={projectDetail?.canon?.primaries || []} selectedKey={selectedEntityKey} onSelect={setSelectedEntityKey} /><div className="rounded-3xl border border-txf-border bg-txf-surface p-4"><div className="mb-3 flex items-center gap-2 text-sm font-semibold"><FileText size={16} /> {t('codex.story_bible')}</div>{selectedProjectId ? <LegacyEmbed title={t('story_alias.legacy_notes_title')} src={legacyUrl('notes', selectedProjectId)} /> : <div className="rounded-2xl border border-txf-border p-4 text-sm text-txf-subtle">{t('codex.select_project')}</div>}</div></div><aside className="col-span-12 lg:col-span-4"><InspectorCard entity={selectedEntity} /></aside></div></section>;
  if (active === 'graph') content = (
    <section data-testid="graph-view">
      <TopBar title={t('graph.title')} subtitle={t('graph.route.subtitle')} actions={<Button variant="secondary" onClick={resetGraphFilters}>{t('graph.reset_filters')}</Button>} />
      <div className="p-5 grid grid-cols-12 gap-5">
        <aside className="col-span-12">
          <GraphToolbar
            selectedKinds={graphKindFilter}
            toggleKind={toggleGraphKind}
            query={graphQuery}
            onQueryChange={setGraphQuery}
            onResetViewport={resetGraphFilters}
          />
        </aside>
        <div className="col-span-12 grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(22rem,26rem)] 2xl:grid-cols-[minmax(0,1fr)_minmax(24rem,30rem)]">
          <div className="min-w-0">
            {selectedProjectId ? <GraphCanvas nodes={filteredGraph.nodes} edges={filteredGraph.edges} selectedNodeId={selectedGraphNodeId} onSelectNode={handleGraphNodeSelect} /> : <div className="rounded-3xl border border-txf-border p-5 text-sm text-txf-subtle">{t('graph.select_project')}</div>}
          </div>
          <aside className="min-w-0 space-y-2 xl:sticky xl:top-5 xl:self-start">
            <GraphInspectorPanel
              node={selectedGraphNode}
              entityCard={selectedGraphEntity}
              entityCardVm={selectedGraphEntityCardVm}
              reviewCountOverride={selectedGraphReviewCount}
              noteContent={selectedGraphNoteContent}
              noteDetail={selectedGraphNoteDetail}
              onEdit={(node: GraphCanvasNode) => setGraphEditNodeId(node.id)}
              onViewLocalGraph={handleGraphLocalView}
              onOpenReview={handleOpenGraphReview}
              onInternalEntityLinkClick={handleGraphInternalEntityLinkClick}
              onSaveFiche={handleSaveGraphEntityFiche}
            />
          </aside>
        </div>
      </div>
      <GraphNodeEditDraftModal node={graphEditNode} onClose={() => setGraphEditNodeId(null)} />
    </section>
  );
    if (active === 'review') content = <section>
    <TopBar
      title={t('review.title')}
      subtitle={t('review.author_decisions_subtitle')}
      actions={<><Button>{t('review.apply_decisions')}</Button><Button variant="secondary">{t('review.rerun_validation')}</Button></>}
    />
    <div className="p-5 grid grid-cols-12 gap-5">
      <div className="col-span-12 lg:col-span-8 space-y-4">
        <div className="flex gap-3">
          <input value={reviewQuery} onChange={(event) => { setReviewEntityFilterTokens(new Set()); setReviewQuery(event.target.value); }} className="flex-1 rounded-2xl border border-txf-border-strong bg-txf-surface px-4 py-2 text-sm text-txf-text placeholder:text-txf-subtle" placeholder={t('review.search_placeholder')} />
          <div className="relative" data-review-severity-dropdown>
            <button type="button" onClick={() => setReviewSeverityOpen((value) => !value)} className="inline-flex min-w-[88px] items-center justify-between gap-3 rounded-2xl border border-txf-border-strong bg-txf-surface px-4 py-2 text-sm text-txf-text hover:bg-txf-surface-soft">
              <span>{formatReviewSeverity(reviewSeverity)}</span>
              <ChevronDown size={16} className={`shrink-0 transition-transform ${reviewSeverityOpen ? 'rotate-180' : ''}`} />
            </button>
            {reviewSeverityOpen ? <div className="absolute right-0 top-[calc(100%+8px)] z-20 overflow-hidden rounded-2xl border border-txf-border-strong bg-txf-surface shadow-txf-floating">{([
              'all',
              'high',
              'medium',
              'low',
            ] as const).map((value) => <button key={value} type="button" onClick={() => { setReviewSeverity(value); setReviewSeverityOpen(false); }} className={`block w-full px-5 py-2 text-left text-sm ${reviewSeverity === value ? 'bg-txf-nav-active text-txf-nav-active-text' : 'text-txf-text hover:bg-txf-surface-soft'}`}>{formatReviewSeverity(value)}</button>)}</div> : null}
          </div>
        </div>
        {visibleDecisions.map((item) => <DecisionCard key={item.id} item={item} selected={selectedDecision?.id === item.id} choice={reviewDecisionChoices[item.id]} onSelect={() => setSelectedDecisionId(item.id)} onChoose={(choice) => setReviewDecisionChoices((previous) => ({ ...previous, [item.id]: choice }))} onOpenEvidencia={() => setEvidenciaModalDecisionId(item.id)} />)}
      </div>
      <aside className="col-span-12 lg:col-span-4 space-y-4">
        <Metric label={t('review.pending_decisions')} value={reviewSummary.total_pending ?? warningsVisible} note={t('review.summary_note')} />
        {([
            ['possible_merges', 'review.possible_merges'],
            ['probable_aliases', 'review.probable_aliases'],
            ['uncertain_relationships', 'review.uncertain_relations'],
            ['insufficient_evidence', 'review.insufficient_evidence'],
            ['pronoun_pov', 'review.pronoun_pov'],
            ['unconfirmed_local_candidates', 'review.unconfirmed_local_candidates'],
          ] as const)
            .filter(([key]) => Number((reviewSummary as Record<string, number>)[key] || 0) > 0)
            .map(([key, label]) => (
              <div key={key} className="rounded-3xl border border-txf-border bg-txf-surface p-5 text-left">
                <div className="text-xs uppercase tracking-wide text-txf-text">{t(label)}</div>
                <div className="mt-1 text-2xl font-semibold">{Number((reviewSummary as Record<string, number>)[key] || 0)}</div>
              </div>
            ))}
      </aside>
    </div>
  </section>;
  if (active === 'editor') content = <section className={editorFullscreen ? 'fixed inset-0 z-30 bg-txf-surface overflow-hidden' : 'h-[calc(100vh-88px)]'}><TopBar title={t('editor.title')} subtitle={t('editor.subtitle')} actions={null} /><div className={editorFullscreen ? 'editor-workspace-shell h-[calc(100vh-88px)] p-4' : 'editor-workspace-shell h-[calc(100vh-88px)] p-5'}><div className={`editor-workspace-grid h-full min-h-0 items-stretch gap-4 ${editorFullscreen ? 'editor-workspace-grid-fullscreen' : ''}` }><aside className="self-stretch rounded-3xl border border-txf-border bg-txf-surface p-4 min-w-0 max-w-full editor-left-rail"><div className="flex items-center justify-between gap-2"><h2 className="font-semibold">{t('editor.chapters')}</h2><div className="flex items-center gap-2"><button type="button" onClick={() => setEditorChapterListOpen((value) => !value)} className="editor-chapter-toggle rounded-xl border border-txf-border bg-txf-surface-soft px-2 py-1 text-xs text-txf-action hover:bg-txf-surface-muted">{editorChapterListOpen ? t('editor.chapter_list.hide') : t('editor.chapter_list.show')}</button><button type="button" onClick={() => setEditDraft({ title: t('editor.chapter.add'), body: t('editor.chapter.add_body') })} className="rounded-xl border border-txf-border bg-txf-surface px-2 py-1 text-xs hover:bg-txf-surface-soft"><Plus size={12} className="inline" /> {t('common.add')}</button></div></div><button type="button" onClick={() => setEditorChapterListOpen((value) => !value)} className="editor-chapter-toggle mt-3 w-full rounded-xl border border-txf-border bg-txf-surface-muted px-3 py-2 text-left text-xs text-txf-subtle"><span className="font-semibold text-txf-text">{t('editor.chapter_list.selected')}</span> {selectedEditorTitleValue || t('editor.chapter_list.empty')}</button><div className={`mt-4 space-y-2 text-sm max-w-full editor-chapter-list ${editorChapterListOpen ? 'editor-chapter-list-open' : ''}`}> {chapterNotes.map((note) => renamingChapterPath === note.path ? <input key={note.path} autoFocus value={renameChapterValue} onChange={(event) => setRenameChapterValue(event.target.value)} onBlur={() => saveChapterTitleRename(note.path, renameChapterValue)} onKeyDown={(event) => { if (event.key === 'Enter') saveChapterTitleRename(note.path, renameChapterValue); if (event.key === 'Escape') { setRenamingChapterPath(''); setRenameChapterValue(''); } }} className="w-full rounded-xl border border-txf-border-strong bg-txf-surface px-3 py-2 text-left text-txf-text" /> : <div key={note.path} className={`flex items-start gap-2 rounded-xl border px-2 py-2 ${editorNotePath === note.path ? 'bg-txf-nav-active text-txf-nav-active-text border-txf-border-strong' : 'bg-txf-surface border-txf-border'}`}><button onClick={() => setEditorNotePath(note.path)} className="flex-1 text-left whitespace-normal break-words px-1">{(note as EditorChapter & { name?: string }).display_title || note.name || note.path}</button><button type="button" onClick={() => { setRenamingChapterPath(note.path); setRenameChapterValue(String((note as EditorChapter & { name?: string }).display_title || note.name || note.path)); }} className={`shrink-0 rounded-lg border px-2 py-1 text-xs ${editorNotePath === note.path ? 'border-neutral-700 bg-neutral-800 text-neutral-100' : 'border-txf-border bg-txf-surface text-txf-subtle'}`}>✎</button></div>)}</div></aside><div className="min-h-0 min-w-0 editor-main-pane"><div className={`rounded-3xl border border-txf-border bg-txf-surface p-5 h-full min-h-0 flex flex-col`}><div className="flex items-center justify-between gap-3"><div><h2 className="text-2xl font-semibold tracking-tight text-neutral-900">{selectedEditorTitleValue}</h2><p className="mt-2 text-xs text-txf-subtle">{editorSaveStatusText || formatRelativeSaveTime(editorLastSavedAt)}</p></div><div className="flex flex-wrap items-center justify-end gap-2"><div className="inline-flex items-center rounded-full border border-txf-border bg-txf-surface-soft p-1"><button type="button" onClick={() => switchEditorMode('markdown')} className={`rounded-full px-3 py-1.5 text-xs transition ${editorMode === 'markdown' ? 'bg-txf-surface text-neutral-900 shadow-txf-card' : 'text-txf-subtle hover:text-neutral-900'}`}>{t('editor.mode.markdown')}</button><button type="button" onClick={() => switchEditorMode('visual')} className={`rounded-full px-3 py-1.5 text-xs transition ${editorMode === 'visual' ? 'bg-txf-surface text-neutral-900 shadow-txf-card' : 'text-txf-subtle hover:text-neutral-900'}`}>{t('editor.mode.visual')}</button></div><Button disabled={!canSaveEditor} onClick={handleSaveEditorChapter} aria-label={t('editor.save.chapter')} title={t('editor.save.chapter')}><Save size={18} className='inline align-middle' /> {editorSaveStatus === 'saving' ? t('editor.save.saving') : ''}</Button><Button variant="secondary" onClick={() => setEditorFullscreen(!editorFullscreen)}><Maximize2 size={14} className="inline" /> {editorFullscreen ? 'Salir fullscreen' : 'Pantalla completa'}</Button></div></div>{editorModeWarning ? <div className="mt-3 rounded-2xl border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">{editorModeWarning}</div> : null}{editorDraft.parseStatus === 'malformed_frontmatter' ? <div className="mt-3 rounded-2xl border border-neutral-300 bg-txf-surface-muted px-3 py-2 text-xs text-txf-text">Frontmatter malformado. Modo Markdown activo para preservar contenido.</div> : null}<div className="mt-3 min-h-[2.25rem]">{editorSaveBannerVisible && editorSaveMessage ? <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }} className={`rounded-2xl border px-3 py-2 text-xs ${editorSaveBannerClass}`}>{editorSaveMessage}</motion.div> : null}</div><div className="mt-4 flex-1 min-h-0 rounded-2xl border border-txf-border bg-txf-surface-muted p-3 overflow-hidden">{editorMode === 'markdown' ? <div className="editor-surface h-full overflow-hidden rounded-2xl border border-txf-border bg-txf-surface p-2">{markdownToolbarShell}<div className="editor-surface-body mt-0 h-[calc(100%-40px)] min-h-0 overflow-hidden rounded-b-2xl"><CodeMirror ref={editorTextareaRef} value={editorDraft.rawMarkdown} height="100%" extensions={[markdown(), EditorView.lineWrapping, history(), keymap.of([{ key: 'Mod-z', run: undo }, { key: 'Mod-y', run: redo }, { key: 'Mod-Shift-z', run: redo }]), placeholder(t('editor.markdown_placeholder'))] } basicSetup={{ lineNumbers: true, highlightActiveLine: true, highlightActiveLineGutter: true, foldGutter: true }} onChange={(value) => updateMarkdownDraft(value)} className="h-full w-full overflow-hidden border-0 bg-txf-surface text-[15px] leading-7 text-txf-text shadow-none" /></div></div> : <div className="h-full overflow-auto rounded-2xl border border-txf-border bg-txf-surface p-2"><MDXEditor key={`${editorDraft.loadedChapterId}:${editorDraft.loadedContentHash}:${editorMode}`} markdown={editorVisualSeedMarkdown} onChange={updateVisualDraft} plugins={[toolbarPlugin({ toolbarClassName: editorToolbarClassName, toolbarContents: () => <><UndoRedo /><Separator /><BoldItalicUnderlineToggles /><Separator /><BlockTypeSelect /><Separator /><ListsToggle /><Separator /><CreateLink /></> }), headingsPlugin(), listsPlugin(), quotePlugin(), linkPlugin(), linkDialogPlugin(), thematicBreakPlugin(), markdownShortcutPlugin()]} /></div>}</div></div></div><aside className="self-stretch min-h-0 min-w-0 editor-right-panel"><div className="editor-right-panel-shell rounded-3xl border border-txf-border bg-txf-surface p-4 text-sm text-txf-text"><div className="mb-3"><h3 className="text-base font-semibold">{t('editor.context_panel')}</h3></div><div className="editor-right-panel-scroll space-y-3 pr-1"><div className="rounded-2xl border border-txf-border bg-txf-surface-muted p-3"><div className="flex items-center gap-2 text-sm font-semibold"><Database size={14} /> {t('editor.source_text')}</div><div className="mt-2 text-xl font-semibold text-txf-text">{String(editorSource?.source_used || 'chapter_manifest')}</div><div className="mt-2 text-sm text-txf-subtle">{t('editor.right_panel_loaded', { count: chapterNotes.length })}</div></div><div className="rounded-2xl border border-txf-border bg-txf-surface p-3"><div className="flex items-center gap-2 text-sm font-semibold"><PenLine size={14} /> {t('editor.rewrite_selection')}</div><div className="mt-2 text-sm text-txf-subtle">{t('common.placeholder')}</div></div><div className="rounded-2xl border border-txf-border bg-txf-surface p-3"><div className="flex items-center gap-2 text-sm font-semibold"><AlertTriangle size={14} /> {t('editor.canon_risks')}</div><div className="mt-2 text-sm font-semibold text-txf-action">{selectedEditorNeedsReanalysis ? t('editor.reanalysis.pending') : t('editor.reanalysis.clean')}</div><div className="mt-1 text-sm text-txf-subtle">{t('editor.reanalysis.notice')}</div><button type="button" onClick={handleRequestChapterReanalysis} className="mt-3 w-full rounded-xl border border-txf-border bg-txf-surface px-3 py-2 text-left text-sm text-txf-text hover:bg-txf-surface-soft"><span className="inline-flex items-center gap-2"><Sparkles size={14} /> {t('editor.reanalysis.action')}</span></button>{editorReanalysisMessage ? <div className={`mt-2 text-xs ${editorReanalysisStatus === 'error' ? 'text-txf-text' : 'text-txf-subtle'}`}>{editorReanalysisMessage}</div> : null}</div><div className="rounded-2xl border border-txf-border bg-txf-surface p-3"><div className="flex items-center justify-between"><div className="flex items-center gap-2 text-sm font-semibold"><Users size={14} /> {t('editor.active_entities')}</div><div className="rounded-full bg-txf-surface-soft px-2 py-0.5 text-xs text-txf-subtle">{(projectDetail?.canon?.primaries || []).slice(0,6).length}</div></div><div className="mt-2 flex flex-wrap gap-2">{(projectDetail?.canon?.primaries || []).slice(0,6).map((entity) => <span key={entity.preferred_slug || entity.canonical_name} className="rounded-lg bg-txf-surface-soft px-2 py-1 text-xs text-txf-text">{entity.canonical_name || entity.preferred_slug}</span>)}</div><button type="button" className="mt-3 w-full rounded-xl border border-txf-border bg-txf-surface px-3 py-2 text-left text-sm text-txf-text hover:bg-txf-surface-soft"><span className="inline-flex items-center gap-2"><Share2 size={14} /> {t('editor.open_relations_graph')}</span><span>↗</span></button></div></div></div></aside></div></div></section>;
  if (active === 'story') content = <StoryAliasView selectedProjectId={selectedProjectId} notesPreview={(projectDetail?.notes || []).slice(0, 16).map((note) => <div key={note.path} className="rounded-xl bg-txf-surface border border-txf-border px-3 py-2">{note.name || note.path}</div>)} legacyNotes={<LegacyEmbed title={t('story_alias.legacy_notes_title')} src={legacyUrl('notes', selectedProjectId)} />} onOpenCanon={() => setActive('codex')} />;
  if (active === 'ask') content = <AIStudioView />;

  return <AppShell active={active} setActive={setActive}><motion.div key={active} className="min-h-full bg-txf-canvas" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.18 }}>{content}</motion.div>{error ? <div className="mx-5 mb-5 rounded-2xl border border-txf-border bg-txf-surface-muted p-3 text-sm text-txf-text">{error}</div> : null}<EvidenciaModal item={evidenceModalItem} onClose={() => setEvidenciaModalDecisionId('')} />{graphInspectorFullscreen ? <div className="fixed inset-0 z-50 bg-[#3a2a21]/35 p-4"><div className="h-full w-full rounded-3xl border border-txf-border bg-txf-surface shadow-txf-floating overflow-y-auto"><div className="sticky top-0 z-10 flex items-center justify-between border-b border-txf-border bg-txf-surface p-4"><h2 className="text-lg font-semibold">{t('graph.node_sheet')}</h2><Button variant="secondary" onClick={() => setGraphInspectorFullscreen(false)}><X size={14} className="inline" /> {t('common.exit_fullscreen')}</Button></div><div className="p-4"><GraphInspectorPanel node={selectedGraphNode} entityCard={selectedGraphEntity} entityCardVm={selectedGraphEntityCardVm} noteContent={selectedGraphNoteContent} noteDetail={selectedGraphNoteDetail} onEdit={(node: GraphCanvasNode) => setGraphEditNodeId(node.id)} onInternalEntityLinkClick={handleGraphInternalEntityLinkClick} onSaveFiche={handleSaveGraphEntityFiche} /></div></div></div> : null}{editDraft ? <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#3a2a21]/35 p-4"><div className="w-full max-w-2xl rounded-3xl border border-txf-border bg-txf-surface shadow-txf-floating"><div className="flex items-center justify-between border-b border-txf-border bg-txf-surface-muted p-5"><div><h2 className="font-semibold">{editDraft.title}</h2><p className="text-sm text-txf-subtle">{editDraft.notePath || t('common.local_draft')}</p></div><button onClick={() => setEditDraft(null)} className="rounded-full p-2 hover:bg-txf-surface-soft"><X size={18} /></button></div><div className="bg-txf-surface p-5"><textarea readOnly value={editDraft.body} className="h-48 w-full rounded-2xl border border-txf-border bg-txf-surface-muted p-4 text-sm text-txf-text" /><p className="mt-3 text-sm text-txf-subtle">{t('common.drafts_note')}</p></div></div></div> : null}</AppShell>;
}

export default App;
