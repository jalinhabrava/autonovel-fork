import React from 'react';
import { Button, TopBar } from '../../common/ui';
import { t } from '../../i18n/ui';

export function GraphView({ graphPanel }: { graphPanel: React.ReactNode }) {
  return <section><TopBar title={t('nav.graph')} subtitle="Exploración visual author-facing con física viva e inspector editorial." actions={<Button variant="secondary">Restablecer filtros</Button>} /><div className="p-5">{graphPanel}</div></section>;
}
