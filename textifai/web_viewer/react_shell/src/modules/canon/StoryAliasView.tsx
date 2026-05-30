import React from 'react';
import { Button, TopBar } from '../../common/ui';
import { t } from '../../i18n/ui';

export function StoryAliasView({ selectedProjectId, notesPreview, legacyNotes, onOpenCanon }: { selectedProjectId: string; notesPreview: React.ReactNode; legacyNotes: React.ReactNode; onOpenCanon: () => void }) {
  return <section><TopBar title={t('nav.codex')} subtitle="Story Bible deep link alias. Canon / VaERL es la vista principal." actions={<Button variant="secondary" onClick={onOpenCanon}>Open Canon / VaERL</Button>} /><div className="p-5 grid grid-cols-12 gap-5"><aside className="col-span-12 lg:col-span-3 rounded-3xl border border-neutral-200 bg-neutral-50 p-4"><h2 className="font-semibold">Vault tree</h2><div className="mt-4 space-y-2 text-sm">{notesPreview}</div></aside><div className="col-span-12 lg:col-span-9">{selectedProjectId ? legacyNotes : <div className="rounded-3xl border border-neutral-200 p-5 text-sm text-neutral-500">Selecciona proyecto.</div>}</div></div></section>;
}
