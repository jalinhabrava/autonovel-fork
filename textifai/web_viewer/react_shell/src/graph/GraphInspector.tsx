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

export function GraphInspector({ node, entityCard, noteContent, noteDetail, onEdit }: GraphInspectorProps) {
  if (!node) {
    return (
      <aside className="rounded-3xl border border-neutral-200 bg-white p-5 text-sm text-neutral-500">
        Ficha del nodo: selecciona un nodo.
      </aside>
    );
  }

  const hasPrimaryData = entityCard && (entityCard.summary || (entityCard.key_facts || []).length || (entityCard.aliases || []).length || (entityCard.relationships || []).length);

  return (
    <aside className="rounded-3xl border border-neutral-200 bg-white p-5 shadow-sm max-h-[640px] overflow-y-auto">
      <div className="text-xs uppercase tracking-wide text-neutral-500">Ficha del nodo</div>
      <h2 className="mt-2 text-xl font-semibold">{entityCard?.canonical_name || node.label}</h2>
      <div className="mt-2 flex flex-wrap gap-2 text-sm text-neutral-600">
        <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs">{node.kind}</span>
        <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs">{node.reviewState || 'sin estado'}</span>
      </div>

      {/* Primary data when available */}
      {hasPrimaryData ? (
        <div className="mt-4 space-y-4 text-sm">
          {entityCard.summary ? (
            <p className="leading-6 text-neutral-700">{entityCard.summary}</p>
          ) : null}
          {(entityCard.aliases || []).length > 0 ? (
            <div>
              <div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Alias</div>
              <div className="flex flex-wrap gap-1">
                {(entityCard.aliases || []).slice(0, 8).map((alias) => (
                  <span key={alias} className="rounded-full border border-neutral-200 bg-white px-2 py-0.5 text-xs">
                    {alias}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
          {(entityCard.key_facts || []).length > 0 ? (
            <div>
              <div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Hechos clave</div>
              <ul className="list-inside list-disc space-y-1 text-sm text-neutral-600">
                {(entityCard.key_facts || []).slice(0, 5).map((fact, i) => (
                  <li key={i}>{fact}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {(entityCard.relationships || []).length > 0 ? (
            <div>
              <div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Relaciones</div>
              <div className="space-y-1">
                {(entityCard.relationships || []).slice(0, 6).map((rel, i) => (
                  <div key={i} className="rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm">
                    {rel.target || 'desconocido'} — {rel.type || rel.relation_type || 'relacionado'}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : (
        <p className="mt-4 text-sm leading-6 text-neutral-600">
          {entityCard?.summary || node.summaryExcerpt || 'Sin datos de entidad disponibles. La primary puede haberse generado solo con provider calls que no se han ejecutado en este runtime.'}
        </p>
      )}

      {/* Note content */}
      {noteDetail ? (
        <div className="mt-4 space-y-3 text-sm">
          {(noteDetail.backlinks || []).length > 0 ? (
            <div>
              <div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Backlinks</div>
              <div className="space-y-1">
                {(noteDetail.backlinks || []).slice(0, 8).map((backlink) => (
                  <div key={backlink} className="rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm">
                    {backlink}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          {(noteDetail.outgoing_wikilinks || []).length > 0 ? (
            <div>
              <div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Enlaces salientes</div>
              <div className="space-y-1">
                {(noteDetail.outgoing_wikilinks || []).slice(0, 8).map((link) => (
                  <div key={link.target || link.label} className="rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm">
                    {link.label || link.target}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          {noteDetail.local_graph?.nodes?.length ? (
            <div>
              <div className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Grafo local</div>
              <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-3 text-sm">
                {noteDetail.local_graph.nodes.length} nodos · {noteDetail.local_graph.edges?.length || 0} relaciones
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {noteContent ? (
        <details className="mt-4">
          <summary className="cursor-pointer rounded-2xl border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs font-semibold">
            Ver contenido de la nota
          </summary>
          <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-2xl bg-neutral-50 p-3 text-xs text-neutral-600">
            {noteContent.slice(0, 2000)}
          </pre>
        </details>
      ) : null}

      {/* Relationships from graph node */}
      <div className="mt-4 grid gap-2 text-sm">
        <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-3">
          Relaciones: {entityCard?.relationships?.length || node.relationshipCount || node.degree || 0}
        </div>
        <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-3">
          Ruta: {node.notePath || 'sin nota'}
        </div>
        {entityCard?.confidence !== undefined ? (
          <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-3">
            Confianza: {entityCard.confidence}
          </div>
        ) : null}
      </div>

      <button
        type="button"
        onClick={() => onEdit(node)}
        className="mt-5 rounded-2xl bg-neutral-900 px-4 py-2 text-sm text-white"
      >
        Editar
      </button>
    </aside>
  );
}
