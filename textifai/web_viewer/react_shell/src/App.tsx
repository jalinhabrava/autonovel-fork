import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Database,
  Eye,
  FileText,
  GitBranch,
  Inbox,
  MessageSquareText,
  Network,
  PenLine,
  Search,
  Settings,
  SplitSquareHorizontal,
  Upload,
} from 'lucide-react';
import {
  CanonEntity,
  IngestionConfig,
  IngestionJob,
  ProjectDetail,
  ProjectSummary,
  ReviewItem,
  fetchArtifacts,
  fetchGraph,
  fetchIngestionConfig,
  fetchIngestionJobs,
  fetchNote,
  fetchProjectDetail,
  fetchProjects,
  fetchReviewQueue,
} from './api';

type SectionId = 'hub' | 'ingest' | 'codex' | 'graph' | 'review' | 'editor' | 'story' | 'ask' | 'overview';

type ScreenConfig = {
  id: SectionId;
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
};

type DecisionItem = {
  id: string;
  title: string;
  severity: string;
  source: string;
  action: string;
  raw: ReviewItem;
};

const screens: ScreenConfig[] = [
  { id: 'hub', label: 'Project Hub', icon: BookOpen },
  { id: 'ingest', label: 'Ingestion', icon: Upload },
  { id: 'codex', label: 'Codex / VaERL', icon: Network },
  { id: 'graph', label: 'Graph', icon: GitBranch },
  { id: 'review', label: 'Review Queue', icon: Inbox },
  { id: 'editor', label: 'Editor', icon: PenLine },
  { id: 'story', label: 'Story Bible', icon: FileText },
  { id: 'ask', label: 'Ask Canon', icon: MessageSquareText },
];

const overviewCards: Array<{ id: SectionId; title: string; text: string; icon: ScreenConfig['icon'] }> = [
  { id: 'hub', title: '1. Project Hub', text: 'Open project bundle via manifest or future .txtfai package.', icon: Database },
  { id: 'ingest', title: '2. Ingestion Wizard', text: 'Create stable folder/artifact structure recognized by the webapp.', icon: Upload },
  { id: 'codex', title: '3. Codex / VaERL', text: 'Inspect semantic source of truth: entities, aliases, evidence, review state.', icon: Network },
  { id: 'graph', title: '4. Graph', text: 'Dedicated visual exploration of entities, relationships, evidence, and review state.', icon: GitBranch },
  { id: 'review', title: '5. Review Queue', text: 'Resolve warnings using explicit author decisions.', icon: Inbox },
  { id: 'editor', title: '6. Editor View', text: 'Inline AI revision grounded in VaERL, chapter state, canon, and voice.', icon: SplitSquareHorizontal },
  { id: 'story', title: '7. Story Bible', text: 'Markdown/wiki projection for author-facing knowledge management.', icon: FileText },
  { id: 'ask', title: '8. Ask Canon', text: 'Q&A layer with evidence, uncertainty, and citations.', icon: MessageSquareText },
];

function toDecisionItem(item: ReviewItem, index: number): DecisionItem {
  const source = item.source_entity || 'Unknown source';
  const target = item.target_entity || 'Unknown target';
  const severity = String(item.severity || 'low');
  const title = source && target ? `${source} / ${target}` : source || target || `Review item ${index + 1}`;
  return {
    id: `${title}-${index}`,
    title,
    severity,
    source: (item.evidence_refs || []).map((row) => row.chapter_id || row.pointer || 'n/a').slice(0, 2).join(', ') || 'Evidence not available',
    action: item.recommendation || item.review_type || 'Needs author decision',
    raw: item,
  };
}

function severityClass(level: string): string {
  const normalized = level.toLowerCase();
  if (normalized === 'high') return 'bg-red-100 text-red-700';
  if (normalized === 'medium') return 'bg-amber-100 text-amber-700';
  return 'bg-neutral-200 text-neutral-700';
}

function legacyUrl(view: 'graph' | 'notes' | 'canon', projectId: string): string {
  return `/index.html?embed=1&view=${encodeURIComponent(view)}&project=${encodeURIComponent(projectId)}`;
}

function Shell({ active, setActive, children }: { active: SectionId; setActive: (id: SectionId) => void; children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-neutral-100 text-neutral-900 p-4 md:p-6">
      <div className="mx-auto max-w-7xl rounded-3xl bg-white shadow-xl overflow-hidden border border-neutral-200">
        <header className="flex items-center justify-between border-b border-neutral-200 px-5 py-4 bg-neutral-50">
          <button type="button" onClick={() => setActive('overview')} className="text-left">
            <div className="text-xl font-bold tracking-tight">TextifAI</div>
            <div className="text-xs text-neutral-500">Narrative semantic engine · author-facing VaERL workspace</div>
          </button>
          <div className="flex items-center gap-2 text-xs">
            <StatusChip>Local project</StatusChip>
            <StatusChip>VaERL ready</StatusChip>
            <Settings size={18} className="text-neutral-500" />
          </div>
        </header>

        <div className="grid grid-cols-12 min-h-[760px]">
          <aside className="col-span-12 md:col-span-2 border-r border-neutral-200 bg-neutral-50 p-3">
            <SidebarNav active={active} setActive={setActive} />
            <div className="mt-6 rounded-2xl border border-dashed border-neutral-300 p-3 text-xs text-neutral-500">
              Global shell stays stable. Main content changes by module. Right inspector/drawer appears when a node, warning, chapter, or evidence item is selected.
            </div>
          </aside>

          <main className="col-span-12 md:col-span-10 bg-white">{children}</main>
        </div>
      </div>
    </div>
  );
}

function SidebarNav({ active, setActive }: { active: SectionId; setActive: (id: SectionId) => void }) {
  return (
    <nav className="space-y-1">
      {screens.map((screen) => {
        const Icon = screen.icon;
        const selected = active === screen.id;
        return (
          <button
            key={screen.id}
            onClick={() => setActive(screen.id)}
            className={`w-full flex items-center gap-2 rounded-2xl px-3 py-2 text-left text-sm transition ${selected ? 'bg-neutral-900 text-white' : 'hover:bg-neutral-200 text-neutral-700'}`}
          >
            <Icon size={16} />
            <span>{screen.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

function TopBar({ title, subtitle, actions }: { title: string; subtitle: string; actions?: React.ReactNode }) {
  return (
    <div className="border-b border-neutral-200 px-5 py-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        <p className="text-sm text-neutral-500 mt-1">{subtitle}</p>
      </div>
      <div className="flex flex-wrap gap-2">{actions}</div>
    </div>
  );
}

function Button({ children, variant = 'primary', disabled = false }: { children: React.ReactNode; variant?: 'primary' | 'secondary'; disabled?: boolean }) {
  return (
    <button
      disabled={disabled}
      className={`rounded-2xl px-4 py-2 text-sm font-medium ${variant === 'primary' ? 'bg-neutral-900 text-white' : 'bg-neutral-100 text-neutral-800 border border-neutral-200'} ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      {children}
    </button>
  );
}

function StatusChip({ children }: { children: React.ReactNode }) {
  return <span className="rounded-full bg-neutral-200 px-3 py-1">{children}</span>;
}

function Metric({ label, value, note }: { label: string; value: string | number; note: string }) {
  return (
    <div className="rounded-3xl border border-neutral-200 bg-white p-4 shadow-sm">
      <div className="text-xs uppercase tracking-wide text-neutral-500">{label}</div>
      <div className="mt-2 text-2xl font-bold">{value}</div>
      <div className="mt-1 text-xs text-neutral-500">{note}</div>
    </div>
  );
}

function ProjectRow({ project, onSelect }: { project: ProjectSummary; onSelect: () => void }) {
  return (
    <button onClick={onSelect} className="w-full rounded-2xl bg-white border border-neutral-200 p-4 grid grid-cols-12 gap-3 items-center text-left">
      <div className="col-span-12 md:col-span-5">
        <div className="font-semibold">{project.work?.title || project.name}</div>
        <div className="text-xs text-neutral-500">Kind: {project.kind || 'project'}</div>
      </div>
      <div className="col-span-4 md:col-span-2 text-sm">{project.chapter_count || 0} chapters</div>
      <div className="col-span-4 md:col-span-2 text-sm">{project.entity_count || 0} entities</div>
      <div className="col-span-4 md:col-span-2 text-sm">{project.review_queue_count ?? 0} warnings</div>
      <div className="col-span-12 md:col-span-1 flex md:justify-end"><Eye size={18} /></div>
    </button>
  );
}

function DecisionCard({ item, onSelect }: { item: DecisionItem; onSelect: () => void }) {
  return (
    <button onClick={onSelect} className="w-full rounded-3xl border border-neutral-200 p-5 bg-white shadow-sm text-left">
      <div className="flex items-start justify-between gap-4">
        <h3 className="font-semibold text-base">{item.title}</h3>
        <span className={`text-xs px-2 py-1 rounded-full ${severityClass(item.severity)}`}>{item.severity}</span>
      </div>
      <p className="mt-2 text-sm text-neutral-600">Source: {item.source}</p>
      <p className="mt-2 text-sm">Action: {item.action}</p>
      <div className="mt-4 flex gap-2 flex-wrap">
        <Button variant="secondary">Open evidence</Button>
        <Button variant="secondary" disabled>Accept</Button>
        <Button variant="secondary" disabled>Reject</Button>
        <Button variant="secondary" disabled>Merge</Button>
      </div>
    </button>
  );
}

function EntityRecordTable({ entities, selectedKey, onSelect }: { entities: CanonEntity[]; selectedKey: string; onSelect: (key: string) => void }) {
  return (
    <div className="rounded-3xl border border-neutral-200 overflow-hidden">
      <div className="grid grid-cols-12 bg-neutral-100 px-4 py-3 text-xs uppercase tracking-wide text-neutral-500">
        <div className="col-span-4">Entity</div>
        <div className="col-span-2">Type</div>
        <div className="col-span-2">Confidence</div>
        <div className="col-span-2">Review</div>
        <div className="col-span-2">Aliases</div>
      </div>
      {entities.map((entity, index) => {
        const key = entity.preferred_slug || entity.canonical_name || String(index);
        const active = key === selectedKey;
        return (
          <button key={key} onClick={() => onSelect(key)} className={`w-full grid grid-cols-12 px-4 py-3 text-sm border-t border-neutral-200 items-center text-left ${active ? 'bg-neutral-50' : 'bg-white hover:bg-neutral-50'}`}>
            <div className="col-span-4 font-medium">{entity.canonical_name || entity.preferred_slug || 'Unknown'}</div>
            <div className="col-span-2">{entity.entity_kind || '—'}</div>
            <div className="col-span-2">{entity.confidence ?? '—'}</div>
            <div className="col-span-2">{entity.review_state || '—'}</div>
            <div className="col-span-2 truncate">{(entity.aliases || []).slice(0, 1).join(', ') || '—'}</div>
          </button>
        );
      })}
    </div>
  );
}

function InspectorCard({ entity }: { entity: CanonEntity | null }) {
  return (
    <div className="rounded-3xl border border-neutral-200 p-5 bg-neutral-50">
      <h2 className="font-semibold">Inspector</h2>
      {entity ? (
        <div className="mt-4 space-y-3 text-sm">
          <div className="rounded-2xl bg-white border border-neutral-200 p-3"><b>Name:</b> {entity.canonical_name || entity.preferred_slug || 'Unknown'}</div>
          <div className="rounded-2xl bg-white border border-neutral-200 p-3"><b>Summary:</b> {entity.summary || 'No summary available yet.'}</div>
          <div className="rounded-2xl bg-white border border-neutral-200 p-3"><b>Aliases:</b> {(entity.aliases || []).join(', ') || '—'}</div>
          <div className="rounded-2xl bg-white border border-neutral-200 p-3"><b>Relationships:</b> {(entity.relationships || []).length}</div>
          <div className="rounded-2xl bg-white border border-neutral-200 p-3"><b>Evidence refs:</b> {(entity.evidence_refs || []).length}</div>
        </div>
      ) : (
        <p className="mt-3 text-sm text-neutral-500">Select a record to inspect details.</p>
      )}
    </div>
  );
}

function LegacyEmbed({ title, src }: { title: string; src: string }) {
  return (
    <div className="rounded-3xl border border-neutral-200 bg-white shadow-sm overflow-hidden">
      <div className="border-b border-neutral-200 bg-neutral-50 px-4 py-2 text-sm text-neutral-600">{title}</div>
      <iframe title={title} src={src} className="h-[560px] w-full" />
    </div>
  );
}

function OverviewBoard({ setActive }: { setActive: (id: SectionId) => void }) {
  return (
    <section>
      <TopBar title="Main TextifAI wireframes" subtitle="Clickable low-fidelity product map for Codex implementation planning." actions={<Button>Use as implementation reference</Button>} />
      <div className="p-5 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        {overviewCards.map((card) => {
          const Icon = card.icon;
          return (
            <button key={card.id} onClick={() => setActive(card.id)} className="rounded-3xl border border-neutral-200 p-5 text-left bg-neutral-50 hover:bg-white hover:shadow-md transition min-h-44">
              <div className="flex items-center gap-3"><div className="rounded-2xl bg-neutral-900 text-white p-3"><Icon size={20} /></div><h2 className="font-bold text-lg">{card.title}</h2></div>
              <p className="mt-4 text-sm text-neutral-600 leading-6">{card.text}</p>
              <div className="mt-4 text-xs text-neutral-500">Click to inspect screen wireframe</div>
            </button>
          );
        })}
      </div>
    </section>
  );
}

export function App() {
  const [active, setActive] = useState<SectionId>('hub');
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [projectDetail, setProjectDetail] = useState<ProjectDetail | null>(null);
  const [selectedEntityKey, setSelectedEntityKey] = useState<string>('');
  const [selectedDecisionId, setSelectedDecisionId] = useState<string>('');
  const [reviewQuery, setReviewQuery] = useState('');
  const [reviewSeverity, setReviewSeverity] = useState('all');
  const [editorNotePath, setEditorNotePath] = useState('');
  const [editorMarkdown, setEditorMarkdown] = useState('');
  const [ingestionConfig, setIngestionConfig] = useState<IngestionConfig | null>(null);
  const [ingestionJobs, setIngestionJobs] = useState<IngestionJob[]>([]);
  const [artifactsCount, setArtifactsCount] = useState<number>(0);
  const [graphStats, setGraphStats] = useState<{ nodes: number; edges: number }>({ nodes: 0, edges: 0 });
  const [error, setError] = useState<string>('');

  const selectedProject = useMemo(() => projects.find((item) => item.project_id === selectedProjectId) || null, [projects, selectedProjectId]);
  const entities = projectDetail?.canon?.primaries || [];
  const selectedEntity = useMemo(() => entities.find((item) => (item.preferred_slug || item.canonical_name || '') === selectedEntityKey) || entities[0] || null, [entities, selectedEntityKey]);

  const allDecisions = useMemo(() => (projectDetail?.canon?.review_queue?.items || []).map(toDecisionItem), [projectDetail]);
  const visibleDecisions = useMemo(() => {
    const query = reviewQuery.trim().toLowerCase();
    return allDecisions.filter((item) => {
      if (reviewSeverity !== 'all' && item.severity.toLowerCase() !== reviewSeverity) return false;
      if (!query) return true;
      return item.title.toLowerCase().includes(query)
        || item.action.toLowerCase().includes(query)
        || String(item.raw.review_type || '').toLowerCase().includes(query);
    });
  }, [allDecisions, reviewQuery, reviewSeverity]);

  const selectedDecision = useMemo(() => visibleDecisions.find((item) => item.id === selectedDecisionId) || visibleDecisions[0] || null, [visibleDecisions, selectedDecisionId]);

  useEffect(() => {
    void loadInitial();
  }, []);

  useEffect(() => {
    if (!selectedProjectId) return;
    void loadProjectContext(selectedProjectId);
  }, [selectedProjectId]);

  useEffect(() => {
    if (!selectedProjectId || !editorNotePath) return;
    void loadEditorNote(selectedProjectId, editorNotePath);
  }, [selectedProjectId, editorNotePath]);

  async function loadInitial() {
    try {
      const [projectList, config, jobs] = await Promise.all([fetchProjects(), fetchIngestionConfig(), fetchIngestionJobs()]);
      setProjects(projectList);
      setIngestionConfig(config);
      setIngestionJobs(jobs);
      if (projectList.length) setSelectedProjectId(projectList[0].project_id);
    } catch (err) {
      setError(String(err));
    }
  }

  async function loadProjectContext(projectId: string) {
    try {
      const [detail, graph, reviewQueue, artifacts] = await Promise.all([
        fetchProjectDetail(projectId),
        fetchGraph(projectId),
        fetchReviewQueue(projectId),
        fetchArtifacts(projectId),
      ]);
      setProjectDetail({ ...detail, canon: { ...detail.canon, review_queue: reviewQueue } });
      setGraphStats({ nodes: (graph?.nodes || []).length, edges: (graph?.edges || []).length });
      setArtifactsCount((artifacts.artifacts || []).length);
      const firstEntity = detail.canon?.primaries?.[0];
      if (firstEntity) setSelectedEntityKey(firstEntity.preferred_slug || firstEntity.canonical_name || '');
      const firstChapter = detail.notes?.find((note) => String(note.kind || '').toLowerCase() === 'chapter') || detail.notes?.[0];
      if (firstChapter?.path) setEditorNotePath(firstChapter.path);
    } catch (err) {
      setError(String(err));
    }
  }

  async function loadEditorNote(projectId: string, notePath: string) {
    try {
      const payload = await fetchNote(projectId, notePath);
      setEditorMarkdown(String(payload.markdown || 'No note content available.'));
    } catch (_err) {
      setEditorMarkdown('No note content available.');
    }
  }

  const warningsVisible = visibleDecisions.length;

  let content: React.ReactNode = null;

  if (active === 'overview') {
    content = <OverviewBoard setActive={setActive} />;
  }

  if (active === 'hub') {
    content = (
      <section>
        <TopBar
          title="Project Hub"
          subtitle="Start here: create, open, validate, or resume a TextifAI project bundle."
          actions={<><Button>New ingestion</Button><Button variant="secondary">Open .txtfai / manifest</Button></>}
        />
        <div className="p-5 grid grid-cols-12 gap-5">
          <div className="col-span-12 lg:col-span-8 space-y-4">
            <div className="rounded-3xl border border-neutral-200 p-5 bg-neutral-50">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-lg">Recent projects</h2>
                  <p className="text-sm text-neutral-500">Real projects loaded from /api/projects. Contract target remains manifest.json and future .txtfai package.</p>
                </div>
                <Search size={18} className="text-neutral-500" />
              </div>
              <div className="mt-4 space-y-3">
                {projects.map((project) => (
                  <ProjectRow key={project.project_id} project={project} onSelect={() => setSelectedProjectId(project.project_id)} />
                ))}
              </div>
            </div>
          </div>
          <aside className="col-span-12 lg:col-span-4 space-y-4">
            <Metric label="Project contract" value="manifest.json" note="One canonical file opens the whole bundle." />
            <Metric label="Recommended future" value=".txtfai" note="A packaged project format can wrap manifest and vault." />
            <div className="rounded-3xl border border-neutral-200 p-5">
              <h3 className="font-semibold">Project health</h3>
              <div className="mt-4 space-y-3 text-sm">
                <div className="flex items-center gap-2"><CheckCircle2 size={16} /> Chapters indexed: {projectDetail?.overview?.chapters_processed ?? 0}</div>
                <div className="flex items-center gap-2"><CheckCircle2 size={16} /> Artifacts discovered: {artifactsCount}</div>
                <div className="flex items-center gap-2"><AlertTriangle size={16} /> Pending warnings: {warningsVisible}</div>
                <div className="flex items-center gap-2"><CheckCircle2 size={16} /> Story bible detected: {selectedProject?.has_markdown_manifest ? 'yes' : 'no'}</div>
              </div>
            </div>
          </aside>
        </div>
      </section>
    );
  }

  if (active === 'ingest') {
    content = (
      <section>
        <TopBar
          title="Ingestion"
          subtitle="Build and validate the project structure used by TextifAI modules and VaERL projections."
          actions={<><Button>Run ingestion</Button><Button variant="secondary">Open output contract</Button></>}
        />
        <div className="p-5 grid grid-cols-12 gap-5">
          <div className="col-span-12 lg:col-span-7 rounded-3xl border border-neutral-200 p-5 bg-neutral-50">
            <h2 className="font-semibold">Source setup and pipeline preview</h2>
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
              <div className="rounded-2xl bg-white border border-neutral-200 p-3"><b>Mode</b><br />{ingestionConfig?.mode || 'n/a'}</div>
              <div className="rounded-2xl bg-white border border-neutral-200 p-3"><b>Input mode</b><br />{ingestionConfig?.supported_input_mode || 'n/a'}</div>
              <div className="rounded-2xl bg-white border border-neutral-200 p-3"><b>Can execute</b><br />{String(Boolean(ingestionConfig?.can_execute))}</div>
              <div className="rounded-2xl bg-white border border-neutral-200 p-3"><b>Output root</b><br />{ingestionConfig?.default_output_root || 'n/a'}</div>
            </div>
            <div className="mt-4 rounded-2xl border border-neutral-200 bg-white p-3 text-sm text-neutral-600">
              {ingestionConfig?.local_only_warning || 'Ingestion contract loaded from backend.'}
            </div>
            <ul className="mt-4 list-disc pl-5 text-xs text-neutral-600 space-y-1">
              {(ingestionConfig?.safety_notes || []).slice(0, 6).map((note) => <li key={note}>{note}</li>)}
            </ul>
          </div>
          <aside className="col-span-12 lg:col-span-5 space-y-4">
            <Metric label="Recent jobs" value={ingestionJobs.length} note="Loaded from /api/ingestion/jobs." />
            <div className="rounded-3xl border border-neutral-200 p-5">
              <h3 className="font-semibold">Recent job activity</h3>
              <div className="mt-4 space-y-2 text-sm">
                {ingestionJobs.slice(0, 8).map((job) => (
                  <div key={job.job_id || Math.random()} className="rounded-2xl bg-neutral-50 border border-neutral-200 p-3">
                    <div className="font-medium">{job.project_title || job.run_name || job.job_id}</div>
                    <div className="text-xs text-neutral-500">{job.status || 'unknown'} · {job.created_at || ''}</div>
                  </div>
                ))}
              </div>
            </div>
          </aside>
        </div>
      </section>
    );
  }

  if (active === 'codex') {
    content = (
      <section>
        <TopBar title="Codex / VaERL" subtitle="Structured semantic records over real TextifAI payloads." actions={<><Button>Open selected in graph</Button><Button variant="secondary">Compare aliases</Button></>} />
        <div className="p-5 grid grid-cols-12 gap-5">
          <div className="col-span-12 lg:col-span-8">
            <EntityRecordTable entities={entities} selectedKey={selectedEntityKey || (selectedEntity?.preferred_slug || selectedEntity?.canonical_name || '')} onSelect={setSelectedEntityKey} />
          </div>
          <aside className="col-span-12 lg:col-span-4">
            <InspectorCard entity={selectedEntity} />
          </aside>
        </div>
      </section>
    );
  }

  if (active === 'graph') {
    content = (
      <section>
        <TopBar title="Graph" subtitle="Dedicated visual exploration for entities, relationships, review markers, and chapter context." actions={<><Button>Open selected entity</Button><Button variant="secondary">Filter by chapter</Button></>} />
        <div className="p-5 grid grid-cols-12 gap-5">
          <div className="col-span-12 lg:col-span-8">
            {selectedProjectId ? <LegacyEmbed title="Graph module (legacy runtime boundary)" src={legacyUrl('graph', selectedProjectId)} /> : <div className="rounded-3xl border border-neutral-200 p-5 text-sm text-neutral-500">Select a project to open Graph.</div>}
          </div>
          <aside className="col-span-12 lg:col-span-4 space-y-4">
            <Metric label="Visible nodes" value={graphStats.nodes} note="Real graph payload count." />
            <Metric label="Visible edges" value={graphStats.edges} note="Real graph payload count." />
            <div className="rounded-3xl border border-neutral-200 p-5 bg-neutral-50">
              <h3 className="font-semibold">Filters and inspector</h3>
              <p className="mt-2 text-sm text-neutral-600">This phase preserves legacy graph renderer while keeping target shell as primary experience.</p>
            </div>
          </aside>
        </div>
      </section>
    );
  }

  if (active === 'review') {
    content = (
      <section>
        <TopBar title="Review Queue" subtitle="Review warnings using explicit author decisions over real review queue payloads." actions={<><Button>Export decisions</Button><Button variant="secondary">Open audit context</Button></>} />
        <div className="p-5 grid grid-cols-12 gap-5">
          <div className="col-span-12 lg:col-span-7 space-y-4">
            <div className="rounded-3xl border border-neutral-200 p-5 bg-neutral-50">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <h2 className="font-semibold">Pending decisions</h2>
                <span className="rounded-full bg-neutral-200 px-3 py-1 text-xs">Visible queue: {visibleDecisions.length}</span>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <input value={reviewQuery} onChange={(event) => setReviewQuery(event.target.value)} className="rounded-2xl border border-neutral-300 px-4 py-2 text-sm" placeholder="Search review items..." />
                <select value={reviewSeverity} onChange={(event) => setReviewSeverity(event.target.value)} className="rounded-2xl border border-neutral-300 px-4 py-2 text-sm">
                  <option value="all">All severities</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
            </div>
            {visibleDecisions.map((item) => (
              <DecisionCard key={item.id} item={item} onSelect={() => setSelectedDecisionId(item.id)} />
            ))}
            {!visibleDecisions.length ? <div className="rounded-3xl border border-neutral-200 p-5 text-sm text-neutral-500">No decisions match current filter.</div> : null}
          </div>
          <aside className="col-span-12 lg:col-span-5 space-y-4">
            <Metric label="Pending warnings" value={visibleDecisions.length} note="Derived from visible queue filter." />
            <Metric label="Decision model" value="Explicit" note="No silent canon changes." />
            <div className="rounded-3xl border border-neutral-200 p-5 bg-neutral-50">
              <h3 className="font-semibold">Decision drawer</h3>
              {selectedDecision ? (
                <div className="mt-3 space-y-2 text-sm">
                  <p><b>{selectedDecision.title}</b></p>
                  <p className="text-neutral-600">{selectedDecision.action}</p>
                  <p className="text-neutral-600">Source: {selectedDecision.source}</p>
                  <div className="pt-2 flex gap-2 flex-wrap">
                    <Button variant="secondary" disabled>accept</Button>
                    <Button variant="secondary" disabled>reject</Button>
                    <Button variant="secondary" disabled>merge</Button>
                    <Button variant="secondary" disabled>edit canonical label</Button>
                  </div>
                </div>
              ) : <p className="text-sm text-neutral-500 mt-2">Select a decision card.</p>}
            </div>
          </aside>
        </div>
      </section>
    );
  }

  if (active === 'editor') {
    content = (
      <section>
        <TopBar title="Editor View" subtitle="Write and revise with grounded context. The LLM proposes changes; author keeps control." actions={<><Button variant="secondary">Rewrite selection</Button><Button variant="secondary">Open chapter context</Button></>} />
        <div className="p-5 grid grid-cols-12 gap-5">
          <aside className="col-span-12 lg:col-span-3 rounded-3xl border border-neutral-200 bg-neutral-50 p-4">
            <h2 className="font-semibold">Chapters</h2>
            <div className="mt-4 space-y-2 text-sm">
              {(projectDetail?.notes || []).slice(0, 16).map((note) => (
                <button key={note.path} onClick={() => setEditorNotePath(note.path)} className={`w-full rounded-xl border px-3 py-2 text-left ${editorNotePath === note.path ? 'bg-neutral-900 text-white border-neutral-900' : 'bg-white border-neutral-200'}`}>
                  {note.name || note.path}
                </button>
              ))}
            </div>
          </aside>
          <div className="col-span-12 lg:col-span-6 rounded-3xl border border-neutral-200 p-5 min-h-[560px]">
            <div className="text-xs uppercase text-neutral-500">Editor preview · real note payload</div>
            <h2 className="font-bold text-xl mt-1">{editorNotePath || 'Select note'}</h2>
            <pre className="mt-5 whitespace-pre-wrap rounded-2xl bg-neutral-50 p-4 border border-neutral-200 text-sm leading-7 max-h-[470px] overflow-auto">{editorMarkdown || 'No note selected.'}</pre>
          </div>
          <aside className="col-span-12 lg:col-span-3 rounded-3xl border border-neutral-200 bg-neutral-50 p-5">
            <h2 className="font-semibold">Context panel</h2>
            <div className="mt-4 space-y-3 text-sm">
              <div className="rounded-2xl bg-white border border-neutral-200 p-3"><b>Active entities</b><br />{(entities || []).slice(0, 4).map((row) => row.canonical_name || row.preferred_slug).filter(Boolean).join(', ') || 'n/a'}</div>
              <div className="rounded-2xl bg-white border border-neutral-200 p-3"><b>Voice constraints</b><br />Placeholder contract for future grounded rewriting.</div>
              <div className="rounded-2xl bg-white border border-neutral-200 p-3"><b>Canon risks</b><br />No fake persistence. No write-back in this phase.</div>
            </div>
          </aside>
        </div>
      </section>
    );
  }

  if (active === 'story') {
    content = (
      <section>
        <TopBar title="Story Bible" subtitle="Author-readable Markdown knowledge base generated from VaERL with preserved provenance." actions={<><Button variant="secondary">Sync Markdown</Button><Button variant="secondary">Open graph side-by-side</Button></>} />
        <div className="p-5 grid grid-cols-12 gap-5">
          <aside className="col-span-12 lg:col-span-3 rounded-3xl border border-neutral-200 bg-neutral-50 p-4">
            <h2 className="font-semibold">Vault tree</h2>
            <div className="mt-4 space-y-2 text-sm">
              {(projectDetail?.notes || []).slice(0, 16).map((note) => <div key={note.path} className="rounded-xl bg-white border border-neutral-200 px-3 py-2">{note.name || note.path}</div>)}
            </div>
          </aside>
          <div className="col-span-12 lg:col-span-9">
            {selectedProjectId ? <LegacyEmbed title="Story Bible module (legacy runtime boundary)" src={legacyUrl('notes', selectedProjectId)} /> : <div className="rounded-3xl border border-neutral-200 p-5 text-sm text-neutral-500">Select a project to open Story Bible.</div>}
          </div>
        </div>
      </section>
    );
  }

  if (active === 'ask') {
    content = (
      <section>
        <TopBar title="Ask Canon" subtitle="Q&A shell grounded in VaERL, evidence, and review state." actions={<><Button variant="secondary">Open answer history</Button><Button variant="secondary">Check source coverage</Button></>} />
        <div className="p-5 grid grid-cols-12 gap-5">
          <div className="col-span-12 lg:col-span-7 rounded-3xl border border-neutral-200 p-5 min-h-[560px] flex flex-col">
            <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4 text-sm text-neutral-500">Ask: “What does Sera know about Kyōmei before chapter 6?”</div>
            <div className="mt-5 rounded-3xl border border-neutral-200 p-5 bg-white shadow-sm">
              <div className="font-semibold">Grounded answer</div>
              <p className="mt-3 text-sm leading-7">Placeholder shell only. This phase does not implement answer generation. Future answers must cite evidence, uncertainty, and review state from real data.</p>
              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                <div className="rounded-2xl bg-neutral-50 border border-neutral-200 p-3">Evidence: pending query layer</div>
                <div className="rounded-2xl bg-neutral-50 border border-neutral-200 p-3">Uncertainty: pending query layer</div>
              </div>
            </div>
            <div className="mt-auto pt-5 flex gap-2"><input className="flex-1 rounded-2xl border border-neutral-300 px-4 py-3 text-sm" placeholder="Ask about canon, continuity, entities, or chapter state..." /><Button variant="secondary" disabled>Send</Button></div>
          </div>
          <aside className="col-span-12 lg:col-span-5 space-y-4">
            <Metric label="Grounding mode" value="Evidence-first" note="No unsupported canon claims." />
            <div className="rounded-3xl border border-neutral-200 p-5 bg-neutral-50">
              <h2 className="font-semibold">Useful query templates</h2>
              <div className="mt-4 space-y-2 text-sm">
                {['What changed between chapters 3 and 4?', 'Which facts about Ren are uncertain?', 'Find contradictions involving Kyōmei.', 'What can Nael know at this point?'].map((question) => <div key={question} className="rounded-xl bg-white border border-neutral-200 px-3 py-2">{question}</div>)}
              </div>
            </div>
          </aside>
        </div>
      </section>
    );
  }

  return (
    <Shell active={active} setActive={setActive}>
      <motion.div key={active} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.18 }}>
        {content}
      </motion.div>
      {error ? <div className="mx-5 mb-5 rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
    </Shell>
  );
}
