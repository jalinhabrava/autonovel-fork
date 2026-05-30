import React from 'react';
import { t } from '../../i18n/ui';

export type EntityFicheViewProps = {
  bodyMarkdown: string;
  onChangeBody: (next: string) => void;
  localDirty: boolean;
};

export function stripFrontmatter(markdown: string): { body: string; frontmatterHidden: boolean } {
  const source = String(markdown || '');
  if (!source.startsWith('---\n')) return { body: source, frontmatterHidden: false };
  const closing = source.indexOf('\n---\n', 4);
  if (closing === -1) return { body: source, frontmatterHidden: false };
  return { body: source.slice(closing + 5), frontmatterHidden: true };
}

export function EntityFicheView({ bodyMarkdown, onChangeBody, localDirty }: EntityFicheViewProps) {
  return (
    <section className="mt-4 rounded-2xl border border-neutral-200 bg-white p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-neutral-800">{t('graph.fiche_body')}</h3>
        <span className="text-xs text-neutral-500">{t('graph.fiche_save_later')}</span>
      </div>
      {localDirty ? <div className="mb-2 text-xs text-amber-700">{t('graph.fiche_local_dirty')}</div> : null}
      <textarea
        value={bodyMarkdown}
        onChange={(event) => onChangeBody(event.target.value)}
        placeholder={t('graph.fiche_empty_placeholder')}
        className="min-h-[300px] w-full rounded-xl border border-neutral-200 bg-neutral-50 p-3 text-sm leading-6 text-neutral-800"
      />
    </section>
  );
}

