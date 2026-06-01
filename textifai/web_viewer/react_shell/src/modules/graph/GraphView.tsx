import React from 'react';
import { Button, TopBar } from '../../common/ui';
import { t } from '../../i18n/ui';

export function GraphView({ graphPanel }: { graphPanel: React.ReactNode }) {
  return <section data-testid="graph-view"><TopBar title={t('nav.graph')} subtitle={t('graph.subtitle')} actions={<Button variant="secondary">{t('graph.reset_filters')}</Button>} /><div className="p-5">{graphPanel}</div></section>;
}
