import { Button, Metric, TopBar } from '../../common/ui';
import type { IngestionJob, ProjectDetail } from '../../api';
import { t, type UiI18nKey } from '../../i18n/ui';

const RUN_STATUS_LABEL_KEYS: Record<string, UiI18nKey> = {
  completed_with_editorial_review: 'ingestion.status_default',
};

function formatRunStatus(status: string | undefined): string {
  if (!status) return t('ingestion.status_default');
  const labelKey = RUN_STATUS_LABEL_KEYS[status];
  return labelKey ? t(labelKey) : status;
}

export function IngestionView({ runStatus, ingestionJobs }: { runStatus: ProjectDetail['run_status']; ingestionJobs: IngestionJob[] }) {
  return <section><TopBar title={t('nav.ingest')} subtitle={t('ingestion.subtitle')} actions={<Button variant="secondary" disabled>{t('ingestion.disabled')}</Button>} /><div className="p-5 grid grid-cols-12 gap-5"><div className="col-span-12 lg:col-span-7 rounded-3xl border border-txf-border p-5 bg-txf-surface"><h2 className="font-semibold">{t('ingestion.progress_title')}</h2><p className="mt-2 text-sm text-txf-subtle">{t('ingestion.progress_note')}</p><div className="mt-5 grid gap-3 text-sm md:grid-cols-2">{(runStatus?.steps || []).map((step) => <div key={step.id || step.label} className="rounded-2xl bg-txf-surface-muted border border-txf-border p-4"><div className="flex items-center justify-between"><div className="font-medium">{step.label || step.id || t('ingestion.step')}</div><span className="text-xs text-txf-subtle">{step.status || t('ingestion.pending')}</span></div><div className="mt-2 h-2 rounded-full bg-txf-surface-soft"><div className="h-2 rounded-full bg-txf-action" style={{ width: `${Math.max(0, Math.min(100, Number(step.progress ?? 0)))}%` }} /></div><div className="mt-1 text-xs text-txf-subtle">{step.progress ?? 0}%</div></div>)}{!(runStatus?.steps || []).length ? <div className="rounded-2xl bg-txf-surface-muted border border-txf-border p-4">{t('ingestion.no_steps')}</div> : null}</div></div><aside className="col-span-12 lg:col-span-5 space-y-4"><Metric label={t('ingestion.status_title')} value={formatRunStatus(runStatus?.status)} note={runStatus?.final_state_detail || t('ingestion.completed_review')} /><div className="rounded-3xl border border-txf-border bg-txf-surface p-5"><h2 className="font-semibold">{t('ingestion.progress')}</h2><div className="mt-3 space-y-2 text-sm"><div className="rounded-xl bg-txf-surface-muted border border-txf-border px-3 py-2">{t('ingestion.run')}: {runStatus?.run_id || t('ingestion.no_run_id')}</div><div className="rounded-xl bg-txf-surface-muted border border-txf-border px-3 py-2">{t('ingestion.safe_workspace')}: {runStatus?.safe_to_open_workspace ? t('common.yes') : t('common.no')}</div>{ingestionJobs.length ? ingestionJobs.map((job) => <div key={job.job_id} className="rounded-xl bg-txf-surface-muted border border-txf-border px-3 py-2">{job.run_name || job.job_id} · {job.status}</div>) : null}</div></div></aside></div></section>;
}
