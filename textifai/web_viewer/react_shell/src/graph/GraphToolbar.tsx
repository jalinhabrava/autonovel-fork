import React from 'react';
import { t, type UiI18nKey } from '../i18n/ui';

const CHIP_TONES: Record<string, { background: string; border: string; color: string }> = {
  all: { background: '#e8d9b8', border: 'rgba(110, 95, 64, 0.18)', color: '#3a2a21' },
  chapter: { background: 'rgba(127, 122, 106, 0.18)', border: 'rgba(127, 122, 106, 0.34)', color: '#5f5a4d' },
  character: { background: 'rgba(17, 24, 39, 0.12)', border: 'rgba(17, 24, 39, 0.24)', color: '#111827' },
  place: { background: 'rgba(29, 78, 216, 0.12)', border: 'rgba(29, 78, 216, 0.24)', color: '#1d4ed8' },
  object: { background: 'rgba(15, 118, 110, 0.12)', border: 'rgba(15, 118, 110, 0.24)', color: '#0f766e' },
  event: { background: 'rgba(154, 52, 18, 0.12)', border: 'rgba(154, 52, 18, 0.24)', color: '#9a3412' },
  concept: { background: 'rgba(107, 114, 128, 0.14)', border: 'rgba(107, 114, 128, 0.24)', color: '#4b5563' },
  review: { background: 'rgba(185, 28, 28, 0.1)', border: 'rgba(185, 28, 28, 0.22)', color: '#b91c1c' },
};

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
    <div className="space-y-3 rounded-3xl border border-txf-border bg-txf-surface p-4">
      <div className="flex flex-wrap gap-2">
        {CHIP_LABELS.map((chip) => (
          (() => {
            const active = selectedKinds.has(chip.id) || (chip.id === 'all' && selectedKinds.size === 0);
            const tone = CHIP_TONES[chip.id] || CHIP_TONES.all;
            return (
              <button
                key={chip.id}
                type="button"
                onClick={() => toggleKind(chip.id)}
                className={`rounded-2xl border px-3 py-1.5 text-sm transition-colors ${active ? 'shadow-[inset_0_0_0_1px_rgba(58,42,33,0.08)]' : ''}`}
                style={{
                  backgroundColor: tone.background,
                  borderColor: tone.border,
                  color: tone.color,
                  boxShadow: active ? `inset 0 0 0 1px ${tone.border}` : undefined,
                }}
              >
                {t(chip.label)}
              </button>
            );
          })()
        ))}
      </div>

      <input
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        placeholder={t('graph.search_placeholder')}
        className="w-full rounded-2xl border border-txf-border-strong bg-txf-surface px-3 py-2 text-sm text-txf-text placeholder:text-txf-subtle"
      />

      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={onResetViewport}
          className="rounded-2xl border border-txf-border bg-txf-surface-soft px-3 py-1.5 text-sm font-medium text-txf-action hover:bg-txf-surface-muted"
        >
          {t('graph.reset_filters')}
        </button>
      </div>
    </div>
  );
}
