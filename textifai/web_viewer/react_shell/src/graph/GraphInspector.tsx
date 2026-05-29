import React from 'react';
import { GraphCanvasNode } from './types';
import { CanonEntity, NoteDetail, EntityCard } from '../api';

export type GraphInspectorProps = {
  node: GraphCanvasNode | null;
  entityCard: CanonEntity | null;
  entityCardVm: EntityCard | null;
  noteContent: string;
  noteDetail: NoteDetail | null;
  onEdit: (node: GraphCanvasNode) => void;
  onOpenReview?: (entityLabel: string) => void;
};

function markdownPreview(markdown: string): string {
  if (!markdown) return '';
  const lines = markdown.split('\n').filter(l => l.trim() && l !== '---' && !l.startsWith('schema:') && !l.started_with && true);
  return lines.filter((l) => l.trim() && l !== '---' && !l.startsWith('schema:') && !l.startsWith('created_at:') && !l.startsWith('updated_at:') && !l.startsWith('id:') && !l.startsWith('canonical_id:')).slice(0, 12).join('\n').slice(0, 1500);
}

export function GraphInspector({ node, entityCard, entityCardVm, noteContent, noteDetail, onEdit, onOpenReview }: GraphInspectorProps) {
  if (!node) {
    return (
      <aside className="rounded-3xl border border-neutral-200 bg-white p-5 text-sm text-neutral-500">
        Ficha del nodo: selecciona un nodo.
      </aside>
    );
  }

  // Prefer EntityCardVm (rich backend) over entityCard
  const vm = entityCardVm;
  const label = vm?.canonical_label || entityCard?.canonical_name || node.label || '';
  const kind = vm?.kind || entityCard?.entity_kind || node.kind || '';
  const status = vm?.status || entityCard?.review_state || node.reviewState || node.status || 'ready';
  const summary = vm?.summary || entityCard?.summary || node.summaryExcerpt || noteDetail?.summary_excerpt || '';
  const relationCount = vm?.relation_count ?? entityCard?.relationships?.length ?? node.relationshipCount ?? node.degree ?? 0;
  const evidenceCount = vm?.evidence_count ?? entityCard?.evidence_refs?.length ?? node.evidenceCount ?? noteDetail?.evidence_count ?? 0;
  const degree = vm?.degree ?? node.degree ?? relationCount;
  const aliases = vm?.aliases || { canonical: [], contextual: [], needs_review: [], suppressed: [] };
  const relationships = vm?.relationships || entityCard?.relationships || [];
  const backlinks = vm?.backlinks || noteDetail?.backlinks || node.backlinks || [];
  const outgoing = vm?.outgoing_links || noteDetail?.outgoing_wikilinks || node.outgoingWikilinks || [];
  const reviewCount = vm?.review?.count ?? node.reviewCount ?? 0;
  const notePath = vm?.markdown?.note_path || node.notePath || node.note_path || node.canonical_note_path || '';
  const authorMarkdown = vm?.markdown?.author_markdown || '';
  const technicalMarkdown = vm?.markdown?.technical_markdown || '';
  const localNodeCount = vm?.local_graph?.node_count ?? noteDetail?.local_graph?.nodes?.length ?? 0;
  const localEdgeCount = vm?.local_graph?.edge_count ?? noteDetail?.local_graph?.edges?.length ?? 0;
  const preview = markdownPreview(authorMarkdown || noteContent || noteDetail?.markdown || '');

  return (
    <aside className="rounded-3xl border border-neutral-200 bg-white p-5 shadow-sm max-h-[780px] overflow-y-auto">
      <div className="text-xs uppercase tracking-wide text-neutral-500">Ficha del nodo</div>
      <h2 className="mt-2 text-xl font-semibold">{label}</h2>
      <div className="mt-2 flex flex-wrap gap-2 text-sm text-neutral-600">
        <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs">{kind}</span>
        <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs">{status}</span>
        <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs">{degree} relaciones</span>
        <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs">{evidenceCount} evidencias</span>
        {reviewCount ? <span className="rounded-full bg-amber-100 px-3 py-1 text-xs">{reviewCount} review</span> : null}
      </div>

      {summary ? (
        <section className="mt-4 rounded-2xl border border-neutral-200 bg-neutral-50 p-4 text-sm leading-6 text-neutral-700">
          {summary}
        </section>
      ) : (
        <section className="mt-4 rounded-2xl border border-neutral-200 bg-neutral-50 p-4 text-sm text-neutral-500">
          Resumen no disponible todavía. Datos desde grafo, VaERL y Markdown disponibles abajo.
        </section>
      )}

      {(aliases.canonical?.length || aliases.contextual?.length || aliases.needs_review?.length) ? (
        <section className="mt-4 space-y-2">
          {aliases.canonical?.length ? (
            <div>
              <div className="mb-1 text-xs uppercase tracking-wide text-neutral-400">Aliases</div>
              <div className="flex flex-wrap gap-1">{aliases.canonical.slice(0, 8).map((a) => <span key={a} className="rounded-full border border-neutral-200 bg-white px-2 py-0.5 text-xs">{a}</span>)}</div>
            </div>
          ) : null}
          {aliases.contextual?.length ? (
            <div>
              <div className="mb-1 text-xs uppercase tracking-wide text-neutral-400">Referencias POV/contextuales</div>
              <div className="flex flex-wrap gap-1">{aliases.contextual.slice(0, 8).map((a) => <span key={a} className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs">{a}</span>)}</div>
            </div>
          ) : null}
          {aliases.needs_review?.length ? (
            <div>
              <div className="mb-1 text-xs uppercase tracking-wide text-neutral-400">Aliases por revisar</div>
              <div className="flex flex-wrap gap-1">{aliases.needs_review.slice(0, 8).map((a) => <span key={a} className="rounded-full border border-orange-200 bg-orange-50 px-2 py-0.5 text-xs">{a}</span>)}</div>
            </div>
          ) : null}
        </section>
      ) : null}

      {relationships.length ? (
        <section className="mt-4">
          <div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Relaciones principales</div>
          <div className="space-y-1">
            {relationships.slice(0, 12).map((r, i) => (
              <div key={i} className="rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm">
                {r.source || '?'} → {r.predicate || 'relacionado'} → {r.target || '?'}
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="mt-4 grid grid-cols-2 gap-2 text-sm">
        <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-3"><b>{backlinks.length}</b> Backlinks</div>
        <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-3"><b>{outgoing.length}</b> Salientes</div>
        <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-3"><b>{localNodeCount}</b> Grafo local nodos</div>
        <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-3"><b>{evidenceCount}</b> Evidencia</div>
      </section>

      {backlinks.length ? <section className="mt-4"><div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Backlinks</div><div className="space-y-1">{backlinks.slice(0, 10).map((b) => <div key={b} className="rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs">{b}</div>)}</div></section> : null}
      {outgoing.length ? <section className="mt-4"><div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Enlaces salientes</div><div className="space-y-1">{outgoing.slice(0, 10).map((o) => <div key={o.label || Math.random()} className="rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs">{o.label || ''}</div>)}</div></section> : null}

      {preview ? <details className="mt-4" open><summary className="cursor-pointer rounded-2xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs font-semibold">Vista Markdown</summary><pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap rounded-2xl bg-neutral-50 p-3 text-xs text-neutral-600">{preview}</pre></details> : null}

      {technicalMarkdown && !preview ? <details className="mt-4"><summary className="cursor-pointer rounded-2xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs font-semibold">Detalles técnicos</summary><pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-2xl bg-neutral-50 p-3 text-xs text-neutral-600">{technicalMarkdown}</pre></details> : null}

      <div className="mt-4 rounded-2xl border border-neutral-200 bg-neutral-50 p-3 text-xs text-neutral-500">Nota: {notePath || 'sin nota'}</div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" onClick={() => onEdit(node)} className="rounded-2xl bg-neutral-900 px-4 py-2 text-sm text-white">Editar</button>
        <button type="button" className="rounded-2xl border border-neutral-200 bg-white px-4 py-2 text-sm">Abrir ficha</button>
        {onOpenReview ? <button type="button" onClick={() => onOpenReview(label)} className="rounded-2xl border border-neutral-200 bg-white px-4 py-2 text-sm">Ver en Review</button> : null}
      </div>
    </aside>
  );
}
