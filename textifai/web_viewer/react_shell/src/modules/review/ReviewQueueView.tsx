import { Button, Metric, TopBar } from '../../common/ui';
import { t } from '../../i18n/ui';

export function ReviewQueueView({ reviewSummary, warningsVisible }: { reviewSummary: Record<string, number>; warningsVisible: number }) {
  return <section><TopBar title={t('nav.review')} subtitle="Cola editorial y decisiones de canon." actions={<Button variant="secondary">Revisar lote</Button>} /><div className="p-5 grid grid-cols-12 gap-5"><aside className="col-span-12 lg:col-span-4 space-y-4"><Metric label="Decisiones pendientes" value={reviewSummary.total_pending ?? warningsVisible} note="Resumen dinámico de cola editorial." /></aside><div className="col-span-12 lg:col-span-8" /></div></section>;
}
