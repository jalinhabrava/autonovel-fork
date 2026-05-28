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
};

export type ReviewItem = {
  source_entity?: string;
  target_entity?: string;
  severity?: string;
  recommendation?: string;
  review_type?: string;
  evidence_refs?: Array<{ chapter_id?: string; pointer?: string }>;
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
      counts_by_severity?: Record<string, number>;
      counts_by_type?: Record<string, number>;
    };
  };
  notes?: Array<{ path: string; name?: string; kind?: string; role?: string; status?: string }>;
  graph?: GraphPayload;
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
  created_at?: string;
};

async function api<T>(path: string): Promise<T> {
  const response = await fetch(path, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

export async function fetchProjects(): Promise<ProjectSummary[]> {
  const payload = await api<{ projects?: ProjectSummary[] }>('/api/projects');
  return payload.projects || [];
}

export async function fetchProjectDetail(projectId: string): Promise<ProjectDetail> {
  return api<ProjectDetail>(`/api/projects/${encodeURIComponent(projectId)}`);
}

export async function fetchGraph(projectId: string): Promise<GraphPayload> {
  return api<GraphPayload>(`/api/projects/${encodeURIComponent(projectId)}/graph`);
}

export async function fetchReviewQueue(projectId: string): Promise<NonNullable<ProjectDetail['canon']>['review_queue']> {
  const detail = await fetchProjectDetail(projectId);
  return detail.canon?.review_queue || { item_count: 0, items: [] };
}

export async function fetchNote(projectId: string, path: string): Promise<{ markdown?: string }> {
  return api<{ markdown?: string }>(`/api/projects/${encodeURIComponent(projectId)}/note?path=${encodeURIComponent(path)}`);
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
