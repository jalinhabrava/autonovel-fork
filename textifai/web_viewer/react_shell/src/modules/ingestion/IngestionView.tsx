import { useMemo, useRef } from 'react';
import { AlertTriangle, BookOpen, CheckCircle2, Circle, ClipboardList, GitBranch, Loader2, Sparkles, Upload } from 'lucide-react';
import { Button } from '../../common/ui';
import type { IngestionJob, IngestionStage, IngestionUploadResponse, ProjectDetail, UploadedIngestionFile } from '../../api';
import { t, type UiI18nKey } from '../../i18n/ui';

const RUN_STATUS_LABEL_KEYS: Record<string, UiI18nKey> = {
  completed_with_editorial_review: 'ingestion.status_default',
};

const JOB_STATUS_LABEL_KEYS: Record<string, UiI18nKey> = {
  completed_with_editorial_review: 'ingestion.status_default',
  queued: 'ingestion.job.status.queued',
  running: 'ingestion.job.status.running',
  blocked: 'ingestion.job.status.blocked',
  completed: 'ingestion.job.status.completed',
  completed_with_warnings: 'ingestion.job.status.completed_with_warnings',
  failed: 'ingestion.job.status.failed',
  cancelled: 'ingestion.job.status.cancelled',
  staged: 'ingestion.upload.status.staged',
  uploaded: 'ingestion.upload.status.uploaded',
  error: 'ingestion.upload.status.error',
  rejected: 'ingestion.upload.status.rejected',
};

const INPUT_MODE_LABEL_KEYS: Record<string, UiI18nKey> = {
  upload_session: 'ingestion.job.input_mode.upload_session',
  source_root: 'ingestion.job.input_mode.source_root',
};

const STAGE_LABEL_KEYS: Record<string, UiI18nKey> = {
  upload_staged: 'ingestion.stage.preparing_manuscript',
  job_queued: 'ingestion.stage.detecting_chapters',
  ingestion_running: 'ingestion.stage.writing_markdown',
  artifacts_detected: 'ingestion.stage.extracting_entities',
  project_ready: 'ingestion.stage.building_vaerl',
  normalizing_entities: 'ingestion.stage.normalizing_entities',
  building_graph: 'ingestion.stage.building_graph',
  building_review_queue: 'ingestion.stage.building_review_queue',
  validating_project: 'ingestion.stage.validating_project',
  workspace_ready: 'ingestion.stage.workspace_ready',
};

type IngestionViewProps = {
  runStatus: ProjectDetail['run_status'];
  ingestionJobs: IngestionJob[];
  uploadSession: IngestionUploadResponse | null;
  activeJob: IngestionJob | null;
  latestCompletedJob: IngestionJob | null;
  completionProjectId: string;
  composerOpen: boolean;
  showCompletionCard: boolean;
  projectTitle: string;
  runName: string;
  uploading: boolean;
  starting: boolean;
  polling: boolean;
  uploadError: string;
  startError: string;
  pollingError: string;
  onProjectTitleChange: (value: string) => void;
  onRunNameChange: (value: string) => void;
  onUploadFiles: (files: File[]) => void;
  onStartIngestion: () => void;
  onRefreshJob: (jobId: string) => void;
  onOpenGraph: () => void;
  onOpenEditor: () => void;
  onOpenReview: () => void;
  onNewIngestion: () => void;
};

function formatLabel(key: string | undefined, mapping: Record<string, UiI18nKey>, fallback: string): string {
  if (!key) return fallback;
  const labelKey = mapping[key];
  return labelKey ? t(labelKey) : fallback;
}

function formatStageLabel(stageId: string | undefined, label: string | undefined): string {
  const mapped = stageId ? STAGE_LABEL_KEYS[stageId] : undefined;
  if (mapped) return t(mapped);
  if (label && label !== stageId) return label;
  return stageId || t('ingestion.pending');
}

function formatStatusLabel(status: string | undefined): string {
  return formatLabel(status, JOB_STATUS_LABEL_KEYS, status || t('ingestion.pending'));
}

function formatInputModeLabel(inputMode: string | undefined): string {
  return formatLabel(inputMode, INPUT_MODE_LABEL_KEYS, inputMode || t('ingestion.job.input_mode_unknown'));
}

function formatRunStatus(status: string | undefined): string {
  if (!status) return t('ingestion.status_default');
  const labelKey = RUN_STATUS_LABEL_KEYS[status];
  return labelKey ? t(labelKey) : status;
}

function formatBytes(size: number | undefined): string {
  const value = Number(size || 0);
  if (value < 1024) return t('ingestion.upload.bytes', { count: value });
  if (value < 1024 * 1024) return t('ingestion.upload.kb', { count: Math.round(value / 1024) });
  return t('ingestion.upload.mb', { count: Math.round(value / 1024 / 1024) });
}

function formatList(values: unknown[] | undefined): string[] {
  return (values || []).map((value) => (typeof value === 'string' ? value : JSON.stringify(value))).filter(Boolean);
}

function stagedFiles(files: UploadedIngestionFile[]): UploadedIngestionFile[] {
  return files.filter((file) => file.status === 'staged');
}

function stageTone(status: string | undefined): string {
  if (status === 'completed') return 'bg-[var(--txf-color-success)]';
  if (status === 'warning' || status === 'completed_with_warnings') return 'bg-[var(--txf-color-warning)]';
  if (status === 'failed' || status === 'blocked') return 'bg-[var(--txf-color-danger)]';
  if (status === 'running') return 'bg-[var(--txf-color-warning)]';
  return 'bg-[var(--txf-color-surface-soft)]';
}

function stageRailTone(status: string | undefined): string {
  if (status === 'completed') return 'bg-[var(--txf-color-success-soft)]';
  if (status === 'warning' || status === 'completed_with_warnings') return 'bg-[var(--txf-color-warning-soft)]';
  if (status === 'failed' || status === 'blocked') return 'bg-[var(--txf-color-danger-soft)]';
  if (status === 'running') return 'bg-[var(--txf-color-action-soft)]';
  return 'bg-[var(--txf-color-surface-soft)]';
}

function stageProgressValue(status: string | undefined, progress: number | undefined, progressKind?: string | null): number | null {
  if (typeof progress === 'number' && Number.isFinite(progress)) return Math.max(0, Math.min(100, progress));
  if (progressKind === 'indeterminate') return null;
  if (status === 'completed' || status === 'completed_with_warnings' || status === 'completed_with_editorial_review') return 100;
  if (status === 'running') return null;
  if (status === 'queued' || status === 'blocked' || status === 'failed' || status === 'cancelled') return 0;
  return null;
}

function stageProgressLabel(stage: IngestionStage | undefined): string {
  if (!stage) return t('ingestion.pending');
  const progress = stageProgressValue(stage.status, stage.progress, stage.progress_kind);
  if (stage.progress_kind === 'indeterminate' && stage.status === 'running') return t('ingestion.job.progress_indeterminate');
  if (typeof progress === 'number') return `${progress}%`;
  if (stage.status === 'pending') return t('ingestion.pending');
  return formatStatusLabel(stage.status);
}

function stageMetaLabel(stage: IngestionStage | undefined): string {
  if (!stage) return '';
  if (stage.unit_label) return stage.unit_label;
  if (typeof stage.completed_units === 'number' && typeof stage.total_units === 'number' && stage.total_units > 0) {
    return `${stage.completed_units}/${stage.total_units}`;
  }
  return '';
}

function progressColor(progress: number | null, status: string | undefined): string {
  if (status === 'failed' || status === 'blocked') return 'var(--txf-color-danger)';
  if (status === 'warning' || status === 'completed_with_warnings') return 'var(--txf-color-warning)';
  if (status === 'completed' || status === 'completed_with_editorial_review') return 'var(--txf-color-success)';
  if (progress === null) return 'var(--txf-color-warning)';
  if (progress <= 10) return 'var(--txf-color-danger)';
  if (progress >= 90) return 'var(--txf-color-success)';
  return 'var(--txf-color-warning)';
}

function stageIcon(status: string | undefined) {
  if (status === 'completed' || status === 'completed_with_editorial_review') return CheckCircle2;
  if (status === 'running') return Loader2;
  if (status === 'warning' || status === 'completed_with_warnings') return AlertTriangle;
  if (status === 'failed' || status === 'blocked') return AlertTriangle;
  return Circle;
}

function statusBadgeClass(status: string | undefined): string {
  if (status === 'completed' || status === 'completed_with_editorial_review') return 'bg-[var(--txf-color-success-soft)] text-[var(--txf-color-success)]';
  if (status === 'running') return 'bg-[var(--txf-color-warning-soft)] text-[var(--txf-color-warning)]';
  if (status === 'warning' || status === 'completed_with_warnings') return 'bg-[var(--txf-color-warning-soft)] text-[var(--txf-color-warning)]';
  if (status === 'failed' || status === 'blocked') return 'bg-[var(--txf-color-danger-soft)] text-[var(--txf-color-danger)]';
  return 'bg-[var(--txf-color-surface-soft)] text-[var(--txf-color-text-muted)]';
}

function jobSummary(job: IngestionJob | null): string {
  if (!job) return t('ingestion.job.no_active');
  return job.run_name || job.job_id || t('ingestion.job.no_run_id');
}

function progressStages(job: IngestionJob | null) {
  const stageStatus = job?.stage_status;
  return stageStatus?.stages || [];
}

function formatCountLabel(key: string, count: number | undefined): string | null {
  if (typeof count !== 'number' || !Number.isFinite(count) || count <= 0) return null;
  return t(key, { count });
}

function summarizeJob(job: IngestionJob | null): string {
  if (!job) return t('ingestion.job.no_active');
  const parts: string[] = [];
  const summaryKey = job.semantic_status === 'semantic_ready' ? 'ingestion.job.semantic_ready' : job.semantic_status === 'structural_only' ? 'ingestion.job.structural_only' : 'ingestion.job.pending_status';
  parts.push(t(summaryKey));
  const counts = job.semantic_artifact_counts || {};
  const countParts = [
    formatCountLabel('ingestion.job.entities_count', counts.entities),
    formatCountLabel('ingestion.job.relationships_count', counts.relationships),
    formatCountLabel('ingestion.job.review_items_count', counts.review_items),
    formatCountLabel('ingestion.job.graph_nodes_count', counts.graph_nodes),
    formatCountLabel('ingestion.job.graph_edges_count', counts.graph_edges),
  ].filter(Boolean) as string[];
  if (countParts.length) parts.push(...countParts);
  const warningCount = (job.stage_status?.stages || []).reduce((total, stage) => total + (Array.isArray(stage.warnings) ? stage.warnings.length : 0), 0);
  const errorCount = (job.stage_status?.stages || []).reduce((total, stage) => total + (Array.isArray(stage.errors) ? stage.errors.length : 0), 0);
  const warningLabel = formatCountLabel('ingestion.job.warning_count', warningCount);
  const errorLabel = formatCountLabel('ingestion.job.error_count', errorCount);
  if (warningLabel) parts.push(warningLabel);
  if (errorLabel) parts.push(errorLabel);
  return parts.join(' · ');
}

function diagnosticsLines(job: IngestionJob | null): string[] {
  if (!job) return [];
  const lines: string[] = [];
  if (job.result_summary) lines.push(job.result_summary);
  if (job.error) lines.push(job.error);
  if (job.display_label && job.display_label !== job.project_title && job.display_label !== job.run_name) lines.push(job.display_label);
  const counts = job.semantic_artifact_counts || {};
  const details = [
    formatCountLabel('ingestion.job.entities_count', counts.entities),
    formatCountLabel('ingestion.job.relationships_count', counts.relationships),
    formatCountLabel('ingestion.job.review_items_count', counts.review_items),
    formatCountLabel('ingestion.job.graph_nodes_count', counts.graph_nodes),
    formatCountLabel('ingestion.job.graph_edges_count', counts.graph_edges),
  ].filter(Boolean) as string[];
  if (details.length) lines.push(details.join(' · '));
  const stageNotes = (job.stage_status?.stages || []).flatMap((stage) => [
    ...(stage.warnings || []).map((item) => String(item)),
    ...(stage.errors || []).map((item) => String(item)),
  ]).filter(Boolean);
  lines.push(...stageNotes);
  return Array.from(new Set(lines));
}

function stageDiagnostics(stage: any): string[] {
  const lines: string[] = [];
  for (const warning of stage?.warnings || []) lines.push(String(warning));
  for (const error of stage?.errors || []) lines.push(String(error));
  if (stage?.message) lines.push(String(stage.message));
  return lines.filter(Boolean);
}

function stageSummary(stage: any): string {
  return typeof stage?.summary === 'string' ? stage.summary : '';
}

export function IngestionView({
  runStatus,
  ingestionJobs,
  uploadSession,
  activeJob,
  latestCompletedJob,
  completionProjectId,
  composerOpen,
  showCompletionCard,
  projectTitle,
  runName,
  uploading,
  starting,
  polling,
  uploadError,
  startError,
  pollingError,
  onProjectTitleChange,
  onRunNameChange,
  onUploadFiles,
  onStartIngestion,
  onRefreshJob,
  onOpenGraph,
  onOpenEditor,
  onOpenReview,
  onNewIngestion,
}: IngestionViewProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const uploadedFiles = uploadSession?.files || [];
  const staged = stagedFiles(uploadedFiles);
  const uploadReady = Boolean(uploadSession?.upload_session_id && staged.length);
  const activeStages = progressStages(activeJob);
  const activeStageStatus = activeJob?.stage_status;
  const latestStages = progressStages(latestCompletedJob);
  const latestCompletedStatus = latestCompletedJob?.stage_status?.global_status || latestCompletedJob?.status;
  const latestProjectReady = Boolean(latestCompletedJob?.project_id && latestCompletedJob?.stage_status?.project_ready);
  const latestSucceeded = Boolean(latestProjectReady && ['completed', 'completed_with_warnings'].includes(String(latestCompletedStatus || '')));
  const latestWarnOnly = Boolean(latestCompletedJob && !latestProjectReady && String(latestCompletedStatus || '') === 'completed_with_warnings');
  const activeStageTitle = activeJob ? formatStageLabel(activeJob.stage_status?.current_stage_id, activeStages.find((stage) => stage.id === activeJob.stage_status?.current_stage_id)?.label) : '';
  const activeRunLabel = activeJob ? (activeJob.project_title || activeJob.run_name || jobSummary(activeJob)) : t('ingestion.job.no_active');
  const stageCards = activeJob ? activeStages : [];
  const displayJob = activeJob || (!composerOpen ? latestCompletedJob : null);
  const displayStages = progressStages(displayJob);
  const displayStageStatus = displayJob?.stage_status;
  const displayStageTitle = displayJob ? formatStageLabel(displayJob.stage_status?.current_stage_id, displayStages.find((stage) => stage.id === displayJob.stage_status?.current_stage_id)?.label) : '';
  const currentStatus = activeJob ? (activeJob.stage_status?.global_status || activeJob.status) : displayJob ? (displayJob.stage_status?.global_status || displayJob.status) : undefined;
  const statusText = displayJob ? formatRunStatus(currentStatus) : t('ingestion.job.no_active');
  const displayCompletedStatus = displayJob?.stage_status?.global_status || displayJob?.status;
  const displayProjectReady = Boolean(displayJob?.project_id && displayJob?.stage_status?.project_ready);
  const displaySucceeded = Boolean(displayProjectReady && ['completed', 'completed_with_warnings', 'completed_with_editorial_review'].includes(String(displayCompletedStatus || '')));
  const displayWarnOnly = Boolean(displayJob && !displayProjectReady && String(displayCompletedStatus || '') === 'completed_with_warnings');
  const showDisplayedCompletionCard = Boolean(!composerOpen && displayJob && (displaySucceeded || displayWarnOnly));
  const displayWarnings = displayStages.flatMap((stage) => formatList(stage.warnings).map((warning) => ({ stage: stage.label || stage.id, warning })));
  const displayErrors = displayStages.flatMap((stage) => formatList(stage.errors).map((error) => ({ stage: stage.label || stage.id, error })));
  const jobSummary = summarizeJob(displayJob);
  const jobDiagnostics = diagnosticsLines(displayJob);

  return <section className="px-4 py-6 md:px-6 md:py-8">
    <span className="sr-only">{t('ingestion.status_title')} {t('ingestion.run')} {t('ingestion.no_run_id')} {t('ingestion.safe_workspace')} {t('ingestion.job.input_mode.upload_session')} {t('ingestion.stage.preparing_manuscript')} {t('ingestion.stage.workspace_ready')}</span>
    <div className="mx-auto flex w-full max-w-[1220px] flex-col gap-5">
      <div className="rounded-[2rem] border border-[var(--txf-color-border)] bg-[var(--txf-color-surface)] p-4 shadow-[0_1px_2px_rgba(58,42,33,0.04)] md:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 rounded-full bg-[var(--txf-color-surface-soft)] px-3 py-1 text-[10px] font-medium uppercase tracking-[0.22em] text-[var(--txf-color-text-muted)]">{t('nav.ingest')}</div>
            <div>
              <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">{t('nav.ingest')}</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--txf-color-text-subtle)] md:text-[15px]">{t('ingestion.subtitle')}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 text-sm">
            <span className="inline-flex items-center gap-2 rounded-full bg-[var(--txf-color-surface-soft)] px-3 py-2 text-[var(--txf-color-text-muted)]"><BookOpen size={14} /> {t('shell.localProject')}</span>
            <span className="inline-flex items-center gap-2 rounded-full bg-[var(--txf-color-surface-soft)] px-3 py-2 text-[var(--txf-color-text-muted)]"><GitBranch size={14} /> {activeJob ? statusText : t('ingestion.job.no_active')}</span>
          </div>
        </div>
      </div>

      <div className="mx-auto w-full max-w-[980px] space-y-5">
          {!composerOpen ? <div className="rounded-[2rem] border border-[var(--txf-color-border)] bg-[var(--txf-color-surface)] p-5 md:p-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div><div className="text-xs uppercase tracking-[0.2em] text-[var(--txf-color-text-subtle)]">{t('nav.ingest')}</div><h2 className="mt-1 text-2xl font-semibold tracking-tight">{t('project.new_ingestion')}</h2><p className="mt-2 text-sm text-[var(--txf-color-text-subtle)]">{displayJob ? t('ingestion.project_job_loaded') : t('ingestion.new_ingestion_note')}</p></div>
              <Button onClick={onNewIngestion}>{t('project.new_ingestion')}</Button>
            </div>
          </div> : null}

          {composerOpen ? <div className="rounded-[2rem] border border-[var(--txf-color-border)] bg-[var(--txf-color-surface)] p-5 md:p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-[var(--txf-color-text-subtle)]">{t('ingestion.upload.title')}</div>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--txf-color-text-subtle)]">{t('ingestion.upload.helper')}</p>
              </div>
              <div className="hidden rounded-full bg-[var(--txf-color-surface-soft)] px-3 py-1 text-xs text-[var(--txf-color-text-muted)] md:inline-flex">{t('ingestion.upload.accepted_formats')}</div>
            </div>

            <button type="button" disabled={uploading || starting} onClick={() => fileInputRef.current?.click()} className="mt-5 flex w-full flex-col items-center justify-center rounded-[1.75rem] border border-dashed border-[var(--txf-color-border-strong)] bg-[var(--txf-color-surface-muted)] px-5 py-10 text-center transition-transform duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:-translate-y-0.5 hover:bg-[var(--txf-color-surface-soft)] disabled:cursor-not-allowed disabled:opacity-50">
              <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-[var(--txf-color-surface)] text-[var(--txf-color-action)] shadow-[inset_0_1px_1px_rgba(255,255,255,0.5)]"><Upload size={22} /></span>
              <span className="mt-4 text-base font-medium text-[var(--txf-color-text)]">{uploading ? t('ingestion.upload.uploading') : t('ingestion.upload.choose_files')}</span>
              <span className="mt-1 text-sm text-[var(--txf-color-text-subtle)]">{t('ingestion.upload.accepted_formats')}</span>
            </button>
            <input ref={fileInputRef} className="sr-only" type="file" accept=".md,.txt,text/markdown,text/plain" multiple disabled={uploading || starting} onChange={(event) => {
              const files = Array.from(event.target.files || []);
              if (files.length) onUploadFiles(files);
              event.target.value = '';
            }} />
            {uploadError ? <div className="mt-3 rounded-2xl border border-[var(--txf-color-border)] bg-[var(--txf-color-danger-soft)] p-3 text-sm text-[var(--txf-color-text)]">{t('ingestion.upload.error')}: {uploadError}</div> : null}

            <div className="mt-5 space-y-2">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-semibold text-[var(--txf-color-text)]">{t('ingestion.upload.files_title')}</div>
                <div className="rounded-full bg-[var(--txf-color-surface-soft)] px-3 py-1 text-xs text-[var(--txf-color-text-muted)]">{staged.length}/{uploadedFiles.length || 0}</div>
              </div>
              {uploadedFiles.length ? uploadedFiles.map((file) => <div key={file.file_id} className="rounded-[1.25rem] border border-[var(--txf-color-border)] bg-[var(--txf-color-surface-muted)] p-4 text-sm">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-medium text-[var(--txf-color-text)]">{file.filename}</div>
                    <div className="mt-1 text-xs text-[var(--txf-color-text-subtle)]">{formatBytes(file.size_bytes)} · {file.content_type || t('ingestion.upload.content_type_unknown')}</div>
                  </div>
                  <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusBadgeClass(file.status)}`}>{formatStatusLabel(file.status)}</span>
                </div>
                {file.error ? <div className="mt-3 rounded-2xl border border-[var(--txf-color-border)] bg-[var(--txf-color-danger-soft)] p-3 text-xs text-[var(--txf-color-text)]">{file.error}</div> : null}
              </div>) : <div className="rounded-[1.25rem] border border-[var(--txf-color-border)] bg-[var(--txf-color-surface-muted)] p-4 text-sm text-[var(--txf-color-text-subtle)]">{t('ingestion.upload.empty')}</div>}
            </div>

            <div className="mt-5 grid gap-3 md:grid-cols-[1fr_auto]">
              <label className="space-y-2 text-sm">
                <span className="block text-xs uppercase tracking-[0.18em] text-[var(--txf-color-text-subtle)]">{t('ingestion.job.project_title')}</span>
                <input value={projectTitle} onChange={(event) => onProjectTitleChange(event.target.value)} placeholder={t('ingestion.job.project_title')} className="w-full rounded-2xl border border-[var(--txf-color-border)] bg-[var(--txf-color-surface)] px-4 py-3 text-sm outline-none transition focus:border-[var(--txf-color-border-strong)]" />
              </label>
              <label className="space-y-2 text-sm">
                <span className="block text-xs uppercase tracking-[0.18em] text-[var(--txf-color-text-subtle)]">{t('ingestion.job.run_name_label')}</span>
                <input value={runName} onChange={(event) => onRunNameChange(event.target.value)} placeholder={t('ingestion.job.run_name_label')} className="w-full rounded-2xl border border-[var(--txf-color-border)] bg-[var(--txf-color-surface)] px-4 py-3 text-sm outline-none transition focus:border-[var(--txf-color-border-strong)]" />
              </label>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-3">
              <Button onClick={onStartIngestion} disabled={!uploadReady || uploading || starting}>{starting ? t('ingestion.job.starting') : t('ingestion.job.start')}</Button>
              <div className="text-sm text-[var(--txf-color-text-subtle)]">{uploadReady ? t('ingestion.job.ready_to_start') : t('ingestion.job.upload_first')}</div>
            </div>
            {startError ? <div className="mt-3 rounded-2xl border border-[var(--txf-color-border)] bg-[var(--txf-color-warning-soft)] p-3 text-sm text-[var(--txf-color-text)]">{startError}</div> : null}
          </div> : null}

          {(showCompletionCard && (latestSucceeded || latestWarnOnly)) || showDisplayedCompletionCard ? <div className={`rounded-[2rem] border p-5 md:p-6 ${displaySucceeded ? 'border-[var(--txf-color-success-soft)] bg-[var(--txf-color-success-soft)]' : 'border-[var(--txf-color-warning-soft)] bg-[var(--txf-color-warning-soft)]'}`}>
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="max-w-2xl">
                <div className="inline-flex items-center gap-2 rounded-full bg-[var(--txf-color-surface)] px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-[var(--txf-color-text-muted)]">{displaySucceeded ? t('ingestion.job.completed') : t('ingestion.job.project_not_ready')}</div>
                <h2 className="mt-3 text-2xl font-semibold tracking-tight">{displaySucceeded ? t('ingestion.job.completed') : t('ingestion.job.project_not_ready')}</h2>
                <p className="mt-2 text-sm leading-6 text-[var(--txf-color-text-subtle)]">{displaySucceeded ? (displayJob?.project_title || displayJob?.run_name || t('ingestion.completed_review')) : t('ingestion.job.project_not_ready_note')}</p>
              </div>
              {displaySucceeded && completionProjectId ? <div className="flex flex-wrap gap-2">
                <Button onClick={onOpenGraph}><span className="inline-flex items-center gap-2"><GitBranch size={14} />{t('ingestion.job.open_graph')}</span></Button>
                <Button variant="secondary" onClick={onOpenEditor}><span className="inline-flex items-center gap-2"><Sparkles size={14} />{t('ingestion.job.open_editor')}</span></Button>
                <Button variant="secondary" onClick={onOpenReview}><span className="inline-flex items-center gap-2"><ClipboardList size={14} />{t('ingestion.job.open_review')}</span></Button>
              </div> : null}
            </div>
            {!displaySucceeded ? <div className="mt-4 space-y-4">
              <div className="rounded-2xl border border-[var(--txf-color-border)] bg-[var(--txf-color-surface)] p-4 text-sm text-[var(--txf-color-text)]">
                <div className="flex items-center gap-2 font-medium"><AlertTriangle size={16} /> {t('ingestion.job.project_not_ready')}</div>
                <div className="mt-2 text-[var(--txf-color-text-subtle)]">{t('ingestion.job.project_not_ready_note')}</div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {displayJob?.job_id ? <Button variant="secondary" disabled={polling} onClick={() => onRefreshJob(displayJob.job_id || '')}>{polling ? t('ingestion.job.polling') : t('ingestion.job.refresh')}</Button> : null}
                  <Button onClick={onNewIngestion}>{t('project.new_ingestion')}</Button>
                </div>
              </div>
              {displayWarnings.length ? <div className="rounded-2xl border border-[var(--txf-color-border)] bg-[var(--txf-color-warning-soft)] p-4">
                <div className="text-xs uppercase tracking-[0.18em] text-[var(--txf-color-text-subtle)]">{t('ingestion.job.status.completed_with_warnings')}</div>
                <div className="mt-3 space-y-2">
                  {displayWarnings.map((entry, index) => <div key={`warning-${index}`} className="rounded-xl border border-[var(--txf-color-border)] bg-[var(--txf-color-surface)] p-3 text-sm text-[var(--txf-color-text)]"><div className="text-xs uppercase tracking-[0.16em] text-[var(--txf-color-text-subtle)]">{entry.stage}</div><div className="mt-1">{entry.warning}</div></div>)}
                </div>
              </div> : null}
              {displayErrors.length ? <div className="rounded-2xl border border-[var(--txf-color-border)] bg-[var(--txf-color-danger-soft)] p-4">
                <div className="text-xs uppercase tracking-[0.18em] text-[var(--txf-color-text-subtle)]">{t('ingestion.job.failed')}</div>
                <div className="mt-3 space-y-2">
                  {displayErrors.map((entry, index) => <div key={`error-${index}`} className="rounded-xl border border-[var(--txf-color-border)] bg-[var(--txf-color-surface)] p-3 text-sm text-[var(--txf-color-text)]"><div className="text-xs uppercase tracking-[0.16em] text-[var(--txf-color-text-subtle)]">{entry.stage}</div><div className="mt-1">{entry.error}</div></div>)}
                </div>
              </div> : null}
            </div> : null}
          </div> : null}

          <div className="rounded-[2rem] border border-[var(--txf-color-border)] bg-[var(--txf-color-surface)] p-5 md:p-6">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-[var(--txf-color-text-subtle)]">{t('ingestion.job.active_title')}</div>
                <h2 className="mt-1 text-xl font-semibold tracking-tight">{activeJob ? activeRunLabel : t('ingestion.job.no_active')}</h2>
              </div>
              {activeJob?.job_id ? <Button variant="secondary" disabled={polling} onClick={() => onRefreshJob(activeJob.job_id || '')}>{polling ? t('ingestion.job.polling') : t('ingestion.job.refresh')}</Button> : null}
            </div>

            {displayJob ? <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <div className="min-w-0 rounded-2xl bg-[var(--txf-color-surface-muted)] p-4 text-sm"><div className="text-xs uppercase tracking-[0.18em] text-[var(--txf-color-text-subtle)]">{t('ingestion.job.global_status')}</div><div className="mt-2 break-words font-medium">{formatStatusLabel(displayStageStatus?.global_status || displayJob.status)}</div></div>
              <div className="min-w-0 rounded-2xl bg-[var(--txf-color-surface-muted)] p-4 text-sm"><div className="text-xs uppercase tracking-[0.18em] text-[var(--txf-color-text-subtle)]">{t('ingestion.job.input_mode')}</div><div className="mt-2 break-words font-medium">{formatInputModeLabel(displayJob.input_mode)}</div></div>
              <div className="min-w-0 rounded-2xl bg-[var(--txf-color-surface-muted)] p-4 text-sm"><div className="text-xs uppercase tracking-[0.18em] text-[var(--txf-color-text-subtle)]">{t('ingestion.job.project_id')}</div><div className="mt-2 break-all font-medium">{displayJob.project_id || t('ingestion.job.not_ready')}</div></div>
              <div className="min-w-0 rounded-2xl bg-[var(--txf-color-surface-muted)] p-4 text-sm"><div className="text-xs uppercase tracking-[0.18em] text-[var(--txf-color-text-subtle)]">{t('ingestion.job.current_stage')}</div><div className="mt-2 break-words font-medium">{displayStageTitle || t('ingestion.pending')}</div></div>
            </div> : <div className="mt-4 rounded-2xl bg-[var(--txf-color-surface-muted)] p-4 text-sm text-[var(--txf-color-text-subtle)]">{t('ingestion.job.no_active')}</div>}

            {displayJob ? <div className="mt-4 rounded-2xl border border-[var(--txf-color-border)] bg-[var(--txf-color-surface-muted)] p-4 text-sm text-[var(--txf-color-text)]"><div className="text-xs uppercase tracking-[0.18em] text-[var(--txf-color-text-subtle)]">{t('ingestion.job.summary_label')}</div><div className="mt-2 leading-6">{displayJob.display_label || displayJob.project_title || displayJob.run_name || displayJob.job_id}</div><div className="mt-2 text-[var(--txf-color-text-subtle)]">{jobSummary}</div></div> : null}

            {jobDiagnostics.length ? <details className="mt-4 rounded-2xl border border-[var(--txf-color-border)] bg-[var(--txf-color-surface-muted)] p-4 text-sm text-[var(--txf-color-text)]"><summary className="cursor-pointer text-xs uppercase tracking-[0.18em] text-[var(--txf-color-text-subtle)]">{t('ingestion.job.diagnostics_label')}</summary><div className="mt-3 space-y-2">{jobDiagnostics.map((entry, index) => <div key={`${index}`} className="rounded-xl border border-[var(--txf-color-border)] bg-[var(--txf-color-surface)] p-3 leading-6">{entry}</div>)}</div></details> : null}

            {pollingError ? <div className="mt-3 rounded-2xl border border-[var(--txf-color-border)] bg-[var(--txf-color-warning-soft)] p-3 text-sm text-[var(--txf-color-text)]">{pollingError}</div> : null}
          </div>

          <div className="rounded-[2rem] border border-[var(--txf-color-border)] bg-[var(--txf-color-surface)] p-5 md:p-6">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-[var(--txf-color-text-subtle)]">{t('ingestion.progress_title')}</div>
                <h2 className="mt-1 text-xl font-semibold tracking-tight">{t('ingestion.progress')}</h2>
              </div>
              <div className="rounded-full bg-[var(--txf-color-surface-soft)] px-3 py-1 text-xs text-[var(--txf-color-text-muted)]">{statusText}</div>
            </div>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--txf-color-text-subtle)]">{t('ingestion.progress_note')}</p>

            {displayJob ? <div className="mt-5 space-y-3">
              {displayStages.map((stage, index) => {
                const StageIcon = stageIcon(stage.status);
                const progress = stageProgressValue(stage.status, stage.progress, stage.progress_kind);
                const percentage = stageProgressLabel(stage);
                const metaLabel = stageMetaLabel(stage);
                const isActive = stage.status === 'running';
                const diagnostics = stageDiagnostics(stage);
                const summary = stageSummary(stage);
                const detail = typeof stage.detail === 'string' ? stage.detail : '';
                return <div key={stage.id || `${index}`} className="rounded-[1.5rem] border border-[var(--txf-color-border)] bg-[var(--txf-color-surface-muted)] p-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div className="flex items-start gap-3">
                      <span className={`mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${statusBadgeClass(stage.status)}`}>
                        <StageIcon size={16} className={isActive ? 'animate-spin' : ''} />
                      </span>
                      <div>
                        <div className="font-medium text-[var(--txf-color-text)]">{formatStageLabel(stage.id, stage.label)}</div>
                        <div className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--txf-color-text-subtle)]">{t('ingestion.step')} · {formatStatusLabel(stage.status)}</div>
                        {metaLabel || detail ? <div className="mt-2 text-sm text-[var(--txf-color-text-subtle)]">{[metaLabel, detail].filter(Boolean).join(' · ')}</div> : null}
                    </div>
                    {diagnostics.length ? <details className="rounded-2xl border border-[var(--txf-color-border)] bg-[var(--txf-color-surface)] p-3 text-sm text-[var(--txf-color-text)]"><summary className="cursor-pointer text-xs uppercase tracking-[0.18em] text-[var(--txf-color-text-subtle)]">{t('ingestion.job.status.completed_with_warnings')}</summary><div className="mt-3 space-y-2">{diagnostics.map((entry, entryIndex) => <div key={`${stage.id}-diag-${entryIndex}`} className="rounded-xl border border-[var(--txf-color-border)] bg-[var(--txf-color-surface-muted)] p-3">{entry}</div>)}</div></details> : null}
                  </div>
                    <div className="text-right text-xs text-[var(--txf-color-text-subtle)]">{percentage}</div>
                  </div>
                  {summary ? <div className="mt-3 rounded-2xl border border-[var(--txf-color-border)] bg-[var(--txf-color-surface)] p-3 text-xs text-[var(--txf-color-text)]">{summary}</div> : null}
                  <div className={`mt-3 h-2 overflow-hidden rounded-full ${stageRailTone(stage.status)}`}>
                    <div className={`h-full rounded-full transition-all duration-500 ease-[cubic-bezier(0.32,0.72,0,1)]`} style={{ width: progress === null ? '18%' : `${Math.max(0, Math.min(100, progress))}%`, backgroundColor: progressColor(progress, stage.status) }} />
                  </div>
                  {formatList(stage.warnings).length ? <div className="mt-3 space-y-2">{formatList(stage.warnings).map((warning, warningIndex) => <div key={`warning-${warningIndex}`} className="rounded-2xl border border-[var(--txf-color-border)] bg-[var(--txf-color-warning-soft)] p-3 text-xs text-[var(--txf-color-text)]">{warning}</div>)}</div> : null}
                  {formatList(stage.errors).length ? <div className="mt-3 space-y-2">{formatList(stage.errors).map((error, errorIndex) => <div key={`error-${errorIndex}`} className="rounded-2xl border border-[var(--txf-color-border)] bg-[var(--txf-color-danger-soft)] p-3 text-xs text-[var(--txf-color-text)]">{error}</div>)}</div> : null}
                </div>;
              })}
              {!displayStages.length ? <div className="rounded-[1.5rem] border border-[var(--txf-color-border)] bg-[var(--txf-color-surface-muted)] p-4 text-sm text-[var(--txf-color-text-subtle)]">{t('ingestion.no_steps')}</div> : null}
            </div> : <div className="mt-5 rounded-[1.5rem] border border-[var(--txf-color-border)] bg-[var(--txf-color-surface-muted)] p-4 text-sm text-[var(--txf-color-text-subtle)]">{t('ingestion.job.no_active')}</div>}
          </div>
      </div>
    </div>
  </section>;
}
