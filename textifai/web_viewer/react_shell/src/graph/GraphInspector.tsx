import React from 'react';
import { GraphCanvasNode } from './types';

export type GraphInspectorProps = {
  node: GraphCanvasNode | null;
  onEdit: (node: GraphCanvasNode) => void;
};

export function GraphInspector({ node, onEdit }: GraphInspectorProps) {
  if (!node) {
    return (
      <aside className="rounded-3xl border border-neutral-200 bg-white p-5 text-sm text-neutral-500">
        Ficha del nodo: selecciona un nodo.
      </aside>
    );
  }

  return (
    <aside className="rounded-3xl border border-neutral-200 bg-white p-5 shadow-sm">
      <div className="text-xs uppercase tracking-wide text-neutral-500">Ficha del nodo</div>
      <h2 className="mt-2 text-xl font-semibold">{node.label}</h2>
      <div className="mt-2 flex flex-wrap gap-2 text-sm text-neutral-600">
        <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs">{node.kind}</span>
        <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs">{node.reviewState || 'sin estado'}</span>
      </div>
      <p className="mt-4 text-sm leading-6 text-neutral-600">
        {node.summaryExcerpt || 'Sin resumen disponible.'}
      </p>
      <div className="mt-4 grid gap-2 text-sm">
        <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-3">
          Relaciones: {node.relationshipCount ?? node.degree ?? 0}
        </div>
        <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-3">
          Ruta: {node.notePath || 'sin nota'}
        </div>
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

