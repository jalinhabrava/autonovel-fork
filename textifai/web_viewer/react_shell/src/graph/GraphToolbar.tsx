import React from 'react';
import { t, type UiI18nKey } from '../i18n/ui';

const CHIP_LABELS: Array<{ id: string; label: UiI18nKey }> = [
  { id: 'all', label: 'graph.filter_all' },
  { id: 'chapter', label: 'graph.filter_chapters' },
  { id: 'character', label: 'graph.filter_characters' },
  { id: 'place', label: 'graph.filter_places' },
  { id: 'object', label: 'graph.filter_objects' },
  { id: 'event', label: 'graph.filter_events' },
  { id: 'concept', label: 'graph.filter_concepts' },
  { id: 'review', label: 'graph.filter_review' },
];

export type GraphToolbarProps = {
  selectedKinds: Set<string>;
  toggleKind: (kind: string) => void;
  query: string;
  onQueryChange: (value: string) => void;
  onResetViewport: () => void;
};

export function GraphToolbar({
  selectedKinds,
  toggleKind,
  query,
  onQueryChange,
  onResetViewport,
}: GraphToolbarProps) {
  return (
    <div className="space-y-3 rounded-3xl border border-neutral-200 bg-neutral-50 p-4">
      <div className="flex flex-wrap gap-2">
        {CHIP_LABELS.map((chip) => (
          <button
            key={chip.id}
            type="button"
            onClick={() => toggleKind(chip.id)}
            className={`rounded-2xl px-3 py-1.5 text-sm ${selectedKinds.has(chip.id) || (chip.id === 'all' && selectedKinds.size === 0) ? 'bg-neutral-900 text-white' : 'border border-neutral-200 bg-white text-neutral-700'}`}
          >
            {t(chip.label)}
          </button>
        ))}
      </div>

      <input
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        placeholder={t('graph.search_placeholder')}
        className="w-full rounded-2xl border border-neutral-300 bg-white px-3 py-2 text-sm"
      />

      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={onResetViewport}
          className="rounded-2xl border border-neutral-200 bg-white px-3 py-1.5 text-sm text-neutral-700"
        >
          {t('graph.reset_filters')}
        </button>
      </div>
    </div>
  );
}
