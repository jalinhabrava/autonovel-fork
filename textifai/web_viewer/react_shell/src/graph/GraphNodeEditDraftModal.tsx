import React from 'react';
import { X } from 'lucide-react';
import { t } from '../i18n/ui';
import { GraphCanvasNode } from './types';

export type GraphNodeEditDraftModalProps = {
  node: GraphCanvasNode | null;
  onClose: () => void;
};

export function GraphNodeEditDraftModal({ node, onClose }: GraphNodeEditDraftModalProps) {
  if (!node) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="w-full max-w-2xl rounded-3xl border border-txf-border bg-txf-surface shadow-txf-floating">
        <div className="flex items-center justify-between border-b border-txf-border p-5">
          <div>
            <h2 className="font-semibold">{`${t('graph.edit_draft')} ${node.label}`}</h2>
            <p className="text-sm text-txf-subtle">{t('common.local_draft')}</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-full p-2 hover:bg-txf-surface-soft">
            <X size={18} />
          </button>
        </div>
        <div className="p-5">
          <textarea
            readOnly
            value={`${t('graph.edit_draft.readonly')}\n\n${t('graph.note_path')}: ${node.notePath || t('common.no_data')}\n${t('graph.node_kind')}: ${node.kind}\n${t('graph.node_state')}: ${node.reviewState || t('common.no_data')}`}
            className="h-52 w-full rounded-2xl border border-txf-border bg-txf-surface-muted p-4 text-sm"
          />
          <p className="mt-3 text-sm text-txf-subtle">
            {t('common.drafts_note')}
          </p>
        </div>
      </div>
    </div>
  );
}
