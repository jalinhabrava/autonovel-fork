import React from 'react';
import { Button, TopBar } from '../../common/ui';
import { t } from '../../i18n/ui';

export function CanonVaerlView({ canonTable, selectedProjectId, legacyNotes }: { canonTable: React.ReactNode; selectedProjectId: string; legacyNotes: React.ReactNode }) {
  return <section><TopBar title={t('nav.codex')} subtitle="Wiki author-facing del canon: entidades, hechos, evidencia y Story Bible consolidada." actions={<><Button variant="secondary">Export selection</Button><Button variant="secondary">Ver evidencia</Button></>} /><div className="p-5 grid grid-cols-12 gap-5"><div className="col-span-12 lg:col-span-8 space-y-5">{canonTable}<div className="rounded-3xl border border-neutral-200 bg-white p-4"><div className="mb-3 flex items-center gap-2 text-sm font-semibold">Story Bible</div>{selectedProjectId ? legacyNotes : <div className="rounded-2xl border border-neutral-200 p-4 text-sm text-neutral-500">Selecciona proyecto.</div>}</div></div><aside className="col-span-12 lg:col-span-4" /></div></section>;
}
