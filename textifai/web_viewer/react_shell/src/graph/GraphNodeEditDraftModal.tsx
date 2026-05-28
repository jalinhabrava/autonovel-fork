import React from 'react';
import { X } from 'lucide-react';
import { GraphCanvasNode } from './types';

export type GraphNodeEditDraftModalProps = {
  node: GraphCanvasNode | null;
  onClose: () => void;
};

export function GraphNodeEditDraftModal({ node, onClose }: GraphNodeEditDraftModalProps) {
  if (!node) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="w-full max-w-2xl rounded-3xl border border-neutral-200 bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-neutral-200 p-5">
          <div>
            <h2 className="font-semibold">Editar {node.label}</h2>
            <p className="text-sm text-neutral-500">Draft local. Guardado real llega con SP-106.</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-full p-2 hover:bg-neutral-100">
            <X size={18} />
          </button>
        </div>
        <div className="p-5">
          <textarea
            readOnly
            value={`No write-back\n\nRuta: ${node.notePath || 'sin nota'}\nTipo: ${node.kind}\nEstado: ${node.reviewState || 'sin estado'}`}
            className="h-52 w-full rounded-2xl border border-neutral-200 bg-neutral-50 p-4 text-sm"
          />
          <p className="mt-3 text-sm text-neutral-500">
            Guardar cambios llega con drafts/patch queue en SP-106. No write-back en esta fase.
          </p>
        </div>
      </div>
    </div>
  );
}

