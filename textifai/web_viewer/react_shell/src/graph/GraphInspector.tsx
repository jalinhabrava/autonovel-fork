import React from 'react';
import { GraphCanvasNode } from './types';
import { CanonEntity, NoteDetail } from '../api';

export type GraphInspectorProps = {
  node: GraphCanvasNode | null;
  entityCard: CanonEntity | null;
  noteContent: string;
  noteDetail: NoteDetail | null;
  onEdit: (node: GraphCanvasNode) => void;
};

function markdownPreview(markdown: string): string {
  return markdown
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line && line !== '---' && !line.startsWith('schema:') && !line.startsWith('created_at:') && !line.startsWith('updated_at:'))
    .slice(0, 8)
    .join('\n')
    .slice(0, 1200);
}

export function GraphInspector({ node, entityCard, noteContent, noteDetail, onEdit }: GraphInspectorProps) {
  if (!node) {
    return (
      <aside className="rounded-3xl border border-neutral-200 bg-white p-5 text-sm text-neutral-500">
        Ficha del nodo: selecciona un nodo.
      </aside>
    );
  }

  const summary = entityCard?.summary || node.summaryExcerpt || noteDetail?.summary_excerpt || '';
  const aliases = Array.from(new Set([...(entityCard?.aliases || []), ...(node.aliases || [])].filter(Boolean)));
  const relationships = entityCard?.relationships || [];
  const facts = entityCard?.key_facts || noteDetail?.key_facts_preview || [];
  const backlinks = noteDetail?.backlinks || node.backlinks || [];
  const outgoing = noteDetail?.outgoing_wikilinks || node.outgoingWikilinks || [];
  const evidenceCount = entityCard?.evidence_refs?.length || node.evidenceCount || noteDetail?.evidence_count || 0;
  const relationCount = relationships.length || node.relationshipCount || noteDetail?.relationship_count || node.degree || 0;
  const preview = markdownPreview(noteContent || noteDetail?.markdown || '');

  return (
    <aside className="rounded-3xl border border-neutral-200 bg-white p-5 shadow-sm max-h-[720px] overflow-y-auto">
      <div className="text-xs uppercase tracking-wide text-neutral-500">Ficha canónica</div>
      <h2 className="mt-2 text-xl font-semibold">{entityCard?.canonical_name || node.label}</h2>
      <div className="mt-2 flex flex-wrap gap-2 text-sm text-neutral-600">
        <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs">{node.kind}</span>
        <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs">{node.reviewState || 'ready'}</span>
        <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs">{relationCount} relaciones</span>
        <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs">{evidenceCount} evidencias</span>
      </div>

      <section className="mt-4 rounded-2xl border border-neutral-200 bg-neutral-50 p-4 text-sm leading-6 text-neutral-700">
        {summary ? summary : 'Resumen no disponible todavía. Se muestran enlaces, relaciones y contenido Markdown disponibles para revisión.'}
      </section>

      {aliases.length > 0 ? (
        <section className="mt-4">
          <div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Aliases</div>
          <div className="flex flex-wrap gap-1">
            {aliases.slice(0, 12).map((alias) => <span key={alias} className="rounded-full border border-neutral-200 bg-white px-2 py-0.5 text-xs">{alias}</span>)}
          </div>
        </section>
      ) : null}

      {facts.length > 0 ? (
        <section className="mt-4">
          <div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Hechos / bio</div>
          <ul className="list-inside list-disc space-y-1 text-sm text-neutral-600">
            {facts.slice(0, 6).map((fact, i) => <li key={i}>{fact}</li>)}
          </ul>
        </section>
      ) : null}

      {relationships.length > 0 ? (
        <section className="mt-4">
          <div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Relaciones principales</div>
          <div className="space-y-1">
            {relationships.slice(0, 8).map((rel, i) => <div key={i} className="rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm">{rel.target || 'sin destino'} — {rel.type || rel.relation_type || 'relacionado'}</div>)}
          </div>
        </section>
      ) : null}

      <section className="mt-4 grid grid-cols-2 gap-2 text-sm">
        <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-3"><b>{backlinks.length}</b><br />Backlinks</div>
        <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-3"><b>{outgoing.length}</b><br />Enlaces salientes</div>
        <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-3"><b>{node.reviewCount || 0}</b><br />Decisiones review</div>
        <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-3"><b>{evidenceCount}</b><br />Evidencia</div>
      </section>

      {backlinks.length > 0 ? <section className="mt-4"><div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Backlinks</div><div className="space-y-1">{backlinks.slice(0, 8).map((b) => <div key={b} className="rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs">{b}</div>)}</div></section> : null}
      {outgoing.length > 0 ? <section className="mt-4"><div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Enlaces salientes</div><div className="space-y-1">{outgoing.slice(0, 8).map((l) => <div key={l.target || l.label} className="rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs">{l.label || l.target}</div>)}</div></section> : null}
      {noteDetail?.local_graph?.nodes?.length ? <section className="mt-4"><div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Grafo local</div><div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-3 text-sm">{noteDetail.local_graph.nodes.length} nodos · {noteDetail.local_graph.edges?.length || 0} relaciones</div></section> : null}

      {preview ? <details className="mt-4" open><summary className="cursor-pointer rounded-2xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs font-semibold">Vista Markdown</summary><pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap rounded-2xl bg-neutral-50 p-3 text-xs text-neutral-600">{preview}</pre></details> : null}

      <div className="mt-4 rounded-2xl border border-neutral-200 bg-neutral-50 p-3 text-xs text-neutral-500">Ruta: {node.notePath || 'sin nota'}</div>
      <div className="mt-4 flex flex-wrap gap-2"><button type="button" onClick={() => onEdit(node)} className="rounded-2xl bg-neutral-900 px-4 py-2 text-sm text-white">Editar</button><button type="button" className="rounded-2xl border border-neutral-200 bg-white px-4 py-2 text-sm">Abrir ficha</button><button type="button" className="rounded-2xl border border-neutral-200 bg-white px-4 py-2 text-sm">Ver en Review</button></div>
    </aside>
  );
}
