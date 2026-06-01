import React, { useEffect, useMemo, useState } from 'react';
import { ArrowUpRight, BookOpenText, Link2, Network, ShieldCheck, Star, Users } from 'lucide-react';
import { GraphCanvasNode } from './types';
import { CanonEntity, NoteDetail, EntityCard, EntityFicheSaveResponse } from '../api';
import { t } from '../i18n/ui';
import { EntityFicheView, stripFrontmatter } from '../modules/canon/EntityFicheView';

export type GraphInspectorProps = {
  node: GraphCanvasNode | null;
  entityCard: CanonEntity | null;
  entityCardVm: EntityCard | null;
  reviewCountOverride?: number;
  noteContent: string;
  noteDetail: NoteDetail | null;
  onEdit: (node: GraphCanvasNode) => void;
  onViewLocalGraph?: (node: GraphCanvasNode) => void;
  onOpenReview?: (entityLabel: string) => void;
  onSaveFiche?: (params: { entityId: string; markdown: string; expectedHash: string; canonicalLabel: string }) => Promise<EntityFicheSaveResponse>;
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

export function GraphInspector({ node, entityCard, entityCardVm, reviewCountOverride, noteContent, noteDetail, onEdit, onViewLocalGraph, onOpenReview, onSaveFiche }: GraphInspectorProps) {
  const [technicalOpen, setTechnicalOpen] = useState(false);
  const [localBody, setLocalBody] = useState('');
  const [loadedBody, setLoadedBody] = useState('');
  const [loadedHash, setLoadedHash] = useState('');
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'conflict' | 'error'>('idle');
  const [saveMessage, setSaveMessage] = useState('');

  const vm = entityCardVm;
  const label = vm?.canonical_label || entityCard?.canonical_name || node?.label || '';
  const kind = vm?.kind || entityCard?.entity_kind || node?.kind || '';
  const status = vm?.status || entityCard?.review_state || node?.reviewState || node?.status || 'ready';
  const summary = vm?.summary || entityCard?.summary || node?.summaryExcerpt || noteDetail?.summary_excerpt || '';
  const relationCount = vm?.relation_count ?? entityCard?.relationships?.length ?? node?.relationshipCount ?? node?.degree ?? 0;
  const evidenceCount = vm?.evidence_count ?? entityCard?.evidence_refs?.length ?? node?.evidenceCount ?? noteDetail?.evidence_count ?? 0;
  const reviewCount = reviewCountOverride ?? vm?.review?.count ?? node?.reviewCount ?? 0;
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
  const entityId = vm?.id || (entityCard as any)?.entity_id || (entityCard as any)?.preferred_slug || node?.id || '';
  const canSave = Boolean(onSaveFiche && entityId && loadedHash && editorBody !== loadedBody && saveState !== 'saving');

  useEffect(() => {
    setLocalBody(normalizedBody);
    setLoadedBody(normalizedBody);
    setLoadedHash(String((vm as any)?.markdown?.content_hash || (vm as any)?.content_hash || ''));
    setSaveState('idle');
    setSaveMessage('');
  }, [editorKey, normalizedBody, vm]);

  async function handleSaveFiche() {
    if (!onSaveFiche || !entityId || !loadedHash) {
      setSaveState('error');
      setSaveMessage(t('graph.fiche_save_unavailable'));
      return;
    }
    setSaveState('saving');
    setSaveMessage(t('graph.fiche_saving'));
    try {
      const result = await onSaveFiche({ entityId, markdown: editorBody, expectedHash: loadedHash, canonicalLabel: label });
      setLoadedHash(String(result.new_hash || loadedHash));
      setLoadedBody(editorBody);
      setSaveState('saved');
      setSaveMessage(t('graph.fiche_saved_pending_reanalysis'));
    } catch (error: any) {
      const payload = error?.payload || {};
      if (payload.error === 'hash_mismatch') {
        setSaveState('conflict');
        setSaveMessage(t('graph.fiche_conflict'));
        return;
      }
      setSaveState('error');
      setSaveMessage(t('graph.fiche_save_error'));
    }
  }
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
      </div>

      <section className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-xl border border-neutral-200 bg-white p-2"><div className="mb-1 flex items-center gap-1.5 text-sm font-semibold text-neutral-900"><Users size={14} />{t('graph.aliases')}</div><div className="flex flex-wrap gap-1">{aliases.length ? aliases.slice(0, 4).map((alias) => <span key={alias} className="rounded-md bg-neutral-100 px-2 py-0.5 text-[11px] text-neutral-700">{alias}</span>) : <span className="text-neutral-500">{t('common.no_data')}</span>}</div></div>
        <div className="rounded-xl border border-neutral-200 bg-white p-2"><div className="mb-1 flex items-center gap-1.5 text-sm font-semibold text-neutral-900"><BookOpenText size={14} />{t('graph.reference_points')}</div><div className="text-xs text-neutral-700"><ul className="list-disc pl-4"><li className="line-clamp-2 break-all">{notePath || t('graph.no_note')}</li></ul></div></div>
        <div className="rounded-xl border border-neutral-200 bg-white p-2"><div className="mb-1 flex items-center gap-1.5 text-sm font-semibold text-neutral-900"><ShieldCheck size={14} />{t('editor.evidence')}</div><div className="text-2xl font-semibold text-neutral-900">{evidenceCount}</div></div>
        <div className="rounded-xl border border-neutral-200 bg-white p-2"><div className="mb-1 flex items-center gap-1.5 text-sm font-semibold text-neutral-900"><Users size={14} />{t('graph.relationships_title')}</div><div className="text-xs text-neutral-700">{relationCount ? `${t('graph.relations')}: ${relationCount}` : t('common.no_data')}</div></div>
        <div className="rounded-xl border border-neutral-200 bg-white p-2"><div className="mb-1 flex items-center gap-1.5 text-sm font-semibold text-neutral-900"><Link2 size={14} />{t('graph.backlinks')}</div><div className="text-2xl font-semibold text-neutral-900">{backlinks.length}</div></div>
        <div className="rounded-xl border border-neutral-200 bg-white p-2"><div className="mb-1 flex items-center gap-1.5 text-sm font-semibold text-neutral-900"><ArrowUpRight size={14} />{t('graph.outgoing_links')}</div><div className="text-2xl font-semibold text-neutral-900">{outgoing.length}</div></div>
      </section>

      <section className="mt-2 rounded-xl border border-neutral-200 bg-white p-2.5">
        <div className="flex items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-1.5 text-sm font-semibold text-neutral-900"><Network size={14} />{t('graph.local_graph')}</div>
            <p className="mt-0.5 text-xs text-neutral-600 line-clamp-2">{t('graph.local_graph_note')}</p>
          </div>
          <button type="button" onClick={() => node && onViewLocalGraph?.(node)} className="rounded-lg border border-orange-300 bg-white px-2.5 py-1.5 text-xs font-medium text-orange-700 hover:bg-orange-50">{t('graph.view_local_graph')}</button>
        </div>
        <div className="mt-1 text-[11px] text-neutral-500">{localNodeCount} {t('graph.local_graph_nodes')} · {localEdgeCount} {t('graph.local_graph_edges')}</div>
      </section>

      <section className="mt-2 rounded-xl border border-neutral-200 bg-white p-2.5">
        <div className="flex items-center justify-between gap-2">
          <div>
            <div className={`flex items-center gap-1.5 text-sm font-semibold ${reviewCount ? 'text-neutral-900' : 'text-neutral-400'}`}><Star size={14} />{t('graph.view_review')}</div>
            <p className={`mt-0.5 text-xs line-clamp-2 ${reviewCount ? 'text-neutral-600' : 'text-neutral-400'}`}>{t('graph.review_filter_hint')}</p>
          </div>
          <button type="button" disabled={!reviewCount} onClick={() => onOpenReview?.(label)} className={`rounded-lg px-2.5 py-1.5 text-xs font-medium ${reviewCount ? 'border border-orange-300 bg-white text-orange-700 hover:bg-orange-50' : 'border border-neutral-200 bg-neutral-100 text-neutral-400 cursor-not-allowed'}`}>{t('graph.view_review')}</button>
        </div>
      </section>

      <EntityFicheView editorKey={editorKey} bodyMarkdown={editorBody} onChangeBody={(next) => { setLocalBody(next); if (saveState === 'saved') setSaveState('idle'); }} localDirty={editorBody !== loadedBody} saveState={saveState} saveMessage={saveMessage} canSave={canSave} onSave={handleSaveFiche} saveDisabledReason={!loadedHash ? t('graph.fiche_save_unavailable') : ''} />

      <details className="mt-4 rounded-2xl border border-neutral-200 bg-neutral-50 p-4" open={technicalOpen} onToggle={(event) => setTechnicalOpen((event.currentTarget as HTMLDetailsElement).open)}>
        <summary className="cursor-pointer list-none text-sm font-semibold text-neutral-800">{t('graph.technical_details')}</summary>
        <div className="mt-3 space-y-3 text-xs text-neutral-600">
          <div><div className="uppercase tracking-wide text-neutral-400">{t('graph.note_path')}</div><div className="mt-1 break-all">{notePath || t('graph.no_note')}</div></div>
          <div><div className="uppercase tracking-wide text-neutral-400">{t('graph.markdown_view')}</div><pre className="mt-1 max-h-52 overflow-y-auto whitespace-pre-wrap rounded-xl border border-neutral-200 bg-white p-3">{rawPreview || t('graph.fiche_empty_placeholder')}</pre></div>
          {vm?.markdown?.technical_markdown ? <div><div className="uppercase tracking-wide text-neutral-400">technical_markdown</div><pre className="mt-1 max-h-52 overflow-y-auto whitespace-pre-wrap rounded-xl border border-neutral-200 bg-white p-3">{vm.markdown.technical_markdown}</pre></div> : null}
        </div>
      </details>
    </aside>
  );
}
