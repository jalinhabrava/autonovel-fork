import { Button, Metric, TopBar } from '../../common/ui';
import { t } from '../../i18n/ui';

export function ReviewQueueView({ reviewSummary, warningsVisible }: { reviewSummary: Record<string, number>; warningsVisible: number }) {
  return <section><TopBar title={t('nav.review')} subtitle={t('review.subtitle')} actions={<Button variant="secondary">{t('review.batch')}</Button>} /><div className="p-5 grid grid-cols-12 gap-5"><aside className="col-span-12 lg:col-span-4 space-y-4"><Metric label={t('review.pending_decisions')} value={reviewSummary.total_pending ?? warningsVisible} note={t('review.summary_note')} /></aside><div className="col-span-12 lg:col-span-8" /></div></section>;
}
