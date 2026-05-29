import React from 'react';

const CHIP_LABELS = [
  { id: 'all', label: 'Todo' },
  { id: 'chapter', label: 'Capítulos' },
  { id: 'character', label: 'Personajes' },
  { id: 'place', label: 'Lugares' },
  { id: 'object', label: 'Objetos' },
  { id: 'event', label: 'Eventos' },
  { id: 'concept', label: 'Conceptos' },
  { id: 'review', label: 'Revisión' },
];

export type GraphToolbarProps = {
  selectedKinds: Set<string>;
  toggleKind: (kind: string) => void;
  query: string;
  onQueryChange: (value: string) => void;
  relatedOnly: boolean;
  onRelatedOnlyChange: (value: boolean) => void;
  onResetViewport: () => void;
};

export function GraphToolbar({
  selectedKinds,
  toggleKind,
  query,
  onQueryChange,
  relatedOnly,
  onRelatedOnlyChange,
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
            {chip.label}
          </button>
        ))}
      </div>

      <input
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        placeholder="Buscar nodo"
        className="w-full rounded-2xl border border-neutral-300 bg-white px-3 py-2 text-sm"
      />

      <div className="flex items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-sm text-neutral-700">
          <input
            type="checkbox"
            checked={relatedOnly}
            onChange={(event) => onRelatedOnlyChange(event.target.checked)}
          />
          Solo relacionados
        </label>
        <button
          type="button"
          onClick={onResetViewport}
          className="rounded-2xl border border-neutral-200 bg-white px-3 py-1.5 text-sm text-neutral-700"
        >
          Restablecer filtros
        </button>
      </div>
    </div>
  );
}
