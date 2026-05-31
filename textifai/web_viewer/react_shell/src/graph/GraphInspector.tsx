import React, { useEffect, useMemo, useState } from 'react';
import { ArrowUpRight, BookOpenText, FileText, Link2, Network, Pencil, ShieldCheck, Star, Users } from 'lucide-react';
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

function wiki(label: string): string {
  const cleaned = String(label || '').trim();
  return cleaned ? `[[${cleaned}]]` : '';
}

function buildFicheMarkdown(params: {
  label: string;
  summary: string;
  sourceBody: string;
  aliases: string[];
  relationships: Array<{ target?: string; type?: string; relation_type?: string }>;
  backlinks: string[];
  outgoing: Array<{ target?: string; label?: string }>;
  notePath: string;
  evidenceCount: number;
}): string {
  const cleanBody = String(params.sourceBody || '').trim();
  if (cleanBody) return cleanBody;

  const sections = [
    `# ${params.label || t('graph.fiche_entity_fallback')}`,
    '',
    params.summary || '',
    '',
    `## ${t('graph.fiche_notes')}`,
    '- ',
  ];

  return sections.join('\n').trim();
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
  const relationships = (entityCard?.relationships || []) as Array<{ target?: string; type?: string; relation_type?: string }>;
  const localNodeCount = vm?.local_graph?.node_count ?? noteDetail?.local_graph?.nodes?.length ?? 0;
  const localEdgeCount = vm?.local_graph?.edge_count ?? noteDetail?.local_graph?.edges?.length ?? 0;
  const sourceMarkdown = vm?.markdown?.author_markdown || noteContent || noteDetail?.markdown || '';
  const { body: bodyMarkdown } = stripFrontmatter(sourceMarkdown);
  const normalizedBody = useMemo(() => buildFicheMarkdown({ label, summary, sourceBody: bodyMarkdown, aliases, relationships, backlinks, outgoing, notePath, evidenceCount }), [aliases, backlinks, bodyMarkdown, evidenceCount, label, notePath, outgoing, relationships, summary]);
  const editorBody = localBody || normalizedBody;
  const editorKey = `${node?.id || 'none'}:${label}`;

  useEffect(() => {
    setLocalBody(normalizedBody);
  }, [editorKey, normalizedBody]);
  const rawPreview = compactPreview(sourceMarkdown);

  if (!node) {
    return <aside className="rounded-3xl border border-neutral-200 bg-white p-5 text-sm text-neutral-500">{t('graph.ficha_hint')}</aside>;
  }

  return (
    <aside className="min-w-0 rounded-3xl border border-neutral-200 bg-white p-4 shadow-sm sm:p-5 xl:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm text-neutral-600">{t('graph.node_sheet')}</div>
          <h2 className="mt-3 break-words text-3xl font-semibold tracking-tight text-neutral-900 sm:text-4xl">{label}</h2>
        </div>
        <button type="button" onClick={() => onEdit(node)} className="w-full rounded-xl border border-orange-300 bg-white px-4 py-2 text-sm font-medium text-orange-700 hover:bg-orange-50 sm:w-auto">
          <span className="inline-flex items-center gap-2"><ArrowUpRight size={14} />{t('graph.open_ficha')}</span>
        </button>
      </div>

      <div className="mt-4 flex flex-wrap gap-2 text-xs text-neutral-700">
        <span className="rounded-full border border-neutral-200 bg-white px-3 py-1">{kind || t('common.label')}</span>
        <span className="rounded-full bg-emerald-100 px-3 py-1 text-emerald-800">{status}</span>
        {reviewCount ? <span className="rounded-full bg-amber-100 px-3 py-1 text-amber-800">{reviewCount} {t('graph.review_label')}</span> : null}
        <span className="rounded-full bg-neutral-100 px-3 py-1">{relationCount} {t('graph.relations')}</span>
        <span className="rounded-full bg-neutral-100 px-3 py-1">{evidenceCount} {t('editor.evidence')}</span>
      </div>

      <section className="mt-5 rounded-2xl border border-neutral-200 bg-white p-5">
        <div className="mb-3 flex items-center gap-2 text-2xl font-semibold text-neutral-900"><FileText size={20} />{t('graph.summary_title')}</div>
        <p className="text-base leading-7 text-neutral-700">{summary || t('graph.summary_missing')}</p>
      </section>

      <section className="mt-4 grid grid-cols-1 gap-3 text-sm 2xl:grid-cols-2">
        <div className="rounded-2xl border border-neutral-200 bg-white p-4"><div className="mb-2 flex items-center gap-2 text-xl font-semibold text-neutral-900"><Users size={18} />{t('graph.aliases')}</div><div className="mt-2 flex flex-wrap gap-2">{aliases.length ? aliases.slice(0, 8).map((alias) => <span key={alias} className="rounded-lg bg-neutral-100 px-3 py-1 text-sm text-neutral-700">{alias}</span>) : <span className="text-neutral-500">{t('common.no_data')}</span>}</div></div>
        <div className="rounded-2xl border border-neutral-200 bg-white p-4"><div className="mb-2 flex items-center gap-2 text-xl font-semibold text-neutral-900"><BookOpenText size={18} />{t('graph.reference_points')}</div><div className="mt-2 text-sm text-neutral-700"><ul className="list-disc space-y-1 pl-5"><li className="break-all">{notePath || t('graph.no_note')}</li></ul></div></div>
        <div className="rounded-2xl border border-neutral-200 bg-white p-4"><div className="mb-2 flex items-center gap-2 text-xl font-semibold text-neutral-900"><ShieldCheck size={18} />{t('editor.evidence')}</div><div className="text-4xl font-semibold text-neutral-900">{evidenceCount}</div><div className="mt-1 text-sm text-neutral-600">{evidenceCount ? t('graph.evidence_available') : t('graph.evidence_empty')}</div></div>
        <div className="rounded-2xl border border-neutral-200 bg-white p-4"><div className="mb-2 flex items-center gap-2 text-xl font-semibold text-neutral-900"><Users size={18} />{t('graph.relationships_title')}</div><div className="mt-2 flex flex-wrap gap-2">{relationCount ? [t('graph.relations')].map((chip) => <span key={chip} className="break-words rounded-lg bg-neutral-100 px-3 py-1 text-sm text-neutral-700">{chip}: {relationCount}</span>) : <span className="text-neutral-500">{t('common.no_data')}</span>}</div></div>
        <div className="rounded-2xl border border-neutral-200 bg-white p-4"><div className="mb-2 flex items-center gap-2 text-xl font-semibold text-neutral-900"><Link2 size={18} />{t('graph.backlinks')}</div><div className="text-4xl font-semibold text-neutral-900">{backlinks.length}</div><div className="mt-1 break-words text-sm text-neutral-600">{backlinks.length ? backlinks.slice(0, 2).join(' · ') : t('graph.backlinks_empty')}</div></div>
        <div className="rounded-2xl border border-neutral-200 bg-white p-4"><div className="mb-2 flex items-center gap-2 text-xl font-semibold text-neutral-900"><ArrowUpRight size={18} />{t('graph.outgoing_links')}</div><div className="text-4xl font-semibold text-neutral-900">{outgoing.length}</div><div className="mt-1 text-sm text-neutral-600">{outgoing.length ? t('graph.outgoing_available') : t('graph.outgoing_empty')}</div></div>
      </section>

      <section className="mt-4 rounded-2xl border border-neutral-200 bg-white p-4">
        <div className="flex items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2 text-xl font-semibold text-neutral-900"><Network size={18} />{t('graph.local_graph')}</div>
            <p className="mt-1 text-sm text-neutral-600">{t('graph.local_graph_note')}</p>
          </div>
          <button type="button" className="rounded-xl border border-orange-300 bg-white px-4 py-2 text-sm font-medium text-orange-700 hover:bg-orange-50">{t('graph.view_local_graph')}</button>
        </div>
        <div className="mt-2 text-sm text-neutral-500">{localNodeCount} {t('graph.local_graph_nodes')} · {localEdgeCount} {t('graph.local_graph_edges')}</div>
      </section>

      <EntityFicheView editorKey={editorKey} bodyMarkdown={editorBody} onChangeBody={setLocalBody} localDirty={editorBody !== normalizedBody} />

      <details className="mt-4 rounded-2xl border border-neutral-200 bg-neutral-50 p-4" open={technicalOpen} onToggle={(event) => setTechnicalOpen((event.currentTarget as HTMLDetailsElement).open)}>
        <summary className="cursor-pointer list-none text-sm font-semibold text-neutral-800">{t('graph.technical_details')}</summary>
        <div className="mt-3 space-y-3 text-xs text-neutral-600">
          <div><div className="uppercase tracking-wide text-neutral-400">{t('graph.note_path')}</div><div className="mt-1 break-all">{notePath || t('graph.no_note')}</div></div>
          <div><div className="uppercase tracking-wide text-neutral-400">{t('graph.markdown_view')}</div><pre className="mt-1 max-h-52 overflow-y-auto whitespace-pre-wrap rounded-xl border border-neutral-200 bg-white p-3">{rawPreview || t('graph.fiche_empty_placeholder')}</pre></div>
          {vm?.markdown?.technical_markdown ? <div><div className="uppercase tracking-wide text-neutral-400">technical_markdown</div><pre className="mt-1 max-h-52 overflow-y-auto whitespace-pre-wrap rounded-xl border border-neutral-200 bg-white p-3">{vm.markdown.technical_markdown}</pre></div> : null}
        </div>
      </details>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs text-neutral-500">
        <span>{t('graph.fiche_local_dirty')}</span>
        <button type="button" onClick={() => onOpenReview?.(label)} className="inline-flex items-center gap-2 rounded-full border border-neutral-200 bg-neutral-50 px-3 py-2 text-neutral-700 hover:bg-neutral-100"><Star size={14} />{t('graph.view_review')}</button>
      </div>
    </aside>
  );
}
