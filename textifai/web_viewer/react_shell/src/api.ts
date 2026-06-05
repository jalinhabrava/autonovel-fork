export type ProjectSummary = {
  project_id: string;
  name: string;
  kind?: string;
  chapter_count?: number;
  entity_count?: number;
  review_queue_count?: number | null;
  review_count?: number | null;
  primary_count?: number | null;
  work?: { title?: string; language?: string };
  has_ingestion_graph?: boolean;
  has_markdown_manifest?: boolean;
  has_markdown_graph_index?: boolean;
  recommended?: boolean;
  graph_summary?: {
    node_count?: number;
    edge_count?: number;
    node_counts_by_kind?: Record<string, number>;
  };
  ingestion_policy?: {
    allow_auto_retries?: boolean;
    max_retries_per_chapter?: number;
    retry_only_technical_failures?: boolean;
    ask_before_extra_costly_retry?: boolean;
  };
  workspace_status?: {
    chapters_detected_label?: string;
    chapters_ready_label?: string;
    chapters_retried_label?: string;
    chapters_still_failed_label?: string;
    semantic_review_label?: string;
    retry_cta?: string;
    review_cta?: string;
  };
};

export type ReviewItem = {
  id?: string;
  type?: string;
  title?: string;
  subtitle?: string;
  source_entity?: string;
  target_label?: string;
  target_entity?: string | { label?: string };
  severity?: string;
  recommendation?: string;
  review_type?: string;
  suggested_action?: string;
  human_reason?: string;
  evidence_summary?: string;
  local_state?: string;
  evidence_refs?: Array<{ chapter_id?: string; chapter_label?: string; pointer?: string; pointer_short?: string; excerpt?: string | null; char_start?: number; char_end?: number; has_text?: boolean; reason?: string | null }>;
  technical_details?: Record<string, unknown>;
  impact_if_accept?: string;
  impact_if_reject?: string;
};

export type CanonEntity = {
  canonical_name?: string;
  preferred_slug?: string;
  entity_kind?: string;
  review_state?: string;
  confidence?: number;
  summary?: string;
  aliases?: string[];
  relationships?: Array<{ target?: string; type?: string; relation_type?: string }>;
  chapter_refs?: string[];
  key_facts?: string[];
  evidence_refs?: Array<{ chapter_id?: string; pointer?: string }>;
};

export type GraphNode = {
  id?: string;
  label?: string;
  kind?: string;
  display_kind?: string;
  role?: string;
  note_path?: string;
  canonical_note_path?: string;
  status?: string;
  review_state?: string;
  degree?: number;
  radius?: number;
  summary_excerpt?: string;
  relationship_count?: number;
  canonical_degree?: number;
  aliases?: string[];
  backlinks?: string[];
  outgoing_wikilinks?: Array<{ target?: string; label?: string }>;
  evidence_count?: number;
  review_count?: number;
  display_label?: string;
};

export type GraphEdge = {
  id?: string;
  source?: string;
  target?: string;
  type?: string;
  kind?: string;
  label?: string;
};

export type GraphPayload = { nodes?: GraphNode[]; edges?: GraphEdge[] };

export type ProjectDetail = {
  project: {
    project_id: string;
    name: string;
    kind?: string;
    root?: string;
    work?: { title?: string; language?: string };
  };
  overview?: {
    chapters_processed?: number;
    chapters_ready?: number;
    chapters_needing_retry?: number;
    chapters_needing_review?: number;
    warning_summary?: Array<{ message?: string; level?: string }>;
    node_counts_by_kind?: Record<string, number>;
    relationship_count?: number;
  };
  canon?: {
    primaries?: CanonEntity[];
    review_entities?: CanonEntity[];
    review_queue?: {
      item_count?: number;
      items?: ReviewItem[];
      decision_items?: ReviewItem[];
      decision_summary?: Record<string, number>;
      counts_by_severity?: Record<string, number>;
      counts_by_type?: Record<string, number>;
    };
  };
  notes?: Array<{ path: string; name?: string; kind?: string; role?: string; status?: string }>;
  graph?: GraphPayload;
  ingestion_policy?: {
    allow_auto_retries?: boolean;
    max_retries_per_chapter?: number;
    retry_only_technical_failures?: boolean;
    ask_before_extra_costly_retry?: boolean;
  };
  workspace_status?: {
    chapters_detected_label?: string;
    chapters_ready_label?: string;
    chapters_retried_label?: string;
    chapters_still_failed_label?: string;
    semantic_review_label?: string;
    retry_cta?: string;
    review_cta?: string;
  };
  run_status?: {
    schema?: string;
    schema_version?: number;
    run_id?: string;
    status?: string;
    safe_to_open_workspace?: boolean;
    steps?: Array<{ id?: string; label?: string; status?: string; progress?: number }>;
    last_artifact?: string;
    final_state_detail?: string;
  };
};

export type IngestionConfig = {
  mode?: string;
  supported_input_mode?: string;
  can_execute?: boolean;
  can_upload?: boolean;
  default_output_root?: string;
  local_only_warning?: string;
  safety_notes?: string[];
};

export type IngestionJob = {
  job_id?: string;
  status?: string;
  run_name?: string;
  project_title?: string;
  display_label?: string;
  created_at?: string;
  input_mode?: string;
  upload_session_id?: string | null;
  project_id?: string | null;
  stage_status?: IngestionStageStatusSnapshot;
  result_status?: string;
  result_summary?: string;
  semantic_status?: string;
  semantic_artifact_counts?: {
    entities?: number;
    relationships?: number;
    graph_nodes?: number;
    graph_edges?: number;
    review_items?: number;
  };
  error?: string | null;
};

export type UploadedIngestionFile = {
  file_id: string;
  filename: string;
  size_bytes: number;
  content_type?: string;
  status: 'staged' | 'rejected';
  error?: string;
};

export type IngestionUploadResponse = {
  upload_session_id: string;
  files: UploadedIngestionFile[];
  created_at?: string;
};

export type IngestionStageStatus = 'pending' | 'running' | 'completed' | 'warning' | 'blocked' | 'failed' | 'skipped';

export type IngestionStage = {
  id: string;
  label: string;
  status: IngestionStageStatus;
  progress?: number;
  summary?: string;
  message?: string;
  warnings?: unknown[];
  errors?: unknown[];
  actions?: string[];
};

export type IngestionStageStatusSnapshot = {
  schema: string;
  global_status?: string;
  current_stage_id?: string;
  project_ready?: boolean;
  progress?: number | null;
  stages?: IngestionStage[];
};


export type ChapterReanalysisResponse = {
  ok?: boolean;
  status?: 'queued' | 'not_implemented';
  chapter_id?: string;
  semantic_state?: string;
  message?: string;
};

export type ChapterSaveResponse = {
  ok?: boolean;
  error?: string;
  chapter_id?: string;
  current_hash?: string;
  expected_hash?: string;
  old_hash?: string;
  new_hash?: string;
  backup_path?: string;
  semantic_state?: string;
  dirty_state?: boolean;
  saved_at?: string;
  warning?: string;
  message?: string;
};

export type EntityFicheSaveResponse = {
  ok?: boolean;
  error?: string;
  entity_id?: string;
  canonical_label?: string;
  current_hash?: string;
  expected_hash?: string;
  old_hash?: string;
  new_hash?: string;
  backup_path?: string;
  semantic_state?: string;
  dirty_state?: boolean;
  saved_at?: string;
  warning?: string;
  message?: string;
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { cache: 'no-store', ...init });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw Object.assign(new Error(`${response.status} ${response.statusText}`), { payload, status: response.status });
  }
  return payload;
}

async function apiPost<T>(path: string, body: object): Promise<T> {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    cache: 'no-store',
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw Object.assign(new Error(`${response.status} ${response.statusText}`), { payload, status: response.status });
  }
  return payload;
}


export type EntityCard = {
  schema?: string;
  schema_version?: number;
  id?: string;
  canonical_label?: string;
  display_label?: string;
  kind?: string;
  status?: string;
  summary?: string;
  degree?: number;
  relation_count?: number;
  evidence_count?: number;
  aliases?: {
    canonical?: string[];
    contextual?: string[];
    needs_review?: string[];
    suppressed?: string[];
  };
  relationships?: Array<{
    source?: string;
    predicate?: string;
    target?: string;
    kind?: string;
    evidence_count?: number;
    review_state?: string;
  }>;
  backlinks?: string[];
  outgoing_links?: Array<{ label?: string }>;
  local_graph?: { node_count?: number; edge_count?: number };
  review?: { count?: number; items?: ReviewItem[] };
  markdown?: {
    note_path?: string;
    sections?: Array<{ title?: string; body?: string }>;
    author_markdown?: string;
    technical_markdown?: string;
  };
  evidence_refs?: Array<{ chapter_id?: string; pointer?: string }>;
  technical?: Record<string, unknown>;
};

export async function fetchEntityCard(projectId: string, params: { node_id?: string; note_path?: string; canonical_label?: string }): Promise<EntityCard> {
  const q = new URLSearchParams();
  if (params.node_id) q.set('node_id', params.node_id);
  if (params.note_path) q.set('note_path', params.note_path);
  if (params.canonical_label) q.set('canonical_label', params.canonical_label);
  return api<EntityCard>(`/api/projects/${encodeURIComponent(projectId)}/entity-card?${q.toString()}`);
}

export async function fetchProjects(): Promise<ProjectSummary[]> {
  const payload = await api<{ projects?: ProjectSummary[] }>('/api/projects');
  return payload.projects || [];
}

export async function fetchProjectDetail(projectId: string): Promise<ProjectDetail> {
  return api<ProjectDetail>(`/api/projects/${encodeURIComponent(projectId)}`);
}

export async function removeProject(projectId: string): Promise<{ ok?: boolean; project_id?: string }> {
  return api<{ ok?: boolean; project_id?: string }>(`/api/projects/${encodeURIComponent(projectId)}`, { method: 'DELETE' });
}

export async function fetchGraph(projectId: string): Promise<GraphPayload> {
  return api<GraphPayload>(`/api/projects/${encodeURIComponent(projectId)}/graph`);
}

export async function fetchReviewQueue(projectId: string): Promise<NonNullable<ProjectDetail['canon']>['review_queue']> {
  const detail = await fetchProjectDetail(projectId);
  return detail.canon?.review_queue || { item_count: 0, items: [] };
}

export type NoteDetail = {
  markdown?: string;
  backlinks?: string[];
  outgoing_wikilinks?: Array<{ target?: string; label?: string }>;
  local_graph?: { nodes?: Array<{ id?: string; label?: string; kind?: string }>; edges?: Array<{ source?: string; target?: string; label?: string }> };
  summary_excerpt?: string;
  key_facts_count?: number;
  key_facts_preview?: string[];
  relationship_count?: number;
  evidence_count?: number;
  display_label?: string;
  display_kind?: string;
};

export async function fetchNote(projectId: string, path: string): Promise<NoteDetail> {
  return api<NoteDetail>(`/api/projects/${encodeURIComponent(projectId)}/note?path=${encodeURIComponent(path)}`);
}

export async function fetchArtifacts(projectId: string): Promise<{ artifacts?: Array<{ path?: string }> }> {
  return api<{ artifacts?: Array<{ path?: string }> }>(`/api/projects/${encodeURIComponent(projectId)}/artifacts`);
}

export async function fetchIngestionConfig(): Promise<IngestionConfig> {
  return api<IngestionConfig>('/api/ingestion/config');
}

export async function fetchIngestionJobs(): Promise<IngestionJob[]> {
  const payload = await api<{ jobs?: IngestionJob[] }>('/api/ingestion/jobs');
  return payload.jobs || [];
}

export async function uploadIngestionFiles(files: File[]): Promise<IngestionUploadResponse> {
  const body = new FormData();
  for (const file of files) body.append('file', file, file.name);
  return api<IngestionUploadResponse>('/api/ingestion/uploads', {
    method: 'POST',
    body,
  });
}

export async function fetchIngestionUploadSession(uploadSessionId: string): Promise<IngestionUploadResponse> {
  return api<IngestionUploadResponse>(`/api/ingestion/uploads?upload_session_id=${encodeURIComponent(uploadSessionId)}`);
}

export async function startIngestionJobFromUpload(payload: { upload_session_id: string; project_title: string; run_name?: string }): Promise<IngestionJob> {
  return apiPost<IngestionJob>('/api/ingestion/jobs', payload);
}

export async function fetchIngestionJob(jobId: string): Promise<IngestionJob> {
  return api<IngestionJob>(`/api/ingestion/jobs/${encodeURIComponent(jobId)}`);
}

export async function saveChapterMarkdown(projectId: string, chapterId: string, markdown: string, expectedHash: string, displayTitle?: string): Promise<ChapterSaveResponse> {
  return apiPost<ChapterSaveResponse>(`/api/projects/${encodeURIComponent(projectId)}/chapters/${encodeURIComponent(chapterId)}/save`, {
    markdown,
    expected_hash: expectedHash,
    display_title: displayTitle,
  });
}

export async function saveEntityFicheMarkdown(projectId: string, entityId: string, markdown: string, expectedHash: string, canonicalLabel?: string, notePath?: string): Promise<EntityFicheSaveResponse> {
  return apiPost<EntityFicheSaveResponse>(`/api/projects/${encodeURIComponent(projectId)}/entities/${encodeURIComponent(entityId)}/save`, {
    markdown,
    expected_hash: expectedHash,
    canonical_label: canonicalLabel,
    note_path: notePath,
  });
}

export async function requestChapterReanalysis(projectId: string, chapterId: string): Promise<ChapterReanalysisResponse> {
  return apiPost<ChapterReanalysisResponse>(`/api/projects/${encodeURIComponent(projectId)}/chapters/${encodeURIComponent(chapterId)}/reanalyze`, {});
}
