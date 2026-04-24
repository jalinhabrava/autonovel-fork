const state = {
  projects: [],
  current: null,
  currentId: null,
  activeView: "overview",
};

const $ = (id) => document.getElementById(id);

async function api(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
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
    <div class="panel">
      <h3>${escapeHtml((canon.work || {}).title || "Untitled work")}</h3>
      <p class="muted">Language: ${escapeHtml((canon.work || {}).language || "unknown")}</p>
      <p class="muted">System root: ${escapeHtml(state.current.project.system_root || "not found")}</p>
    </div>
  `;
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
  return text.replace(/\[\[([^\]]+)\]\]/g, "<strong>[[$1]]</strong>");
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
  const graph = state.current.graph || { nodes: [], edges: [] };
  const hideSystem = $("hide-system").checked;
  const hideReview = $("hide-review").checked;
  const hideChapters = $("hide-chapters").checked;
  const kindFilter = $("graph-kind-filter").value;
  const kinds = [...new Set(graph.nodes.map((node) => node.kind).filter(Boolean))].sort();
  if (!$("graph-kind-filter").dataset.ready) {
    $("graph-kind-filter").innerHTML = `<option value="">all kinds</option>${kinds.map((kind) => `<option value="${escapeHtml(kind)}">${escapeHtml(kind)}</option>`).join("")}`;
    $("graph-kind-filter").dataset.ready = "1";
    $("graph-kind-filter").onchange = renderGraph;
  }
  const visibleNodes = graph.nodes.filter((node) => {
    if (hideSystem && node.role === "system") return false;
    if (hideReview && node.role === "review") return false;
    if (hideChapters && node.role === "chapter") return false;
    if (kindFilter && node.kind !== kindFilter) return false;
    return true;
  });
  const visibleIds = new Set(visibleNodes.map((node) => node.id));
  const visibleEdges = graph.edges.filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target));
  drawGraph(visibleNodes, visibleEdges);
}

function drawGraph(nodes, edges) {
  const svg = $("graph-svg");
  const width = 1200;
  const height = 720;
  const byId = Object.fromEntries(nodes.map((node, index) => {
    const angle = (index / Math.max(nodes.length, 1)) * Math.PI * 2;
    const radius = 230 + (index % 5) * 24;
    return [node.id, { ...node, x: width / 2 + Math.cos(angle) * radius, y: height / 2 + Math.sin(angle) * radius }];
  }));
  svg.innerHTML = `
    ${edges.map((edge) => {
      const a = byId[edge.source], b = byId[edge.target];
      if (!a || !b) return "";
      return `<line class="edge" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"><title>${escapeHtml(edge.type)}</title></line>`;
    }).join("")}
    ${Object.values(byId).map((node) => `
      <g class="node" data-node="${escapeHtml(node.id)}" transform="translate(${node.x}, ${node.y})">
        <circle r="${node.role === "primary" ? 11 : 8}" fill="${nodeColor(node)}"></circle>
        <text x="14" y="4">${escapeHtml(node.label)}</text>
      </g>
    `).join("")}
  `;
  svg.querySelectorAll("[data-node]").forEach((nodeEl) => {
    nodeEl.addEventListener("click", () => {
      const node = byId[nodeEl.dataset.node];
      $("graph-detail").innerHTML = `
        <h3>${escapeHtml(node.label)}</h3>
        <p><span class="badge">${escapeHtml(node.kind)}</span> <span class="badge">${escapeHtml(node.role)}</span></p>
        <p class="muted">${escapeHtml(node.id)}</p>
        ${node.note_path ? `<button id="open-node-note">Open note</button>` : ""}
      `;
      const button = $("open-node-note");
      if (button) {
        button.onclick = () => {
          setView("notes");
          openNote(node.note_path);
        };
      }
    });
  });
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

loadProjects().catch((error) => {
  $("project-list").innerHTML = `<div class="panel">Failed to load projects: ${escapeHtml(error.message)}</div>`;
});
