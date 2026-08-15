const API_BASE = window.DATAGUARD_API_BASE || "https://datagaurdai.onrender.com" || "http://localhost:8000";

const AGENT_STAGES = [
  { id: "ingestion",  label: "Ingestion" },
  { id: "profiling",  label: "Profiling" },
  { id: "checker",    label: "Quality check" },
  { id: "advisor",    label: "Repair advice" },
  { id: "planner",    label: "Planning" },
  { id: "executor",   label: "Execution" },
  { id: "scorer",     label: "Evaluation" },
  { id: "explainer",  label: "Explanation" },
  { id: "monitor",    label: "Monitoring" },
];

let selectedFile = null;

const $ = (id) => document.getElementById(id);

// ---------- upload interactions ----------
const dropzone = $("dropzone");
const fileInput = $("file-input");
const dzFilename = $("dz-filename");
const runBtn = $("run-btn");
const runHint = $("run-hint");

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    fileInput.click();
  }
});

["dragenter", "dragover"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  })
);
["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
  })
);
dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  if (file) handleFileSelect(file);
});
fileInput.addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (file) handleFileSelect(file);
});

function handleFileSelect(file) {
  if (!file.name.toLowerCase().endsWith(".csv")) {
    runHint.textContent = "That's not a .csv file. Choose a CSV.";
    runHint.classList.add("err");
    return;
  }
  selectedFile = file;
  dzFilename.textContent = file.name;
  runBtn.disabled = false;
  runHint.textContent = "Ready to run.";
  runHint.classList.remove("err");
}

runBtn.addEventListener("click", runPipeline);

// ---------- pipeline rail ----------
function buildRail() {
  const rail = $("rail");
  rail.innerHTML = "";
  AGENT_STAGES.forEach((stage) => {
    const node = document.createElement("div");
    node.className = "rail-node";
    node.id = `rail-${stage.id}`;
    node.innerHTML = `<div class="rail-dot"></div><div class="rail-label">${stage.label}</div>`;
    rail.appendChild(node);
  });
}

async function animateRail() {
  // Purely visual sequencing while the real request is in flight —
  // the backend runs synchronously, so this gives a sense of progress
  // rather than tracking literal server-side stage completion.
  for (const stage of AGENT_STAGES) {
    const node = $(`rail-${stage.id}`);
    node.classList.add("running");
    await sleep(140);
    node.classList.remove("running");
    node.classList.add("done");
  }
}

function sleep(ms) {
  return new Promise((res) => setTimeout(res, ms));
}

// ---------- run ----------
async function runPipeline() {
  if (!selectedFile) return;

  hideError();
  runBtn.disabled = true;
  $("run-btn-label").textContent = "Running…";
  $("rail-section").hidden = false;
  $("results").hidden = true;
  buildRail();

  const formData = new FormData();
  formData.append("file", selectedFile);
  // Featherless API key/model are configured server-side via backend/.env —
  // nothing to send from the UI.

  const railAnimation = animateRail();

  try {
    const resp = await fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      body: formData,
    });

    await railAnimation;

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || "Pipeline failed.");
    }

    const data = await resp.json();
    renderResults(data);
    $("results").hidden = false;
    $("results").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    await railAnimation;
    showError(e.message || "Something went wrong reaching the backend.");
  } finally {
    runBtn.disabled = false;
    $("run-btn-label").textContent = "Run pipeline";
  }
}

function showError(msg) {
  const banner = $("error-banner");
  banner.textContent = msg;
  banner.hidden = false;
}
function hideError() {
  $("error-banner").hidden = true;
}

// ---------- rendering ----------
function renderResults(data) {
  renderScores(data.score_before, data.score_after);
  renderOverview(data.ingestion_report, data.profiles);
  renderIssues(data.issues);
  renderPlan(data.recommendations, data.plan);
  renderLog(data.execution_log);
  renderExplanation(data.explanation);
  renderMonitor(data.monitor_summary);
  renderCleaned(data.preview_after, data.columns);
  $("download-btn").href = `${API_BASE}/api/download-cleaned`;
}

function renderScores(before, after) {
  $("score-before").textContent = before.score.toFixed(2);
  $("score-after").textContent = after.score.toFixed(2);
  const delta = (after.score - before.score).toFixed(2);
  $("score-delta").textContent = (delta >= 0 ? "+" : "") + delta;
}

function renderOverview(report, profiles) {
  $("stat-rows").textContent = report.rows;
  $("stat-cols").textContent = report.columns;

  const table = $("table-profile");
  table.innerHTML = `
    <thead><tr><th>Column</th><th>Dtype</th><th>Kind</th><th>Missing</th><th>Unique</th></tr></thead>
    <tbody>${profiles.map(p => `
      <tr>
        <td class="emphasis">${escapeHtml(p.name)}</td>
        <td>${escapeHtml(p.dtype)}</td>
        <td>${escapeHtml(p.kind)}</td>
        <td>${p.missing_count}</td>
        <td>${p.unique_count}</td>
      </tr>`).join("")}</tbody>`;
}

function renderIssues(issues) {
  const table = $("table-issues");
  if (!issues.length) {
    table.innerHTML = `<tbody><tr><td class="empty-note">No issues detected — dataset is clean.</td></tr></tbody>`;
    return;
  }
  table.innerHTML = `
    <thead><tr><th>Type</th><th>Column</th><th>Count</th><th>Detail</th></tr></thead>
    <tbody>${issues.map(i => `
      <tr>
        <td class="emphasis">${escapeHtml(i.issue_type)}</td>
        <td>${escapeHtml(i.column || "(dataset-wide)")}</td>
        <td>${i.count}</td>
        <td>${escapeHtml(i.detail)}</td>
      </tr>`).join("")}</tbody>`;
}

function renderPlan(recs, plan) {
  const table = $("table-recs");
  if (!recs.length) {
    table.innerHTML = `<tbody><tr><td class="empty-note">No repairs needed.</td></tr></tbody>`;
  } else {
    table.innerHTML = `
      <thead><tr><th>Column</th><th>Issue</th><th>Method</th><th>Severity</th></tr></thead>
      <tbody>${recs.map(r => `
        <tr>
          <td class="emphasis">${escapeHtml(r.column)}</td>
          <td>${escapeHtml(r.issue_type)}</td>
          <td>${escapeHtml(r.method)}</td>
          <td><span class="badge badge-${r.severity.toLowerCase()}">${escapeHtml(r.severity)}</span></td>
        </tr>`).join("")}</tbody>`;
  }

  const planEl = $("plan-steps");
  planEl.innerHTML = plan.map(s =>
    `<div class="plan-step-item"><b>${escapeHtml(s.step_id)}</b> → ${s.targets.map(escapeHtml).join(", ")}</div>`
  ).join("");
}

function renderLog(log) {
  const table = $("table-log");
  if (!log.length) {
    table.innerHTML = `<tbody><tr><td class="empty-note">Nothing executed — dataset was already clean.</td></tr></tbody>`;
    return;
  }
  table.innerHTML = `
    <thead><tr><th>Step</th><th>Column</th><th>Action</th><th>Value used</th><th>Rows affected</th></tr></thead>
    <tbody>${log.map(e => `
      <tr>
        <td>${escapeHtml(e.step_id)}</td>
        <td class="emphasis">${escapeHtml(e.column)}</td>
        <td>${escapeHtml(e.action)}</td>
        <td>${formatValueUsed(e.value_used)}</td>
        <td>${e.rows_affected}</td>
      </tr>`).join("")}</tbody>`;
}

function formatValueUsed(v) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return v.toFixed(2);
  return escapeHtml(String(v));
}

function renderExplanation(text) {
  const container = $("explanation-text");
  if (!text || !text.trim()) {
    container.innerHTML = `<p class="empty-note">No explanation generated.</p>`;
    return;
  }
  // Split into paragraphs on blank lines; bold a leading "Column:" label
  // if present so each block reads as a distinct, scannable item.
  const paragraphs = text.split(/\n\s*\n/).map(p => p.trim()).filter(Boolean);
  container.innerHTML = paragraphs.map(p => {
    const match = p.match(/^([^:]{1,40}):\s*(.*)$/s);
    if (match) {
      return `<p class="explanation-para"><strong>${escapeHtml(match[1])}:</strong> ${escapeHtml(match[2])}</p>`;
    }
    return `<p class="explanation-para">${escapeHtml(p)}</p>`;
  }).join("");
}

function renderMonitor(mon) {
  const grid = $("mon-grid");
  const items = [
    { label: "API key", value: mon["API Key"], cls: mon["API Key"] === "Detected" ? "ok" : "" },
    { label: "LLM calls", value: mon["LLM Calls"] },
    { label: "Response time", value: mon["Last LLM Response Time (ms)"] ? `${mon["Last LLM Response Time (ms)"]} ms` : "—" },
    { label: "Fallback used", value: mon["Used Fallback"] ? "Yes" : "No", cls: mon["Used Fallback"] ? "warn" : "ok" },
  ];
  grid.innerHTML = items.map(it => `
    <div class="mon-item">
      <div class="mon-item-label">${escapeHtml(it.label)}</div>
      <div class="mon-item-value ${it.cls || ""}">${escapeHtml(String(it.value))}</div>
    </div>`).join("");
}

function renderCleaned(rows, columns) {
  const table = $("table-cleaned");
  if (!rows.length) {
    table.innerHTML = `<tbody><tr><td class="empty-note">No preview available.</td></tr></tbody>`;
    return;
  }
  table.innerHTML = `
    <thead><tr>${columns.map(c => `<th>${escapeHtml(c)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map(r => `
      <tr>${columns.map(c => `<td>${formatValueUsed(r[c])}</td>`).join("")}</tr>`).join("")}</tbody>`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}