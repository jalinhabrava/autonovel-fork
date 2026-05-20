const state = {
  projects: [],
  current: null,
  currentId: null,
  activeView: "overview",
  selectedGraphNodeId: null,
  graphAnimation: null,
  graphViewBox: { x: 0, y: 0, width: 1200, height: 720 },
  graphPan: null,
  graphDidPan: false,
  hiddenGraphTags: new Set(),
};

const $ = (id) => document.getElementById(id);

async function api(path) {
  const response = await fetch(path);
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

async function loadProjects() {
  const data = await api("/api/projects");
  state.projects = data.projects || [];
  renderProjects();
}

function renderProjects() {
  $("project-list").innerHTML = state.projects.map((project) => `
    <div class="project-card ${project.project_id === state.currentId ? "active" : ""}" data-project="${project.project_id}">
      <strong>${escapeHtml(project.name)}</strong>
      <small>${escapeHtml(project.kind)} · ${fmtCount(project.primary_count)} primaries · ${fmtCount(project.review_queue_count)} review items</small>
      <small>${escapeHtml(project.invariants_status || "no invariant audit")}</small>
    </div>
  `).join("");
  document.querySelectorAll("[data-project]").forEach((node) => {
    node.addEventListener("click", () => selectProject(node.dataset.project));
  });
}

async function selectProject(projectId) {
  state.currentId = projectId;
  state.current = await api(`/api/projects/${encodeURIComponent(projectId)}`);
  state.selectedGraphNodeId = null;
  state.hiddenGraphTags = new Set();
  resetGraphViewBox();
  $("graph-kind-filter").dataset.ready = "";
  renderProjects();
  renderCurrentProject();
}

function renderCurrentProject() {
  const project = state.current.project;
  const canon = state.current.canon;
  $("project-title").textContent = project.name;
  $("project-meta").textContent = `${project.kind} · ${project.root}`;
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

function renderOverview() {
  if (!state.current) return;
  const canon = state.current.canon;
  const queue = canon.review_queue || {};
  $("view-overview").innerHTML = `
    <div class="stats-grid">
      <div class="stat-card"><span>Chapters</span><strong>${canon.chapters.length}</strong></div>
      <div class="stat-card"><span>Primaries</span><strong>${canon.primaries.length}</strong></div>
      <div class="stat-card"><span>Review Entities</span><strong>${canon.review_entities.length}</strong></div>
      <div class="stat-card"><span>Review Items</span><strong>${fmtCount(queue.item_count)}</strong></div>
    </div>
    ${renderSemanticHealth(state.current.health || {})}
    <div class="panel">
      <h3>${escapeHtml((canon.work || {}).title || "Untitled work")}</h3>
      <p class="muted">Language: ${escapeHtml((canon.work || {}).language || "unknown")}</p>
      <p class="muted">System root: ${escapeHtml(state.current.project.system_root || "not found")}</p>
    </div>
  `;
  attachHealthArtifactLinks();
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
  const checks = invariants.failing_checks || [];
  return `
    <div class="health-inline">
      ${healthStatusBadge(invariants.status || "not_available")}
      <span>Failures: <strong>${fmtCount(invariants.failure_count)}</strong></span>
      <span>Warnings: <strong>${fmtCount(invariants.warning_count)}</strong></span>
      ${invariants.raw_artifact_path ? `<button class="artifact-link" data-health-artifact="${escapeHtml(invariants.raw_artifact_path)}">Open raw artifact</button>` : ""}
    </div>
    ${checks.length ? `<table class="table compact-table"><thead><tr><th>Check</th><th>Status</th><th>Summary</th></tr></thead><tbody>
      ${checks.slice(0, 8).map((check) => `<tr>
        <td>${escapeHtml(check.name)}</td>
        <td>${escapeHtml(check.status)}</td>
        <td>${escapeHtml(check.summary)}</td>
      </tr>`).join("")}
    </tbody></table>` : `<p class="muted">No failing or warning invariant checks available.</p>`}
  `;
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

function attachHealthArtifactLinks() {
  document.querySelectorAll("[data-health-artifact]").forEach((node) => {
    node.addEventListener("click", () => {
      setView("artifacts");
      openArtifact(node.dataset.healthArtifact);
    });
  });
}

function renderNotes() {
  if (!state.current) return;
  const notes = state.current.notes || [];
  const filter = $("note-filter");
  const draw = () => {
    const needle = filter.value.toLowerCase();
    $("note-list").innerHTML = notes
      .filter((note) => `${note.path} ${note.tags.join(" ")} ${note.role}`.toLowerCase().includes(needle))
      .map((note) => `
        <div class="list-item" data-note="${escapeHtml(note.path)}">
          <strong>${escapeHtml(note.name)}</strong>
          <small>${escapeHtml(note.path)}</small>
          <small>${escapeHtml(note.role)} ${note.tags.map((tag) => `<span class="badge">${escapeHtml(tag)}</span>`).join("")}</small>
        </div>
      `).join("");
    document.querySelectorAll("[data-note]").forEach((node) => {
      node.addEventListener("click", () => openNote(node.dataset.note));
    });
  };
  filter.oninput = draw;
  draw();
}

async function openNote(path) {
  const data = await api(`/api/projects/${encodeURIComponent(state.currentId)}/note?path=${encodeURIComponent(path)}`);
  $("note-detail").innerHTML = `
    <h3>${escapeHtml(data.path)}</h3>
    <details open><summary>Frontmatter</summary><pre class="frontmatter">${escapeHtml(JSON.stringify(data.frontmatter || {}, null, 2))}</pre></details>
    <article class="markdown">${renderMarkdown(data.markdown || "")}</article>
  `;
  attachWikiLinkHandlers($("note-detail"));
  selectGraphNodeByNotePath(path, { render: false });
  highlightNote(path);
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
    state.selectedGraphNodeId = resolved.nodeId;
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
  return {
    nodeId: (node && node.id) || findNodeIdByNotePath(note && note.path),
    notePath: (node && node.note_path) || (note && note.path) || null,
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
  const key = normalizeKey(path);
  const graph = state.current && state.current.graph ? state.current.graph : { nodes: [] };
  const node = (graph.nodes || []).find((item) => normalizeKey(item.note_path || "") === key);
  return node ? node.id : null;
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

function highlightNote(path) {
  document.querySelectorAll("[data-note]").forEach((node) => node.classList.toggle("active", node.dataset.note === path));
}

function renderCanon() {
  const canon = state.current.canon;
  $("view-canon").innerHTML = `
    <h3>Primaries</h3>
    ${entityTable(canon.primaries)}
    <h3 style="margin-top:24px">Chapters</h3>
    ${chapterTable(canon.chapters)}
    <h3 style="margin-top:24px">Review Entities</h3>
    ${entityTable(canon.review_entities.slice(0, 80))}
  `;
}

function entityTable(entities) {
  return `<table class="table"><thead><tr><th>Name</th><th>Kind</th><th>Slug</th><th>Summary</th></tr></thead><tbody>
    ${entities.map((entity) => `<tr>
      <td>${escapeHtml(entity.canonical_name)}</td>
      <td>${escapeHtml(entity.entity_kind || "")}</td>
      <td>${escapeHtml(entity.preferred_slug || "")}</td>
      <td>${escapeHtml(entity.summary || "").slice(0, 260)}</td>
    </tr>`).join("")}
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
  $("view-review").innerHTML = `
    <div class="stats-grid">
      <div class="stat-card"><span>Items</span><strong>${items.length}</strong></div>
      <div class="stat-card"><span>Types</span><strong>${Object.keys(queue.counts_by_type || {}).length}</strong></div>
      <div class="stat-card"><span>Status</span><strong style="font-size:20px">${escapeHtml(queue.status || "unknown")}</strong></div>
    </div>
    <table class="table"><thead><tr><th>Severity</th><th>Type</th><th>Source</th><th>Target</th><th>Candidates</th><th>Evidence</th></tr></thead><tbody>
      ${items.map((item) => `<tr>
        <td>${escapeHtml(item.severity)}</td>
        <td>${escapeHtml(item.review_type)}</td>
        <td>${escapeHtml(item.source_entity)}</td>
        <td>${escapeHtml(item.target_text)}</td>
        <td>${(item.candidate_entities || []).slice(0, 3).map((c) => `<span class="badge">${escapeHtml(c.canonical_name)} ${c.entity_kind ? `(${escapeHtml(c.entity_kind)})` : ""}</span>`).join("")}</td>
        <td>${escapeHtml(((item.evidence || [])[0] || {}).text || "").slice(0, 220)}</td>
      </tr>`).join("")}
    </tbody></table>
  `;
}

function renderArtifacts() {
  const artifacts = state.current.artifacts || [];
  $("artifact-list").innerHTML = artifacts.map((artifact) => `
    <div class="list-item" data-artifact="${escapeHtml(artifact.path)}">
      <strong>${escapeHtml(artifact.name)}</strong>
      <small>${escapeHtml(artifact.kind)} · ${fmtCount(artifact.size)} bytes</small>
    </div>
  `).join("");
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
  const graph = state.current.graph || { nodes: [], edges: [] };
  const hideSystem = $("hide-system").checked;
  const hideReview = $("hide-review").checked;
  const hideChapters = $("hide-chapters").checked;
  const kindFilter = $("graph-kind-filter").value;
  const kinds = [...new Set(graph.nodes.map((node) => node.kind).filter(Boolean))].sort();
  const tags = [...new Set(graph.nodes.flatMap((node) => node.tags || []))].sort();
  if (!$("graph-kind-filter").dataset.ready) {
    $("graph-kind-filter").innerHTML = `<option value="">all kinds</option>${kinds.map((kind) => `<option value="${escapeHtml(kind)}">${escapeHtml(kind)}</option>`).join("")}`;
    $("graph-kind-filter").dataset.ready = "1";
    $("graph-kind-filter").onchange = renderGraph;
  }
  renderGraphTagFilter(tags);
  const visibleNodes = graph.nodes.filter((node) => {
    if (hideSystem && node.role === "system") return false;
    if (hideReview && node.role === "review") return false;
    if (hideChapters && node.role === "chapter") return false;
    if (kindFilter && node.kind !== kindFilter) return false;
    if ((node.tags || []).some((tag) => state.hiddenGraphTags.has(tag))) return false;
    return true;
  });
  const visibleIds = new Set(visibleNodes.map((node) => node.id));
  const visibleEdges = graph.edges.filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target));
  drawForceGraph(visibleNodes, visibleEdges);
}

function renderGraphTagFilter(tags) {
  const container = $("graph-tag-filter");
  if (!container) return;
  const activeCount = state.hiddenGraphTags.size;
  container.innerHTML = `
    <span class="tag-filter-label">Hide tags</span>
    ${tags.map((tag) => `
      <button type="button" class="tag-chip ${state.hiddenGraphTags.has(tag) ? "active" : ""}" data-graph-tag="${escapeHtml(tag)}">${escapeHtml(tag)}</button>
    `).join("")}
    ${activeCount ? `<button type="button" class="tag-chip clear" id="clear-graph-tags">clear ${activeCount}</button>` : ""}
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

function drawForceGraph(nodes, edges) {
  const svg = $("graph-svg");
  const width = 1200;
  const height = 720;
  const byId = seedGraphPositions(nodes, width, height);
  svg.innerHTML = `
    <g class="edges"></g>
    <g class="nodes">
    ${Object.values(byId).map((node) => `
      <g class="node ${node.id === state.selectedGraphNodeId ? "selected" : ""}" data-node="${escapeHtml(node.id)}" transform="translate(${node.x}, ${node.y})">
        <circle r="${node.role === "primary" ? 11 : 8}" fill="${nodeColor(node)}"></circle>
        <text x="14" y="4">${escapeHtml(node.label)}</text>
      </g>
    `).join("")}
    </g>
  `;
  const edgeLayer = svg.querySelector(".edges");
  edgeLayer.innerHTML = edges.map((edge, index) => `<line class="edge" data-edge="${index}"><title>${escapeHtml(edge.type)}</title></line>`).join("");
  applyGraphViewBox();
  bindGraphViewportHandlers(svg);

  svg.querySelectorAll("[data-node]").forEach((nodeEl) => {
    nodeEl.addEventListener("click", (event) => {
      event.stopPropagation();
      if (state.graphDidPan) {
        state.graphDidPan = false;
        return;
      }
      const node = byId[nodeEl.dataset.node];
      selectGraphNode(node.id);
    });
  });

  let tick = 0;
  const step = () => {
    runForceTick(byId, edges, width, height, tick);
    updateGraphDom(svg, byId, edges);
    tick += 1;
    if (tick < 180) state.graphAnimation = requestAnimationFrame(step);
  };
  step();
  if (state.selectedGraphNodeId && byId[state.selectedGraphNodeId]) {
    renderGraphNodeDetail(byId[state.selectedGraphNodeId]);
  }
}

function seedGraphPositions(nodes, width, height) {
  return Object.fromEntries(nodes.map((node, index) => {
    const previous = node._position || {};
    const angle = (index / Math.max(nodes.length, 1)) * Math.PI * 2;
    const radius = 180 + (index % 7) * 28;
    return [node.id, {
      ...node,
      x: previous.x === undefined ? width / 2 + Math.cos(angle) * radius : previous.x,
      y: previous.y === undefined ? height / 2 + Math.sin(angle) * radius : previous.y,
      vx: previous.vx === undefined ? 0 : previous.vx,
      vy: previous.vy === undefined ? 0 : previous.vy,
    }];
  }));
}

function runForceTick(byId, edges, width, height, tick) {
  const nodes = Object.values(byId);
  const cooling = Math.max(0.12, 1 - tick / 190);
  for (let i = 0; i < nodes.length; i += 1) {
    for (let j = i + 1; j < nodes.length; j += 1) {
      const a = nodes[i], b = nodes[j];
      const dx = a.x - b.x || 0.01;
      const dy = a.y - b.y || 0.01;
      const dist2 = dx * dx + dy * dy;
      const force = Math.min(4500 / dist2, 2.4) * cooling;
      a.vx += dx * force * 0.012;
      a.vy += dy * force * 0.012;
      b.vx -= dx * force * 0.012;
      b.vy -= dy * force * 0.012;
    }
  }
  for (const edge of edges) {
    const a = byId[edge.source], b = byId[edge.target];
    if (!a || !b) continue;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const desired = 120;
    const force = (dist - desired) * 0.006 * cooling;
    const fx = (dx / dist) * force;
    const fy = (dy / dist) * force;
    a.vx += fx;
    a.vy += fy;
    b.vx -= fx;
    b.vy -= fy;
  }
  for (const node of nodes) {
    node.vx += (width / 2 - node.x) * 0.0008 * cooling;
    node.vy += (height / 2 - node.y) * 0.0008 * cooling;
    node.vx *= 0.86;
    node.vy *= 0.86;
    node.x = Math.max(30, Math.min(width - 180, node.x + node.vx));
    node.y = Math.max(30, Math.min(height - 30, node.y + node.vy));
  }
}

function updateGraphDom(svg, byId, edges) {
  svg.querySelectorAll("[data-edge]").forEach((line) => {
    const edge = edges[Number(line.dataset.edge)];
    const a = byId[edge.source], b = byId[edge.target];
    if (!a || !b) return;
    line.setAttribute("x1", a.x);
    line.setAttribute("y1", a.y);
    line.setAttribute("x2", b.x);
    line.setAttribute("y2", b.y);
  });
  svg.querySelectorAll("[data-node]").forEach((nodeEl) => {
    const node = byId[nodeEl.dataset.node];
    if (!node) return;
    nodeEl.setAttribute("transform", `translate(${node.x}, ${node.y})`);
    nodeEl.classList.toggle("selected", node.id === state.selectedGraphNodeId);
  });
}

function selectGraphNode(nodeId) {
  state.selectedGraphNodeId = nodeId;
  const graph = state.current && state.current.graph ? state.current.graph : { nodes: [] };
  const node = (graph.nodes || []).find((item) => item.id === nodeId);
  if (!node) return;
  renderGraphNodeDetail(node);
  document.querySelectorAll("[data-node]").forEach((nodeEl) => nodeEl.classList.toggle("selected", nodeEl.dataset.node === nodeId));
}

async function renderGraphNodeDetail(node) {
  if (node.note_path) {
    await openGraphNote(node.note_path, node.id);
    return;
  }
  $("graph-detail").innerHTML = graphNodeSummary(node);
}

async function openGraphNote(path, nodeId = null) {
  if (nodeId) state.selectedGraphNodeId = nodeId;
  const data = await api(`/api/projects/${encodeURIComponent(state.currentId)}/note?path=${encodeURIComponent(path)}`);
  $("graph-detail").innerHTML = `
    ${graphNodeSummary((state.current.graph.nodes || []).find((item) => item.id === state.selectedGraphNodeId) || {})}
    <hr />
    <h3>${escapeHtml(data.path)}</h3>
    <details><summary>Frontmatter</summary><pre class="frontmatter">${escapeHtml(JSON.stringify(data.frontmatter || {}, null, 2))}</pre></details>
    <article class="markdown">${renderMarkdown(data.markdown || "")}</article>
  `;
  attachWikiLinkHandlers($("graph-detail"));
}

function graphNodeSummary(node) {
  const entity = node.entity || {};
  const chapter = node.chapter || {};
  const hasVaerlDetail = Object.keys(entity).length || Object.keys(chapter).length;
  return `
    <h3>${escapeHtml(node.label || "Unresolved")}</h3>
    <p><span class="badge">${escapeHtml(node.kind || "unknown")}</span> <span class="badge">${escapeHtml(node.role || "unknown")}</span></p>
    ${(node.tags || []).length ? `<p>${(node.tags || []).map((tag) => `<span class="badge tag-badge">${escapeHtml(tag)}</span>`).join("")}</p>` : ""}
    <p class="muted">${escapeHtml(node.id || "")}</p>
    ${node.note_path
      ? `<p class="muted">${escapeHtml(node.note_path)}</p>`
      : hasVaerlDetail
        ? `<p class="note-fallback">No Markdown note found. Showing VaERL data from <code>obsidian_import.json</code>.</p>`
        : `<p class="muted">No materialized note or VaERL detail for this node.</p>`}
    ${Object.keys(entity).length ? entityDetail(entity) : ""}
    ${Object.keys(chapter).length ? chapterDetail(chapter) : ""}
  `;
}

function entityDetail(entity) {
  const aliases = entity.aliases || [];
  const facts = entity.key_facts || [];
  const relationships = entity.relationships || [];
  const mentions = entity.source_mentions || [];
  return `
    <div class="entity-detail">
      <dl class="meta-list">
        <div><dt>Slug</dt><dd>${escapeHtml(entity.preferred_slug || "")}</dd></div>
        <div><dt>State</dt><dd>${escapeHtml(entity.review_state || entity.note_role || "")}</dd></div>
        <div><dt>Subkind</dt><dd>${escapeHtml(entity.entity_subkind || "")}</dd></div>
      </dl>
      ${entity.summary ? `<h4>Summary</h4><p>${escapeHtml(entity.summary)}</p>` : ""}
      ${aliases.length ? `<h4>Aliases</h4><p>${aliases.slice(0, 24).map((alias) => `<span class="badge">${escapeHtml(alias)}</span>`).join("")}</p>` : ""}
      ${facts.length ? `<h4>Key facts</h4><ul>${facts.slice(0, 12).map((fact) => `<li>${escapeHtml(fact)}</li>`).join("")}</ul>` : ""}
      ${relationships.length ? `<h4>Relationships</h4><ul>${relationships.slice(0, 12).map((rel) => `<li><strong>${escapeHtml(rel.target || "")}</strong>${rel.type || rel.relation_type ? ` (${escapeHtml(rel.type || rel.relation_type)})` : ""}${(rel.facts || []).length ? `: ${escapeHtml((rel.facts || [])[0])}` : ""}</li>`).join("")}</ul>` : ""}
      ${mentions.length ? `<h4>Source mentions</h4><p>${mentions.slice(0, 20).map((mention) => `<span class="badge">${escapeHtml(mention)}</span>`).join("")}</p>` : ""}
    </div>
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
  state.graphViewBox = { x: 0, y: 0, width: 1200, height: 720 };
  applyGraphViewBox();
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
  if (node.role === "primary") return "#1d6f68";
  if (node.role === "review") return "#b45b35";
  if (node.role === "chapter") return "#8b7b52";
  if (node.kind === "unresolved") return "#a23b55";
  return "#5b6577";
}

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
