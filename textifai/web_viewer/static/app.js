const state = {
  projects: [],
  current: null,
  currentId: null,
  currentVisibleGraph: null,
  locale: "en",
  activeView: "overview",
  selectedGraphNodeId: null,
  graphAnimation: null,
  graphSimulation: null,
  graphViewBox: { x: 0, y: 0, width: 1200, height: 720 },
  graphPan: null,
  graphDidPan: false,
  graphDidDragNode: false,
  graphDrag: null,
  graphShowAllNodes: false,
  hiddenGraphTags: new Set(),
  wikiFilters: { query: "", kind: "", tag: "", status: "" },
  selectedCanonEntityKey: null,
  selectedReviewItemId: null,
  navNotice: null,
  viewerNavBack: [],
  viewerNavForward: [],
  viewerRecent: [],
  ingestionConfig: null,
  ingestionConfigError: "",
  ingestionWizard: {
    sourceRoot: "",
    projectTitle: "",
    runName: "",
    primaryLanguage: "",
    workingLanguages: "",
    skipPluginInstall: true,
    submitting: false,
    submitError: "",
    currentJobId: "",
    currentJob: null,
    recentJobs: [],
    historySummary: null,
    historyFilters: { status: "", mode: "", query: "", sortBy: "newest" },
    pollingTimer: null,
  },
  compareView: { baseId: "", candidateId: "", loading: false, result: null, error: "" },
  reviewView: { severity: "", reviewType: "", query: "", sortBy: "severity_desc", quickFilter: "all", candidate: "" },
  autoOpenedRecommendedProject: false,
};

const I18N = {
  en: {
    appTitle: "TextifAI Viewer",
    brandSubtitle: "Author knowledge workspace",
    refresh: "Refresh",
    currentProject: "Current project",
    selectProject: "Select project",
    readOnlyPreview: "Read-only preview",
    overview: "Overview",
    wiki: "Wiki",
    canon: "Canon",
    review: "Review",
    graph: "Graph",
    artifacts: "Technical details",
    projectPanelTitle: "Story workspace",
    projectPanelSubtitle: "Choose the narrative project to review.",
    active: "active",
    open: "Open",
    authorProject: "Author project",
    technicalArtifact: "Technical artifact",
    technicalDetails: "Technical details",
    chapters: "chapters",
    nodes: "nodes",
    edges: "edges",
    ready: "ready",
    needsReview: "review",
    retry: "retry",
    wikiSubtitle: "Read-only Markdown notes projected from VaERL.",
    searchNotes: "Search notes",
    allKinds: "All kinds",
    allTags: "All tags",
    allStatus: "All status",
    hideSystem: "Hide system",
    hideReview: "Hide review",
    hideChapters: "Hide chapters",
    localGraph: "Local graph",
    showAllNodes: "Show all nodes",
    resetLayout: "Reset layout",
    zoomIn: "Zoom +",
    zoomOut: "Zoom -",
    openInCanon: "Open in Canon",
    clearHiddenTags: "clear {count}",
    selectNode: "Select a node to inspect.",
    selectArtifact: "Select an artifact.",
    summary: "Bio / Summary",
    facts: "Key facts",
    storyRelationships: "Story relationships",
    appearancesEvidence: "Appearances / evidence",
    markdownLinks: "Markdown links",
    backlinks: "Notes linking here",
    outgoingLinks: "Outgoing Markdown links",
    localGraphSummary: "Local graph",
    noSummary: "No summary yet. This node may need enrichment.",
    noFacts: "Facts are thin or missing for this note.",
    duplicateRedirected: "Duplicate note redirected to canonical node.",
    viewInWiki: "View in wiki",
    openReview: "Open review",
    reviewUnavailable: "No review item available for this node.",
    back: "Back",
    forward: "Forward",
    recent: "Recent",
    degree: "Degree",
    storyWorkspace: "Story workspace",
    workspaceStatus: "Author-ready preview",
    storyHealth: "Story health",
    graphHealth: "Graph health",
    nextAction: "Next action",
    reviewQueue: "Decision queue",
    evidence: "Evidence",
    keyFacts: "Key facts",
    dev: "Dev",
    devDrawer: "Developer drawer",
    globalGraph: "Global graph",
    kindCharacter: "character",
    kindPlace: "place",
    kindEvent: "event",
    kindObject: "object",
    kindConcept: "concept",
    kindReview: "review",
  },
  es: {
    appTitle: "Visor TextifAI",
    brandSubtitle: "Workspace narrativo para autores",
    refresh: "Actualizar",
    currentProject: "Proyecto actual",
    selectProject: "Selecciona proyecto",
    readOnlyPreview: "Vista de solo lectura",
    overview: "Resumen",
    wiki: "Wiki",
    canon: "Canon",
    review: "Revisión",
    graph: "Grafo",
    artifacts: "Detalles técnicos",
    projectPanelTitle: "Workspace narrativo",
    projectPanelSubtitle: "Elige el proyecto narrativo para revisar.",
    active: "activo",
    open: "Abrir",
    authorProject: "Proyecto de autor",
    technicalArtifact: "Artefacto técnico",
    technicalDetails: "Detalles técnicos",
    chapters: "capítulos",
    nodes: "nodos",
    edges: "relaciones",
    ready: "listo",
    needsReview: "revisión",
    retry: "reintento",
    wikiSubtitle: "Notas Markdown de solo lectura proyectadas desde VaERL.",
    searchNotes: "Buscar notas",
    allKinds: "Todos los tipos",
    allTags: "Todas las etiquetas",
    allStatus: "Todos los estados",
    hideSystem: "Ocultar sistema",
    hideReview: "Ocultar revisión",
    hideChapters: "Ocultar capítulos",
    localGraph: "Grafo local",
    showAllNodes: "Mostrar todo",
    resetLayout: "Reiniciar layout",
    zoomIn: "Zoom +",
    zoomOut: "Zoom -",
    openInCanon: "Abrir en canon",
    clearHiddenTags: "limpiar {count}",
    selectNode: "Selecciona un nodo para revisar.",
    selectArtifact: "Selecciona un artefacto.",
    summary: "Bio / Resumen",
    facts: "Datos clave",
    storyRelationships: "Relaciones narrativas",
    appearancesEvidence: "Apariciones / evidencia",
    markdownLinks: "Enlaces Markdown",
    backlinks: "Notas que enlazan aquí",
    outgoingLinks: "Enlaces Markdown salientes",
    localGraphSummary: "Grafo local",
    noSummary: "Aún no hay resumen. Este nodo puede necesitar enriquecimiento.",
    noFacts: "Los datos clave faltan o son escasos para esta nota.",
    duplicateRedirected: "Nota duplicada redirigida al nodo canónico.",
    viewInWiki: "Ver en wiki",
    openReview: "Abrir revisión",
    reviewUnavailable: "No hay elemento de revisión para este nodo.",
    back: "Atrás",
    forward: "Adelante",
    recent: "Recientes",
    degree: "Grado",
    storyWorkspace: "Workspace narrativo",
    workspaceStatus: "Vista lista para autor",
    storyHealth: "Salud narrativa",
    graphHealth: "Salud del grafo",
    nextAction: "Siguiente acción",
    reviewQueue: "Cola de decisiones",
    evidence: "Evidencia",
    keyFacts: "Hechos clave",
    dev: "Dev",
    devDrawer: "Panel técnico",
    globalGraph: "Grafo global",
    kindCharacter: "personaje",
    kindPlace: "lugar",
    kindEvent: "evento",
    kindObject: "objeto",
    kindConcept: "concepto",
    kindReview: "revisión",
  },
};

const RECOMMENDED_ACTION_VIEWER_ACTIONS = {
  review_merge_or_alias: ["merge", "mark_alias"],
  review_create_primary: ["promote"],
  review_keep_secondary: ["keep_secondary"],
  review_reject_noise: ["reject_noise"],
  review_insufficient_evidence: [],
  review_attach_role_or_title: ["attach_role_or_title"],
  review_enrich_existing_entity: ["enrich_existing_entity"],
};

const VIEWER_ACTION_DESCRIPTORS = {
  merge: {
    label: "Future action: Merge",
    shortLabel: "Merge",
    explanation: "Potential merge into canonical entity. Advisory only.",
    preconditions: ["candidate_entities available", "do_not_auto_merge remains true"],
    requiredFields: ["candidate_entities", "metadata.recommended_action"],
    safetyWarning: "Read-only. No merge or write-back happens here.",
    futureWritebackTarget: "merge into canonical entity",
  },
  mark_alias: {
    label: "Future action: Mark alias",
    shortLabel: "Mark alias",
    explanation: "Potential alias attachment to existing entity. Advisory only.",
    preconditions: ["candidate_entities available"],
    requiredFields: ["candidate_entities"],
    safetyWarning: "Read-only. Alias is not persisted from viewer.",
    futureWritebackTarget: "add alias to entity",
  },
  promote: {
    label: "Future action: Promote",
    shortLabel: "Promote",
    explanation: "Potential promotion to primary entity. Advisory only.",
    preconditions: ["durable signal", "review item evidence available"],
    requiredFields: ["metadata.recommended_action", "metadata.semantic_value"],
    safetyWarning: "Read-only. No entity promotion happens here.",
    futureWritebackTarget: "promote review entity",
  },
  attach_role_or_title: {
    label: "Future action: Attach role/title",
    shortLabel: "Attach role/title",
    explanation: "Potential role/title/descriptor attachment to existing entity. Advisory only.",
    preconditions: ["surface_type role/title/descriptor", "candidate_entities preferred"],
    requiredFields: ["metadata.surface_type", "metadata.semantic_value"],
    safetyWarning: "Read-only. No role/title attachment happens here.",
    futureWritebackTarget: "attach role/title/descriptor",
  },
  enrich_existing_entity: {
    label: "Future action: Enrich existing entity",
    shortLabel: "Enrich entity",
    explanation: "Potential enrichment of existing canonical entity with retained facts. Advisory only.",
    preconditions: ["candidate_entities available", "evidence available"],
    requiredFields: ["candidate_entities", "evidence"],
    safetyWarning: "Read-only. No entity enrichment happens here.",
    futureWritebackTarget: "enrich existing entity",
  },
  keep_secondary: {
    label: "Future action: Keep secondary",
    shortLabel: "Keep secondary",
    explanation: "Potential keep-as-secondary decision. Advisory only.",
    preconditions: ["review item exists"],
    requiredFields: ["review_type"],
    safetyWarning: "Read-only. No state mutation happens here.",
    futureWritebackTarget: "keep secondary mention",
  },
  reject_noise: {
    label: "Future action: Reject noise",
    shortLabel: "Reject noise",
    explanation: "Potential reject-as-noise decision. Advisory only.",
    preconditions: ["low-confidence or noisy signal"],
    requiredFields: ["review_type"],
    safetyWarning: "Read-only. No suppression happens here.",
    futureWritebackTarget: "reject/noise suppression",
  },
};

const KIND_COLORS = {
  character: "#247c7a",
  place: "#4f8f4f",
  event: "#d5793a",
  object: "#a9782b",
  concept: "#6c6f93",
  chapter: "#7f7a6a",
  review: "#b45b35",
  unresolved: "#a23b55",
};

const STATUS_BORDERS = {
  ready: "#247c7a",
  needs_review: "#d59a2f",
  needs_retry: "#a23b55",
  failed: "#7b1f2a",
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function escapeHtml(value) {
  return String(value === null || value === undefined ? "" : value)
    .split("&").join("&amp;")
    .split("<").join("&lt;")
    .split(">").join("&gt;")
    .split('"').join("&quot;");
}

function fmtCount(value) {
  return value === null || value === undefined ? "—" : String(value);
}

function t(key, vars = {}) {
  const locale = I18N[state.locale] ? state.locale : "en";
  const fallback = I18N.en[key] || key;
  const template = I18N[locale][key] || fallback;
  return String(template).replace(/\{(\w+)\}/g, (_match, name) => String(vars[name] ?? ""));
}

function localeFromLanguage(value) {
  const language = String(value || "").toLowerCase();
  if (language.startsWith("es")) return "es";
  if (language.startsWith("en")) return "en";
  return "";
}

function detectLocale(project = null) {
  const candidates = [
    project?.work?.language,
    project?.work?.primary_language,
    state.current?.project?.work?.language,
    state.current?.project?.work?.primary_language,
    state.current?.canon?.work?.language,
    state.current?.canon?.work?.primary_language,
    preferredProject(state.projects || [])?.work?.language,
    preferredProject(state.projects || [])?.work?.primary_language,
  ];
  for (const candidate of candidates) {
    const locale = localeFromLanguage(candidate);
    if (locale) return locale;
  }
  const navLanguage = String(navigator.language || "en").toLowerCase();
  if (navLanguage.startsWith("es")) return "es";
  return "en";
}

function projectTitle(project = {}, current = state.current) {
  return current?.canon?.work?.title
    || project?.work?.title
    || project?.name
    || t('selectProject');
}

function kindLabel(kind) {
  const normalized = String(kind || '').toLowerCase();
  if (normalized === 'character') return t('kindCharacter');
  if (normalized === 'place') return t('kindPlace');
  if (normalized === 'event') return t('kindEvent');
  if (normalized === 'object') return t('kindObject');
  if (normalized === 'concept') return t('kindConcept');
  if (normalized === 'review') return t('kindReview');
  return normalized || '—';
}

function applyStaticTranslations() {
  document.documentElement.lang = state.locale;
  document.title = t('appTitle');
  $("brand-title").textContent = t('appTitle');
  $("brand-subtitle").textContent = t('brandSubtitle');
  $("refresh-projects").textContent = t('refresh');
  $("current-project-eyebrow").textContent = t('currentProject');
  $("project-title").textContent = state.current ? $("project-title").textContent : t('selectProject');
  if (!state.current) $("project-meta").textContent = t('readOnlyPreview');
  $("tab-overview").textContent = t('overview');
  $("tab-notes").textContent = t('wiki');
  $("tab-canon").textContent = t('canon');
  $("tab-review").textContent = t('review');
  $("tab-graph").textContent = t('graph');
  if ($("tab-dev")) $("tab-dev").textContent = t('dev');
  $("wiki-title").textContent = t('wiki');
  $("wiki-subtitle").textContent = t('wikiSubtitle');
  if ($("dev-title")) $("dev-title").textContent = t('technicalDetails');
  $("note-filter").placeholder = t('searchNotes');
  $("label-hide-system").textContent = t('hideSystem');
  $("label-hide-review").textContent = t('hideReview');
  $("label-hide-chapters").textContent = t('hideChapters');
  $("label-local-graph").textContent = t('localGraph');
  if ($("label-show-all-nodes")) $("label-show-all-nodes").textContent = t('showAllNodes');
  $("legend-character").textContent = t('kindCharacter');
  $("legend-place").textContent = t('kindPlace');
  $("legend-event").textContent = t('kindEvent');
  $("legend-object").textContent = t('kindObject');
  $("legend-concept").textContent = t('kindConcept');
  $("legend-review").textContent = t('kindReview');
  if ($("graph-zoom-in")) $("graph-zoom-in").textContent = t('zoomIn');
  if ($("graph-zoom-out")) $("graph-zoom-out").textContent = t('zoomOut');
  $("graph-zoom-reset").textContent = t('resetLayout');
  if (!state.current) $("graph-detail").textContent = t('selectNode');
  if ($("artifact-detail") && !state.current) $("artifact-detail").textContent = t('selectArtifact');
}

function preferredProject(projects) {
  return projects.find((project) => String(project.name || '') === 'viewer_project')
    || projects.find((project) => project.recommended)
    || projects[0]
    || null;
}

async function loadProjects() {
  await loadIngestionConfig();
  await loadIngestionJobs();
  const data = await api("/api/projects");
  state.projects = data.projects || [];
  state.locale = detectLocale(preferredProject(state.projects));
  applyStaticTranslations();
  renderProjects();
  const recommended = preferredProject(state.projects);
  const currentStillExists = state.currentId && state.projects.some((project) => project.project_id === state.currentId);
  if (!currentStillExists && recommended) {
    await selectProject(recommended.project_id, { preserveNotice: true });
    return;
  }
  if (!state.autoOpenedRecommendedProject && recommended && state.currentId !== recommended.project_id) {
    state.autoOpenedRecommendedProject = true;
    await selectProject(recommended.project_id, { notice: `Opened recommended project ${recommended.name} for manual review.` });
  }
}

async function loadIngestionConfig() {
  try {
    state.ingestionConfig = await api("/api/ingestion/config");
    state.ingestionConfigError = "";
  } catch (error) {
    state.ingestionConfig = null;
    state.ingestionConfigError = error.message || String(error);
  }
}

async function loadIngestionJobs() {
  try {
    const payload = await api("/api/ingestion/jobs");
    state.ingestionWizard.recentJobs = payload.jobs || [];
    state.ingestionWizard.historySummary = payload.summary || null;
    if (state.ingestionWizard.currentJobId) {
      const selected = state.ingestionWizard.recentJobs.find((job) => job.job_id === state.ingestionWizard.currentJobId);
      if (selected) state.ingestionWizard.currentJob = selected;
    }
  } catch (_error) {
    state.ingestionWizard.recentJobs = [];
    state.ingestionWizard.historySummary = null;
  }
}

function renderProjects() {
  const projects = state.projects || [];
  const list = $("project-list");
  if (!projects.length) {
    list.innerHTML = `<div class="empty">${escapeHtml(t('selectProject'))}</div>`;
    return;
  }
  const authorProjects = projects.filter((project) => String(project.name || '') === 'viewer_project' || project.recommended);
  const devProjects = projects.filter((project) => !authorProjects.includes(project));
  const primary = authorProjects.length ? authorProjects : [projects[0]];
  const renderCard = (project, kind) => {
    const graphSummary = project.graph_summary || {};
    const writerOutcome = project.writer_outcome || {};
    const active = project.project_id === state.currentId;
    const title = project.work?.title || project.name || project.project_id;
    return `
      <div class="project-card workspace-card ${active ? "active" : ""}" data-project="${escapeHtml(project.project_id)}">
        <div class="project-card-header">
          <strong>${escapeHtml(title)}</strong>
          <div class="project-card-actions">
            <span class="badge ${kind === 'author' ? 'inspectable-badge' : 'warning-badge'}">${escapeHtml(kind === 'author' ? t('authorProject') : t('technicalArtifact'))}</span>
            ${active ? `<span class="badge">${escapeHtml(t('active'))}</span>` : `<button type="button" class="inline-action" data-open-project="${escapeHtml(project.project_id)}">${escapeHtml(t('open'))}</button>`}
          </div>
        </div>
        <small>${escapeHtml(t('chapters'))} ${escapeHtml(fmtCount(project.chapter_count))} · ${escapeHtml(t('nodes'))} ${escapeHtml(fmtCount(graphSummary.node_count ?? '—'))} · ${escapeHtml(t('edges'))} ${escapeHtml(fmtCount(graphSummary.edge_count ?? '—'))}</small>
        <small>${escapeHtml(t('ready'))} ${escapeHtml(fmtCount(writerOutcome.chapters_ready ?? '—'))} · ${escapeHtml(t('needsReview'))} ${escapeHtml(fmtCount(writerOutcome.chapters_needing_review ?? '—'))} · ${escapeHtml(t('retry'))} ${escapeHtml(fmtCount(writerOutcome.chapters_needing_retry ?? '—'))}</small>
      </div>
    `;
  };
  list.innerHTML = `
    <div class="panel open-project-panel">
      <p class="eyebrow">${escapeHtml(t('storyWorkspace'))}</p>
      <p class="muted">${escapeHtml(t('workspaceStatus'))}</p>
      <div class="open-project-list">${primary.map((project) => renderCard(project, 'author')).join('')}</div>
      ${devProjects.length ? `<details class="dev-drawer"><summary>${escapeHtml(t('devDrawer'))}</summary><div class="open-project-list">${devProjects.map((project) => renderCard(project, 'dev')).join('')}</div></details>` : ''}
    </div>
  `;
  document.querySelectorAll("[data-project]").forEach((node) => {
    node.addEventListener("click", () => selectProject(node.dataset.project));
  });
  document.querySelectorAll("[data-open-project]").forEach((node) => {
    node.addEventListener("click", (event) => {
      event.stopPropagation();
      selectProject(node.dataset.openProject, { notice: `${t('open')}: ${node.dataset.openProject}` });
    });
  });
}

async function selectProject(projectId, options = {}) {
  state.currentId = projectId;
  state.current = await api(`/api/projects/${encodeURIComponent(projectId)}`);
  state.locale = detectLocale(state.current?.project || preferredProject(state.projects));
  applyStaticTranslations();
  state.selectedGraphNodeId = null;
  state.selectedCanonEntityKey = null;
  state.selectedReviewItemId = null;
  state.navNotice = null;
  state.compareView = { baseId: projectId, candidateId: state.compareView.candidateId || "", loading: false, result: null, error: "" };
  state.hiddenGraphTags = new Set();
  state.wikiFilters = { query: "", kind: "", tag: "", status: "" };
  state.reviewView = { severity: "", reviewType: "", query: "", sortBy: "severity_desc", quickFilter: "all", candidate: "" };
  state.viewerNavBack = [];
  state.viewerNavForward = [];
  state.viewerRecent = [];
  state.graphShowAllNodes = false;
  if (state.current && state.current.graph) state.current.graphDetailPath = "";
  if (options.notice) setNavNotice(options.notice, "info");
  else if (!options.preserveNotice) state.navNotice = null;
  resetGraphViewBox();
  $("graph-kind-filter").dataset.ready = "";
  if ($("show-all-nodes")) $("show-all-nodes").checked = false;
  renderProjects();
  renderCurrentProject();
}

function renderCurrentProject() {
  const project = state.current.project;
  $("project-title").textContent = project.work?.title || project.name || t('selectProject');
  $("project-meta").textContent = t('readOnlyPreview');
  renderOverview();
  renderNotes();
  renderCanon();
  renderReview();
  renderArtifacts();
  renderGraph();
}

function setView(view) {
  state.activeView = view;
  document.querySelectorAll(".tabs button").forEach((button) => button.classList.toggle("active", button.dataset.view === view));
  document.querySelectorAll(".view").forEach((node) => node.classList.toggle("active", node.id === `view-${view}`));
  if (view === "graph") renderGraph();
}

function setNavNotice(message, level = "info") {
  state.navNotice = message ? { message, level } : null;
}

function renderNavNotice() {
  if (!state.navNotice || !state.navNotice.message) return "";
  return `<div class="nav-notice ${escapeHtml(state.navNotice.level || "info")}">${escapeHtml(state.navNotice.message)}</div>`;
}

function navEntry({ nodeId = null, notePath = null } = {}) {
  return { nodeId, notePath };
}

function pushViewerNav(entry) {
  const previous = state.viewerNavBack[state.viewerNavBack.length - 1] || null;
  if (previous && previous.nodeId === entry.nodeId && previous.notePath === entry.notePath) return;
  state.viewerNavBack.push(entry);
  if (state.viewerNavBack.length > 48) state.viewerNavBack = state.viewerNavBack.slice(-48);
}

function rememberRecentNode(node) {
  if (!node || !node.id) return;
  state.viewerRecent = [node, ...state.viewerRecent.filter((item) => item.id !== node.id)].slice(0, 12);
}

function graphPositionsStorageKey() {
  return `textifai.graph.positions.${state.currentId || "unknown"}`;
}

function loadGraphPositions() {
  try {
    const raw = localStorage.getItem(graphPositionsStorageKey());
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (_error) {
    return {};
  }
}

function hasPersistedGraphPositions() {
  return Object.keys(loadGraphPositions()).length > 0;
}

function persistGraphPositions(byId) {
  try {
    const payload = Object.fromEntries(Object.values(byId).map((node) => [node.id, { x: node.x, y: node.y }]));
    localStorage.setItem(graphPositionsStorageKey(), JSON.stringify(payload));
  } catch (_error) {
    // best effort
  }
}

function clearGraphPositions() {
  try {
    localStorage.removeItem(graphPositionsStorageKey());
  } catch (_error) {
    // best effort
  }
}

function hashFloat(value) {
  const text = String(value || '');
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return ((hash >>> 0) % 10000) / 10000;
}

function autoFitGraphViewBox(byId, { padding = 120 } = {}) {
  const nodes = Object.values(byId || {});
  if (!nodes.length) return;
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const node of nodes) {
    const radius = graphNodeRadius(node);
    minX = Math.min(minX, node.x - radius);
    minY = Math.min(minY, node.y - radius);
    maxX = Math.max(maxX, node.x + radius);
    maxY = Math.max(maxY, node.y + radius);
  }
  state.graphViewBox = {
    x: minX - padding,
    y: minY - padding,
    width: Math.max(640, (maxX - minX) + padding * 2),
    height: Math.max(420, (maxY - minY) + padding * 2),
  };
  applyGraphViewBox();
}

function viewerNavBack() {
  if (state.viewerNavBack.length < 2) return;
  const current = state.viewerNavBack.pop();
  state.viewerNavForward.push(current);
  const previous = state.viewerNavBack[state.viewerNavBack.length - 1];
  applyViewerNavEntry(previous, { pushHistory: false });
}

function viewerNavForward() {
  const next = state.viewerNavForward.pop();
  if (!next) return;
  state.viewerNavBack.push(next);
  applyViewerNavEntry(next, { pushHistory: false });
}

function applyViewerNavEntry(entry, { pushHistory = false } = {}) {
  if (!entry) return;
  if (entry.nodeId) {
    selectGraphNode(entry.nodeId, { pushHistory, renderDetail: true });
  } else if (entry.notePath) {
    openGraphNote(entry.notePath, state.selectedGraphNodeId, { pushHistory });
  }
}

function renderOverview() {
  if (!state.current) return;
  const overview = state.current.overview || {};
  const health = state.current.health || {};
  const graph = normalizeGraphData(state.current.graph || { nodes: [], edges: [] });
  const reviewCount = Number(overview.chapters_needing_review || 0) + Number(overview.unresolved_link_count || 0);
  const retryCount = Number(overview.chapters_needing_retry || 0);
  $("view-overview").innerHTML = `
    <section class="author-hero panel">
      <div>
        <p class="eyebrow">${escapeHtml(t('storyWorkspace'))}</p>
        <h3>${escapeHtml(projectTitle(state.current.project || {}))}</h3>
        <p class="muted">${escapeHtml(overview.user_summary || t('workspaceStatus'))}</p>
      </div>
      <div class="hero-actions">
        <button id="overview-open-wiki" type="button">${escapeHtml(t('wiki'))}</button>
        <button id="overview-open-graph" type="button">${escapeHtml(t('graph'))}</button>
      </div>
    </section>
    <div class="stats-grid author-dashboard">
      <div class="stat-card"><span>${escapeHtml(t('storyHealth'))}</span><strong>${escapeHtml(health.status || t('ready'))}</strong></div>
      <div class="stat-card"><span>${escapeHtml(t('chapters'))}</span><strong>${fmtCount(overview.chapters_processed || 0)}</strong></div>
      <div class="stat-card"><span>${escapeHtml(t('reviewQueue'))}</span><strong>${fmtCount(reviewCount)}</strong></div>
      <div class="stat-card"><span>${escapeHtml(t('retry'))}</span><strong>${fmtCount(retryCount)}</strong></div>
      <div class="stat-card"><span>${escapeHtml(t('graphHealth'))}</span><strong>${fmtCount(graph.nodes.length)} / ${fmtCount(graph.edges.length)}</strong></div>
      <div class="stat-card"><span>${escapeHtml(t('nextAction'))}</span><strong>${escapeHtml((overview.primary_action || {}).label || overview.next_action_cta || t('review'))}</strong></div>
    </div>
    ${renderSemanticHealth(state.current.health || {})}
    ${renderIngestionWizard()}
    ${renderCompareRunsPanel()}
    ${renderEntityTriagePanel()}
  `;
  bindHealthInteractions();
  bindIngestionWizardInteractions();
  bindCompareRunsInteractions();
  bindEntityTriageInteractions();
  $("overview-open-wiki")?.addEventListener("click", () => setView("notes"));
  $("overview-open-graph")?.addEventListener("click", () => setView("graph"));
}

function renderIngestionWizard() {
  const config = state.ingestionConfig || {};
  const wizard = state.ingestionWizard || {};
  const preview = buildIngestionCommandPreview(config, wizard);
  const historySummary = wizard.historySummary || {};
  const hasPotentialDuplicate = Boolean((wizard.recentJobs || []).find((job) => {
    const sameSource = normalizeKey(job.source_root) === normalizeKey(String(wizard.sourceRoot || "").trim());
    const sameTitle = normalizeKey(job.project_title) === normalizeKey(String(wizard.projectTitle || "").trim());
    const sameRun = normalizeKey(job.run_name) === normalizeKey(sanitizePreviewSlug(wizard.runName || ""));
    return (job.status === "queued" || job.status === "running") && sameSource && sameTitle && sameRun;
  }));
  const canSubmit = config.can_execute && preview.canSubmit && !wizard.submitting && !hasPotentialDuplicate;
  return `
    <section class="ingestion-wizard panel">
      <div class="wizard-header">
        <div>
          <p class="eyebrow">Ingestion Wizard</p>
          <h3>Local path ingestion job</h3>
          <p class="muted">Controlled local execution only. Output limited to dedicated runs/web_ingestion targets.</p>
        </div>
        <span class="badge">${escapeHtml(config.mode || "config unavailable")}</span>
      </div>
      ${state.ingestionConfigError ? `<div class="nav-notice warning">Ingestion config unavailable: ${escapeHtml(state.ingestionConfigError)}</div>` : ""}
      <div class="wizard-steps">
        ${["Start ingestion", "Input mode", "Source material", "Output/run settings", "Command preview", "Safety review", "Execution placeholder"].map((step, index) => `
          <div class="wizard-step"><span>${index + 1}</span>${escapeHtml(step)}</div>
        `).join("")}
      </div>
      <div class="wizard-grid">
        <label>Source root path
          <input id="wizard-source-root" class="search compact" placeholder="/path/to/source" value="${escapeHtml(wizard.sourceRoot || "")}" />
        </label>
        <label>Project title
          <input id="wizard-project-title" class="search compact" placeholder="My Narrative Project" value="${escapeHtml(wizard.projectTitle || "")}" />
        </label>
        <label>Run name / output slug
          <input id="wizard-run-name" class="search compact" placeholder="my_narrative_run" value="${escapeHtml(wizard.runName || "")}" />
        </label>
        <label>Primary language
          <input id="wizard-primary-language" class="search compact" placeholder="es" value="${escapeHtml(wizard.primaryLanguage || "")}" />
        </label>
        <label>Working languages
          <input id="wizard-working-languages" class="search compact" placeholder="es,en" value="${escapeHtml(wizard.workingLanguages || "")}" />
        </label>
        <label class="checkbox-row">
          <input id="wizard-skip-plugin" type="checkbox" ${wizard.skipPluginInstall !== false ? "checked" : ""} />
          skip plugin install (recommended)
        </label>
      </div>
      <div class="wizard-preview">
        <h4>Output root preview</h4>
        <code>${escapeHtml(preview.outputRoot)}</code>
        <h4>Args list preview</h4>
        <ol class="args-list">${preview.args.map((arg) => `<li><code>${escapeHtml(arg)}</code></li>`).join("")}</ol>
        ${preview.warnings.length ? `<div class="nav-notice warning">${preview.warnings.map(escapeHtml).join("<br />")}</div>` : ""}
      </div>
      <div class="wizard-safety">
        <h4>Safety review</h4>
        <ul>
          ${(config.safety_notes || [
            "Preview only: no subprocess execution.",
            "No files will be written.",
            "Execution will be enabled in a future safepoint.",
          ]).map((note) => `<li>${escapeHtml(note)}</li>`).join("")}
        </ul>
        <button type="button" id="wizard-submit-job" ${canSubmit ? "" : "disabled"}>${wizard.submitting ? "Submitting..." : "Submit ingestion job"}</button>
        ${hasPotentialDuplicate ? `<div class="nav-notice warning">Active job already exists for same source/project/run. Wait for completion or change run name.</div>` : ""}
        ${wizard.submitError ? `<div class="nav-notice warning">${escapeHtml(wizard.submitError)}</div>` : ""}
      </div>
      <div class="wizard-job-status">
        <h4>Job status</h4>
        ${renderWizardJobStatus(wizard.currentJob)}
      </div>
      <div class="wizard-job-status">
        <h4>Recent jobs</h4>
        ${renderIngestionHistory(wizard.recentJobs, historySummary, wizard.historyFilters)}
      </div>
    </section>
  `;
}

function bindIngestionWizardInteractions() {
  const bindValue = (id, key) => {
    $(id)?.addEventListener("input", (event) => {
      state.ingestionWizard[key] = event.target.value;
      renderOverview();
    });
  };
  bindValue("wizard-source-root", "sourceRoot");
  bindValue("wizard-project-title", "projectTitle");
  bindValue("wizard-run-name", "runName");
  bindValue("wizard-primary-language", "primaryLanguage");
  bindValue("wizard-working-languages", "workingLanguages");
  $("wizard-skip-plugin")?.addEventListener("change", (event) => {
    state.ingestionWizard.skipPluginInstall = event.target.checked;
    renderOverview();
  });
  $("wizard-history-status")?.addEventListener("change", (event) => {
    state.ingestionWizard.historyFilters.status = event.target.value;
    renderOverview();
  });
  $("wizard-history-mode")?.addEventListener("change", (event) => {
    state.ingestionWizard.historyFilters.mode = event.target.value;
    renderOverview();
  });
  $("wizard-history-query")?.addEventListener("input", (event) => {
    state.ingestionWizard.historyFilters.query = event.target.value;
    renderOverview();
  });
  $("wizard-history-sort")?.addEventListener("change", (event) => {
    state.ingestionWizard.historyFilters.sortBy = event.target.value;
    renderOverview();
  });
  $("wizard-submit-job")?.addEventListener("click", submitIngestionJob);
}

function buildIngestionCommandPreview(config, wizard) {
  const base = (config.recommended_command || {}).program || ["uv", "run", "python", "scripts/textifai.py", "init"];
  const defaultOutputRoot = config.default_output_root || "runs/web_ingestion";
  const runSlug = sanitizePreviewSlug(wizard.runName || wizard.projectTitle || "new_run");
  const outputRoot = `${defaultOutputRoot}/${runSlug || "<run_slug>"}`;
  const args = [...base, "--vault-root", outputRoot];
  if (wizard.sourceRoot) args.push("--source-root", wizard.sourceRoot);
  else args.push("--source-root", "<source_root>");
  if (wizard.projectTitle) args.push("--project-title", wizard.projectTitle);
  else args.push("--project-title", "<project_title>");
  if (wizard.primaryLanguage) args.push("--primary-language", wizard.primaryLanguage);
  for (const lang of splitWorkingLanguages(wizard.workingLanguages)) {
    args.push("--working-language", lang);
  }
  if (wizard.skipPluginInstall !== false) args.push("--skip-plugin-install");
  const warnings = [];
  if (!wizard.sourceRoot) warnings.push("source_root is required before execution can be enabled.");
  if (!wizard.projectTitle) warnings.push("project_title is required before execution can be enabled.");
  if (!wizard.runName) warnings.push("run_name/output_slug is required before execution can be enabled.");
  if (!config.can_execute) warnings.push("Execution disabled by server config.");
  warnings.push("Command is executed server-side with args list only. No shell interpolation.");
  return { args, outputRoot, warnings, canSubmit: Boolean(config.can_execute) && !(!wizard.sourceRoot || !wizard.projectTitle || !wizard.runName) };
}

function splitWorkingLanguages(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function sanitizePreviewSlug(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 80);
}

function renderWizardJobStatus(job) {
  if (!job) return `<p class="muted">No job submitted yet.</p>`;
  const restoredBadge = job.restored_from_disk ? `<span class="badge restored-badge">restored</span>` : "";
  const summary = renderHistoricalRunQualitySummary(job);
  const compareReadiness = renderCompareReadiness(job);
  const qaChecklist = renderRunQaChecklist(job);
  const previousTarget = findHistoricalCompareTarget(job, "previous");
  const latestTarget = findHistoricalCompareTarget(job, "latest");
  return `
    <div class="wizard-job-card">
      <p><strong>job_id:</strong> <code>${escapeHtml(job.job_id || "not available")}</code></p>
      <p><strong>status:</strong> <span class="badge ${escapeHtml(`status-${job.status || "unknown"}`)}">${escapeHtml(job.status || "unknown")}</span> ${restoredBadge}</p>
      <p><strong>output_root:</strong> <code>${escapeHtml(job.output_root || "not available")}</code></p>
      <p><strong>safe_output_root:</strong> <code>${escapeHtml(job.safe_output_root || "not available")}</code></p>
      <p><strong>created:</strong> ${escapeHtml(job.created_at || "not available")}</p>
      <p><strong>started:</strong> ${escapeHtml(job.started_at || "not available")}</p>
      <p><strong>finished:</strong> ${escapeHtml(job.finished_at || "not available")}</p>
      <p><strong>duration_seconds:</strong> ${escapeHtml(job.duration_seconds === null || job.duration_seconds === undefined ? "not available" : job.duration_seconds)}</p>
      <p><strong>exit_code:</strong> ${escapeHtml(job.exit_code === null || job.exit_code === undefined ? "not available" : job.exit_code)}</p>
      <p><strong>result_detected:</strong> ${escapeHtml(job.result_detected ? "yes" : "no")}</p>
      <p><strong>result_status:</strong> ${escapeHtml(job.result_status || "not available")}</p>
      <p><strong>inspectable_artifacts:</strong> ${escapeHtml(job.inspectable_artifacts_available ? "yes" : "no")}</p>
      <p><strong>review_queue_available:</strong> ${escapeHtml(job.review_queue_available ? "yes" : "no")}</p>
      <p><strong>log_size_bytes:</strong> ${escapeHtml(job.log_size_bytes === null || job.log_size_bytes === undefined ? "not available" : job.log_size_bytes)}</p>
      <p><strong>log_truncated:</strong> ${escapeHtml(job.log_truncated ? "yes" : "no")}</p>
      <p><strong>log_source:</strong> ${escapeHtml(job.log_source || "memory")}</p>
      ${job.project_id ? `<p><strong>project_id:</strong> <code>${escapeHtml(job.project_id)}</code></p>` : ""}
      ${!job.project_id ? `<p class="muted"><strong>open result:</strong> not available yet. Inspect output root or refresh projects.</p>` : ""}
      <p class="muted"><strong>execution log:</strong> wizard runtime log. Semantic artifacts are separate outputs.</p>
      ${(job.result_warnings || []).length ? `<div class="nav-notice warning">${job.result_warnings.map((item) => escapeHtml(item)).join("<br />")}</div>` : ""}
      ${job.log_warning ? `<div class="nav-notice warning">${escapeHtml(job.log_warning)}</div>` : ""}
      ${job.error ? `<p class="nav-notice warning">${escapeHtml(job.error)}</p>` : ""}
      ${summary}
      ${compareReadiness}
      ${qaChecklist}
      <details>
        <summary>Command preview</summary>
        <ol class="args-list">${(job.command_preview || []).map((arg) => `<li><code>${escapeHtml(arg)}</code></li>`).join("")}</ol>
      </details>
      <details>
        <summary>Log tail</summary>
        <pre class="frontmatter">${escapeHtml(job.log_tail || "not available")}</pre>
      </details>
      <div class="wizard-job-actions">
        <button type="button" id="wizard-refresh-projects">Refresh projects</button>
        <button type="button" id="wizard-view-log">View log</button>
        ${job.project_id ? `<button type="button" id="wizard-open-result">Open result</button>` : ""}
        ${job.project_id ? `<button type="button" id="wizard-open-overview">Open Overview</button>` : ""}
        ${job.project_id ? `<button type="button" id="wizard-open-health">Open Semantic Health</button>` : ""}
        ${job.project_id ? `<button type="button" id="wizard-open-review">Open Review Queue</button>` : ""}
        ${job.project_id ? `<button type="button" id="wizard-open-canon">Open Canon</button>` : ""}
        ${job.project_id ? `<button type="button" id="wizard-open-graph">Open Graph</button>` : ""}
        ${job.project_id ? `<button type="button" id="wizard-open-artifacts">Open Artifacts</button>` : ""}
        ${job.project_id ? `<button type="button" id="wizard-open-triage">Open Entity Triage</button>` : ""}
        ${job.project_id ? `<button type="button" id="wizard-use-base">Use as base</button>` : ""}
        ${job.project_id ? `<button type="button" id="wizard-use-candidate">Use as candidate</button>` : ""}
        ${job.project_id ? `<button type="button" id="wizard-open-compare">Open Compare Runs</button>` : ""}
        ${job.project_id && previousTarget ? `<button type="button" id="wizard-compare-previous">Compare with previous run</button>` : `<button type="button" disabled>Compare with previous run unavailable</button>`}
        ${job.project_id && latestTarget ? `<button type="button" id="wizard-compare-latest">Compare with latest run</button>` : `<button type="button" disabled>Compare with latest run unavailable</button>`}
      </div>
      ${renderHistoricalArtifactShortcuts(job)}
    </div>
  `;
}

function renderHistoricalRunQualitySummary(job) {
  if (!job?.project_id || state.currentId !== job.project_id || !state.current) {
    return `<p class="muted">Semantic quality summary loads after opening this run in viewer.</p>`;
  }
  const project = state.current.project || {};
  const canon = state.current.canon || {};
  const health = state.current.health || {};
  const triage = buildEntityTriage(state.current, state.compareView?.result || null);
  return `
    <div class="wizard-history-summary quality-summary">
      <span class="badge">health ${escapeHtml((health.overall_status || "not available"))}</span>
      <span class="badge">primaries ${escapeHtml((project.primary_count ?? canon.primaries?.length ?? "—"))}</span>
      <span class="badge">review entities ${escapeHtml((canon.review_entities || []).length)}</span>
      <span class="badge">review queue ${escapeHtml(((canon.review_queue || {}).item_count ?? "—"))}</span>
      <span class="badge">invariants ${escapeHtml(((health.semantic_invariants || {}).status || "not available"))}</span>
      <span class="badge">triage rows ${escapeHtml((triage.rows || []).length)}</span>
    </div>
  `;
}

function renderHistoricalArtifactShortcuts(job) {
  const availability = job?.artifact_availability || {};
  const button = (artifact, label) => {
    const enabled = Boolean(job?.project_id && availability[artifact]);
    return `<button type="button" class="inline-action" data-history-artifact="${escapeHtml(artifact)}" ${enabled ? "" : "disabled"}>${escapeHtml(label)}</button>`;
  };
  return `
    <div class="wizard-history-artifacts">
      <p class="muted"><strong>Semantic artifacts:</strong> ingestion outputs, separate from wizard execution log.</p>
      ${button("obsidian_import.json", "Open obsidian_import.json")}
      ${button("review_queue.json", "Open review_queue.json")}
      ${button("semantic_invariants_audit.json", "Open semantic_invariants_audit.json")}
      ${button("run_comparability_manifest.json", "Open run_comparability_manifest.json")}
    </div>
  `;
}

function renderCompareReadiness(job) {
  const availability = job?.artifact_availability || {};
  const canCompare = Boolean(job?.can_compare ?? (job?.project_id && availability["obsidian_import.json"]));
  const reason = job?.compare_unavailable_reason || (canCompare ? "" : "project_id or semantic artifacts missing");
  return `
    <div class="wizard-qa-panel">
      <h4>Compare readiness</h4>
      <div class="wizard-history-summary">
        <span class="badge ${canCompare ? "inspectable-badge" : "warning-badge"}">can_compare: ${canCompare ? "yes" : "no"}</span>
        <span class="badge">project_id: ${job?.project_id ? "available" : "missing"}</span>
        <span class="badge">manifest: ${availability["run_comparability_manifest.json"] ? "available" : "not available"}</span>
        <span class="badge">semantic artifacts: ${availability["obsidian_import.json"] ? "available" : "missing"}</span>
      </div>
      ${reason ? `<p class="muted">${escapeHtml(reason)}</p>` : `<p class="muted">Compare action is observability-only and reuses existing Compare Runs panel.</p>`}
    </div>
  `;
}

function qaStatusBadge(status) {
  const cls = status === "available" ? "inspectable-badge" : status === "missing" ? "warning-badge" : status === "recommended" ? "stale-badge" : "";
  return `<span class="badge ${cls}">${escapeHtml(status)}</span>`;
}

function buildRunQaChecklist(job) {
  const availability = job?.artifact_availability || {};
  const hasWarnings = (job?.result_warnings || []).length > 0;
  const reviewRecommended = Boolean(job?.review_queue_available);
  const compareReady = Boolean(job?.can_compare ?? (job?.project_id && availability["obsidian_import.json"]));
  return [
    { label: "Result is inspectable", status: job?.result_detected ? "available" : "missing", view: "overview" },
    { label: "obsidian_import.json available", status: availability["obsidian_import.json"] ? "available" : "missing", artifact: "obsidian_import.json" },
    { label: "review_queue.json available", status: availability["review_queue.json"] ? "available" : "missing", artifact: "review_queue.json" },
    { label: "semantic_invariants_audit.json available", status: availability["semantic_invariants_audit.json"] ? "available" : "missing", artifact: "semantic_invariants_audit.json" },
    { label: "Semantic Health status reviewed", status: hasWarnings ? "recommended" : "manual", view: "overview" },
    { label: "Review Queue checked", status: reviewRecommended ? "recommended" : "not available", view: "review" },
    { label: "Entity Triage checked", status: job?.project_id ? "manual" : "not available", view: "overview" },
    { label: "Canonicalization risk checked", status: job?.project_id ? "manual" : "not available", view: "canon" },
    { label: "Compare against previous/baseline run", status: compareReady ? "manual" : "not available", action: "compare" },
    { label: "Open Graph for unresolved targets", status: job?.project_id ? "manual" : "not available", view: "graph" },
    { label: "Check raw artifacts if health is warning/critical", status: hasWarnings ? "recommended" : "manual", view: "artifacts" },
  ];
}

function renderRunQaChecklist(job) {
  const items = buildRunQaChecklist(job);
  return `
    <div class="wizard-qa-panel">
      <h4>Run QA checklist</h4>
      <p class="muted">Read-only guide. No checklist state is saved.</p>
      <div class="qa-checklist">
        ${items.map((item) => `
          <div class="qa-checklist-item">
            <span>${escapeHtml(item.label)}</span>
            ${qaStatusBadge(item.status)}
            ${item.view && job?.project_id ? `<button type="button" class="inline-action" data-checklist-view="${escapeHtml(item.view)}">Open</button>` : ""}
            ${item.artifact && job?.project_id && (job.artifact_availability || {})[item.artifact] ? `<button type="button" class="inline-action" data-checklist-artifact="${escapeHtml(item.artifact)}">Open raw</button>` : ""}
            ${item.action === "compare" && job?.project_id ? `<button type="button" class="inline-action" data-checklist-compare="open">Open Compare Runs</button>` : ""}
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function classifyJob(job) {
  const warnings = job.result_warnings || [];
  const stale = warnings.some((item) => String(item || "").toLowerCase().includes("status cannot be trusted"));
  return {
    stale,
    restored: Boolean(job.restored_from_disk),
    inspectable: Boolean(job.result_detected || job.project_id),
    failed: job.status === "failed",
    active: job.status === "queued" || job.status === "running",
    finished: job.status === "succeeded" || job.status === "failed",
  };
}

function applyHistoryFilters(jobs, filters) {
  const items = [...(jobs || [])];
  const activeFilters = filters || {};
  const query = normalizeKey(activeFilters.query || "");
  let filtered = items.filter((job) => {
    const meta = classifyJob(job);
    if (activeFilters.status && job.status !== activeFilters.status) return false;
    if (activeFilters.mode === "restored" && !meta.restored) return false;
    if (activeFilters.mode === "inspectable" && !meta.inspectable) return false;
    if (activeFilters.mode === "failed_or_stale" && !(meta.failed || meta.stale)) return false;
    if (!query) return true;
    return [
      job.project_title,
      job.run_name,
      job.output_root,
      job.job_id,
    ].some((value) => normalizeKey(value).includes(query));
  });
  const sortBy = activeFilters.sortBy || "newest";
  filtered.sort((left, right) => {
    if (sortBy === "oldest") return String(left.created_at || "").localeCompare(String(right.created_at || ""));
    if (sortBy === "status") return String(left.status || "").localeCompare(String(right.status || "")) || String(right.created_at || "").localeCompare(String(left.created_at || ""));
    if (sortBy === "project_title") return String(left.project_title || "").localeCompare(String(right.project_title || "")) || String(right.created_at || "").localeCompare(String(left.created_at || ""));
    return String(right.created_at || "").localeCompare(String(left.created_at || ""));
  });
  return filtered;
}

function findHistoricalCompareTarget(job, mode) {
  if (!job?.project_id) return null;
  const inspectableJobs = (state.ingestionWizard.recentJobs || []).filter((item) => item.project_id && item.job_id !== job.job_id);
  if (!inspectableJobs.length) return null;
  const sorted = [...inspectableJobs].sort((left, right) => String(right.created_at || "").localeCompare(String(left.created_at || "")));
  if (mode === "latest") return sorted[0] || null;
  if (mode === "previous") {
    const older = sorted
      .filter((item) => String(item.created_at || "") < String(job.created_at || ""))
      .sort((left, right) => String(right.created_at || "").localeCompare(String(left.created_at || "")));
    return older[0] || null;
  }
  return null;
}

function renderIngestionHistory(jobs, summary, filters) {
  const items = applyHistoryFilters(jobs, filters);
  const ignoredCount = Number(summary?.ignored_output_dirs_without_metadata || 0);
  const approxLogBytes = Number(summary?.approx_log_bytes || 0);
  if (!jobs || !jobs.length) {
    return `
      <p class="muted">No recent jobs in memory or restored history.</p>
      ${ignoredCount ? `<div class="nav-notice warning">${ignoredCount} web ingestion folders without job metadata were ignored.</div>` : ""}
    `;
  }
  return `
    <div class="wizard-history-summary">
      <span class="badge">jobs ${escapeHtml(summary?.job_count ?? jobs.length)}</span>
      <span class="badge">restored ${escapeHtml(summary?.restored_count ?? 0)}</span>
      <span class="badge">active ${escapeHtml(summary?.active_count ?? 0)}</span>
      <span class="badge">inspectable ${escapeHtml(summary?.inspectable_count ?? 0)}</span>
      <span class="badge">failed ${escapeHtml(summary?.failed_count ?? 0)}</span>
      <span class="badge">log bytes ${escapeHtml(approxLogBytes)}</span>
    </div>
    ${ignoredCount ? `<div class="nav-notice warning">${ignoredCount} web ingestion folders without job metadata were ignored.</div>` : ""}
    <div class="wizard-history-controls">
      <label>Status
        <select id="wizard-history-status" class="search compact">
          <option value="">All</option>
          ${["queued", "running", "succeeded", "failed"].map((status) => `<option value="${status}" ${filters?.status === status ? "selected" : ""}>${status}</option>`).join("")}
        </select>
      </label>
      <label>Mode
        <select id="wizard-history-mode" class="search compact">
          <option value="" ${!filters?.mode ? "selected" : ""}>All</option>
          <option value="restored" ${filters?.mode === "restored" ? "selected" : ""}>Restored only</option>
          <option value="inspectable" ${filters?.mode === "inspectable" ? "selected" : ""}>Inspectable only</option>
          <option value="failed_or_stale" ${filters?.mode === "failed_or_stale" ? "selected" : ""}>Failed/Stale only</option>
        </select>
      </label>
      <label>Search
        <input id="wizard-history-query" class="search compact" placeholder="project / run / output" value="${escapeHtml(filters?.query || "")}" />
      </label>
      <label>Sort
        <select id="wizard-history-sort" class="search compact">
          <option value="newest" ${filters?.sortBy === "newest" ? "selected" : ""}>Newest first</option>
          <option value="oldest" ${filters?.sortBy === "oldest" ? "selected" : ""}>Oldest first</option>
          <option value="status" ${filters?.sortBy === "status" ? "selected" : ""}>Status</option>
          <option value="project_title" ${filters?.sortBy === "project_title" ? "selected" : ""}>Project title</option>
        </select>
      </label>
      <button type="button" disabled title="Future phase only">Retention cleanup is not implemented yet</button>
    </div>
    <div class="wizard-recent-jobs">
      ${items.slice(0, 12).map((job) => {
        const meta = classifyJob(job);
        const staleBadge = meta.stale ? `<span class="badge stale-badge">stale</span>` : "";
        const inspectableBadge = meta.inspectable ? `<span class="badge inspectable-badge">inspectable</span>` : `<span class="badge warning-badge">not inspectable</span>`;
        const logBadge = `<span class="badge">${escapeHtml(job.log_source || (job.restored_from_disk ? "persisted?" : "memory"))}</span>`;
        const compareBadge = `<span class="badge ${job.can_compare ? "inspectable-badge" : "warning-badge"}">compare ${job.can_compare ? "yes" : "no"}</span>`;
        return `
        <div class="wizard-job-row ${job.job_id === state.ingestionWizard.currentJobId ? "active" : ""}">
          <div>
            <p><strong>${escapeHtml(job.project_title || "untitled")}</strong> · <code>${escapeHtml(job.run_name || "n/a")}</code> ${job.restored_from_disk ? `<span class="badge restored-badge">restored</span>` : ""} ${staleBadge} ${inspectableBadge}</p>
            <p class="muted"><code>${escapeHtml(job.job_id)}</code> · ${escapeHtml(job.status || "unknown")} · ${escapeHtml(job.output_root || "not available")}</p>
            <p class="muted">created ${escapeHtml(job.created_at || "n/a")} · finished ${escapeHtml(job.finished_at || "n/a")} · duration ${escapeHtml(job.duration_seconds ?? "n/a")} · ${logBadge} · ${compareBadge} · review queue ${escapeHtml(job.review_queue_available ? "yes" : "no")} · result ${escapeHtml(job.result_status || "n/a")}</p>
            ${(job.result_warnings || []).length ? `<p class="muted">${escapeHtml(job.result_warnings[0])}</p>` : ""}
          </div>
          <div class="wizard-job-actions">
            <button type="button" data-wizard-select-job="${escapeHtml(job.job_id)}">Inspect</button>
            ${job.project_id ? `<button type="button" data-wizard-open-job="${escapeHtml(job.job_id)}">Open result</button>` : ""}
            ${job.project_id ? `<button type="button" data-wizard-use-base="${escapeHtml(job.job_id)}">Use as base</button>` : ""}
            ${job.project_id ? `<button type="button" data-wizard-use-candidate="${escapeHtml(job.job_id)}">Use as candidate</button>` : ""}
          </div>
        </div>
      `; }).join("")}
    </div>
  `;
}

async function submitIngestionJob() {
  const wizard = state.ingestionWizard;
  wizard.submitError = "";
  wizard.submitting = true;
  renderOverview();
  try {
    const payload = {
      source_root: wizard.sourceRoot,
      project_title: wizard.projectTitle,
      run_name: wizard.runName,
      primary_language: wizard.primaryLanguage || null,
      working_languages: splitWorkingLanguages(wizard.workingLanguages),
      skip_plugin_install: wizard.skipPluginInstall !== false,
    };
    const job = await api("/api/ingestion/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    wizard.currentJobId = job.job_id || "";
    wizard.currentJob = job;
    await loadIngestionJobs();
    wizard.submitting = false;
    renderOverview();
    bindWizardJobActions();
    scheduleJobPolling();
  } catch (error) {
    wizard.submitError = `Job submit failed: ${error.message || String(error)}`;
    wizard.submitting = false;
    renderOverview();
  }
}

function bindWizardJobActions() {
  $("wizard-refresh-projects")?.addEventListener("click", async () => {
    await loadProjects();
    renderOverview();
  });
  $("wizard-view-log")?.addEventListener("click", async () => {
    const job = state.ingestionWizard.currentJob;
    if (!job?.job_id) return;
    const payload = await api(`/api/ingestion/jobs/${encodeURIComponent(job.job_id)}/log?max_chars=40000`);
    state.ingestionWizard.currentJob = {
      ...job,
      log_tail: payload.log || "",
      last_log_lines: payload.last_log_lines || [],
      log_size_bytes: payload.log_size_bytes,
      log_truncated: payload.log_truncated,
      log_source: payload.log_source,
      log_warning: payload.warning || "",
    };
    renderOverview();
    bindWizardJobActions();
  });
  $("wizard-open-result")?.addEventListener("click", async () => {
    const job = state.ingestionWizard.currentJob;
    if (job?.project_id) await openHistoricalJobTarget(job, "overview", null, "Opened result from historical job");
  });
  $("wizard-open-overview")?.addEventListener("click", async () => openSelectedHistoricalView("overview", "Opened Overview from historical job"));
  $("wizard-open-health")?.addEventListener("click", async () => openSelectedHistoricalView("overview", "Opened Semantic Health for historical job"));
  $("wizard-open-review")?.addEventListener("click", async () => openSelectedHistoricalView("review", "Opened Review Queue for restored job"));
  $("wizard-open-canon")?.addEventListener("click", async () => openSelectedHistoricalView("canon", "Opened Canon for historical job"));
  $("wizard-open-graph")?.addEventListener("click", async () => openSelectedHistoricalView("graph", "Opened Graph for historical job"));
  $("wizard-open-artifacts")?.addEventListener("click", async () => openSelectedHistoricalView("artifacts", "Opened Artifacts for historical job"));
  $("wizard-open-triage")?.addEventListener("click", async () => openSelectedHistoricalView("overview", "Opened Entity Triage for historical job"));
  $("wizard-use-base")?.addEventListener("click", async () => assignSelectedHistoricalCompareRole("base"));
  $("wizard-use-candidate")?.addEventListener("click", async () => assignSelectedHistoricalCompareRole("candidate"));
  $("wizard-open-compare")?.addEventListener("click", async () => openHistoricalComparePanel());
  $("wizard-compare-previous")?.addEventListener("click", async () => compareSelectedHistoricalJobAgainst("previous"));
  $("wizard-compare-latest")?.addEventListener("click", async () => compareSelectedHistoricalJobAgainst("latest"));
  document.querySelectorAll("[data-wizard-select-job]").forEach((node) => {
    node.addEventListener("click", async () => {
      const jobId = node.getAttribute("data-wizard-select-job");
      if (!jobId) return;
      const job = await api(`/api/ingestion/jobs/${encodeURIComponent(jobId)}`);
      state.ingestionWizard.currentJobId = jobId;
      state.ingestionWizard.currentJob = job;
      renderOverview();
      bindWizardJobActions();
      scheduleJobPolling();
    });
  });
  document.querySelectorAll("[data-wizard-open-job]").forEach((node) => {
    node.addEventListener("click", async () => {
      const jobId = node.getAttribute("data-wizard-open-job");
      const job = (state.ingestionWizard.recentJobs || []).find((item) => item.job_id === jobId);
      if (!job?.project_id) {
        state.ingestionWizard.submitError = "Result is not inspectable yet. Try Refresh projects or inspect output root.";
        renderOverview();
        bindWizardJobActions();
        return;
      }
      await loadProjects();
      await selectProject(job.project_id);
      setView("overview");
      setNavNotice("Opened result from historical job", "info");
      renderCurrentProject();
    });
  });
  document.querySelectorAll("[data-wizard-use-base]").forEach((node) => {
    node.addEventListener("click", () => assignHistoricalCompareRoleById(node.getAttribute("data-wizard-use-base"), "base"));
  });
  document.querySelectorAll("[data-wizard-use-candidate]").forEach((node) => {
    node.addEventListener("click", () => assignHistoricalCompareRoleById(node.getAttribute("data-wizard-use-candidate"), "candidate"));
  });
  document.querySelectorAll("[data-history-artifact]").forEach((node) => {
    node.addEventListener("click", async () => {
      const artifact = node.getAttribute("data-history-artifact");
      const job = state.ingestionWizard.currentJob;
      if (!artifact || !job?.project_id) return;
      await openHistoricalJobTarget(job, "artifacts", artifact, `Opened artifact ${artifact} from historical job`);
    });
  });
  document.querySelectorAll("[data-checklist-view]").forEach((node) => {
    node.addEventListener("click", async () => {
      const view = node.getAttribute("data-checklist-view");
      if (!view) return;
      await openSelectedHistoricalView(view, `Opened ${view} from QA checklist`);
    });
  });
  document.querySelectorAll("[data-checklist-artifact]").forEach((node) => {
    node.addEventListener("click", async () => {
      const artifact = node.getAttribute("data-checklist-artifact");
      const job = state.ingestionWizard.currentJob;
      if (!artifact || !job?.project_id) return;
      await openHistoricalJobTarget(job, "artifacts", artifact, `Opened raw artifact ${artifact} from QA checklist`);
    });
  });
  document.querySelectorAll("[data-checklist-compare]").forEach((node) => {
    node.addEventListener("click", async () => {
      await openHistoricalComparePanel();
    });
  });
}

async function openSelectedHistoricalView(view, notice) {
  const job = state.ingestionWizard.currentJob;
  if (!job?.project_id) {
    state.ingestionWizard.submitError = "Historical run is not inspectable yet. Refresh projects or inspect output root.";
    renderOverview();
    bindWizardJobActions();
    return;
  }
  await openHistoricalJobTarget(job, view, null, notice);
}

async function assignSelectedHistoricalCompareRole(role) {
  const job = state.ingestionWizard.currentJob;
  await assignHistoricalCompareRole(job, role);
}

async function assignHistoricalCompareRoleById(jobId, role) {
  const job = (state.ingestionWizard.recentJobs || []).find((item) => item.job_id === jobId);
  await assignHistoricalCompareRole(job, role);
}

async function assignHistoricalCompareRole(job, role) {
  if (!job?.project_id) {
    state.ingestionWizard.submitError = "Cannot use this historical run in compare because project_id is not available.";
    renderOverview();
    bindWizardJobActions();
    return;
  }
  if (role === "base") state.compareView.baseId = job.project_id;
  if (role === "candidate") state.compareView.candidateId = job.project_id;
  state.compareView.result = null;
  state.compareView.error = "";
  if (state.currentId !== job.project_id) await loadProjects();
  setView("overview");
  setNavNotice(`Historical run assigned as ${role} for Compare Runs`, "info");
  renderOverview();
  bindWizardJobActions();
}

async function compareSelectedHistoricalJobAgainst(mode) {
  const job = state.ingestionWizard.currentJob;
  if (!job?.project_id) {
    state.ingestionWizard.submitError = "Cannot compare this run because project_id is not available.";
    renderOverview();
    bindWizardJobActions();
    return;
  }
  const other = findHistoricalCompareTarget(job, mode);
  if (!other?.project_id) {
    state.ingestionWizard.submitError = `No ${mode} compare target is available for this historical run.`;
    renderOverview();
    bindWizardJobActions();
    return;
  }
  state.compareView.baseId = mode === "latest" ? other.project_id : other.project_id;
  state.compareView.candidateId = job.project_id;
  state.compareView.result = null;
  state.compareView.error = "";
  await openHistoricalComparePanel(`Compare target set from ${mode} historical run`);
}

async function openHistoricalComparePanel(notice = "Opened Compare Runs from historical job") {
  const job = state.ingestionWizard.currentJob;
  if (job?.project_id && state.currentId !== job.project_id) {
    await loadProjects();
    await selectProject(job.project_id);
  }
  setView("overview");
  setNavNotice(notice, "info");
  if (state.current) renderCurrentProject();
}

async function openHistoricalJobTarget(job, view, artifactPath = null, notice = "") {
  await loadProjects();
  await selectProject(job.project_id);
  setView(view);
  if (artifactPath) {
    await openArtifact(artifactPath);
  }
  setNavNotice(notice, "info");
  if (state.current) renderCurrentProject();
}

function scheduleJobPolling() {
  const jobId = state.ingestionWizard.currentJobId;
  if (!jobId) return;
  if (state.ingestionWizard.pollingTimer) {
    clearTimeout(state.ingestionWizard.pollingTimer);
    state.ingestionWizard.pollingTimer = null;
  }
  const tick = async () => {
    try {
      const job = await api(`/api/ingestion/jobs/${encodeURIComponent(jobId)}`);
      state.ingestionWizard.currentJob = job;
      await loadIngestionJobs();
      renderOverview();
      bindWizardJobActions();
      if (job.status === "queued" || job.status === "running") {
        state.ingestionWizard.pollingTimer = setTimeout(tick, 3000);
      } else {
        await loadProjects();
        renderOverview();
        bindWizardJobActions();
        state.ingestionWizard.pollingTimer = null;
      }
    } catch (_error) {
      state.ingestionWizard.pollingTimer = setTimeout(tick, 4000);
    }
  };
  state.ingestionWizard.pollingTimer = setTimeout(tick, 1200);
}

function renderCompareRunsPanel() {
  const compare = state.compareView || {};
  const baseId = compare.baseId || state.currentId || "";
  const candidateId = compare.candidateId || "";
  const projectOptions = state.projects.map((project) => `
    <option value="${escapeHtml(project.project_id)}">${escapeHtml(project.name)}</option>
  `).join("");
  return `
    <section class="compare-runs panel">
      <div class="compare-header">
        <div>
          <p class="eyebrow">Compare Runs</p>
          <h3>Canon drift & cross-run diff</h3>
          <p class="muted">Read-only comparison. Labels are metric-based observability, not canon truth.</p>
        </div>
        <button type="button" id="compare-runs-run">${compare.loading ? "Comparing..." : "Compare"}</button>
      </div>
      <div class="compare-controls">
        <label>Base run
          <select id="compare-base-run">
            ${projectOptions}
          </select>
        </label>
        <label>Candidate run
          <select id="compare-candidate-run">
            <option value="">select candidate</option>
            ${projectOptions}
          </select>
        </label>
      </div>
      ${compare.error ? `<div class="nav-notice warning">${escapeHtml(compare.error)}</div>` : ""}
      ${compare.result ? renderCompareResult(compare.result) : `<p class="muted">Select two runs to compare canon stability, review pressure, invariants, and manifest availability.</p>`}
    </section>
  `;
}

function bindCompareRunsInteractions() {
  const base = $("compare-base-run");
  const candidate = $("compare-candidate-run");
  if (base) base.value = state.compareView.baseId || state.currentId || "";
  if (candidate) candidate.value = state.compareView.candidateId || "";
  base?.addEventListener("change", (event) => {
    state.compareView.baseId = event.target.value || "";
    state.compareView.result = null;
  });
  candidate?.addEventListener("change", (event) => {
    state.compareView.candidateId = event.target.value || "";
    state.compareView.result = null;
  });
  $("compare-runs-run")?.addEventListener("click", compareSelectedRuns);
  document.querySelectorAll("[data-compare-project]").forEach((node) => {
    node.addEventListener("click", () => selectProject(node.dataset.compareProject));
  });
  document.querySelectorAll("[data-compare-artifact]").forEach((node) => {
    node.addEventListener("click", () => openCompareArtifact(node.dataset.compareProjectId || "", node.dataset.compareArtifact || ""));
  });
}

async function compareSelectedRuns() {
  const baseId = $("compare-base-run")?.value || state.currentId || "";
  const candidateId = $("compare-candidate-run")?.value || "";
  if (!baseId || !candidateId) {
    state.compareView = { ...state.compareView, baseId, candidateId, result: null, error: "Select both base and candidate runs." };
    renderOverview();
    return;
  }
  state.compareView = { ...state.compareView, baseId, candidateId, loading: true, error: "" };
  renderOverview();
  try {
    const [basePayload, candidatePayload] = await Promise.all([
      baseId === state.currentId ? Promise.resolve(state.current) : api(`/api/projects/${encodeURIComponent(baseId)}`),
      candidateId === state.currentId ? Promise.resolve(state.current) : api(`/api/projects/${encodeURIComponent(candidateId)}`),
    ]);
    const [baseManifest, candidateManifest] = await Promise.all([
      fetchArtifactJson(baseId, "run_comparability_manifest.json"),
      fetchArtifactJson(candidateId, "run_comparability_manifest.json"),
    ]);
    const result = buildRunComparison(basePayload, candidatePayload, baseManifest, candidateManifest);
    state.compareView = { baseId, candidateId, loading: false, result, error: "" };
  } catch (error) {
    state.compareView = { ...state.compareView, loading: false, result: null, error: error.message || String(error) };
  }
  renderOverview();
}

async function fetchArtifactJson(projectId, artifactPath) {
  try {
    const data = await api(`/api/projects/${encodeURIComponent(projectId)}/artifact?path=${encodeURIComponent(artifactPath)}`);
    return data.kind === "json" ? data.json : null;
  } catch (_error) {
    return null;
  }
}

async function openCompareArtifact(projectId, artifactPath) {
  if (!projectId || !artifactPath) return;
  if (projectId !== state.currentId) await selectProject(projectId);
  setView("artifacts");
  openArtifact(artifactPath);
}

function buildRunComparison(basePayload, candidatePayload, baseManifest, candidateManifest) {
  const baseEntities = canonicalEntityIndex(basePayload);
  const candidateEntities = canonicalEntityIndex(candidatePayload);
  const baseKeys = new Set(Object.keys(baseEntities));
  const candidateKeys = new Set(Object.keys(candidateEntities));
  const sharedKeys = [...baseKeys].filter((key) => candidateKeys.has(key)).sort();
  const onlyBase = [...baseKeys].filter((key) => !candidateKeys.has(key)).sort();
  const onlyCandidate = [...candidateKeys].filter((key) => !baseKeys.has(key)).sort();
  const changed = sharedKeys.map((key) => entityDriftRow(key, baseEntities[key], candidateEntities[key])).filter((row) => row.change_count > 0);
  const review = reviewPressureDiff(basePayload, candidatePayload);
  const invariants = invariantDiff(basePayload, candidatePayload);
  const comparability = comparabilityDiff(baseManifest, candidateManifest);
  return {
    base: projectSummaryForCompare(basePayload),
    candidate: projectSummaryForCompare(candidatePayload),
    entity_counts: {
      base: Object.keys(baseEntities).length,
      candidate: Object.keys(candidateEntities).length,
      matched: sharedKeys.length,
      only_base: onlyBase.length,
      only_candidate: onlyCandidate.length,
      changed: changed.length,
    },
    only_base: onlyBase.map((key) => entityCompareSummary(baseEntities[key])),
    only_candidate: onlyCandidate.map((key) => entityCompareSummary(candidateEntities[key])),
    changed,
    review,
    invariants,
    comparability,
  };
}

function canonicalEntityIndex(payload) {
  const canon = payload.canon || {};
  const entities = [...(canon.primaries || [])];
  const out = {};
  for (const entity of entities) {
    const key = compareEntityKey(entity);
    if (key && !out[key]) out[key] = entity;
  }
  return out;
}

function compareEntityKey(entity) {
  const kind = normalizeKey(entity.entity_kind || "entity");
  const id = normalizeKey(entity.preferred_slug || entity.canonical_name || "");
  return id ? `${kind}:${id}` : "";
}

function entityCompareSummary(entity) {
  return {
    key: compareEntityKey(entity),
    canonical_name: entity.canonical_name || "not available",
    preferred_slug: entity.preferred_slug || "not available",
    entity_kind: entity.entity_kind || "not available",
    confidence: entity.confidence,
    aliases: entity.aliases || [],
    source_mentions: entity.source_mentions || [],
  };
}

function entityDriftRow(key, baseEntity, candidateEntity) {
  const aliasDiff = setDiff(baseEntity.aliases || [], candidateEntity.aliases || []);
  const mentionDiff = setDiff(baseEntity.source_mentions || [], candidateEntity.source_mentions || []);
  const chapterDiff = setDiff(baseEntity.chapter_refs || [], candidateEntity.chapter_refs || []);
  const relationshipDelta = (candidateEntity.relationships || []).length - (baseEntity.relationships || []).length;
  const keyFactDelta = (candidateEntity.key_facts || []).length - (baseEntity.key_facts || []).length;
  const changes = [];
  if ((baseEntity.canonical_name || "") !== (candidateEntity.canonical_name || "")) changes.push("canonical_name");
  if ((baseEntity.preferred_slug || "") !== (candidateEntity.preferred_slug || "")) changes.push("preferred_slug");
  if ((baseEntity.entity_kind || "") !== (candidateEntity.entity_kind || "")) changes.push("entity_kind");
  if ((baseEntity.entity_subkind || "") !== (candidateEntity.entity_subkind || "")) changes.push("entity_subkind");
  if ((baseEntity.review_state || "") !== (candidateEntity.review_state || "")) changes.push("review_state");
  if ((baseEntity.confidence ?? null) !== (candidateEntity.confidence ?? null)) changes.push("confidence");
  if (aliasDiff.added.length || aliasDiff.removed.length) changes.push("aliases");
  if (mentionDiff.added.length || mentionDiff.removed.length) changes.push("source_mentions");
  if (chapterDiff.added.length || chapterDiff.removed.length) changes.push("chapter_refs");
  if (relationshipDelta) changes.push("relationships");
  if (keyFactDelta) changes.push("key_facts");
  return {
    key,
    base: entityCompareSummary(baseEntity),
    candidate: entityCompareSummary(candidateEntity),
    changes,
    change_count: changes.length,
    alias_diff: aliasDiff,
    source_mention_diff: mentionDiff,
    chapter_ref_diff: chapterDiff,
    relationship_delta: relationshipDelta,
    key_fact_delta: keyFactDelta,
  };
}

function setDiff(baseValues, candidateValues) {
  const base = new Map((baseValues || []).map((value) => [normalizeKey(value), value]).filter(([key]) => key));
  const candidate = new Map((candidateValues || []).map((value) => [normalizeKey(value), value]).filter(([key]) => key));
  return {
    added: [...candidate.entries()].filter(([key]) => !base.has(key)).map(([, value]) => value),
    removed: [...base.entries()].filter(([key]) => !candidate.has(key)).map(([, value]) => value),
  };
}

function reviewPressureDiff(basePayload, candidatePayload) {
  const base = reviewMetrics(basePayload);
  const candidate = reviewMetrics(candidatePayload);
  const totalDelta = candidate.total - base.total;
  const highDelta = candidate.high - base.high;
  return { base, candidate, total_delta: totalDelta, high_delta: highDelta, label: metricLabel(totalDelta + highDelta) };
}

function reviewMetrics(payload) {
  const queue = ((payload.canon || {}).review_queue || {});
  const items = queue.items || [];
  const counts = queue.counts_by_severity || {};
  return {
    total: Number(queue.item_count ?? items.length ?? 0),
    high: Number(counts.high || 0),
    medium: Number(counts.medium || 0),
    low: Number(counts.low || 0),
    type_counts: queue.counts_by_type || {},
    with_candidates: items.filter((item) => (item.candidate_entities || []).length).length,
    with_evidence: items.filter((item) => (item.evidence || []).length).length,
  };
}

function invariantDiff(basePayload, candidatePayload) {
  const base = invariantMetrics(basePayload);
  const candidate = invariantMetrics(candidatePayload);
  return {
    base,
    candidate,
    failure_delta: candidate.failure_count - base.failure_count,
    warning_delta: candidate.warning_count - base.warning_count,
    failing_added: setDiff(base.failing_checks, candidate.failing_checks).added,
    failing_removed: setDiff(base.failing_checks, candidate.failing_checks).removed,
    warning_added: setDiff(base.warning_checks, candidate.warning_checks).added,
    warning_removed: setDiff(base.warning_checks, candidate.warning_checks).removed,
  };
}

function invariantMetrics(payload) {
  const invariants = ((payload.health || {}).semantic_invariants || {});
  const checks = invariants.checks || invariants.failing_checks || [];
  return {
    status: invariants.status || "not available",
    failure_count: Number(invariants.failure_count || 0),
    warning_count: Number(invariants.warning_count || 0),
    failing_checks: checks.filter((check) => String(check.status || "").toLowerCase() === "fail").map((check) => check.name || "unknown"),
    warning_checks: checks.filter((check) => String(check.status || "").toLowerCase() === "warn").map((check) => check.name || "unknown"),
  };
}

function comparabilityDiff(baseManifest, candidateManifest) {
  return {
    base_available: !!baseManifest,
    candidate_available: !!candidateManifest,
    base_summary: manifestSummary(baseManifest),
    candidate_summary: manifestSummary(candidateManifest),
  };
}

function manifestSummary(manifest) {
  if (!manifest || typeof manifest !== "object") return { status: "not available" };
  const warnings = manifest.warnings || manifest.comparability_warnings || [];
  return {
    status: manifest.status || manifest.comparable || manifest.semantic_quality_comparable || "available",
    schema_version: manifest.schema_version || "not available",
    warnings: Array.isArray(warnings) ? warnings.slice(0, 6) : [],
    keys: Object.keys(manifest).slice(0, 12),
  };
}

function projectSummaryForCompare(payload) {
  return {
    project_id: payload.project.project_id,
    name: payload.project.name,
  };
}

function metricLabel(delta) {
  if (delta < 0) return "improved";
  if (delta > 0) return "worsened";
  return "unchanged";
}

function renderCompareResult(result) {
  return `
    <div class="compare-result">
      <div class="compare-run-actions">
        <button type="button" class="inline-action" data-compare-project="${escapeHtml(result.base.project_id)}">Open base run</button>
        <button type="button" class="inline-action" data-compare-project="${escapeHtml(result.candidate.project_id)}">Open candidate run</button>
      </div>
      <div class="stats-grid">
        <div class="stat-card"><span>Matched primaries</span><strong>${fmtCount(result.entity_counts.matched)}</strong></div>
        <div class="stat-card"><span>Only base</span><strong>${fmtCount(result.entity_counts.only_base)}</strong></div>
        <div class="stat-card"><span>Only candidate</span><strong>${fmtCount(result.entity_counts.only_candidate)}</strong></div>
        <div class="stat-card"><span>Changed matched</span><strong>${fmtCount(result.entity_counts.changed)}</strong></div>
      </div>
      ${renderCompareSection("Review Pressure", renderReviewDiff(result.review))}
      ${renderCompareSection("Semantic Invariants", renderInvariantDiff(result.invariants, result.base.project_id, result.candidate.project_id))}
      ${renderCompareSection("Comparability Manifest", renderComparabilityDiff(result.comparability, result.base.project_id, result.candidate.project_id))}
      ${renderCompareSection("Entities only in base", renderEntityCompareList(result.only_base, result.base.project_id))}
      ${renderCompareSection("Entities only in candidate", renderEntityCompareList(result.only_candidate, result.candidate.project_id))}
      ${renderCompareSection("Matched entity drift", renderChangedEntityRows(result.changed, result.base.project_id, result.candidate.project_id))}
    </div>
  `;
}

function renderCompareSection(title, body) {
  return `<details class="compare-section" open><summary>${escapeHtml(title)}</summary>${body}</details>`;
}

function renderEntityTriagePanel() {
  const triage = buildEntityTriage(state.current, state.compareView?.result || null);
  return `
    <section class="entity-triage panel">
      <div class="triage-header">
        <div>
          <p class="eyebrow">Entity Triage</p>
          <h3>Diagnostic priority</h3>
          <p class="muted">Observability-only ranking. No semantic truth claims or automated fixes.</p>
        </div>
        <span class="badge">${triage.comparison_active ? `compare: ${escapeHtml(triage.base_name)} → ${escapeHtml(triage.candidate_name)}` : "single run"}</span>
      </div>
      <div class="stats-grid">
        <div class="stat-card"><span>Entities flagged</span><strong>${fmtCount(triage.summary.flagged)}</strong></div>
        <div class="stat-card"><span>High priority</span><strong>${fmtCount(triage.summary.high)}</strong></div>
        <div class="stat-card"><span>Medium priority</span><strong>${fmtCount(triage.summary.medium)}</strong></div>
        <div class="stat-card"><span>Top reasons</span><strong style="font-size:16px">${escapeHtml(triage.summary.top_reasons.join(", ") || "not available")}</strong></div>
      </div>
      ${triage.rows.length ? `<div class="triage-list">${triage.rows.map((row) => renderEntityTriageRow(row)).join("")}</div>` : `<p class="muted">No entity triage signals available.</p>`}
    </section>
  `;
}

function buildEntityTriage(currentPayload, compareResult) {
  const canon = currentPayload?.canon || {};
  const currentEntities = [...(canon.primaries || []), ...(canon.review_entities || [])];
  const rows = currentEntities.map((entity) => triageRowForEntity(entity, compareResult)).filter(Boolean).sort((a, b) => b.score - a.score || a.name.localeCompare(b.name));
  const high = rows.filter((row) => row.score >= 6).length;
  const medium = rows.filter((row) => row.score >= 3 && row.score < 6).length;
  const reasonCounts = {};
  for (const row of rows) {
    for (const reason of row.reasons) {
      reasonCounts[reason.key] = (reasonCounts[reason.key] || 0) + 1;
    }
  }
  const topReasons = Object.entries(reasonCounts).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([key]) => key.replaceAll("_", " "));
  return {
    comparison_active: !!compareResult,
    base_name: compareResult?.base?.name || "",
    candidate_name: compareResult?.candidate?.name || currentPayload?.project?.name || "",
    summary: { flagged: rows.length, high, medium, top_reasons: topReasons },
    rows: rows.slice(0, 24),
  };
}

function triageRowForEntity(entity, compareResult) {
  const canonical = canonicalizationSummary(entity) || {};
  const terms = new Set([normalizeKey(entity.canonical_name), normalizeKey(entity.preferred_slug), ...(entity.aliases || []).map(normalizeKey), ...(entity.source_mentions || []).map(normalizeKey)].filter(Boolean));
  const invariantRefs = invariantReferencesForTerms(terms);
  const reasons = [];
  let score = 0;
  const confidence = typeof canonical.confidence === "number" ? canonical.confidence : entity.confidence;
  if (typeof confidence === "number" && confidence < 0.75) {
    reasons.push({ key: "low_confidence", label: `low confidence ${confidence.toFixed(2)}`, weight: 3 });
    score += 3;
  }
  if ((canonical.review_pressure_count || 0) > 0) {
    reasons.push({ key: "review_pressure", label: `review pressure ${canonical.review_pressure_count}`, weight: 2 });
    score += Math.min(3, canonical.review_pressure_count);
  }
  if ((canonical.nearby_review_entity_count || 0) > 0) {
    reasons.push({ key: "nearby_review_candidates", label: `nearby review ${canonical.nearby_review_entity_count}`, weight: 2 });
    score += 2;
  }
  for (const signal of canonical.risk_signals || []) {
    const key = normalizeKey(signal.label || "risk");
    reasons.push({ key, label: `${signal.label}: ${signal.value}`, weight: 1 });
    score += 1;
  }
  if (invariantRefs.length) {
    reasons.push({ key: "invariant_reference", label: `invariant refs ${invariantRefs.length}`, weight: 2 });
    score += Math.min(3, invariantRefs.length);
  }
  const drift = triageDriftForEntity(entity, compareResult);
  for (const reason of drift.reasons) {
    reasons.push(reason);
    score += reason.weight;
  }
  if (!reasons.length) return null;
  return {
    key: canonEntityKey(entity),
    name: entity.canonical_name || "not available",
    entity_kind: entity.entity_kind || "not available",
    entity_subkind: entity.entity_subkind || "",
    review_state: entity.review_state || entity.note_role || "not available",
    confidence: confidence,
    score,
    priority: score >= 6 ? "high" : score >= 3 ? "medium" : "low",
    review_pressure_count: canonical.review_pressure_count || 0,
    invariant_reference_count: invariantRefs.length,
    invariant_references: invariantRefs,
    reasons,
    artifact_refs: canonical.artifact_refs || [],
  };
}

function triageDriftForEntity(entity, compareResult) {
  if (!compareResult) return { reasons: [] };
  const key = compareEntityKey(entity);
  const change = (compareResult.changed || []).find((row) => row.key === key || row.candidate?.key === key || row.base?.key === key);
  if (!change) return { reasons: [] };
  const reasons = [];
  if (change.changes.includes("canonical_name")) reasons.push({ key: "canonical_drift", label: "canonical drift", weight: 2 });
  if (change.changes.includes("preferred_slug")) reasons.push({ key: "slug_drift", label: "slug drift", weight: 2 });
  if (change.changes.includes("review_state")) reasons.push({ key: "review_state_changed", label: "review_state changed", weight: 2 });
  if ((change.alias_diff?.added?.length || 0) + (change.alias_diff?.removed?.length || 0) > 0) reasons.push({ key: "alias_drift", label: "alias drift", weight: 2 });
  if ((change.source_mention_diff?.added?.length || 0) + (change.source_mention_diff?.removed?.length || 0) > 0) reasons.push({ key: "source_mention_drift", label: "source mention drift", weight: 2 });
  if (change.relationship_delta) reasons.push({ key: "relationship_count_drift", label: `relationship drift ${change.relationship_delta > 0 ? "+" : ""}${change.relationship_delta}`, weight: 1 });
  return { reasons };
}

function invariantReferencesForTerms(terms) {
  const checks = state.current?.health?.semantic_invariants?.checks || [];
  const matches = [];
  for (const check of checks) {
    const pool = [
      ...(check.affected_entities || []),
      ...(check.affected_targets || []),
      ...(check.review_terms || []),
    ];
    if (pool.some((value) => terms.has(normalizeKey(value)))) {
      matches.push(check.name || "unknown");
    }
  }
  return [...new Set(matches)].slice(0, 8);
}

function renderEntityTriageRow(row) {
  return `
    <details class="triage-row ${escapeHtml(row.priority)}">
      <summary>
        <span class="badge triage-priority ${escapeHtml(row.priority)}">${escapeHtml(row.priority)}</span>
        <strong>${escapeHtml(row.name)}</strong>
        <span class="muted">${escapeHtml(row.entity_kind)}${row.entity_subkind ? ` / ${escapeHtml(row.entity_subkind)}` : ""}</span>
        <span class="badge">score ${escapeHtml(row.score)}</span>
        <span class="badge">${escapeHtml(row.review_state)}</span>
      </summary>
      <div class="triage-body">
        <p><strong>Confidence:</strong> ${row.confidence === undefined || row.confidence === null ? "not available" : escapeHtml(row.confidence)}</p>
        <p><strong>Review pressure:</strong> ${fmtCount(row.review_pressure_count)} · <strong>Invariant refs:</strong> ${fmtCount(row.invariant_reference_count)}</p>
        <p><strong>Reasons:</strong> ${row.reasons.map((reason) => `<span class="badge">${escapeHtml(reason.label)}</span>`).join("")}</p>
        <div class="triage-actions">
          <button type="button" class="inline-action" data-triage-canon="${escapeHtml(row.key)}">Open in Canon</button>
          <button type="button" class="inline-action" data-triage-graph="${escapeHtml(row.key)}">Open in Graph</button>
          <button type="button" class="inline-action" data-triage-review="${escapeHtml(row.name)}">Open Review Context</button>
          ${row.invariant_references[0] ? `<button type="button" class="inline-action" data-triage-artifact="semantic_invariants_audit.json">Open invariant artifact</button>` : ""}
          ${row.artifact_refs[0] ? `<button type="button" class="inline-action" data-triage-artifact="${escapeHtml(row.artifact_refs[0])}">Open related artifact</button>` : ""}
        </div>
        ${row.invariant_references.length ? `<p><strong>Invariant checks:</strong> ${row.invariant_references.map((value) => `<span class="badge warning-badge">${escapeHtml(value)}</span>`).join("")}</p>` : `<p class="muted">Invariant context: not available</p>`}
      </div>
    </details>
  `;
}

function bindEntityTriageInteractions() {
  document.querySelectorAll("[data-triage-canon]").forEach((node) => {
    node.addEventListener("click", () => {
      const term = node.dataset.triageCanon || "";
      if (term) navigateToCanonTerm(term, { from: "Entity Triage" });
    });
  });
  document.querySelectorAll("[data-triage-graph]").forEach((node) => {
    node.addEventListener("click", () => {
      const term = node.dataset.triageGraph || "";
      if (term) navigateToGraphTerm(term, { from: "Entity Triage" });
    });
  });
  document.querySelectorAll("[data-triage-review]").forEach((node) => {
    node.addEventListener("click", () => {
      const term = node.dataset.triageReview || "";
      if (term) navigateToReviewContext(term, { from: "Entity Triage" });
    });
  });
  document.querySelectorAll("[data-triage-artifact]").forEach((node) => {
    node.addEventListener("click", () => {
      const artifact = node.dataset.triageArtifact || "";
      if (!artifact) return;
      setView("artifacts");
      openArtifact(artifact);
    });
  });
}

function renderReviewDiff(review) {
  return `
    <p><span class="diff-label ${escapeHtml(review.label)}">${escapeHtml(review.label)}</span> total delta: ${escapeHtml(review.total_delta)}, high delta: ${escapeHtml(review.high_delta)}</p>
    <table class="table compact-table"><thead><tr><th>Metric</th><th>Base</th><th>Candidate</th></tr></thead><tbody>
      ${["total", "high", "medium", "low", "with_candidates", "with_evidence"].map((key) => `
        <tr><td>${escapeHtml(key)}</td><td>${fmtCount(review.base[key])}</td><td>${fmtCount(review.candidate[key])}</td></tr>
      `).join("")}
    </tbody></table>
    <p><strong>Review types:</strong> ${renderTypeCountDiff(review.base.type_counts, review.candidate.type_counts)}</p>
  `;
}

function renderTypeCountDiff(baseCounts, candidateCounts) {
  const keys = [...new Set([...Object.keys(baseCounts || {}), ...Object.keys(candidateCounts || {})])].sort();
  if (!keys.length) return `<span class="muted">not available</span>`;
  return keys.map((key) => `<span class="badge">${escapeHtml(key)}: ${fmtCount(baseCounts[key] || 0)} → ${fmtCount(candidateCounts[key] || 0)}</span>`).join("");
}

function renderInvariantDiff(invariants, baseId, candidateId) {
  const label = metricLabel(invariants.failure_delta + invariants.warning_delta);
  return `
    <div class="compare-run-actions">
      <button type="button" class="inline-action" data-compare-project-id="${escapeHtml(baseId)}" data-compare-artifact="semantic_invariants_audit.json">Open base invariants</button>
      <button type="button" class="inline-action" data-compare-project-id="${escapeHtml(candidateId)}" data-compare-artifact="semantic_invariants_audit.json">Open candidate invariants</button>
    </div>
    <p><span class="diff-label ${escapeHtml(label)}">${escapeHtml(label)}</span> failures delta: ${escapeHtml(invariants.failure_delta)}, warnings delta: ${escapeHtml(invariants.warning_delta)}</p>
    <table class="table compact-table"><thead><tr><th>Metric</th><th>Base</th><th>Candidate</th></tr></thead><tbody>
      <tr><td>Status</td><td>${escapeHtml(invariants.base.status)}</td><td>${escapeHtml(invariants.candidate.status)}</td></tr>
      <tr><td>Failures</td><td>${fmtCount(invariants.base.failure_count)}</td><td>${fmtCount(invariants.candidate.failure_count)}</td></tr>
      <tr><td>Warnings</td><td>${fmtCount(invariants.base.warning_count)}</td><td>${fmtCount(invariants.candidate.warning_count)}</td></tr>
    </tbody></table>
    <p><strong>Failing checks added:</strong> ${renderBadgesOrUnavailable(invariants.failing_added)}</p>
    <p><strong>Failing checks removed:</strong> ${renderBadgesOrUnavailable(invariants.failing_removed)}</p>
    <p><strong>Warning checks added:</strong> ${renderBadgesOrUnavailable(invariants.warning_added)}</p>
    <p><strong>Warning checks removed:</strong> ${renderBadgesOrUnavailable(invariants.warning_removed)}</p>
  `;
}

function renderComparabilityDiff(comparability, baseId, candidateId) {
  return `
    <div class="compare-run-actions">
      <button type="button" class="inline-action" data-compare-project-id="${escapeHtml(baseId)}" data-compare-artifact="run_comparability_manifest.json">Open base manifest</button>
      <button type="button" class="inline-action" data-compare-project-id="${escapeHtml(candidateId)}" data-compare-artifact="run_comparability_manifest.json">Open candidate manifest</button>
    </div>
    <table class="table compact-table"><thead><tr><th>Metric</th><th>Base</th><th>Candidate</th></tr></thead><tbody>
      <tr><td>Available</td><td>${comparability.base_available ? "yes" : "not available"}</td><td>${comparability.candidate_available ? "yes" : "not available"}</td></tr>
      <tr><td>Status</td><td>${escapeHtml(comparability.base_summary.status)}</td><td>${escapeHtml(comparability.candidate_summary.status)}</td></tr>
      <tr><td>Schema</td><td>${escapeHtml(comparability.base_summary.schema_version || "not available")}</td><td>${escapeHtml(comparability.candidate_summary.schema_version || "not available")}</td></tr>
    </tbody></table>
    <p><strong>Base warnings:</strong> ${renderBadgesOrUnavailable(comparability.base_summary.warnings || [])}</p>
    <p><strong>Candidate warnings:</strong> ${renderBadgesOrUnavailable(comparability.candidate_summary.warnings || [])}</p>
  `;
}

function renderEntityCompareList(rows, projectId) {
  if (!rows.length) return `<p class="muted">not available</p>`;
  return `<div class="compare-entity-list">${rows.slice(0, 24).map((row) => `
    <div class="compare-entity-card">
      <strong>${escapeHtml(row.canonical_name)}</strong>
      <small>${escapeHtml(row.entity_kind)} · ${escapeHtml(row.preferred_slug)} · confidence ${escapeHtml(row.confidence === undefined ? "n/a" : row.confidence)}</small>
      <button type="button" class="inline-action" data-compare-project="${escapeHtml(projectId)}">Open run</button>
    </div>
  `).join("")}</div>`;
}

function renderChangedEntityRows(rows, baseId, candidateId) {
  if (!rows.length) return `<p class="muted">No matched entity drift detected by conservative key matching.</p>`;
  return rows.slice(0, 30).map((row) => `
    <details class="compare-entity-drift">
      <summary><strong>${escapeHtml(row.base.canonical_name)}</strong> <span class="muted">→</span> <strong>${escapeHtml(row.candidate.canonical_name)}</strong> ${row.changes.map((change) => `<span class="badge">${escapeHtml(change)}</span>`).join("")}</summary>
      <div class="compare-run-actions">
        <button type="button" class="inline-action" data-compare-project="${escapeHtml(baseId)}">Open base run</button>
        <button type="button" class="inline-action" data-compare-project="${escapeHtml(candidateId)}">Open candidate run</button>
      </div>
      <table class="table compact-table"><tbody>
        <tr><th>Slug</th><td>${escapeHtml(row.base.preferred_slug)}</td><td>${escapeHtml(row.candidate.preferred_slug)}</td></tr>
        <tr><th>Kind</th><td>${escapeHtml(row.base.entity_kind)}</td><td>${escapeHtml(row.candidate.entity_kind)}</td></tr>
        <tr><th>Confidence</th><td>${escapeHtml(row.base.confidence === undefined ? "n/a" : row.base.confidence)}</td><td>${escapeHtml(row.candidate.confidence === undefined ? "n/a" : row.candidate.confidence)}</td></tr>
        <tr><th>Relationships Δ</th><td colspan="2">${escapeHtml(row.relationship_delta)}</td></tr>
        <tr><th>Key facts Δ</th><td colspan="2">${escapeHtml(row.key_fact_delta)}</td></tr>
      </tbody></table>
      <p><strong>Aliases added:</strong> ${renderBadgesOrUnavailable(row.alias_diff.added)}</p>
      <p><strong>Aliases removed:</strong> ${renderBadgesOrUnavailable(row.alias_diff.removed)}</p>
      <p><strong>Source mentions added:</strong> ${renderBadgesOrUnavailable(row.source_mention_diff.added)}</p>
      <p><strong>Source mentions removed:</strong> ${renderBadgesOrUnavailable(row.source_mention_diff.removed)}</p>
      <p><strong>Chapter refs added:</strong> ${renderBadgesOrUnavailable(row.chapter_ref_diff.added)}</p>
      <p><strong>Chapter refs removed:</strong> ${renderBadgesOrUnavailable(row.chapter_ref_diff.removed)}</p>
    </details>
  `).join("");
}

function renderBadgesOrUnavailable(values) {
  if (!values || !values.length) return `<span class="muted">not available</span>`;
  return values.slice(0, 16).map((value) => `<span class="badge">${escapeHtml(value)}</span>`).join("");
}

function renderSemanticHealth(health) {
  const canon = health.canon_stability || {};
  const relationships = health.relationship_integrity || {};
  const review = health.review_pressure || {};
  const materialization = health.materialization_integrity || {};
  const invariants = health.semantic_invariants || {};
  const highlights = health.highlights || [];
  return `
    <section class="semantic-health panel">
      <div class="health-header">
        <div>
          <p class="eyebrow">Semantic Health</p>
          <h3>Run observability</h3>
        </div>
        ${healthStatusBadge(health.overall_status || "unknown")}
      </div>
      ${highlights.length ? `<div class="health-warnings">${highlights.map((item) => `
        <span class="health-warning ${escapeHtml(item.level || "info")}">${escapeHtml(item.message)}</span>
      `).join("")}</div>` : `<p class="muted">No diagnostic warnings derived from available artifacts.</p>`}
      <div class="health-grid">
        ${healthMetricCard("Canon Stability", [
          ["Primaries", canon.canonical_primary_count],
          ["Review entities", canon.review_entity_count],
          ["Collisions", canon.canonical_collision_count],
          ["Ambiguity items", canon.canonical_ambiguity_items],
        ])}
        ${healthMetricCard("Relationship Integrity", [
          ["Edges", relationships.relationship_edge_count],
          ["Unresolved targets", relationships.unresolved_relationship_targets],
          ["Dangling edges", relationships.dangling_relationship_edges],
        ])}
        ${healthMetricCard("Review Pressure", [
          ["Queue size", review.review_queue_size],
          ["High severity", review.high_severity_items],
          ["Medium severity", review.medium_severity_items],
          ["Types", review.review_type_count],
        ])}
        ${healthMetricCard("Materialization Integrity", [
          ["Missing artifacts", materialization.missing_expected_artifacts_count],
          ["Missing primary notes", materialization.missing_primary_notes],
          ["Missing review notes", materialization.missing_review_notes],
          ["Broken wikilinks", materialization.broken_wikilinks === null ? "not available" : materialization.broken_wikilinks],
        ])}
      </div>
      <div class="health-sections">
        ${healthSection("Semantic Invariants", renderInvariantSummary(invariants))}
        ${healthSection("Unresolved Targets", renderUnresolvedSummary(relationships))}
        ${healthSection("Missing Artifacts", renderMissingArtifacts(materialization))}
      </div>
    </section>
  `;
}

function healthStatusBadge(status) {
  const normalized = String(status || "unknown").toLowerCase();
  return `<span class="health-status ${escapeHtml(normalized)}">${escapeHtml(status || "unknown")}</span>`;
}

function healthMetricCard(title, rows) {
  return `
    <div class="health-card">
      <h4>${escapeHtml(title)}</h4>
      <dl class="health-metrics">
        ${rows.map(([label, value]) => `
          <div><dt>${escapeHtml(label)}</dt><dd>${fmtCount(value)}</dd></div>
        `).join("")}
      </dl>
    </div>
  `;
}

function healthSection(title, body) {
  return `
    <details class="health-section" open>
      <summary>${escapeHtml(title)}</summary>
      ${body}
    </details>
  `;
}

function renderInvariantSummary(invariants) {
  const checks = invariants.checks || [];
  const failing = checks.filter((check) => String(check.status || "").toLowerCase() === "fail");
  const warnings = checks.filter((check) => String(check.status || "").toLowerCase() === "warn");
  const statusCounts = invariantStatusCounts(checks, invariants);
  const typeCounts = invariantTypeCounts([...failing, ...warnings]);
  return `
    <div class="health-inline">
      ${healthStatusBadge(invariants.status || "not_available")}
      <span>Failures: <strong>${fmtCount(invariants.failure_count)}</strong></span>
      <span>Warnings: <strong>${fmtCount(invariants.warning_count)}</strong></span>
      <span>Pass: <strong>${fmtCount(statusCounts.pass)}</strong></span>
      <span>Skip: <strong>${fmtCount(statusCounts.skip)}</strong></span>
      <span>Total: <strong>${fmtCount(invariants.total_count === null || invariants.total_count === undefined ? checks.length : invariants.total_count)}</strong></span>
      ${invariants.raw_artifact_path ? `<button class="artifact-link" data-health-artifact="${escapeHtml(invariants.raw_artifact_path)}">Open raw artifact</button>` : ""}
    </div>
    <div class="invariant-summary-grid">
      <div class="invariant-summary-card">
        <h4>By severity/status</h4>
        <p>${renderInvariantStatusBadges(statusCounts)}</p>
      </div>
      <div class="invariant-summary-card">
        <h4>By check type (fail/warn)</h4>
        <p>${renderInvariantTypeBadges(typeCounts)}</p>
      </div>
    </div>
    ${renderInvariantGroup("Failing checks", failing)}
    ${renderInvariantGroup("Warning checks", warnings)}
  `;
}

function invariantStatusCounts(checks, invariants) {
  const fallback = { fail: 0, warn: 0, pass: 0, skip: 0, unknown: 0 };
  for (const check of checks || []) {
    const status = String(check.status || "unknown").toLowerCase();
    if (!(status in fallback)) fallback.unknown += 1;
    else fallback[status] += 1;
  }
  if (checks && checks.length) return fallback;
  return {
    fail: Number(invariants.failure_count || 0),
    warn: Number(invariants.warning_count || 0),
    pass: Number(invariants.pass_count || 0),
    skip: Number(invariants.skip_count || 0),
    unknown: 0,
  };
}

function invariantTypeCounts(checks) {
  const counts = {};
  for (const check of checks || []) {
    const key = String(check.name || "unknown");
    counts[key] = (counts[key] || 0) + 1;
  }
  return counts;
}

function renderInvariantStatusBadges(counts) {
  const ordered = ["fail", "warn", "pass", "skip", "unknown"];
  return ordered
    .filter((status) => (counts[status] || 0) > 0)
    .map((status) => `<span class="badge invariant-status-badge ${escapeHtml(invariantSeverityClass(status))}">${escapeHtml(status)}: ${fmtCount(counts[status])}</span>`)
    .join("") || `<span class="muted">not available</span>`;
}

function renderInvariantTypeBadges(counts) {
  const entries = Object.entries(counts || {}).sort((a, b) => String(a[0]).localeCompare(String(b[0])));
  if (!entries.length) return `<span class="muted">not available</span>`;
  return entries
    .map(([name, count]) => `<span class="badge">${escapeHtml(name)}: ${fmtCount(count)}</span>`)
    .join("");
}

function renderInvariantGroup(title, checks) {
  if (!checks.length) {
    return `<div class="invariant-group"><h4>${escapeHtml(title)}</h4><p class="muted">not available</p></div>`;
  }
  return `
    <div class="invariant-group">
      <h4>${escapeHtml(title)} (${checks.length})</h4>
      <div class="invariant-check-list">
        ${checks.map((check, index) => renderInvariantCheckCard(check, index)).join("")}
      </div>
    </div>
  `;
}

function renderInvariantCheckCard(check, index) {
  const entities = check.affected_entities || [];
  const chapters = check.affected_chapters || [];
  const targets = check.affected_targets || [];
  const reviewTerms = check.review_terms || [];
  const artifacts = check.related_artifacts || [];
  const context = check.raw_context || {};
  const severity = invariantSeverityClass(check.status || check.severity || "unknown");
  return `
    <details class="invariant-check ${escapeHtml(severity)}" ${index < 1 ? "open" : ""}>
      <summary>
        <span class="badge invariant-status-badge ${escapeHtml(severity)}">${escapeHtml(String(check.status || "unknown").toLowerCase())}</span>
        <strong>${escapeHtml(check.name || "unknown_check")}</strong>
        <span class="muted">${escapeHtml(check.summary || "details available")}</span>
      </summary>
      <div class="invariant-check-body">
        <p><strong>Summary:</strong> ${escapeHtml(check.summary || "not available")}</p>
        <p><strong>Severity:</strong> ${escapeHtml(check.severity || "not available")}</p>
        <p><strong>Message:</strong> ${escapeHtml(check.message || "not available")}</p>
        <div class="invariant-actions">
          ${entities[0] ? `<button type="button" class="inline-action" data-health-to-canon="${escapeHtml(entities[0])}">Open entity in Canon</button>` : ""}
          ${entities[0] ? `<button type="button" class="inline-action" data-health-to-graph="${escapeHtml(entities[0])}">Open entity in Graph</button>` : ""}
          ${targets[0] ? `<button type="button" class="inline-action" data-health-to-graph="${escapeHtml(targets[0])}">Open target in Graph</button>` : ""}
          ${reviewTerms[0] ? `<button type="button" class="inline-action" data-health-to-review="${escapeHtml(reviewTerms[0])}">Open review context</button>` : ""}
          ${artifacts[0] ? `<button type="button" class="inline-action" data-health-artifact="${escapeHtml(artifacts[0])}">Open related artifact</button>` : ""}
        </div>
        ${renderInvariantField("Affected entities", entities)}
        ${renderInvariantField("Affected chapters", chapters)}
        ${renderInvariantField("Affected targets", targets)}
        ${renderInvariantField("Affected review terms", reviewTerms)}
        ${renderInvariantField("Related artifacts", artifacts, "warning-badge")}
        ${Object.keys(context).length ? `<details><summary>Raw context (limited)</summary><pre class="frontmatter">${escapeHtml(JSON.stringify(context, null, 2))}</pre></details>` : `<p class="muted">Raw context: not available</p>`}
      </div>
    </details>
  `;
}

function renderInvariantField(label, values, badgeClass = "") {
  if (!values || !values.length) return `<p><strong>${escapeHtml(label)}:</strong> <span class="muted">not available</span></p>`;
  return `
    <p><strong>${escapeHtml(label)}:</strong></p>
    <p>${values.slice(0, 10).map((value) => `<span class="badge ${badgeClass ? escapeHtml(badgeClass) : ""}">${escapeHtml(value)}</span>`).join("")}</p>
  `;
}

function invariantSeverityClass(status) {
  const value = String(status || "").toLowerCase();
  if (value === "fail" || value === "critical") return "critical";
  if (value === "warn" || value === "warning") return "warning";
  if (value === "pass" || value === "healthy") return "healthy";
  return "unknown";
}

function renderUnresolvedSummary(relationships) {
  const targets = relationships.sample_unresolved_targets || [];
  return `
    <p><strong>${fmtCount(relationships.unresolved_relationship_targets)}</strong> unresolved relationship targets derived from graph payload.</p>
    ${targets.length ? `<p>${targets.map((target) => `<span class="badge">${escapeHtml(target)}</span>`).join("")}</p>` : `<p class="muted">No unresolved target samples available.</p>`}
  `;
}

function renderMissingArtifacts(materialization) {
  const missing = materialization.missing_expected_artifacts || [];
  return missing.length
    ? `<p>${missing.map((name) => `<span class="badge warning-badge">${escapeHtml(name)}</span>`).join("")}</p>`
    : `<p class="muted">Expected viewer artifacts are present.</p>`;
}

function bindHealthInteractions() {
  document.querySelectorAll("[data-health-artifact]").forEach((node) => {
    node.addEventListener("click", () => {
      setView("artifacts");
      openArtifact(node.dataset.healthArtifact);
    });
  });
  document.querySelectorAll("[data-health-to-canon]").forEach((node) => {
    node.addEventListener("click", () => {
      const term = node.dataset.healthToCanon || "";
      if (term) navigateToCanonTerm(term, { from: "Invariant Drilldown" });
    });
  });
  document.querySelectorAll("[data-health-to-graph]").forEach((node) => {
    node.addEventListener("click", () => {
      const term = node.dataset.healthToGraph || "";
      if (term) navigateToGraphTerm(term, { from: "Invariant Drilldown" });
    });
  });
  document.querySelectorAll("[data-health-to-review]").forEach((node) => {
    node.addEventListener("click", () => {
      const term = node.dataset.healthToReview || "";
      if (term) navigateToReviewContext(term, { from: "Invariant Drilldown" });
    });
  });
}

function renderNotes() {
  if (!state.current) return;
  const notes = state.current.notes || [];
  const filter = $("note-filter");
  const kindFilter = $("note-kind-filter");
  const tagFilter = $("note-tag-filter");
  const statusFilter = $("note-status-filter");
  const kinds = [...new Set(notes.map((note) => note.kind || note.frontmatter?.kind || note.role).filter(Boolean))].sort();
  const tags = [...new Set(notes.flatMap((note) => note.tags || []))].sort();
  const statuses = [...new Set(notes.map((note) => note.review_state || note.status || note.frontmatter?.review_state || note.frontmatter?.status).filter(Boolean))].sort();
  kindFilter.innerHTML = `<option value="">all kinds</option>${kinds.map((kind) => `<option value="${escapeHtml(kind)}">${escapeHtml(kind)}</option>`).join("")}`;
  tagFilter.innerHTML = `<option value="">all tags</option>${tags.map((tag) => `<option value="${escapeHtml(tag)}">${escapeHtml(tag)}</option>`).join("")}`;
  statusFilter.innerHTML = `<option value="">all status</option>${statuses.map((status) => `<option value="${escapeHtml(status)}">${escapeHtml(status)}</option>`).join("")}`;
  kindFilter.value = state.wikiFilters.kind || "";
  tagFilter.value = state.wikiFilters.tag || "";
  statusFilter.value = state.wikiFilters.status || "";
  filter.value = state.wikiFilters.query || "";
  const draw = () => {
    state.wikiFilters = {
      query: filter.value || "",
      kind: kindFilter.value || "",
      tag: tagFilter.value || "",
      status: statusFilter.value || "",
    };
    const needle = state.wikiFilters.query.toLowerCase();
    $("note-list").innerHTML = notes
      .filter((note) => {
        const searchBlob = `${note.name} ${note.path} ${(note.tags || []).join(" ")} ${note.role} ${(note.aliases || []).join(" ")}`.toLowerCase();
        if (needle && !searchBlob.includes(needle)) return false;
        if (state.wikiFilters.kind && (note.kind || note.frontmatter?.kind || note.role) !== state.wikiFilters.kind) return false;
        if (state.wikiFilters.tag && !(note.tags || []).includes(state.wikiFilters.tag)) return false;
        const noteStatus = note.review_state || note.status || note.frontmatter?.review_state || note.frontmatter?.status || "";
        if (state.wikiFilters.status && noteStatus !== state.wikiFilters.status) return false;
        return true;
      })
      .map((note) => `
        <div class="list-item" data-note="${escapeHtml(note.path)}">
          <strong>${escapeHtml(note.name)}</strong>
          <small>${escapeHtml(note.path)}</small>
          <small>${escapeHtml(note.kind || note.role)} · degree ${escapeHtml(fmtCount(note.degree || 0))} · backlinks ${escapeHtml(fmtCount((note.backlinks || []).length))}</small>
          <small>${(note.tags || []).map((tag) => `<span class="badge">${escapeHtml(tag)}</span>`).join("")}</small>
        </div>
      `).join("");
    document.querySelectorAll("[data-note]").forEach((node) => {
      node.addEventListener("click", () => openNote(node.dataset.note));
    });
  };
  filter.oninput = draw;
  kindFilter.onchange = draw;
  tagFilter.onchange = draw;
  statusFilter.onchange = draw;
  draw();
}

async function openNote(path) {
  const canonicalPath = resolveCanonicalNotePath(path);
  const data = await api(`/api/projects/${encodeURIComponent(state.currentId)}/note?path=${encodeURIComponent(canonicalPath)}`);
  const backlinks = data.backlinks || [];
  const outgoing = data.outgoing_wikilinks || [];
  const local = data.local_graph || {};
  $("note-detail").innerHTML = `
    <h3>${escapeHtml(data.path)}</h3>
    <p>${(data.tags || []).map((tag) => `<span class="badge tag-badge">${escapeHtml(tag)}</span>`).join("")}</p>
    <p class="muted">Degree ${escapeHtml(fmtCount(data.degree || 0))} · backlinks ${escapeHtml(fmtCount(backlinks.length))} · outgoing ${escapeHtml(fmtCount(outgoing.length))}</p>
    <details open><summary>Frontmatter</summary><pre class="frontmatter">${escapeHtml(JSON.stringify(data.frontmatter || {}, null, 2))}</pre></details>
    ${backlinks.length ? `<details open><summary>Backlinks</summary><ul>${backlinks.map((item) => `<li><a href="#" class="wikilink" data-wikilink="${escapeHtml(item)}">${escapeHtml(item)}</a></li>`).join("")}</ul></details>` : `<p class="muted">Backlinks: none.</p>`}
    ${outgoing.length ? `<details open><summary>Outgoing links</summary><ul>${outgoing.map((item) => `<li><a href="#" class="wikilink" data-wikilink="${escapeHtml(item.target || item.label || "")}">[[${escapeHtml(item.label || item.target || "") }]]</a></li>`).join("")}</ul></details>` : `<p class="muted">Outgoing links: none.</p>`}
    ${(local.nodes || []).length ? `<details><summary>Local graph</summary><p class="muted">Nodes ${escapeHtml(fmtCount((local.nodes || []).length))} · edges ${escapeHtml(fmtCount((local.edges || []).length))}</p></details>` : ""}
    <article class="markdown">${renderMarkdown(data.markdown || "")}</article>
  `;
  attachWikiLinkHandlers($("note-detail"));
  selectGraphNodeByNotePath(canonicalPath, { render: false });
  highlightNote(canonicalPath);
}

function renderMarkdown(markdown) {
  const body = markdown.replace(/^---[\s\S]*?---\s*/, "");
  const lines = escapeHtml(body).split("\n");
  let inList = false;
  const out = [];
  for (const line of lines) {
    if (line.startsWith("# ")) out.push(`<h1>${line.slice(2)}</h1>`);
    else if (line.startsWith("## ")) out.push(`<h2>${line.slice(3)}</h2>`);
    else if (line.startsWith("### ")) out.push(`<h3>${line.slice(4)}</h3>`);
    else if (line.startsWith("- ")) {
      if (!inList) out.push("<ul>");
      inList = true;
      out.push(`<li>${linkify(line.slice(2))}</li>`);
    } else {
      if (inList) out.push("</ul>");
      inList = false;
      out.push(line.trim() ? `<p>${linkify(line)}</p>` : "");
    }
  }
  if (inList) out.push("</ul>");
  return out.join("\n");
}

function linkify(text) {
  return text.replace(/\[\[([^\]]+)\]\]/g, (_match, target) => {
    const safeTarget = escapeHtml(target);
    return `<a href="#" class="wikilink" data-wikilink="${safeTarget}">[[${safeTarget}]]</a>`;
  });
}

function attachWikiLinkHandlers(root) {
  root.querySelectorAll("[data-wikilink]").forEach((node) => {
    node.addEventListener("click", (event) => {
      event.preventDefault();
      navigateWikiLink(node.dataset.wikilink || "");
    });
  });
}

function navigateWikiLink(target) {
  const resolved = resolveWikiLink(target);
  if (!resolved) return;
  if (resolved.nodeId) {
    state.selectedGraphNodeId = resolveCanonicalNodeId(resolved.nodeId) || resolved.nodeId;
  }
  if (resolved.notePath) {
    if (state.activeView === "graph") {
      openGraphNote(resolved.notePath, resolved.nodeId);
    } else {
      openNote(resolved.notePath);
    }
  } else if (resolved.nodeId) {
    setView("graph");
    renderGraph();
  }
}

function resolveWikiLink(rawTarget) {
  const target = rawTarget.split("|")[0].split("#")[0].trim();
  const key = normalizeKey(target);
  const graph = state.current && state.current.graph ? state.current.graph : { nodes: [] };
  const notes = state.current && state.current.notes ? state.current.notes : [];
  const node = graph.nodes.find((item) =>
    normalizeKey(item.label) === key ||
    normalizeKey(item.id.split(":").slice(1).join(":")) === key ||
    normalizeKey(item.note_path || "") === key ||
    normalizeKey(lastPathPartWithoutMd(item.note_path || "")) === key
  );
  const note = notes.find((item) =>
    normalizeKey(item.name) === key ||
    normalizeKey(item.path) === key ||
    normalizeKey(lastPathPartWithoutMd(item.path)) === key
  );
  if (!node && !note) return null;
  const nodeId = (node && (node.canonical_node_id || node.id)) || findNodeIdByNotePath(note && note.path);
  const notePath = resolveCanonicalNotePath((node && (node.canonical_note_path || node.note_path)) || (note && note.path) || null);
  return {
    nodeId,
    notePath,
  };
}

function normalizeKey(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\.md$/, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function findNodeIdByNotePath(path) {
  if (!path) return null;
  const canonicalPath = resolveCanonicalNotePath(path);
  const key = normalizeKey(canonicalPath);
  const graph = state.current && state.current.graph ? state.current.graph : { nodes: [] };
  const node = (graph.nodes || []).find((item) => normalizeKey(item.note_path || "") === key || normalizeKey(item.canonical_note_path || "") === key);
  return node ? (node.canonical_node_id || node.id) : null;
}

function lastPathPartWithoutMd(value) {
  const last = String(value || "").split("/").pop() || "";
  return last.replace(/\.md$/, "");
}

function selectGraphNodeByNotePath(path, { render = true } = {}) {
  const nodeId = findNodeIdByNotePath(path);
  if (!nodeId) return;
  state.selectedGraphNodeId = nodeId;
  if (render && state.activeView === "graph") renderGraph();
}

function allCanonEntities() {
  const canon = state.current && state.current.canon ? state.current.canon : {};
  return [
    ...(canon.primaries || []),
    ...(canon.review_entities || []),
  ];
}

function canonEntityKey(entity) {
  return normalizeKey(entity.preferred_slug || entity.canonical_name || "");
}

function findCanonEntityByTerm(term) {
  const key = normalizeKey(term);
  if (!key) return null;
  return allCanonEntities().find((entity) => {
    const aliases = entity.aliases || [];
    return (
      normalizeKey(entity.preferred_slug || "") === key ||
      normalizeKey(entity.canonical_name || "") === key ||
      aliases.some((alias) => normalizeKey(alias) === key)
    );
  }) || null;
}

function findGraphNodeByTerm(term) {
  const key = normalizeKey(term);
  if (!key) return null;
  const graph = state.current && state.current.graph ? state.current.graph : { nodes: [] };
  const matches = (graph.nodes || []).filter((node) => {
    const entity = node.entity || {};
    const chapter = node.chapter || {};
    const aliases = entity.aliases || [];
    return (
      normalizeKey(node.id || "") === key ||
      normalizeKey((node.id || "").split(":").slice(1).join(":")) === key ||
      normalizeKey(node.label || "") === key ||
      normalizeKey(node.note_path || "") === key ||
      normalizeKey(lastPathPartWithoutMd(node.note_path || "")) === key ||
      normalizeKey(entity.preferred_slug || "") === key ||
      normalizeKey(entity.canonical_name || "") === key ||
      normalizeKey(chapter.chapter_id || "") === key ||
      normalizeKey(chapter.chapter_title_original || chapter.chapter_title_canonical || "") === key ||
      aliases.some((alias) => normalizeKey(alias) === key)
    );
  });
  if (!matches.length) return null;
  matches.sort((a, b) => graphNodePreferenceScore(b) - graphNodePreferenceScore(a));
  const best = matches[0];
  const canonicalId = resolveCanonicalNodeId(best.canonical_node_id || best.id || best.note_path || best.label);
  if (!canonicalId) return best;
  return (graph.nodes || []).find((node) => node.id === canonicalId) || best;
}

function graphNodePreferenceScore(node) {
  const kind = String(node.kind || "");
  const degree = Number(node.degree || 0);
  const kindScore = {
    character: 400,
    place: 320,
    object: 280,
    event: 240,
    concept: 180,
    chapter: 120,
    review: 80,
    unresolved: 0,
  }[kind] || 40;
  const hasSummary = node.entity && node.entity.summary ? 20 : 0;
  const hasFacts = node.entity && (node.entity.facts || node.entity.key_facts || []).length ? 15 : 0;
  return kindScore + Math.min(degree, 60) + hasSummary + hasFacts;
}

function findReviewItemsByTerm(term) {
  const key = normalizeKey(term);
  if (!key) return [];
  const queue = state.current && state.current.canon ? state.current.canon.review_queue || {} : {};
  return (queue.items || []).map((item, index) => ({ item, index, key: reviewItemKey(item, index) })).filter(({ item }) => {
    const candidates = item.candidate_entities || [];
    return (
      normalizeKey(item.source_entity || "") === key ||
      normalizeKey(item.target_text || "") === key ||
      candidates.some((candidate) => normalizeKey(candidate.canonical_name || "") === key || normalizeKey(candidate.preferred_slug || "") === key)
    );
  });
}

function reviewItemKey(item, index) {
  return normalizeKey([
    index,
    item.review_type || "",
    item.source_entity || "",
    item.target_text || "",
  ].join(":"));
}

function navigateToGraphTerm(term, { from = "Viewer" } = {}) {
  const node = findGraphNodeByTerm(term);
  if (!node) {
    setNavNotice(`${from}: "${term}" not found in graph.`, "warning");
    if (state.activeView === "canon") renderCanon();
    if (state.activeView === "review") renderReview();
    return false;
  }
  state.selectedGraphNodeId = node.canonical_node_id || node.id;
  const entity = node.entity || {};
  if (Object.keys(entity).length) state.selectedCanonEntityKey = canonEntityKey(entity);
  setNavNotice(`${from}: opened "${node.label || node.id}" in graph.`, "success");
  setView("graph");
  renderGraph();
  renderGraphNodeDetail(node);
  return true;
}

function navigateToCanonTerm(term, { from = "Viewer" } = {}) {
  const entity = findCanonEntityByTerm(term);
  if (!entity) {
    setNavNotice(`${from}: "${term}" not found in canon.`, "warning");
    if (state.activeView === "graph") {
      const selected = findSelectedGraphNode();
      if (selected) renderGraphNodeDetail(selected);
    }
    if (state.activeView === "review") renderReview();
    return false;
  }
  state.selectedCanonEntityKey = canonEntityKey(entity);
  setNavNotice(`${from}: highlighted "${entity.canonical_name || term}" in canon.`, "success");
  setView("canon");
  renderCanon();
  return true;
}

function navigateToReviewContext(term, { from = "Graph" } = {}) {
  const matches = findReviewItemsByTerm(term);
  if (!matches.length) {
    setNavNotice(`${from}: no review queue context found for "${term}".`, "info");
    const selected = findSelectedGraphNode();
    if (selected) renderGraphNodeDetail(selected);
    return false;
  }
  state.selectedReviewItemId = matches[0].key;
  setNavNotice(`${from}: opened review context for "${term}".`, "success");
  setView("review");
  renderReview();
  return true;
}

function findSelectedGraphNode() {
  const graph = state.current && state.current.graph ? state.current.graph : { nodes: [] };
  return (graph.nodes || []).find((item) => item.id === state.selectedGraphNodeId) || null;
}

function highlightNote(path) {
  document.querySelectorAll("[data-note]").forEach((node) => node.classList.toggle("active", node.dataset.note === path));
}

function renderCanon() {
  const canon = state.current.canon;
  const focusEntity = selectedCanonEntity();
  $("view-canon").innerHTML = `
    ${renderNavNotice()}
    <h3>Canonicalization Visibility</h3>
    ${focusEntity ? renderCanonicalizationVisibility(focusEntity, { source: "canon" }) : `<p class="muted">Select entity in Canon or Graph to inspect merge/canonicalization visibility.</p>`}
    <h3>Primaries</h3>
    ${entityTable(canon.primaries)}
    <h3 style="margin-top:24px">Chapters</h3>
    ${chapterTable(canon.chapters)}
    <h3 style="margin-top:24px">Review Entities</h3>
    ${entityTable(canon.review_entities.slice(0, 80))}
  `;
  bindCanonNavigation();
  bindCanonicalizationInteractions();
}

function entityTable(entities) {
  return `<table class="table"><thead><tr><th>Name</th><th>Kind</th><th>Slug</th><th>Summary</th><th>Navigate</th></tr></thead><tbody>
    ${entities.map((entity) => {
      const key = canonEntityKey(entity);
      return `<tr class="${state.selectedCanonEntityKey === key ? "row-highlight" : ""}">
      <td>${escapeHtml(entity.canonical_name)}</td>
      <td>${escapeHtml(entity.entity_kind || "")}</td>
      <td>${escapeHtml(entity.preferred_slug || "")}</td>
      <td>${escapeHtml(entity.summary || "").slice(0, 260)}</td>
      <td>
        <button type="button" class="inline-action" data-canon-inspect="${escapeHtml(key)}">Inspect</button>
        <button type="button" class="inline-action" data-canon-graph="${escapeHtml(key)}">View in graph</button>
      </td>
    </tr>`;
    }).join("")}
  </tbody></table>`;
}

function chapterTable(chapters) {
  return `<table class="table"><thead><tr><th>ID</th><th>Title</th><th>Summary</th></tr></thead><tbody>
    ${chapters.map((chapter) => `<tr>
      <td>${escapeHtml(chapter.chapter_id)}</td>
      <td>${escapeHtml(chapter.chapter_title_original || chapter.chapter_title_canonical || "")}</td>
      <td>${escapeHtml(chapter.chapter_summary || chapter.summary || "").slice(0, 260)}</td>
    </tr>`).join("")}
  </tbody></table>`;
}

function renderReview() {
  const queue = state.current.canon.review_queue || {};
  const items = queue.items || [];
  const severityCounts = deriveReviewSeverityCounts(queue, items);
  const typeCounts = deriveReviewTypeCounts(queue, items);
  const typeOptions = Object.keys(typeCounts).sort((a, b) => a.localeCompare(b));
  const view = state.reviewView || { severity: "", reviewType: "", query: "", sortBy: "severity_desc", quickFilter: "all", candidate: "" };
  const filtered = applyReviewFilters(items, view);
  const sorted = sortReviewItems(filtered, view.sortBy);
  const grouped = groupReviewItemsForPresentation(sorted);
  const quickFiltered = applyReviewQuickFilter({ grouped, filterKey: view.quickFilter || "all" });
  const candidateFiltered = applyReviewCandidateFilter({ grouped: quickFiltered, candidateName: view.candidate || "" });
  const candidateEntries = deriveReviewCandidates(grouped);
  const candidateCount = items.filter((item) => (item.candidate_entities || []).length > 0).length;
  const evidenceCount = items.filter((item) => (item.evidence || []).length > 0).length;
  const highSeverity = severityCounts.high || 0;
  $("view-review").innerHTML = `
    ${renderNavNotice()}
    <div class="review-header panel">
      <div class="review-header-title">
        <p class="eyebrow">Review Queue</p>
        <h3>Deep visibility</h3>
        <p class="muted">Prioriza revisión por severidad, tipo, evidencia y candidatos.</p>
      </div>
      <div class="review-header-actions">
        <button type="button" id="review-open-raw">Open raw review_queue.json</button>
      </div>
    </div>
    <div class="stats-grid">
      <div class="stat-card"><span>Total items</span><strong>${items.length}</strong></div>
      <div class="stat-card"><span>High severity</span><strong>${highSeverity}</strong></div>
      <div class="stat-card"><span>With candidates</span><strong>${candidateCount}</strong></div>
      <div class="stat-card"><span>With evidence</span><strong>${evidenceCount}</strong></div>
      <div class="stat-card"><span>Review types</span><strong>${Object.keys(typeCounts).length}</strong></div>
      <div class="stat-card"><span>Status</span><strong style="font-size:20px">${escapeHtml(queue.status || "unknown")}</strong></div>
    </div>
    <div class="review-summary panel">
      <div class="review-summary-block">
        <h4>By severity</h4>
        <p>${renderCountBadges(severityCounts, "severity")}</p>
      </div>
      <div class="review-summary-block">
        <h4>By review type</h4>
        <p>${renderCountBadges(typeCounts, "type")}</p>
      </div>
    </div>
    ${renderReviewPresentationSummary(grouped)}
    ${renderReviewQuickFilters(view.quickFilter || "all")}
    ${renderReviewCandidateDrilldown(candidateEntries, view.candidate || "")}
    <div class="review-filters panel">
      <label>Severity
        <select id="review-filter-severity">
          <option value="">all</option>
          ${Object.keys(severityCounts).sort((a, b) => reviewSeverityRank(a) - reviewSeverityRank(b)).map((severity) => `
            <option value="${escapeHtml(severity)}" ${view.severity === severity ? "selected" : ""}>${escapeHtml(severity)}</option>
          `).join("")}
        </select>
      </label>
      <label>Review type
        <select id="review-filter-type">
          <option value="">all</option>
          ${typeOptions.map((reviewType) => `
            <option value="${escapeHtml(reviewType)}" ${view.reviewType === reviewType ? "selected" : ""}>${escapeHtml(reviewType)}</option>
          `).join("")}
        </select>
      </label>
      <label>Search
        <input id="review-filter-query" class="search compact" placeholder="source, target, type, evidence..." value="${escapeHtml(view.query || "")}" />
      </label>
      <label>Sort
        <select id="review-sort-by">
          <option value="severity_desc" ${view.sortBy === "severity_desc" ? "selected" : ""}>severity (high → low)</option>
          <option value="review_type_asc" ${view.sortBy === "review_type_asc" ? "selected" : ""}>review_type (A→Z)</option>
          <option value="source_asc" ${view.sortBy === "source_asc" ? "selected" : ""}>source (A→Z)</option>
          <option value="target_asc" ${view.sortBy === "target_asc" ? "selected" : ""}>target (A→Z)</option>
        </select>
      </label>
      <button type="button" id="review-filter-reset">Reset</button>
    </div>
    <div class="review-results panel">
      <p class="muted">Showing ${countRenderedReviewItems(candidateFiltered)} visible grouped entries from ${items.length} raw items</p>
      ${countRenderedReviewItems(candidateFiltered) ? renderReviewPresentationGroups(candidateFiltered) : `<p class="muted">No groups match this filter.</p>`}
    </div>
  `;
  bindReviewQueueInteractions();
}

function deriveReviewSeverityCounts(queue, items) {
  const fromQueue = queue.counts_by_severity || {};
  const fallback = {};
  for (const item of items || []) {
    const severity = String(item.severity || "unknown").toLowerCase();
    fallback[severity] = (fallback[severity] || 0) + 1;
  }
  return Object.keys(fromQueue).length ? fromQueue : fallback;
}

function deriveReviewTypeCounts(queue, items) {
  const fromQueue = queue.counts_by_type || {};
  const fallback = {};
  for (const item of items || []) {
    const reviewType = String(item.review_type || "unknown");
    fallback[reviewType] = (fallback[reviewType] || 0) + 1;
  }
  return Object.keys(fromQueue).length ? fromQueue : fallback;
}

function reviewSeverityRank(severity) {
  const value = String(severity || "").toLowerCase();
  if (value === "high") return 1;
  if (value === "medium") return 2;
  if (value === "low") return 3;
  return 4;
}

function applyReviewFilters(items, view) {
  const query = String(view.query || "").trim().toLowerCase();
  return (items || []).filter((item) => {
    const severity = String(item.severity || "").toLowerCase();
    const reviewType = String(item.review_type || "");
    const metadata = reviewMetadata(item);
    if (view.severity && severity !== String(view.severity).toLowerCase()) return false;
    if (view.reviewType && reviewType !== view.reviewType) return false;
    if (!query) return true;
    const haystack = [
      item.severity,
      item.review_type,
      item.source_entity,
      item.target_text,
      metadata.recommended_action,
      metadata.signal_tier,
      metadata.candidate_status,
      metadata.surface_type,
      metadata.semantic_value,
      metadata.language_hint,
      ...normalizedFutureViewerActions(item),
      ...((item.candidate_entities || []).map((candidate) => `${candidate.canonical_name || ""} ${candidate.entity_kind || ""}`)),
      ...((item.evidence || []).map((entry) => entry.text || "")),
    ].join(" ").toLowerCase();
    return haystack.includes(query);
  });
}

function sortReviewItems(items, sortBy) {
  const sorted = [...(items || [])];
  const byText = (value) => String(value || "").toLowerCase();
  if (sortBy === "review_type_asc") {
    sorted.sort((a, b) => byText(a.review_type).localeCompare(byText(b.review_type)));
  } else if (sortBy === "source_asc") {
    sorted.sort((a, b) => byText(a.source_entity).localeCompare(byText(b.source_entity)));
  } else if (sortBy === "target_asc") {
    sorted.sort((a, b) => byText(a.target_text).localeCompare(byText(b.target_text)));
  } else {
    sorted.sort((a, b) => reviewSeverityRank(a.severity) - reviewSeverityRank(b.severity));
  }
  return sorted;
}

function groupReviewItemsForPresentation(items) {
  const groupsByKey = new Map();
  const ungrouped = [];
  for (const item of items || []) {
    const groupKey = reviewPresentationGroupKey(item);
    if (!groupKey) {
      ungrouped.push(item);
      continue;
    }
    if (!groupsByKey.has(groupKey)) {
      groupsByKey.set(groupKey, {
        group_key: groupKey,
        group_type: reviewPresentationGroupType(item),
        candidate_name: primaryReviewCandidateName(item),
        recommended_action: reviewActionPresentation(item).recommendedAction,
        descriptor_category: reviewMetadata(item).descriptor_category || "",
        equivalent_signal_group: reviewMetadata(item).equivalent_signal_group || "",
        principal: null,
        related_items: [],
        items: [],
      });
    }
    groupsByKey.get(groupKey).items.push(item);
  }
  const groups = [...groupsByKey.values()].map((group) => {
    const sortedItems = sortReviewGroupItems(group.items);
    const principal = sortedItems[0] || null;
    return {
      ...group,
      principal,
      related_items: sortedItems.slice(1),
      items: sortedItems,
    };
  });
  groups.sort((left, right) => {
    const severityDelta = reviewSeverityRank(left.principal?.severity) - reviewSeverityRank(right.principal?.severity);
    if (severityDelta) return severityDelta;
    return String(left.group_key).localeCompare(String(right.group_key));
  });
  return { groups, ungrouped };
}

function reviewPresentationGroupKey(item) {
  const metadata = reviewMetadata(item);
  const candidateName = primaryReviewCandidateName(item);
  const recommendedAction = reviewActionPresentation(item).recommendedAction;
  const descriptorCategory = metadata.descriptor_category || "";
  if (!candidateName || !recommendedAction) return "";
  if (reviewPresentationGroupType(item) === "object_retention_group") {
    return ["object", normalizeKey(candidateName || item.source_entity || item.target_text), recommendedAction].join("|");
  }
  if (!descriptorCategory && !metadata.equivalent_signal_group) return "";
  return [
    "descriptor",
    normalizeKey(candidateName),
    normalizeKey(recommendedAction),
    normalizeKey(descriptorCategory || "uncategorized"),
    normalizeKey(metadata.equivalent_signal_group || ""),
  ].join("|");
}

function reviewPresentationGroupType(item) {
  const metadata = reviewMetadata(item);
  const recommendedAction = reviewActionPresentation(item).recommendedAction;
  const semanticValue = String(metadata.semantic_value || "").toLowerCase();
  if (
    recommendedAction === "review_create_primary" ||
    recommendedAction === "review_keep_secondary" ||
    metadata.candidate_status === "no_clear_existing_primary" ||
    semanticValue.includes("object")
  ) {
    return "object_retention_group";
  }
  return "descriptor_group";
}

function primaryReviewCandidateName(item) {
  const candidates = item?.candidate_entities || [];
  const candidate = candidates.find((entry) => entry.canonical_name || entry.name) || null;
  return candidate?.canonical_name || candidate?.name || item?.source_entity || item?.target_text || "";
}

function sortReviewGroupItems(items) {
  return [...(items || [])].sort((left, right) => {
    const leftPrimary = reviewItemPrincipalScore(left);
    const rightPrimary = reviewItemPrincipalScore(right);
    if (leftPrimary !== rightPrimary) return rightPrimary - leftPrimary;
    const severityDelta = reviewSeverityRank(left.severity) - reviewSeverityRank(right.severity);
    if (severityDelta) return severityDelta;
    return 0;
  });
}

function reviewItemPrincipalScore(item) {
  const metadata = reviewMetadata(item);
  let score = 0;
  if (!metadata.degraded_due_to_equivalent_signal) score += 4;
  if (metadata.primary_equivalent_surface && item?.target_text === metadata.primary_equivalent_surface) score += 4;
  if (String(item?.severity || "").toLowerCase() === "medium") score += 2;
  if (String(item?.severity || "").toLowerCase() === "high") score += 3;
  return score;
}

function renderReviewPresentationGroups(grouped) {
  const groupHtml = (grouped.groups || []).map((group, index) => renderReviewGroupCard(group, index)).join("");
  const legacyHtml = (grouped.ungrouped || []).length
    ? `<div class="review-legacy-group">
        <h4>Legacy / ungrouped review items</h4>
        ${(grouped.ungrouped || []).map((item, index) => renderReviewItemCard(item, index + (grouped.groups || []).length)).join("")}
      </div>`
    : "";
  return `${groupHtml}${legacyHtml}`;
}

function summarizeReviewPresentationGroups(grouped) {
  const groups = grouped?.groups || [];
  const ungrouped = grouped?.ungrouped || [];
  const summary = {
    total_groups: groups.length,
    requires_human_review_groups: 0,
    groups_by_highest_severity: { high: 0, medium: 0, low: 0, unknown: 0 },
    groups_with_related_items: 0,
    object_retention_groups: 0,
    legacy_ungrouped_count: ungrouped.length,
    future_action_groups: 0,
    total_related_items: 0,
    total_evidence_items: 0,
    groups_by_action: {},
  };
  for (const group of groups) {
    const items = groupItems(group);
    const principal = group.principal || items[0] || {};
    const severity = highestReviewSeverity(items);
    summary.groups_by_highest_severity[severity] = (summary.groups_by_highest_severity[severity] || 0) + 1;
    if (groupRequiresHumanReview(group)) summary.requires_human_review_groups += 1;
    if ((group.related_items || []).length) summary.groups_with_related_items += 1;
    if (group.group_type === "object_retention_group") summary.object_retention_groups += 1;
    if (items.some((item) => normalizedFutureViewerActions(item).length)) summary.future_action_groups += 1;
    summary.total_related_items += (group.related_items || []).length;
    summary.total_evidence_items += groupEvidenceCount(group);
    const action = group.recommended_action || reviewActionPresentation(principal).recommendedAction || "unknown";
    summary.groups_by_action[action] = (summary.groups_by_action[action] || 0) + 1;
  }
  return summary;
}

function renderReviewPresentationSummary(grouped) {
  const summary = summarizeReviewPresentationGroups(grouped);
  return `
    <div class="review-group-summary panel">
      <div class="review-group-summary-title">
        <p class="eyebrow">Decision summary</p>
        <h4>Prioritized review groups</h4>
        <p class="muted">Read-only grouping summary. Use groups below to inspect principal and related signals.</p>
      </div>
      <div class="review-group-summary-cards">
        ${renderReviewSummaryCard("Total review groups", summary.total_groups)}
        ${renderReviewSummaryCard("Requires human review", summary.requires_human_review_groups)}
        ${renderReviewSummaryCard("High groups", summary.groups_by_highest_severity.high || 0)}
        ${renderReviewSummaryCard("Medium groups", summary.groups_by_highest_severity.medium || 0)}
        ${renderReviewSummaryCard("Low groups", summary.groups_by_highest_severity.low || 0)}
        ${renderReviewSummaryCard("Groups with related/equivalent items", summary.groups_with_related_items)}
        ${renderReviewSummaryCard("Object retention groups", summary.object_retention_groups)}
        ${renderReviewSummaryCard("Legacy / ungrouped", summary.legacy_ungrouped_count)}
      </div>
      <div class="review-group-summary-actions">
        <span class="muted">Groups by action:</span>
        ${renderCountBadges(summary.groups_by_action, "action")}
        <span class="badge review-group-badge">Read-only</span>
        <span class="badge review-group-badge">Future actions disabled</span>
      </div>
    </div>
  `;
}

function renderReviewSummaryCard(label, value) {
  return `<div class="review-summary-card"><span>${escapeHtml(label)}</span><strong>${fmtCount(value)}</strong></div>`;
}

function reviewQuickFilterPresentation(filterKey) {
  const labels = {
    all: "All groups",
    requires_human_review: "Requires human review",
    high: "High",
    medium: "Medium",
    has_related: "Has related/equivalent items",
    object_retention: "Object retention",
    legacy: "Legacy/ungrouped",
    future_actions: "Future actions",
  };
  const key = labels[filterKey] ? filterKey : "all";
  return {
    key,
    label: key === "all" ? "Active filter: All groups" : `Active filter: ${labels[key]}`,
    showClear: key !== "all",
  };
}

function renderReviewQuickFilters(activeFilter) {
  const filters = [
    { key: "all", label: "All" },
    { key: "requires_human_review", label: "Requires human review" },
    { key: "high", label: "High" },
    { key: "medium", label: "Medium" },
    { key: "has_related", label: "Has related/equivalent items" },
    { key: "object_retention", label: "Object retention" },
    { key: "legacy", label: "Legacy/ungrouped" },
    { key: "future_actions", label: "Future actions" },
  ];
  const presentation = reviewQuickFilterPresentation(activeFilter || "all");
  return `
    <div class="review-quick-filters panel">
      <div class="review-quick-filters-header">
        <h4>Quick filters</h4>
        <span class="badge review-group-badge">${escapeHtml(presentation.label)}</span>
        ${presentation.showClear ? `<button type="button" id="review-quick-filter-clear">Clear filter</button>` : ""}
      </div>
      <div class="review-quick-filters-chips">
        ${filters.map((filter) => `<button type="button" class="review-quick-filter-chip ${filter.key === presentation.key ? "is-active" : ""}" data-review-quick-filter="${escapeHtml(filter.key)}">${escapeHtml(filter.label)}</button>`).join("")}
      </div>
    </div>
  `;
}

function applyReviewQuickFilter({ grouped, filterKey }) {
  const key = filterKey || "all";
  const groups = [...(grouped?.groups || [])];
  const ungrouped = [...(grouped?.ungrouped || [])];
  if (key === "all") return { groups, ungrouped };
  if (key === "legacy") return { groups: [], ungrouped };
  const filteredGroups = groups.filter((group) => {
    const highest = highestReviewSeverity(groupItems(group));
    if (key === "high") return highest === "high";
    if (key === "medium") return highest === "medium";
    if (key === "requires_human_review") return groupRequiresHumanReview(group);
    if (key === "has_related") return (group.related_items || []).length > 0;
    if (key === "object_retention") return group.group_type === "object_retention_group";
    if (key === "future_actions") return groupItems(group).some((item) => Array.isArray(reviewMetadata(item).future_viewer_actions) && reviewMetadata(item).future_viewer_actions.length > 0);
    return true;
  });
  return { groups: filteredGroups, ungrouped: [] };
}

function deriveReviewCandidates(grouped) {
  const map = new Map();
  for (const group of grouped?.groups || []) {
    const name = String(group.candidate_name || "").trim();
    if (!name) continue;
    if (!map.has(name)) {
      map.set(name, {
        name,
        group_count: 0,
        requires_human_review: false,
        review_state: "",
      });
    }
    const entry = map.get(name);
    entry.group_count += 1;
    if (groupRequiresHumanReview(group)) entry.requires_human_review = true;
    if (!entry.review_state) {
      const state = String(reviewMetadata(group.principal).candidate_review_state || "").toLowerCase();
      if (state) entry.review_state = state;
    }
  }
  return [...map.values()].sort((left, right) => left.name.localeCompare(right.name));
}

function renderReviewCandidateDrilldown(candidates, selectedCandidate) {
  return `
    <div class="review-candidate-drilldown panel">
      <div class="review-quick-filters-header">
        <h4>Candidate drilldown</h4>
        <span class="muted">${selectedCandidate ? `Selected: ${escapeHtml(selectedCandidate)}` : "Selected: all candidates"}</span>
      </div>
      <div class="review-candidate-chips">
        <button type="button" class="review-candidate-chip ${selectedCandidate ? "" : "is-active"}" data-review-candidate="">All candidates</button>
        ${candidates.map((candidate) => `<button type="button" class="review-candidate-chip ${candidate.name === selectedCandidate ? "is-active" : ""}" data-review-candidate="${escapeHtml(candidate.name)}">${escapeHtml(candidate.name)} · ${fmtCount(candidate.group_count)}${candidate.review_state ? ` · ${escapeHtml(candidate.review_state)}` : ""}${candidate.requires_human_review ? " · requires review" : ""}</button>`).join("")}
      </div>
    </div>
  `;
}

function applyReviewCandidateFilter({ grouped, candidateName }) {
  const selected = String(candidateName || "").trim();
  if (!selected) return { groups: [...(grouped?.groups || [])], ungrouped: [...(grouped?.ungrouped || [])] };
  return {
    groups: (grouped?.groups || []).filter((group) => String(group.candidate_name || "") === selected),
    ungrouped: [...(grouped?.ungrouped || [])],
  };
}

function countRenderedReviewItems(grouped) {
  return (grouped?.groups || []).length + ((grouped?.ungrouped || []).length ? 1 : 0);
}

function renderCountBadges(counts, badgeType) {
  const entries = Object.entries(counts || {});
  if (!entries.length) return `<span class="muted">not available</span>`;
  const sorted = badgeType === "severity"
    ? entries.sort((a, b) => reviewSeverityRank(a[0]) - reviewSeverityRank(b[0]))
    : entries.sort((a, b) => String(a[0]).localeCompare(String(b[0])));
  return sorted
    .map(([label, count]) => `<span class="badge ${badgeType === "severity" ? `severity-${escapeHtml(String(label).toLowerCase())}` : ""}">${escapeHtml(label)}: ${fmtCount(count)}</span>`)
    .join("");
}

function reviewMetadata(item) {
  return item?.metadata || {};
}

function viewerActionDescriptor(actionKey) {
  return VIEWER_ACTION_DESCRIPTORS[actionKey] || null;
}

function mapRecommendedActionToViewerActions(recommendedAction) {
  return [...(RECOMMENDED_ACTION_VIEWER_ACTIONS[recommendedAction] || [])];
}

function normalizedFutureViewerActions(item) {
  const metadata = reviewMetadata(item);
  const explicit = Array.isArray(metadata.future_viewer_actions)
    ? metadata.future_viewer_actions.filter((actionKey) => !!viewerActionDescriptor(actionKey))
    : [];
  if (explicit.length) return explicit;
  const recommendedAction = metadata.recommended_action || item?.suggested_action || "";
  return mapRecommendedActionToViewerActions(recommendedAction);
}

function reviewActionPresentation(item) {
  const metadata = reviewMetadata(item);
  const actions = normalizedFutureViewerActions(item);
  return {
    recommendedAction: metadata.recommended_action || item?.suggested_action || "",
    signalTier: metadata.signal_tier || "",
    candidateStatus: metadata.candidate_status || "",
    surfaceType: metadata.surface_type || "",
    semanticValue: metadata.semantic_value || "",
    languageHint: metadata.language_hint || "",
    doNotAutoMerge: Boolean(metadata.do_not_auto_merge),
    noClearCandidate: Boolean(metadata.no_clear_existing_primary),
    actions,
  };
}

function renderReviewActionDescriptors(item) {
  const presentation = reviewActionPresentation(item);
  const actionDescriptors = presentation.actions.map((actionKey) => viewerActionDescriptor(actionKey)).filter(Boolean);
  if (!actionDescriptors.length) {
    return `<p class="muted">Future actions: inspect evidence only.</p>`;
  }
  return `
    <div class="future-action-badges">
      ${actionDescriptors.map((descriptor) => `<span class="badge future-action-badge">${escapeHtml(descriptor.label)}</span>`).join("")}
    </div>
    <div class="future-action-buttons">
      ${actionDescriptors.map((descriptor) => `
        <button type="button" class="future-action-button" disabled title="${escapeHtml(descriptor.safetyWarning)}">
          ${escapeHtml(descriptor.shortLabel)}
        </button>
      `).join("")}
    </div>
    <ul class="future-action-details">
      ${actionDescriptors.map((descriptor) => `
        <li>
          <strong>${escapeHtml(descriptor.shortLabel)}</strong>
          <span>${escapeHtml(descriptor.explanation)}</span>
        </li>
      `).join("")}
    </ul>
  `;
}

function renderReviewContractWarnings(item) {
  const presentation = reviewActionPresentation(item);
  const warnings = [];
  if (presentation.doNotAutoMerge) warnings.push("do_not_auto_merge: true — viewer never executes merge automatically.");
  if (reviewMetadata(item).do_not_auto_promote) warnings.push("do_not_auto_promote: true — viewer never promotes entities automatically.");
  if (presentation.noClearCandidate) warnings.push("No clear candidate available — review_create_primary / keep_secondary remains editorial.");
  if (presentation.surfaceType === "pronoun_like") warnings.push("Pronoun-like surface — use conservative review wording and avoid primary promotion.");
  if (!warnings.length) return "";
  return `<div class="review-safety-warning">${warnings.map((warning) => `<p>${escapeHtml(warning)}</p>`).join("")}</div>`;
}

function renderReviewGroupCard(group, index) {
  if (group?.group) group = group.group;
  const principal = group.principal;
  if (!principal) return "";
  const openAttr = index < 2 ? "open" : "";
  const presentation = reviewActionPresentation(principal);
  const related = group.related_items || [];
  const highestSeverity = highestReviewSeverity(groupItems(group));
  const evidenceCount = groupEvidenceCount(group);
  const requiresHumanReview = groupRequiresHumanReview(group);
  return `
    <details class="review-group ${escapeHtml(group.group_type || "descriptor_group")}" ${openAttr}>
      <summary>
        <span class="badge review-group-kind">${escapeHtml(groupLabel(group))}</span>
        <strong>${escapeHtml(group.candidate_name || "Unknown candidate")}</strong>
        <span class="muted">·</span>
        <span>${escapeHtml(group.recommended_action || "editorial review")}</span>
        ${group.descriptor_category ? `<span class="badge">${escapeHtml(group.descriptor_category)}</span>` : ""}
        <span class="badge severity-${escapeHtml(highestSeverity)}">${escapeHtml(highestSeverity)}</span>
        ${related.length ? `<span class="badge">${related.length} related</span>` : ""}
        <span class="badge">${evidenceCount} evidence</span>
      </summary>
      <div class="review-group-body">
        <div class="review-group-header">
          <div>
            <p class="eyebrow">Editorial decision</p>
            <h4>${escapeHtml(groupTitle(group))}</h4>
            <p class="muted">${escapeHtml(groupSubtitle(group))}</p>
          </div>
          <div class="review-group-badges">
            <span class="badge review-group-badge">Read-only</span>
            ${requiresHumanReview ? `<span class="badge review-group-badge">Requires human review</span>` : ""}
            ${presentation.doNotAutoMerge ? `<span class="badge review-group-badge">No auto-merge</span>` : ""}
            ${reviewMetadata(principal).do_not_auto_promote ? `<span class="badge review-group-badge">No auto-promote</span>` : ""}
            ${group.group_type === "object_retention_group" ? `<span class="badge review-group-badge">Object retention</span>` : ""}
          </div>
        </div>
        <div class="review-group-section">
          <h5>Primary signal</h5>
          ${renderReviewItemCard(principal, index)}
        </div>
        ${related.length ? `<div class="review-group-section">
          <h5>Related / equivalent signals</h5>
          <div class="review-related-list">
            ${related.map((item, relatedIndex) => renderReviewRelatedItem(item, `${index}-${relatedIndex}`)).join("")}
          </div>
        </div>` : ""}
      </div>
    </details>
  `;
}

function groupItems(group) {
  return [group?.principal, ...(group?.related_items || [])].filter(Boolean);
}

function highestReviewSeverity(items) {
  const sorted = [...(items || [])].sort((left, right) => reviewSeverityRank(left?.severity) - reviewSeverityRank(right?.severity));
  return String(sorted[0]?.severity || "unknown").toLowerCase();
}

function groupRequiresHumanReview(group) {
  return groupItems(group).some((item) => {
    const metadata = reviewMetadata(item);
    return Boolean(
      metadata.candidate_requires_review ||
      metadata.do_not_auto_merge ||
      metadata.do_not_auto_promote ||
      String(metadata.candidate_review_state || "").toLowerCase() === "review"
    );
  });
}

function groupEvidenceCount(group) {
  return groupItems(group).reduce((total, item) => total + ((item?.evidence || []).length), 0);
}

function renderReviewRelatedItem(item, index) {
  const presentation = reviewActionPresentation(item);
  return `
    <details class="review-item review-item-related" data-review-item-id="${escapeHtml(reviewItemKey(item, index))}">
      <summary>
        <span class="badge severity-${escapeHtml(String(item.severity || "unknown").toLowerCase())}">${escapeHtml(item.severity || "unknown")}</span>
        <strong>${escapeHtml(item.target_text || "not available")}</strong>
        ${reviewMetadata(item).degraded_due_to_equivalent_signal ? `<span class="badge">equivalent</span>` : ""}
      </summary>
      <div class="review-item-body">
        <p class="muted">Related signal for same editorial decision.</p>
        <div class="review-meta-grid">
          <div><span class="muted">Source:</span> ${escapeHtml(item.source_entity || "not available")}</div>
          <div><span class="muted">Action:</span> ${escapeHtml(presentation.recommendedAction || "not available")}</div>
          <div><span class="muted">Signal tier:</span> ${escapeHtml(presentation.signalTier || "not available")}</div>
          <div><span class="muted">Surface type:</span> ${escapeHtml(presentation.surfaceType || "not available")}</div>
        </div>
        ${renderReviewContractWarnings(item)}
        <h5>Future viewer actions</h5>
        ${renderReviewActionDescriptors(item)}
      </div>
    </details>
  `;
}

function groupLabel(group) {
  if (group.group_type === "object_retention_group") return "Object retention group";
  return "Descriptor decision group";
}

function groupTitle(group) {
  if (group.group_type === "object_retention_group") {
    return `Review object retention for ${group.candidate_name || "item"}`;
  }
  return `Review ${humanizeReviewAction(group.recommended_action)} for ${group.candidate_name || "candidate"}`;
}

function groupSubtitle(group) {
  if (group.group_type === "object_retention_group") {
    return "Object retention remains separate from descriptor review grouping.";
  }
  return "Primary signal shown first; related low/equivalent signals stay visible underneath.";
}

function humanizeReviewAction(action) {
  const map = {
    review_attach_role_or_title: "role/title attachment",
    review_enrich_existing_entity: "entity enrichment",
    review_create_primary: "primary creation",
    review_keep_secondary: "secondary retention",
    review_merge_or_alias: "merge / alias review",
    review_reject_noise: "noise rejection",
  };
  return map[action] || action || "editorial review";
}

function renderReviewItemCard(item, index) {
  const candidates = item.candidate_entities || [];
  const evidence = item.evidence || [];
  const reviewId = reviewItemKey(item, index);
  const presentation = reviewActionPresentation(item);
  return `
    <details class="review-item ${state.selectedReviewItemId === reviewId ? "review-highlight" : ""}" data-review-item-id="${escapeHtml(reviewId)}" ${index < 2 || state.selectedReviewItemId === reviewId ? "open" : ""}>
      <summary>
        <span class="badge severity-${escapeHtml(String(item.severity || "unknown").toLowerCase())}">${escapeHtml(item.severity || "unknown")}</span>
        <span class="badge">${escapeHtml(item.review_type || "unknown")}</span>
        <strong>${escapeHtml(item.source_entity || "not available")}</strong>
        <span class="muted">→</span>
        <strong>${escapeHtml(item.target_text || "not available")}</strong>
      </summary>
      <div class="review-item-body">
        <div class="review-meta-grid">
          <div><span class="muted">Candidates:</span> ${fmtCount(candidates.length)}</div>
          <div><span class="muted">Evidence:</span> ${fmtCount(evidence.length)}</div>
          <div><span class="muted">Severity:</span> ${escapeHtml(item.severity || "not available")}</div>
          <div><span class="muted">Type:</span> ${escapeHtml(item.review_type || "not available")}</div>
          <div><span class="muted">Recommended action:</span> ${escapeHtml(presentation.recommendedAction || "not available")}</div>
          <div><span class="muted">Signal tier:</span> ${escapeHtml(presentation.signalTier || "not available")}</div>
          <div><span class="muted">Candidate status:</span> ${escapeHtml(presentation.candidateStatus || "not available")}</div>
          <div><span class="muted">Semantic value:</span> ${escapeHtml(presentation.semanticValue || "not available")}</div>
          <div><span class="muted">Surface type:</span> ${escapeHtml(presentation.surfaceType || "not available")}</div>
          <div><span class="muted">Language hint:</span> ${escapeHtml(presentation.languageHint || "not available")}</div>
        </div>
        ${renderReviewContractWarnings(item)}
        <div class="review-actions">
          ${item.source_entity ? `<button type="button" data-review-graph="${escapeHtml(item.source_entity)}">Source → graph</button>` : ""}
          ${item.target_text ? `<button type="button" data-review-graph="${escapeHtml(item.target_text)}">Target → graph</button>` : ""}
          ${item.source_entity ? `<button type="button" data-review-canon="${escapeHtml(item.source_entity)}">Source → canon</button>` : ""}
          ${item.target_text ? `<button type="button" data-review-canon="${escapeHtml(item.target_text)}">Target → canon</button>` : ""}
          <button type="button" data-review-open-canon="1">Open canon</button>
        </div>
        <h4>Future viewer actions</h4>
        ${renderReviewActionDescriptors(item)}
        ${candidates.length ? `<h4>Candidates</h4><div class="review-candidates">${candidates.map((candidate) => `
          <div class="candidate-card">
            <strong>${escapeHtml(candidate.canonical_name || "not available")}</strong>
            <small>${escapeHtml(candidate.entity_kind || "not available")}</small>
            <div class="candidate-actions">
              ${candidate.canonical_name ? `<button type="button" class="inline-action" data-review-graph="${escapeHtml(candidate.canonical_name)}">Graph</button>` : ""}
              ${candidate.canonical_name ? `<button type="button" class="inline-action" data-review-canon="${escapeHtml(candidate.canonical_name)}">Canon</button>` : ""}
            </div>
          </div>
        `).join("")}</div>` : `<p class="muted">Candidates: not available</p>`}
        ${evidence.length ? `<h4>Evidence</h4><ul class="review-evidence">${evidence.map((entry) => `
          <li>
            <p>${escapeHtml(entry.text || "not available")}</p>
            <small class="muted">${escapeHtml(entry.chapter_id || entry.source || "")}</small>
          </li>
        `).join("")}</ul>` : `<p class="muted">Evidence: not available</p>`}
      </div>
    </details>
  `;
}

function bindReviewQueueInteractions() {
  document.querySelectorAll("[data-review-item-id]").forEach((node) => {
    node.addEventListener("toggle", () => {
      if (node.open) state.selectedReviewItemId = node.dataset.reviewItemId || null;
    });
  });
  $("review-open-raw")?.addEventListener("click", () => {
    setView("artifacts");
    openArtifact("review_queue.json");
  });
  $("review-filter-severity")?.addEventListener("change", (event) => {
    state.reviewView.severity = event.target.value || "";
    renderReview();
  });
  $("review-filter-type")?.addEventListener("change", (event) => {
    state.reviewView.reviewType = event.target.value || "";
    renderReview();
  });
  $("review-filter-query")?.addEventListener("change", (event) => {
    state.reviewView.query = event.target.value || "";
    renderReview();
  });
  $("review-sort-by")?.addEventListener("change", (event) => {
    state.reviewView.sortBy = event.target.value || "severity_desc";
    renderReview();
  });
  $("review-filter-reset")?.addEventListener("click", () => {
    state.reviewView = { severity: "", reviewType: "", query: "", sortBy: "severity_desc", quickFilter: "all", candidate: "" };
    renderReview();
  });
  document.querySelectorAll("[data-review-quick-filter]").forEach((node) => {
    node.addEventListener("click", () => {
      state.reviewView.quickFilter = node.dataset.reviewQuickFilter || "all";
      renderReview();
    });
  });
  $("review-quick-filter-clear")?.addEventListener("click", () => {
    state.reviewView.quickFilter = "all";
    state.reviewView.candidate = "";
    renderReview();
  });
  document.querySelectorAll("[data-review-candidate]").forEach((node) => {
    node.addEventListener("click", () => {
      state.reviewView.candidate = node.dataset.reviewCandidate || "";
      renderReview();
    });
  });
  document.querySelectorAll("[data-review-graph]").forEach((node) => {
    node.addEventListener("click", () => {
      const term = node.dataset.reviewGraph || "";
      if (term) navigateToGraphTerm(term, { from: "Review Queue" });
    });
  });
  document.querySelectorAll("[data-review-canon]").forEach((node) => {
    node.addEventListener("click", () => {
      const term = node.dataset.reviewCanon || "";
      if (term) navigateToCanonTerm(term, { from: "Review Queue" });
    });
  });
  document.querySelectorAll("[data-review-open-canon]").forEach((node) => {
    node.addEventListener("click", () => setView("canon"));
  });
}

function bindCanonNavigation() {
  document.querySelectorAll("[data-canon-inspect]").forEach((node) => {
    node.addEventListener("click", () => {
      const key = node.dataset.canonInspect || "";
      if (!key) return;
      state.selectedCanonEntityKey = normalizeKey(key);
      setNavNotice(`Canon: inspecting "${key}".`, "info");
      renderCanon();
    });
  });
  document.querySelectorAll("[data-canon-graph]").forEach((node) => {
    node.addEventListener("click", () => {
      const key = node.dataset.canonGraph || "";
      if (key) navigateToGraphTerm(key, { from: "Canon" });
    });
  });
}

function renderArtifacts() {
  const artifacts = state.current.artifacts || [];
  $("artifact-list").innerHTML = `
    <div class="panel"><p class="muted"><strong>${escapeHtml(t('devDrawer'))}:</strong> ${escapeHtml(t('technicalDetails'))}.</p></div>
    ${artifacts.map((artifact) => `
      <div class="list-item" data-artifact="${escapeHtml(artifact.path)}">
        <strong>${escapeHtml(artifact.name)}</strong>
        <small>${escapeHtml(artifact.kind)} · ${fmtCount(artifact.size)} bytes</small>
      </div>
    `).join("")}
  `;
  document.querySelectorAll("[data-artifact]").forEach((node) => {
    node.addEventListener("click", () => openArtifact(node.dataset.artifact));
  });
}

async function openArtifact(path) {
  const data = await api(`/api/projects/${encodeURIComponent(state.currentId)}/artifact?path=${encodeURIComponent(path)}`);
  $("artifact-detail").textContent = data.kind === "json"
    ? JSON.stringify(data.json, null, 2)
    : data.kind === "directory"
      ? JSON.stringify(data.children, null, 2)
      : data.text;
}

function renderGraph() {
  if (!state.current) return;
  if (state.graphAnimation) {
    cancelAnimationFrame(state.graphAnimation);
    state.graphAnimation = null;
  }
  const graph = normalizeGraphData(state.current.graph || { nodes: [], edges: [] });
  const hideSystem = $("hide-system").checked;
  const hideReview = $("hide-review").checked;
  const hideChapters = $("hide-chapters").checked;
  const localGraphMode = $("local-graph-mode")?.checked;
  const showAllNodes = $("show-all-nodes")?.checked || false;
  state.graphShowAllNodes = showAllNodes;
  const kindFilter = $("graph-kind-filter").value;
  const statusFilter = $("graph-status-filter").value;
  const kinds = [...new Set(graph.nodes.map((node) => node.display_kind || node.canonical_kind || node.kind).filter(Boolean))].sort();
  const tags = [...new Set(graph.nodes.flatMap((node) => node.tags || []))].sort();
  const statuses = [...new Set(graph.nodes.map((node) => node.frontmatter?.review_state || node.frontmatter?.status || node.role).filter(Boolean))].sort();
  if (!$("graph-kind-filter").dataset.ready) {
    $("graph-kind-filter").innerHTML = `<option value="">${escapeHtml(t('allKinds'))}</option>${kinds.map((kind) => `<option value="${escapeHtml(kind)}">${escapeHtml(kindLabel(kind))}</option>`).join("")}`;
    $("graph-status-filter").innerHTML = `<option value="">${escapeHtml(t('allStatus'))}</option>${statuses.map((status) => `<option value="${escapeHtml(status)}">${escapeHtml(status)}</option>`).join("")}`;
    $("graph-kind-filter").dataset.ready = "1";
    $("graph-kind-filter").onchange = renderGraph;
    $("graph-status-filter").onchange = renderGraph;
    $("local-graph-mode").onchange = renderGraph;
    $("show-all-nodes").onchange = renderGraph;
  }
  renderGraphTagFilter(tags);
  state.current.graph = graph;
  state.current.visibleGraph = buildVisibleGraph(graph, {
    hideSystem,
    hideReview,
    hideChapters,
    showAllNodes,
    localGraphMode,
    kindFilter,
    statusFilter,
    hiddenTags: state.hiddenGraphTags,
    selectedGraphNodeId: state.selectedGraphNodeId,
  });
  state.currentVisibleGraph = state.current.visibleGraph;
  drawForceGraph(state.current.visibleGraph);
}

function normalizeGraphData(rawGraph) {
  const graph = rawGraph && typeof rawGraph === "object" ? rawGraph : {};
  const rawNodes = Array.isArray(graph.nodes) ? graph.nodes : [];
  const rawEdges = Array.isArray(graph.edges) ? graph.edges : [];
  const nodes = rawNodes.map((node) => {
    const safeNode = node && typeof node === "object" ? node : {};
    const degree = Number(safeNode.degree || 0);
    const radius = Number(safeNode.radius || graphNodeRadius(safeNode));
    const color = safeNode.color || safeNode.visual?.kind_color || kindColor(safeNode.kind);
    const status = safeNode.review_state || safeNode.status || safeNode.frontmatter?.review_state || safeNode.frontmatter?.status || safeNode.role || "ready";
    return {
      ...safeNode,
      degree,
      radius,
      color,
      status,
      review_state: status,
      note_path: safeNode.note_path || safeNode.id,
      canonical_kind: safeNode.canonical_kind || safeNode.display_kind || safeNode.kind,
      display_kind: safeNode.display_kind || safeNode.canonical_kind || safeNode.kind,
      canonical_degree: Number(safeNode.canonical_degree ?? degree),
      tags: Array.isArray(safeNode.tags) ? safeNode.tags : [],
    };
  });
  const nodeIds = new Set(nodes.map((node) => node.id));
  const canonical_redirects = graph.canonical_redirects && typeof graph.canonical_redirects === "object" ? graph.canonical_redirects : {};
  const canonical_note_redirects = graph.canonical_note_redirects && typeof graph.canonical_note_redirects === "object" ? graph.canonical_note_redirects : {};
  const edges = rawEdges
    .map((edge) => {
      const safeEdge = edge && typeof edge === "object" ? edge : {};
      return {
        ...safeEdge,
        id: safeEdge.id || edgeIdFor(safeEdge),
        source: safeEdge.source,
        target: safeEdge.target,
        kind: safeEdge.kind || safeEdge.type || safeEdge.label || "wikilink",
        label: safeEdge.label || safeEdge.type || safeEdge.kind || "wikilink",
      };
    })
    .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target));
  return {
    ...graph,
    graph_contract_version: Number(graph.graph_contract_version || graph.metadata?.graph_contract_version || 2),
    canonical_redirects,
    canonical_note_redirects,
    nodes,
    edges,
  };
}

function resolveCanonicalNodeId(idOrPathOrLabel) {
  const graph = state.current && state.current.graph ? state.current.graph : { nodes: [], canonical_redirects: {} };
  const redirects = graph.canonical_redirects || {};
  const noteRedirects = graph.canonical_note_redirects || {};
  const raw = String(idOrPathOrLabel || "");
  if (!raw) return null;
  const byPath = noteRedirects[raw] || raw;
  const direct = redirects[raw] || byPath;
  if ((graph.nodes || []).some((node) => node.id === direct)) return direct;
  const pathNode = (graph.nodes || []).find((node) => String(node.note_path || "") === byPath || String(node.canonical_note_path || "") === byPath);
  if (pathNode) return pathNode.canonical_node_id || pathNode.id;
  const match = findGraphNodeByTerm(raw);
  return match ? (match.canonical_node_id || match.id) : null;
}

function resolveCanonicalNotePath(path) {
  const graph = state.current && state.current.graph ? state.current.graph : { canonical_note_redirects: {} };
  return (graph.canonical_note_redirects || {})[String(path || "")] || String(path || "");
}

function edgeIdFor(edge) {
  return `edge:${slugify(`${edge.source || ""}::${edge.label || edge.type || edge.kind || "edge"}::${edge.target || ""}`)}`;
}

function collapseGraphEdges(edges, redirects) {
  const deduped = new Map();
  for (const edge of edges || []) {
    const source = redirects[edge.source] || edge.source;
    const target = redirects[edge.target] || edge.target;
    if (!source || !target || source === target) continue;
    const normalized = {
      ...edge,
      source,
      target,
      id: edgeIdFor({ source, target, label: edge.label || edge.type || edge.kind || "wikilink" }),
    };
    if (!deduped.has(normalized.id)) deduped.set(normalized.id, normalized);
  }
  return [...deduped.values()];
}

function buildVisibleGraph(graph, options) {
  const {
    hideSystem,
    hideReview,
    hideChapters,
    showAllNodes,
    localGraphMode,
    kindFilter,
    statusFilter,
    hiddenTags,
    selectedGraphNodeId,
  } = options;
  const redirects = graph.canonical_redirects || {};
  const scopedEdges = showAllNodes ? (graph.edges || []) : collapseGraphEdges(graph.edges || [], redirects);
  let visibleNodes = graph.nodes.filter((node) => {
    const filterKind = node.display_kind || node.canonical_kind || node.kind;
    const degree = Number(node.canonical_degree ?? node.degree ?? 0);
    if (hideSystem && node.role === "system") return false;
    if (hideReview && node.role === "review") return false;
    if (hideChapters && node.role === "chapter") return false;
    if (!showAllNodes) {
      if (node.canonical_redirected) return false;
      if (node.role === "review" || node.kind === "review") return false;
      if (node.role === "chapter" || node.kind === "chapter") return false;
      if (["character", "place", "object", "event"].includes(filterKind) && degree < 2) return false;
      if (filterKind === "concept" && degree < 8) return false;
    }
    if (kindFilter && filterKind !== kindFilter) return false;
    const nodeStatus = node.review_state || node.status || node.frontmatter?.review_state || node.frontmatter?.status || node.role || "";
    if (statusFilter && nodeStatus !== statusFilter) return false;
    if ((node.tags || []).some((tag) => hiddenTags.has(tag))) return false;
    return true;
  });
  if (localGraphMode && selectedGraphNodeId) {
    const neighborIds = new Set([selectedGraphNodeId]);
    for (const edge of scopedEdges) {
      if (edge.source === selectedGraphNodeId) neighborIds.add(edge.target);
      if (edge.target === selectedGraphNodeId) neighborIds.add(edge.source);
    }
    visibleNodes = visibleNodes.filter((node) => neighborIds.has(node.id));
  }
  const visibleIds = new Set(visibleNodes.map((node) => node.id));
  const visibleEdges = scopedEdges.filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target));
  return {
    nodes: visibleNodes,
    edges: visibleEdges,
    edgeById: Object.fromEntries(visibleEdges.map((edge) => [edge.id, edge])),
    nodeById: Object.fromEntries(visibleNodes.map((node) => [node.id, node])),
    local_graph: { enabled: Boolean(localGraphMode), center_node_id: selectedGraphNodeId || null },
  };
}

function renderGraphTagFilter(tags) {
  const container = $("graph-tag-filter");
  if (!container) return;
  const activeCount = state.hiddenGraphTags.size;
  container.innerHTML = `
    <span class="tag-filter-label">${escapeHtml(t('allTags'))}</span>
    ${tags.map((tag) => `
      <button type="button" class="tag-chip ${state.hiddenGraphTags.has(tag) ? "active" : ""}" data-graph-tag="${escapeHtml(tag)}">${escapeHtml(tag)}</button>
    `).join("")}
    ${activeCount ? `<button type="button" class="tag-chip clear" id="clear-graph-tags">${escapeHtml(t('clearHiddenTags', { count: activeCount }))}</button>` : ""}
  `;
  container.querySelectorAll("[data-graph-tag]").forEach((button) => {
    button.addEventListener("click", () => {
      const tag = button.dataset.graphTag;
      if (state.hiddenGraphTags.has(tag)) state.hiddenGraphTags.delete(tag);
      else state.hiddenGraphTags.add(tag);
      renderGraph();
    });
  });
  const clear = $("clear-graph-tags");
  if (clear) {
    clear.addEventListener("click", () => {
      state.hiddenGraphTags = new Set();
      renderGraph();
    });
  }
}

function drawForceGraph(visibleGraph) {
  const svg = $("graph-svg");
  const width = 1200;
  const height = 720;
  if (state.graphSimulation) {
    state.graphSimulation.stop();
    state.graphSimulation = null;
  }
  const layoutState = createGraphLayout(visibleGraph, width, height);
  const byId = layoutState.byId;
  svg.innerHTML = renderGraphDom(visibleGraph, layoutState);
  applyGraphViewBox();
  bindGraphViewportHandlers(svg);
  bindGraphInteractions(svg, visibleGraph, layoutState);
  tickGraph(layoutState, visibleGraph);
  if (!hasPersistedGraphPositions()) autoFitGraphViewBox(layoutState.byId, { padding: 100 });
  if (state.selectedGraphNodeId && byId[state.selectedGraphNodeId]) {
    renderGraphNodeDetail(byId[state.selectedGraphNodeId]);
  }
}

function renderGraphDom(visibleGraph, layoutState) {
  const byId = layoutState.byId;
  return `
    <g class="edges"></g>
    <g class="nodes">
      ${Object.values(byId).map((node) => `
        <g class="node ${node.id === state.selectedGraphNodeId ? "selected" : ""}" data-node-id="${escapeHtml(node.id)}" transform="translate(${node.x}, ${node.y})">
        <circle r="${graphNodeRadius(node)}" fill="${nodeColor(node)}" stroke="${nodeStatusBorder(node)}"></circle>
        <text class="node-label ${showNodeLabel(node) ? "" : "is-muted"}" x="${graphNodeRadius(node) + 4}" y="4">${escapeHtml(node.label)}</text>
        </g>
      `).join("")}
    </g>
  `;
}

function bindGraphInteractions(svg, visibleGraph, layoutState) {
  const byId = layoutState.byId;
  const edgeLayer = svg.querySelector(".edges");
  edgeLayer.innerHTML = visibleGraph.edges.map((edge) => `<g class="edge-group" data-edge-group-id="${escapeHtml(edge.id)}"><line class="edge" data-edge-id="${escapeHtml(edge.id)}"><title>${escapeHtml(edge.label || edge.type || "")}</title></line><text class="edge-label hidden">${escapeHtml(edge.label || edge.type || "")}</text></g>`).join("");
  edgeLayer.querySelectorAll("[data-edge-group-id]").forEach((groupEl) => {
    groupEl.addEventListener('pointerenter', () => {
      const label = groupEl.querySelector('.edge-label');
      if (label) label.classList.remove('hidden');
    });
    groupEl.addEventListener('pointerleave', () => {
      const label = groupEl.querySelector('.edge-label');
      if (label) label.classList.add('hidden');
    });
  });
  svg.querySelectorAll("[data-node-id]").forEach((nodeEl) => {
    const node = byId[nodeEl.dataset.nodeId];
    bindNodeDrag(nodeEl, node, layoutState, svg, visibleGraph);
    nodeEl.addEventListener("click", (event) => {
      event.stopPropagation();
      if (state.graphDidDragNode) {
        state.graphDidDragNode = false;
        return;
      }
      if (state.graphDidPan) {
        state.graphDidPan = false;
        return;
      }
      selectGraphNode(node.id, { pushHistory: true });
    });
  });
}

function createGraphLayout(visibleGraph, width, height) {
  const byId = seedGraphPositions(visibleGraph.nodes, width, height);
  return { width, height, byId, warnings: [], edgeWarnings: 0 };
}

function tickGraph(layoutState, visibleGraph) {
  if (!globalThis.d3 || !globalThis.d3.forceSimulation) {
    const svg = $("graph-svg");
    svg.innerHTML = `<text class="graph-error" x="48" y="64">d3-force no cargó. Revisa /vendor/d3-force.bundle.min.js.</text>`;
    return;
  }
  const nodes = Object.values(layoutState.byId);
  const links = (visibleGraph.edges || [])
    .filter((edge) => layoutState.byId[edge.source] && layoutState.byId[edge.target])
    .map((edge) => ({ ...edge, source: layoutState.byId[edge.source], target: layoutState.byId[edge.target] }));
  const centerX = layoutState.width / 2;
  const centerY = layoutState.height / 2;
  state.graphSimulation = globalThis.d3.forceSimulation(nodes)
    .force("center", globalThis.d3.forceCenter(centerX, centerY))
    .force("charge", globalThis.d3.forceManyBody().strength((node) => node.kind === 'character' ? -290 : -160))
    .force("link", globalThis.d3.forceLink(links).id((node) => node.id).distance((edge) => edge.kind === 'related' ? 110 : 148).strength(0.45))
    .force("collide", globalThis.d3.forceCollide().radius((node) => (node.radius || graphNodeRadius(node)) + 14).iterations(2))
    .force("x", globalThis.d3.forceX((node) => (node.kind === 'character' || Number(node.degree || 0) >= 10) ? centerX : centerX).strength(0.03))
    .force("y", globalThis.d3.forceY(centerY).strength(0.03))
    .alpha(0.92)
    .alphaDecay(0.05)
    .on("tick", () => {
      nodes.forEach((node) => {
        const margin = Math.max(36, (node.radius || graphNodeRadius(node)) + 12);
        node.x = Math.max(margin, Math.min(layoutState.width - margin, node.x || centerX));
        node.y = Math.max(margin, Math.min(layoutState.height - margin, node.y || centerY));
      });
      updateGraphDom($("graph-svg"), visibleGraph, layoutState);
    });
}

function seedGraphPositions(nodes, width, height) {
  const persisted = loadGraphPositions();
  const centerX = width / 2;
  const centerY = height / 2;
  const sorted = [...nodes].sort((a, b) => Number(b.degree || 0) - Number(a.degree || 0));
  const byId = {};
  sorted.forEach((node, index) => {
    const previous = node._position || {};
    const saved = persisted[node.id] || {};
    const angle = (index / Math.max(sorted.length, 1)) * Math.PI * 2;
    const ring = Math.max(120, Math.min(width, height) * 0.34);
    const bias = node.kind === 'character' || Number(node.degree || 0) > 10 ? 0.45 : 1;
    const radius = ring * bias + (index % 7) * 14;
    byId[node.id] = {
      ...node,
      x: saved.x ?? (previous.x ?? centerX + Math.cos(angle) * radius),
      y: saved.y ?? (previous.y ?? centerY + Math.sin(angle) * radius),
      vx: previous.vx === undefined ? 0 : previous.vx,
      vy: previous.vy === undefined ? 0 : previous.vy,
      pinned: Boolean(saved.pinned),
      fx: saved.pinned ? saved.x : null,
      fy: saved.pinned ? saved.y : null,
    };
  });
  return byId;
}

function runForceTick(byId, edges, width, height, tick) {
  return { byId, edges, width, height, tick };
}

function updateGraphDom(svg, visibleGraph, layoutState) {
  const byId = layoutState.byId;
  const edgeById = visibleGraph.edgeById || Object.fromEntries((visibleGraph.edges || []).map((edge) => [edge.id, edge]));
  svg.querySelectorAll("[data-edge-id]").forEach((line) => {
    const edge = edgeById[line.dataset.edgeId];
    if (!edge) return;
    const a = byId[edge.source], b = byId[edge.target];
    if (!a || !b) {
      layoutState.edgeWarnings += 1;
      return;
    }
    line.setAttribute("x1", a.x);
    line.setAttribute("y1", a.y);
    line.setAttribute("x2", b.x);
    line.setAttribute("y2", b.y);
  });
  svg.querySelectorAll("[data-edge-group-id]").forEach((groupEl) => {
    const edge = edgeById[groupEl.dataset.edgeGroupId];
    if (!edge) return;
    const a = byId[edge.source], b = byId[edge.target];
    if (!a || !b) return;
    const label = groupEl.querySelector(".edge-label");
    if (!label) return;
    label.setAttribute("x", (a.x + b.x) / 2);
    label.setAttribute("y", (a.y + b.y) / 2 - 4);
    label.classList.add("hidden");
  });
  svg.querySelectorAll("[data-node-id]").forEach((nodeEl) => {
    const node = byId[nodeEl.dataset.nodeId];
    if (!node) return;
    nodeEl.setAttribute("transform", `translate(${node.x}, ${node.y})`);
    nodeEl.classList.toggle("selected", node.id === state.selectedGraphNodeId);
    const text = nodeEl.querySelector(".node-label");
    if (text) text.classList.toggle("is-muted", !showNodeLabel(node));
  });
}

function graphNodeRadius(node) {
  if (Number(node.radius || 0) > 0) return Number(node.radius);
  const degree = Number(node.degree || 0);
  const base = node.kind === "character" ? 13 : node.role === "chapter" ? 8 : node.role === "review" ? 10 : 11;
  return Math.max(base, Math.min(base + degree * 1.45, 26));
}

function showNodeLabel(node) {
  return node.id === state.selectedGraphNodeId || node.kind === "character" || Number(node.degree || 0) >= 5;
}

function bindNodeDrag(nodeEl, node, layoutState, svg, visibleGraph) {
  if (!node) return;
  nodeEl.onpointerdown = (event) => {
    event.stopPropagation();
    nodeEl.setPointerCapture(event.pointerId);
    state.graphDrag = { pointerId: event.pointerId, nodeId: node.id };
    node.fx = node.x;
    node.fy = node.y;
    node.pinned = true;
    state.graphDidDragNode = false;
    if (state.graphSimulation) state.graphSimulation.alphaTarget(0.25).restart();
  };
  nodeEl.onpointermove = (event) => {
    if (!state.graphDrag || state.graphDrag.pointerId !== event.pointerId || state.graphDrag.nodeId !== node.id) return;
    const point = clientToGraphPoint(svg, event.clientX, event.clientY);
    node.fx = point.x;
    node.fy = point.y;
    node.x = point.x;
    node.y = point.y;
    node.pinned = true;
    state.graphDidDragNode = true;
    updateGraphDom(svg, visibleGraph || state.currentVisibleGraph || { edges: [] }, layoutState);
  };
  nodeEl.onpointerup = (event) => finishNodeDrag(nodeEl, event.pointerId, layoutState.byId);
  nodeEl.onpointercancel = (event) => finishNodeDrag(nodeEl, event.pointerId, layoutState.byId);
}

function finishNodeDrag(nodeEl, pointerId, byId) {
  if (!state.graphDrag || state.graphDrag.pointerId !== pointerId) return;
  try {
    nodeEl.releasePointerCapture(pointerId);
  } catch (_error) {
  }
  persistGraphPositions(byId);
  if (state.graphSimulation) state.graphSimulation.alphaTarget(0);
  state.graphDrag = null;
}

function selectGraphNode(nodeId, { pushHistory = false, renderDetail = true } = {}) {
  const canonicalNodeId = resolveCanonicalNodeId(nodeId) || nodeId;
  if (pushHistory) {
    pushViewerNav(navEntry({ nodeId: state.selectedGraphNodeId }));
    state.viewerNavForward = [];
  }
  state.selectedGraphNodeId = canonicalNodeId;
  const graph = state.current && state.current.graph ? state.current.graph : { nodes: [] };
  const node = (graph.nodes || []).find((item) => item.id === canonicalNodeId);
  if (!node) return;
  const entity = node.entity || {};
  if (Object.keys(entity).length) state.selectedCanonEntityKey = canonEntityKey(entity);
  rememberRecentNode({ id: node.id, label: node.label, kind: node.kind, note_path: node.note_path });
  if (renderDetail) renderGraphNodeDetail(node);
  document.querySelectorAll("[data-node-id]").forEach((nodeEl) => nodeEl.classList.toggle("selected", nodeEl.dataset.nodeId === canonicalNodeId));
}

async function renderGraphNodeDetail(node) {
  const canonicalNotePath = resolveCanonicalNotePath(node.canonical_note_path || node.note_path || "");
  if (canonicalNotePath) {
    await openGraphNote(canonicalNotePath, node.canonical_node_id || node.id);
    return;
  }
  $("graph-detail").innerHTML = graphNodeSummary(node);
  bindGraphDetailNavigation();
  bindCanonicalizationInteractions();
}

function parseMarkdownSections(markdownText) {
  const sections = { summary: "", facts: [], relationships: [], evidence: [] };
  let current = "";
  for (const rawLine of String(markdownText || "").split(/\r?\n/)) {
    const line = rawLine.trim();
    const heading = line.match(/^##\s+(.+)$/);
    if (heading) {
      const key = normalizeKey(heading[1]);
      current = key.includes("summary") ? "summary"
        : key.includes("fact") ? "facts"
        : key.includes("relationship") ? "relationships"
        : key.includes("evidence") ? "evidence"
        : "";
      continue;
    }
    if (!current || !line || line.startsWith("<!--")) continue;
    const cleaned = line.replace(/^[-*]\s+/, "").replace(/\[\[([^\]|]+)(?:\|[^\]]+)?\]\]/g, "$1").trim();
    if (!cleaned) continue;
    if (current === "summary") sections.summary = [sections.summary, cleaned].filter(Boolean).join(" ");
    else sections[current].push(cleaned);
  }
  return sections;
}

async function openGraphNote(path, nodeId = null, { pushHistory = true } = {}) {
  const canonicalPath = resolveCanonicalNotePath(path);
  const canonicalNodeId = resolveCanonicalNodeId(nodeId || canonicalPath) || nodeId;
  if (pushHistory) {
    pushViewerNav(navEntry({ nodeId: state.selectedGraphNodeId, notePath: canonicalPath }));
    state.viewerNavForward = [];
  }
  if (canonicalNodeId) state.selectedGraphNodeId = canonicalNodeId;
  state.current.graphDetailPath = canonicalPath;
  const data = await api(`/api/projects/${encodeURIComponent(state.currentId)}/note?path=${encodeURIComponent(canonicalPath)}`);
  const backlinks = data.backlinks || [];
  const outgoing = data.outgoing_wikilinks || [];
  const local = data.local_graph || {};
  const markdownText = String(data.markdown || "");
  const sections = parseMarkdownSections(markdownText);
  const fallbackSummary = summaryNode.summary_excerpt || "";
  const fallbackFacts = summaryNode.key_facts_preview || [];
  const hasSummary = Boolean(sections.summary || fallbackSummary);
  const hasFacts = sections.facts.length > 0 || fallbackFacts.length > 0;
  const hasRelationships = sections.relationships.length > 0;
  const hasEvidence = sections.evidence.length > 0;
  const chapterIds = data.frontmatter?.chapter_ids || [];
  const summaryNode = (state.current.graph.nodes || []).find((item) => item.id === state.selectedGraphNodeId) || {};
  const showReviewAction = findReviewItemsByTerm(summaryNode.label || "").length > 0;
  const canonicalPathChanged = canonicalPath !== String(path || "");
  $("graph-detail").innerHTML = `
    ${graphNodeSummary(summaryNode)}
    <hr />
    ${canonicalPathChanged ? `<p class="muted">${escapeHtml(t('duplicateRedirected'))}</p>` : ""}
    <h3>${escapeHtml(data.title || data.path || summaryNode.label || '')}</h3>
    <p class="muted">${escapeHtml(t('degree'))} ${escapeHtml(fmtCount(data.degree || 0))}</p>
    <p>${(data.tags || []).map((tag) => `<span class="badge tag-badge">${escapeHtml(tag)}</span>`).join("")}</p>
    <h4>${escapeHtml(t('summary'))}</h4>
    ${hasSummary ? `<p>${escapeHtml(sections.summary || fallbackSummary)}</p>` : `<p class="note-fallback">${escapeHtml(t('noSummary'))}</p>`}
    <h4>${escapeHtml(t('facts'))}</h4>
    ${hasFacts ? `<ul>${(sections.facts.length ? sections.facts : fallbackFacts).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : `<p class="muted">${escapeHtml(t('noFacts'))}</p>`}
    <h4>${escapeHtml(t('storyRelationships'))}</h4>
    ${hasRelationships ? `<ul>${sections.relationships.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : `<p class="muted">—</p>`}
    <h4>${escapeHtml(t('appearancesEvidence'))}</h4>
    ${hasEvidence ? `<ul>${sections.evidence.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : `<p class="muted">${chapterIds.length ? chapterIds.map((item) => escapeHtml(item)).join(', ') : '—'}</p>`}
    <h4>${escapeHtml(t('markdownLinks'))}</h4>
    ${backlinks.length ? `<details><summary>${escapeHtml(t('backlinks'))}</summary><ul>${backlinks.map((item) => `<li><a href="#" class="wikilink" data-wikilink="${escapeHtml(item)}">${escapeHtml(item)}</a></li>`).join("")}</ul></details>` : ""}
    ${outgoing.length ? `<details><summary>${escapeHtml(t('outgoingLinks'))}</summary><ul>${outgoing.map((item) => `<li><a href="#" class="wikilink" data-wikilink="${escapeHtml(item.target || item.label || "")}">[[${escapeHtml(item.label || item.target || "")}]]</a></li>`).join("")}</ul></details>` : ""}
    ${showReviewAction ? `<div class="nav-actions"><button type="button" data-graph-open-review="${escapeHtml(summaryNode.label || '')}">${escapeHtml(t('openReview'))}</button></div>` : `<p class="muted">${escapeHtml(t('reviewUnavailable'))}</p>`}
    <details>
      <summary>${escapeHtml(t('technicalDetails'))}</summary>
      <p class="muted">${escapeHtml(data.path || '')}</p>
      ${(local.nodes || []).length ? `<p class="muted">${escapeHtml(t('localGraphSummary'))}: ${escapeHtml(fmtCount((local.nodes || []).length))} / ${escapeHtml(fmtCount((local.edges || []).length))}</p>` : ""}
      <pre class="frontmatter">${escapeHtml(JSON.stringify(data.frontmatter || {}, null, 2))}</pre>
      <details><summary>Markdown</summary><article class="markdown">${renderMarkdown(markdownText)}</article></details>
    </details>
  `;
  attachWikiLinkHandlers($("graph-detail"));
  bindGraphDetailNavigation();
  bindCanonicalizationInteractions();
}

function graphNodeSummary(node) {
  const entity = node.entity || {};
  const chapter = node.chapter || {};
  const frontmatter = node.frontmatter || {};
  const canonLabel = Object.keys(entity).length ? (entity.canonical_name || entity.preferred_slug || node.label || "") : "";
  const reviewLabel = entity.canonical_name || entity.preferred_slug || node.label || chapter.chapter_id || "";
  const hasReviewContext = reviewLabel ? findReviewItemsByTerm(reviewLabel).length > 0 : false;
  const canonicalNodeId = node.canonical_node_id || node.id;
  const canonicalNotePath = resolveCanonicalNotePath(node.canonical_note_path || node.note_path || "");
  const showOpenNote = canonicalNotePath && canonicalNotePath !== String(state.current?.graphDetailPath || "");
  return `
    ${renderNavNotice()}
    <article class="inspector-card narrative-card">
      <header>
        <h3>${escapeHtml(node.label || "Unresolved")}</h3>
        <p><span class="badge kind-badge kind-${escapeHtml(String(node.display_kind || node.canonical_kind || node.kind || 'unknown').toLowerCase())}">${escapeHtml(kindLabel(node.display_kind || node.canonical_kind || node.kind || "unknown"))}</span> <span class="badge">${escapeHtml(node.role || "unknown")}</span></p>
      </header>
      <section><h4>${escapeHtml(t('summary'))}</h4><p>${escapeHtml(entity.summary || node.summary || node.summary_excerpt || t('noSummary'))}</p></section>
      <section><h4>${escapeHtml(t('facts'))}</h4>${(entity.facts || entity.key_facts || node.key_facts_preview || []).length ? `<ul>${(entity.facts || entity.key_facts || node.key_facts_preview || []).slice(0, 12).map((fact) => `<li>${escapeHtml(String(fact))}</li>`).join('')}</ul>` : `<p class="muted">${escapeHtml(t('noFacts'))}</p>`}</section>
      <section><h4>${escapeHtml(t('storyRelationships'))}</h4>${(entity.relationships || []).length ? `<ul>${(entity.relationships || []).slice(0, 10).map((rel) => `<li>${escapeHtml(rel.target || rel.source || '')}${rel.type || rel.relation_type ? ` (${escapeHtml(rel.type || rel.relation_type)})` : ''}</li>`).join('')}</ul>` : `<p class="muted">—</p>`}</section>
      <section><h4>${escapeHtml(t('appearancesEvidence'))}</h4>${(entity.evidence_refs || []).length ? `<ul>${(entity.evidence_refs || []).slice(0, 10).map((ref) => `<li>${escapeHtml(ref.chapter_id || 'chapter')}${ref.pointer ? ` · ${escapeHtml(ref.pointer)}` : ''}</li>`).join('')}</ul>` : `<p class="muted">${escapeHtml(t('evidence'))}</p>`}</section>
      <section><h4>${escapeHtml(t('backlinks'))}</h4><p class="muted">${escapeHtml(fmtCount((node.backlinks || []).length))}</p></section>
      <div class="nav-actions">
        <button type="button" data-graph-nav-back ${state.viewerNavBack.length < 2 ? "disabled" : ""}>${escapeHtml(t('back'))}</button>
        <button type="button" data-graph-nav-forward ${state.viewerNavForward.length < 1 ? "disabled" : ""}>${escapeHtml(t('forward'))}</button>
        ${canonLabel ? `<button type="button" data-graph-open-canon="${escapeHtml(canonLabel)}">${escapeHtml(t('openInCanon'))}</button>` : ""}
        ${hasReviewContext ? `<button type="button" data-graph-open-review="${escapeHtml(reviewLabel)}">${escapeHtml(t('openReview'))}</button>` : ""}
        ${showOpenNote ? `<button type="button" data-graph-open-note="${escapeHtml(canonicalNotePath)}">${escapeHtml(t('viewInWiki'))}</button>` : ""}
      </div>
      ${state.viewerRecent.length ? `<p class="muted">${escapeHtml(t('recent'))}: ${state.viewerRecent.slice(0, 6).map((row) => `<button type="button" class="inline-action" data-graph-recent="${escapeHtml(row.id)}">${escapeHtml(row.label || row.id)}</button>`).join(' ')}</p>` : ""}
      <details class="technical-details">
        <summary>${escapeHtml(t('technicalDetails'))}</summary>
        ${canonicalNodeId !== node.id ? `<p class="muted">${escapeHtml(t('duplicateRedirected'))}: ${escapeHtml(node.id)} → ${escapeHtml(canonicalNodeId)}</p>` : ""}
        <p class="muted">${escapeHtml(t('degree'))} ${escapeHtml(fmtCount(node.degree || 0))}</p>
        ${Object.keys(frontmatter).length ? `<pre class="frontmatter">${escapeHtml(JSON.stringify(frontmatter, null, 2))}</pre>` : ""}
        ${Object.keys(entity).length ? entityDetail(entity) : ""}
      </details>
      ${Object.keys(entity).length ? renderCanonicalizationVisibility(entity, { source: "graph" }) : ""}
      ${Object.keys(chapter).length ? chapterDetail(chapter) : ""}
    </article>
  `;
}

function bindGraphDetailNavigation() {
  document.querySelectorAll("[data-graph-nav-back]").forEach((node) => node.addEventListener("click", viewerNavBack));
  document.querySelectorAll("[data-graph-nav-forward]").forEach((node) => node.addEventListener("click", viewerNavForward));
  document.querySelectorAll("[data-graph-recent]").forEach((node) => {
    node.addEventListener("click", () => {
      const nodeId = node.dataset.graphRecent || "";
      if (nodeId) selectGraphNode(nodeId, { pushHistory: true });
    });
  });
  document.querySelectorAll("[data-graph-open-canon]").forEach((node) => {
    node.addEventListener("click", () => {
      const term = node.dataset.graphOpenCanon || "";
      if (term) navigateToCanonTerm(term, { from: "Graph" });
    });
  });
  document.querySelectorAll("[data-graph-open-review]").forEach((node) => {
    node.addEventListener("click", () => {
      const term = node.dataset.graphOpenReview || "";
      if (term) navigateToReviewContext(term, { from: "Graph" });
    });
  });
  document.querySelectorAll("[data-graph-open-note]").forEach((node) => {
    node.addEventListener("click", () => {
      const path = node.dataset.graphOpenNote || "";
      if (path) openGraphNote(path, state.selectedGraphNodeId);
    });
  });
}

function bindCanonicalizationInteractions() {
  document.querySelectorAll("[data-canonvis-graph]").forEach((node) => {
    node.addEventListener("click", () => {
      const term = node.dataset.canonvisGraph || "";
      if (term) navigateToGraphTerm(term, { from: "Canonicalization" });
    });
  });
  document.querySelectorAll("[data-canonvis-review]").forEach((node) => {
    node.addEventListener("click", () => {
      const term = node.dataset.canonvisReview || "";
      if (term) navigateToReviewContext(term, { from: "Canonicalization" });
    });
  });
  document.querySelectorAll(".canonicalization-panel [data-health-artifact]").forEach((node) => {
    node.addEventListener("click", () => {
      setView("artifacts");
      openArtifact(node.dataset.healthArtifact);
    });
  });
}

function entityDetail(entity) {
  const aliases = entity.aliases || [];
  const facts = entity.facts || entity.key_facts || [];
  const relationships = entity.relationships || [];
  const relationshipsOut = entity.relationships_out || [];
  const relationshipsIn = entity.relationships_in || [];
  const mentions = entity.surface_forms || entity.source_mentions || [];
  const sourceRefs = entity.source_refs || [];
  const evidenceRefs = entity.evidence_refs || [];
  const backlinks = entity.backlinks || [];
  return `
    <div class="entity-detail">
      <dl class="meta-list">
        <div><dt>Slug</dt><dd>${escapeHtml(entity.preferred_slug || "")}</dd></div>
        <div><dt>State</dt><dd>${escapeHtml(entity.review_state || entity.note_role || "")}</dd></div>
        <div><dt>Kind</dt><dd>${escapeHtml(entity.entity_kind || entity.entity_subkind || "")}</dd></div>
      </dl>
      ${entity.summary ? `<h4>Summary</h4><p>${escapeHtml(entity.summary)}</p>` : ""}
      ${aliases.length ? `<h4>Aliases</h4><p>${aliases.slice(0, 24).map((alias) => `<span class="badge">${escapeHtml(alias)}</span>`).join("")}</p>` : ""}
      ${mentions.length ? `<h4>Surface forms</h4><p>${mentions.slice(0, 24).map((mention) => `<span class="badge">${escapeHtml(mention)}</span>`).join("")}</p>` : ""}
      ${facts.length ? `<h4>Facts</h4><ul>${facts.slice(0, 12).map((fact) => `<li>${escapeHtml(fact)}</li>`).join("")}</ul>` : ""}
      ${relationships.length ? `<h4>Relationships</h4><ul>${relationships.slice(0, 12).map((rel) => `<li><strong>${escapeHtml(rel.target || rel.source || "")}</strong>${rel.type || rel.relation_type ? ` (${escapeHtml(rel.type || rel.relation_type)})` : ""}${(rel.facts || []).length ? `: ${escapeHtml((rel.facts || [])[0])}` : ""}</li>`).join("")}</ul>` : ""}
      ${relationshipsOut.length ? `<h4>Outgoing links</h4><ul>${relationshipsOut.slice(0, 12).map((rel) => `<li>${escapeHtml(rel.label || rel.kind || "related_to")} → <strong>${escapeHtml(rel.target || "")}</strong></li>`).join("")}</ul>` : ""}
      ${relationshipsIn.length ? `<h4>Incoming links</h4><ul>${relationshipsIn.slice(0, 12).map((rel) => `<li><strong>${escapeHtml(rel.source || "")}</strong> → ${escapeHtml(rel.label || rel.kind || "related_to")}</li>`).join("")}</ul>` : ""}
      ${sourceRefs.length ? `<h4>Source refs</h4><ul>${sourceRefs.slice(0, 12).map((ref) => `<li>${escapeHtml(ref.chapter_id || ref.chapter || "chapter")}${ref.span_id ? ` · ${escapeHtml(ref.span_id)}` : ""}${ref.source_span ? ` · ${escapeHtml(ref.source_span)}` : ""}</li>`).join("")}</ul>` : ""}
      ${evidenceRefs.length ? `<h4>Evidence</h4><ul>${evidenceRefs.slice(0, 12).map((ref) => `<li>${escapeHtml(ref.chapter_id || "chapter")}${ref.pointer ? ` · ${escapeHtml(ref.pointer)}` : ""}</li>`).join("")}</ul>` : ""}
      ${backlinks.length ? `<h4>Backlinks</h4><p>${backlinks.slice(0, 20).map((item) => `<span class="badge">${escapeHtml(item)}</span>`).join("")}</p>` : ""}
    </div>
  `;
}

function selectedCanonEntity() {
  const key = normalizeKey(state.selectedCanonEntityKey || "");
  if (!key) return null;
  return allCanonEntities().find((entity) => canonEntityKey(entity) === key) || null;
}

function canonicalizationSummary(entity) {
  const payload = state.current && state.current.canonicalization ? state.current.canonicalization : {};
  const byEntity = payload.by_entity || {};
  const key = canonEntityKey(entity);
  return byEntity[key] || null;
}

function renderCanonicalizationVisibility(entity, { source = "canon" } = {}) {
  const summary = canonicalizationSummary(entity);
  if (!summary) return `<div class="canonicalization-panel panel"><p class="muted">Canonicalization visibility: not available.</p></div>`;
  const aliases = summary.aliases || [];
  const mentions = summary.source_mentions || [];
  const chapterRefs = summary.chapter_refs || [];
  const riskSignals = summary.risk_signals || [];
  const reviewItems = summary.related_review_items || [];
  const nearbyReviewEntities = summary.nearby_review_entities || [];
  const artifacts = summary.artifact_refs || [];
  const preVaerl = summary.pre_vaerl_matches || { counts: {}, samples: {} };
  const relationshipRec = summary.relationship_reconciliation || { counts: {}, samples: {} };
  return `
    <section class="canonicalization-panel panel">
      <div class="canonicalization-header">
        <div>
          <p class="eyebrow">Merge & Canonicalization Visibility</p>
          <h4>${escapeHtml(summary.canonical_name || entity.canonical_name || "not available")}</h4>
        </div>
        <span class="badge">${escapeHtml(summary.review_state || "not available")}</span>
      </div>
      <div class="canonicalization-metrics">
        <div><span>Slug</span><strong>${escapeHtml(summary.preferred_slug || "not available")}</strong></div>
        <div><span>Kind</span><strong>${escapeHtml(summary.entity_kind || "not available")}</strong></div>
        <div><span>Subkind</span><strong>${escapeHtml(summary.entity_subkind || "not available")}</strong></div>
        <div><span>Confidence</span><strong>${summary.confidence === null || summary.confidence === undefined ? "not available" : escapeHtml(summary.confidence)}</strong></div>
        <div><span>Aliases</span><strong>${fmtCount(aliases.length)}</strong></div>
        <div><span>Source mentions</span><strong>${fmtCount(mentions.length)}</strong></div>
        <div><span>Chapter refs</span><strong>${fmtCount(chapterRefs.length)}</strong></div>
        <div><span>Relationships</span><strong>${fmtCount(summary.relationship_count)}</strong></div>
        <div><span>Key facts</span><strong>${fmtCount(summary.key_fact_count)}</strong></div>
        <div><span>Review pressure</span><strong>${fmtCount(summary.review_pressure_count)}</strong></div>
      </div>
      <div class="canonicalization-actions">
        ${summary.canonical_name ? `<button type="button" class="inline-action" data-canonvis-graph="${escapeHtml(summary.canonical_name)}">Open in Graph</button>` : ""}
        ${summary.canonical_name ? `<button type="button" class="inline-action" data-canonvis-review="${escapeHtml(summary.canonical_name)}">Open Review Context</button>` : ""}
        ${artifacts.length ? artifacts.slice(0, 4).map((artifact) => `<button type="button" class="inline-action" data-health-artifact="${escapeHtml(artifact)}">Open ${escapeHtml(artifact)}</button>`).join("") : `<span class="muted">Audit artifacts: not available</span>`}
      </div>
      <div class="canonicalization-columns">
        <div>
          <h5>Aliases</h5>
          ${aliases.length ? `<p>${aliases.slice(0, 24).map((value) => `<span class="badge">${escapeHtml(value)}</span>`).join("")}</p>` : `<p class="muted">not available</p>`}
          <h5>Source mentions</h5>
          ${mentions.length ? `<p>${mentions.slice(0, 24).map((value) => `<span class="badge">${escapeHtml(value)}</span>`).join("")}</p>` : `<p class="muted">not available</p>`}
          <h5>Chapter refs</h5>
          ${chapterRefs.length ? `<p>${chapterRefs.slice(0, 20).map((value) => `<span class="badge">${escapeHtml(value)}</span>`).join("")}</p>` : `<p class="muted">not available</p>`}
        </div>
        <div>
          <h5>Risk signals</h5>
          ${riskSignals.length ? `<p>${riskSignals.map((signal) => `<span class="badge ${escapeHtml(signal.level === "warning" ? "warning-badge" : "")}">${escapeHtml(signal.label)}: ${escapeHtml(signal.value)}</span>`).join("")}</p>` : `<p class="muted">not available</p>`}
          <h5>Nearby review entities</h5>
          ${nearbyReviewEntities.length ? `<ul>${nearbyReviewEntities.slice(0, 6).map((row) => `<li><strong>${escapeHtml(row.canonical_name || "not available")}</strong> · ${escapeHtml(row.review_state || "review")} · conf ${escapeHtml(row.confidence === undefined ? "n/a" : row.confidence)}</li>`).join("")}</ul>` : `<p class="muted">not available</p>`}
          <h5>Related review items</h5>
          ${reviewItems.length ? `<ul>${reviewItems.slice(0, 6).map((row) => `<li><span class="badge severity-${escapeHtml(String(row.severity || "unknown").toLowerCase())}">${escapeHtml(row.severity || "unknown")}</span> ${escapeHtml(row.review_type || "unknown")} · ${escapeHtml(row.source_entity || "n/a")} → ${escapeHtml(row.target_text || "n/a")}</li>`).join("")}</ul>` : `<p class="muted">not available</p>`}
        </div>
      </div>
      ${renderCanonicalizationAuditSection("Resolution audit", summary.resolution_match)}
      ${renderCanonicalizationAuditSection("Cluster audit", summary.cluster_match)}
      ${renderCanonicalizationAuditSection("Promotion decision", summary.promotion_match)}
      ${renderCanonicalizationAuditSection("Resolved entity", summary.resolved_entity)}
      ${renderCanonicalizationAuditSection("Cleaned entity", summary.cleaned_entity)}
      ${renderCanonicalizationAuditSection("Cleanup summary", summary.cleanup_summary)}
      ${renderCanonicalizationAuditSection("Pre-VaERL reconciliation", preVaerl)}
      ${renderCanonicalizationAuditSection("Relationship reconciliation", relationshipRec)}
      ${renderCanonicalizationAuditSection("Unresolved relationship hints", { items: summary.unresolved_relationship_hints || [] })}
      ${source === "canon" ? `<p class="muted">Panel is observability-only. No merge/canonicalization actions are executed here.</p>` : ""}
    </section>
  `;
}

function renderCanonicalizationAuditSection(title, payload) {
  if (!payload || (typeof payload === "object" && !Array.isArray(payload) && !Object.keys(payload).length)) {
    return `<details class="canonicalization-audit"><summary>${escapeHtml(title)}</summary><p class="muted">not available</p></details>`;
  }
  return `
    <details class="canonicalization-audit">
      <summary>${escapeHtml(title)}</summary>
      <pre class="frontmatter">${escapeHtml(JSON.stringify(payload, null, 2))}</pre>
    </details>
  `;
}

function chapterDetail(chapter) {
  const summary = chapter.chapter_summary || chapter.summary || "";
  return `
    <div class="entity-detail">
      <dl class="meta-list">
        <div><dt>Sequence</dt><dd>${escapeHtml(chapter.sequence_index || "")}</dd></div>
        <div><dt>Label</dt><dd>${escapeHtml(chapter.chapter_label_type || "")}</dd></div>
        <div><dt>Label number</dt><dd>${escapeHtml(chapter.chapter_number_in_label === null ? "null" : chapter.chapter_number_in_label || "")}</dd></div>
      </dl>
      ${summary ? `<h4>Summary</h4><p>${escapeHtml(summary)}</p>` : ""}
      ${chapter.title_parse_signals ? `<details><summary>Title parse signals</summary><pre class="frontmatter">${escapeHtml(JSON.stringify(chapter.title_parse_signals, null, 2))}</pre></details>` : ""}
    </div>
  `;
}

function resetGraphViewBox() {
  clearGraphPositions();
  if (state.current && state.current.graph) state.current.graphDetailPath = "";
  state.graphViewBox = { x: 0, y: 0, width: 1200, height: 720 };
  applyGraphViewBox();
  if (state.activeView === "graph") renderGraph();
}

function applyGraphViewBox() {
  const svg = $("graph-svg");
  if (!svg) return;
  const box = state.graphViewBox;
  svg.setAttribute("viewBox", `${box.x} ${box.y} ${box.width} ${box.height}`);
}

function zoomGraph(factor, anchor = null) {
  const svg = $("graph-svg");
  const box = state.graphViewBox;
  const point = anchor || { x: box.x + box.width / 2, y: box.y + box.height / 2 };
  const nextWidth = Math.max(180, Math.min(2600, box.width * factor));
  const nextHeight = Math.max(108, Math.min(1560, box.height * factor));
  const relX = (point.x - box.x) / box.width;
  const relY = (point.y - box.y) / box.height;
  state.graphViewBox = {
    x: point.x - nextWidth * relX,
    y: point.y - nextHeight * relY,
    width: nextWidth,
    height: nextHeight,
  };
  applyGraphViewBox(svg);
}

function bindGraphViewportHandlers(svg) {
  svg.onwheel = (event) => {
    event.preventDefault();
    zoomGraph(event.deltaY < 0 ? 0.86 : 1.16, clientToGraphPoint(svg, event.clientX, event.clientY));
  };
  svg.onpointerdown = (event) => {
    if (event.target.closest(".node")) return;
    svg.setPointerCapture(event.pointerId);
    state.graphPan = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
    state.graphDidPan = false;
  };
  svg.onpointermove = (event) => {
    if (!state.graphPan || state.graphPan.pointerId !== event.pointerId) return;
    const dx = event.clientX - state.graphPan.x;
    const dy = event.clientY - state.graphPan.y;
    if (Math.abs(dx) + Math.abs(dy) > 2) state.graphDidPan = true;
    const rect = svg.getBoundingClientRect();
    const box = state.graphViewBox;
    state.graphViewBox = {
      ...box,
      x: box.x - dx * (box.width / Math.max(rect.width, 1)),
      y: box.y - dy * (box.height / Math.max(rect.height, 1)),
    };
    state.graphPan = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
    applyGraphViewBox();
  };
  svg.onpointerup = (event) => finishGraphPan(svg, event.pointerId);
  svg.onpointercancel = (event) => finishGraphPan(svg, event.pointerId);
}

function finishGraphPan(svg, pointerId) {
  if (!state.graphPan || state.graphPan.pointerId !== pointerId) return;
  try {
    svg.releasePointerCapture(pointerId);
  } catch (_error) {
    // Browsers may release capture automatically.
  }
  state.graphPan = null;
}

function clientToGraphPoint(svg, clientX, clientY) {
  const rect = svg.getBoundingClientRect();
  const box = state.graphViewBox;
  return {
    x: box.x + ((clientX - rect.left) / Math.max(rect.width, 1)) * box.width,
    y: box.y + ((clientY - rect.top) / Math.max(rect.height, 1)) * box.height,
  };
}

function nodeColor(node) {
  return kindColor(node.kind);
}

function kindColor(kind) {
  return KIND_COLORS[String(kind || "concept")] || KIND_COLORS.concept;
}

function slugify(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .toLowerCase();
}

function nodeStatusBorder(node) {
  const status = node.frontmatter?.review_state || node.frontmatter?.status || node.visual?.status || "ready";
  return node.visual?.status_border || STATUS_BORDERS[status] || "#fffaf0";
}

globalThis.__TEXTIFAI_REVIEW_ACTIONS__ = {
  mapRecommendedActionToViewerActions,
  normalizedFutureViewerActions,
  reviewActionPresentation,
  groupReviewItemsForPresentation,
  summarizeReviewPresentationGroups,
  renderReviewPresentationSummary,
  reviewQuickFilterPresentation,
  applyReviewQuickFilter,
  deriveReviewCandidates,
  applyReviewCandidateFilter,
  renderReviewPresentationGroups,
  renderReviewGroupCard,
  renderReviewActionDescriptors,
  renderReviewContractWarnings,
  renderReviewItemCard,
};

document.querySelectorAll(".tabs button").forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
$("refresh-projects").addEventListener("click", loadProjects);
$("hide-system").addEventListener("change", renderGraph);
$("hide-review").addEventListener("change", renderGraph);
$("hide-chapters").addEventListener("change", renderGraph);
$("graph-zoom-in").addEventListener("click", () => zoomGraph(0.82));
$("graph-zoom-out").addEventListener("click", () => zoomGraph(1.22));
$("graph-zoom-reset").addEventListener("click", resetGraphViewBox);

loadProjects().catch((error) => {
  $("project-list").innerHTML = `<div class="panel">Failed to load projects: ${escapeHtml(error.message)}</div>`;
});
