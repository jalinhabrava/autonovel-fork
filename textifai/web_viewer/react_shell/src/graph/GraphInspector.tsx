import React, { useMemo, useState } from 'react';
import { Pencil, Eye, X } from 'lucide-react';
import { GraphCanvasNode } from './types';
import { CanonEntity, NoteDetail, EntityCard } from '../api';
import { t } from '../i18n/ui';
import { EntityFicheView, stripFrontmatter } from '../modules/canon/EntityFicheView';

export type GraphInspectorProps = {
  node: GraphCanvasNode | null;
  entityCard: CanonEntity | null;
  entityCardVm: EntityCard | null;
  noteContent: string;
  noteDetail: NoteDetail | null;
  onEdit: (node: GraphCanvasNode) => void;
  onOpenReview?: (entityLabel: string) => void;
};

function toList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0) : [];
}

function compactPreview(markdown: string): string {
  return String(markdown || '')
    .split('\n')
    .filter((line) => line.trim() && line !== '---' && !line.startsWith('schema:') && !line.startsWith('created_at:') && !line.startsWith('updated_at:') && !line.startsWith('id:') && !line.startsWith('canonical_id:'))
    .slice(0, 12)
    .join('\n')
    .slice(0, 1600);
}

export function GraphInspector({ node, entityCard, entityCardVm, noteContent, noteDetail, onEdit, onOpenReview }: GraphInspectorProps) {
  const [technicalOpen, setTechnicalOpen] = useState(false);
  const [localBody, setLocalBody] = useState('');

  const vm = entityCardVm;
  const label = vm?.canonical_label || entityCard?.canonical_name || node?.label || '';
  const kind = vm?.kind || entityCard?.entity_kind || node?.kind || '';
  const status = vm?.status || entityCard?.review_state || node?.reviewState || node?.status || 'ready';
  const summary = vm?.summary || entityCard?.summary || node?.summaryExcerpt || noteDetail?.summary_excerpt || '';
  const relationCount = vm?.relation_count ?? entityCard?.relationships?.length ?? node?.relationshipCount ?? node?.degree ?? 0;
  const evidenceCount = vm?.evidence_count ?? entityCard?.evidence_refs?.length ?? node?.evidenceCount ?? noteDetail?.evidence_count ?? 0;
  const reviewCount = vm?.review?.count ?? node?.reviewCount ?? 0;
  const notePath = vm?.markdown?.note_path || node?.notePath || node?.note_path || node?.canonical_note_path || '';
  const aliases = useMemo(() => Array.from(new Set([...(vm?.aliases?.canonical || []), ...(vm?.aliases?.contextual || []), ...(entityCard?.aliases || []), ...toList(node?.aliases)])).filter(Boolean), [entityCard?.aliases, node?.aliases, vm?.aliases?.canonical, vm?.aliases?.contextual]);
  const backlinks = vm?.backlinks || noteDetail?.backlinks || node?.backlinks || [];
  const outgoing = vm?.outgoing_links || noteDetail?.outgoing_wikilinks || node?.outgoingWikilinks || [];
  const localNodeCount = vm?.local_graph?.node_count ?? noteDetail?.local_graph?.nodes?.length ?? 0;
  const localEdgeCount = vm?.local_graph?.edge_count ?? noteDetail?.local_graph?.edges?.length ?? 0;
  const sourceMarkdown = vm?.markdown?.author_markdown || noteContent || noteDetail?.markdown || '';
  const { body: bodyMarkdown } = stripFrontmatter(sourceMarkdown);
  const editorBody = localBody || bodyMarkdown;
  const rawPreview = compactPreview(sourceMarkdown);

  if (!node) {
    return <aside className="rounded-3xl border border-neutral-200 bg-white p-5 text-sm text-neutral-500">{t('graph.ficha_hint')}</aside>;
  }

  return (
    <aside className="rounded-3xl border border-neutral-200 bg-white p-5 shadow-sm max-h-[780px] overflow-y-auto">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-wide text-neutral-500">{t('graph.node_sheet')}</div>
          <h2 className="mt-2 text-xl font-semibold text-neutral-900">{label}</h2>
        </div>
        <button type="button" onClick={() => onEdit(node)} className="rounded-full border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-700 hover:bg-neutral-100">
          <span className="inline-flex items-center gap-2"><Pencil size={14} />{t('graph.open_ficha')}</span>
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-xs text-neutral-700">
        <span className="rounded-full bg-neutral-100 px-3 py-1">{kind || t('common.label')}</span>
        <span className="rounded-full bg-neutral-100 px-3 py-1">{status}</span>
        <span className="rounded-full bg-neutral-100 px-3 py-1">{relationCount} {t('graph.relations')}</span>
        <span className="rounded-full bg-neutral-100 px-3 py-1">{evidenceCount} {t('editor.evidence')}</span>
        {reviewCount ? <span className="rounded-full bg-amber-100 px-3 py-1">{reviewCount} {t('graph.review_label')}</span> : null}
      </div>

      {summary ? <section className="mt-4 rounded-2xl border border-neutral-200 bg-neutral-50 p-4 text-sm leading-6 text-neutral-700">{summary}</section> : <section className="mt-4 rounded-2xl border border-neutral-200 bg-neutral-50 p-4 text-sm text-neutral-500">{t('graph.summary_missing')}</section>}

      <section className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-2xl border border-neutral-200 bg-white p-3"><div className="text-xs uppercase tracking-wide text-neutral-400">{t('graph.aliases')}</div><div className="mt-2 flex flex-wrap gap-2">{aliases.length ? aliases.slice(0, 8).map((alias) => <span key={alias} className="rounded-full bg-neutral-100 px-2 py-1 text-xs text-neutral-700">{alias}</span>) : <span className="text-neutral-500">—</span>}</div></div>
        <div className="rounded-2xl border border-neutral-200 bg-white p-3"><div className="text-xs uppercase tracking-wide text-neutral-400">{t('graph.reference_points')}</div><div className="mt-2 text-xs text-neutral-600">{notePath || t('graph.no_note')}</div></div>
        <div className="rounded-2xl border border-neutral-200 bg-white p-3"><div className="text-xs uppercase tracking-wide text-neutral-400">{t('graph.backlinks')}</div><div className="mt-2 text-xs text-neutral-600">{backlinks.length ? backlinks.slice(0, 3).map((item: string) => <div key={item} className="truncate">{item}</div>) : <span>—</span>}</div></div>
        <div className="rounded-2xl border border-neutral-200 bg-white p-3"><div className="text-xs uppercase tracking-wide text-neutral-400">{t('graph.outgoing_links')}</div><div className="mt-2 text-xs text-neutral-600">{outgoing.length ? outgoing.slice(0, 3).map((item: { target?: string; label?: string }, index: number) => <div key={`${item.target || item.label || index}`} className="truncate">{item.label || item.target || '—'}</div>) : <span>—</span>}</div></div>
        <div className="rounded-2xl border border-neutral-200 bg-white p-3"><div className="text-xs uppercase tracking-wide text-neutral-400">{t('graph.local_graph_nodes')}</div><div className="mt-2 text-xs text-neutral-600">{localNodeCount} / {localEdgeCount}</div></div>
      </section>

      <EntityFicheView bodyMarkdown={editorBody} onChangeBody={setLocalBody} localDirty={localBody !== bodyMarkdown} />

      <details className="mt-4 rounded-2xl border border-neutral-200 bg-neutral-50 p-4" open={technicalOpen} onToggle={(event) => setTechnicalOpen((event.currentTarget as HTMLDetailsElement).open)}>
        <summary className="cursor-pointer list-none text-sm font-semibold text-neutral-800">{t('graph.technical_details')}</summary>
        <div className="mt-3 space-y-3 text-xs text-neutral-600">
          <div><div className="uppercase tracking-wide text-neutral-400">{t('graph.note_path')}</div><div className="mt-1 break-all">{notePath || t('graph.no_note')}</div></div>
          <div><div className="uppercase tracking-wide text-neutral-400">{t('graph.markdown_view')}</div><pre className="mt-1 whitespace-pre-wrap rounded-xl border border-neutral-200 bg-white p-3">{rawPreview || t('graph.ficha_empty_placeholder')}</pre></div>
          {vm?.markdown?.technical_markdown ? <div><div className="uppercase tracking-wide text-neutral-400">technical_markdown</div><pre className="mt-1 whitespace-pre-wrap rounded-xl border border-neutral-200 bg-white p-3">{vm.markdown.technical_markdown}</pre></div> : null}
        </div>
      </details>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs text-neutral-500">
        <span>{t('graph.fiche_local_dirty')}</span>
        <button type="button" onClick={() => onOpenReview?.(label)} className="inline-flex items-center gap-2 rounded-full border border-neutral-200 bg-neutral-50 px-3 py-2 text-neutral-700 hover:bg-neutral-100"><Eye size={14} />{t('graph.view_review')}</button>
      </div>
    </aside>
  );
}

