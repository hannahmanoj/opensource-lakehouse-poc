const $ = (s, r = document) => r.querySelector(s),
  $$ = (s, r = document) => [...r.querySelectorAll(s)],
  host = location.hostname || "localhost";
const services = {
  minio: {
    name: "MinIO",
    category: "Storage",
    icon: "◫",
    logo: "assets/minio.png",
    purpose: "S3-compatible storage for lakehouse objects.",
    port: "9001",
    protocol: "http",
    metric: "Object storage console",
    dependencies: "Iceberg, Spark, NiFi",
  },
  airflow: {
    name: "Apache Airflow",
    category: "Orchestration",
    icon: "⇢",
    logo: "assets/Apache-Airflow.png",
    purpose: "Schedules and monitors data workflows.",
    port: "8090",
    protocol: "http",
    metric: "1 configured DAG",
    dependencies: "Trino, Spark",
  },
  trino: {
    name: "Trino",
    category: "Query",
    icon: "⌕",
    logo: "https://trino.io/assets/images/trino-logo/cbb.svg",
    purpose: "Queries open Iceberg tables with distributed SQL.",
    port: "8080",
    protocol: "http",
    metric: "Distributed SQL",
    dependencies: "Iceberg",
  },
  openmetadata: {
    name: "OpenMetadata",
    category: "Governance",
    icon: "⌘",
    logo: "assets/openmetadata.png",
    purpose: "Provides catalogue, ownership, quality, and lineage.",
    port: "8585",
    protocol: "http",
    metric: "Optional profile",
    dependencies: "MySQL, Elasticsearch",
  },
  nifi: {
    name: "Apache NiFi",
    category: "Ingestion",
    icon: "⇣",
    logo: "assets/nifi.webp",
    purpose: "Moves source data into governed storage flows.",
    port: "8443",
    protocol: "https",
    path: "/nifi/",
    metric: "TLS console",
    dependencies: "SQL Server, MinIO",
    manual: "warning",
  },
  spark: {
    name: "Apache Spark",
    category: "Compute",
    icon: "ϟ",
    logo: "https://spark.apache.org/images/spark-logo-rev.svg",
    purpose: "Cleans, enriches, and aggregates data.",
    port: "8888",
    protocol: "http",
    metric: "Notebook workspace",
    dependencies: "Iceberg, MinIO",
    manual: "warning",
  },
  copilot: {
    name: "Operations Copilot",
    category: "Assistant",
    icon: "✦",
    purpose: "Provides read-only, evidence-grounded guidance.",
    port: "8100",
    protocol: "http",
    metric: "Qwen3 8B via Ollama",
    dependencies: "PostgreSQL, Ollama",
  },
  sqlserver: {
    name: "SQL Server",
    category: "Source",
    icon: "▣",
    purpose: "Operational source used by ingestion flows.",
    port: "1433",
    protocol: "tcp",
    metric: "Source system",
    dependencies: "None",
    manual: "warning",
  },
  iceberg: {
    name: "Apache Iceberg",
    category: "Table format",
    icon: "✣",
    logo: "assets/iceberg.png",
    purpose: "Tracks table schemas, snapshots, and files.",
    port: "8181",
    protocol: "http",
    metric: "REST catalogue",
    dependencies: "MinIO",
    manual: "warning",
  },
};
const checked = ["minio", "airflow", "trino", "openmetadata", "copilot"],
  health = new Map(),
  url = (s) => `${s.protocol}://${host}:${s.port}${s.path || ""}`;
let current = "workflow",
  statusFilter = "all";
function esc(v = "") {
  const d = document.createElement("div");
  d.textContent = String(v);
  return d.innerHTML;
}
function badge(st) {
  return `<span class="status-badge ${st}"><i></i>${{ healthy: "Healthy", offline: "Unavailable", warning: "Unknown", checking: "Checking" }[st]}</span>`;
}
function serviceIcon(service) {
  return service.logo
    ? `<i class="service-icon service-logo"><img src="${service.logo}" alt="" /></i>`
    : `<i class="service-icon">${service.icon}</i>`;
}
function route() {
  current = location.hash.slice(1) || "workflow";
  if (!$(`[data-page="${current}"]`)) current = "workflow";
  $$(`[data-page]`).forEach((p) => (p.hidden = p.dataset.page !== current));
  $$(`[data-route]`).forEach((a) =>
    a.classList.toggle("active", a.dataset.route === current),
  );
  $("#copilot-context").textContent =
    current[0].toUpperCase() + current.slice(1);
  if (current === "workflow") setTimeout(fit, 0);
}
addEventListener("hashchange", route);
route();
function renderServices() {
  const term = $("#service-search")?.value.toLowerCase() || "";
  $("#service-list").innerHTML = Object.entries(services)
    .filter(
      ([id, s]) =>
        (!term || s.name.toLowerCase().includes(term)) &&
        (statusFilter === "all" ||
          (health.get(id) || s.manual) == statusFilter),
    )
    .map(([id, s]) => {
      const st = health.get(id) || s.manual || "checking";
      return `<button class="canvas-service-card" data-service="${id}"><header>${serviceIcon(s)}${badge(st)}</header><h2>${s.name}</h2><p>${s.purpose}</p><footer><span>${s.category}</span></footer></button>`;
    })
    .join("");
  $$(`[data-service]`).forEach(
    (b) => (b.onclick = () => openDetail(b.dataset.service)),
  );
}
async function refresh() {
  checked.forEach((n) => health.set(n, "checking"));
  updateHealth();
  await Promise.all(
    checked.map(async (n) => {
      try {
        const r = await fetch(`/health/${n}`, {
          cache: "no-store",
          signal: AbortSignal.timeout(4000),
        });
        health.set(n, r.ok ? "healthy" : "offline");
      } catch {
        health.set(n, "offline");
      }
    }),
  );
  updateHealth();
}
function updateHealth() {
  const pending = [...health.values()].some((x) => x === "checking"),
    good = [...health.values()].filter((x) => x === "healthy").length,
    bad = [...health.values()].filter((x) => x === "offline").length;
  $("#global-health").innerHTML = pending
    ? '<i class="status-dot checking"></i><span>Checking</span>'
    : `<i class="status-dot ${bad ? "warning" : "healthy"}"></i><span>${good}/${checked.length} healthy</span>`;
  $$(`[data-node-health]`).forEach(
    (e) =>
      (e.className =
        health.get(e.dataset.nodeHealth) ||
        services[e.dataset.nodeHealth]?.manual ||
        "warning"),
  );
  renderServices();
}
refresh();
setInterval(refresh, 30000);
$("#refresh-services").onclick = refresh;
$("#service-search").oninput = renderServices;
$$(`#service-filter button`).forEach(
  (b) =>
    (b.onclick = () => {
      $$(`#service-filter button`).forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      statusFilter = b.dataset.status;
      renderServices();
    }),
);
const detail = $("#detail-panel"),
  answer = $("#answer-panel");
function closePanels() {
  detail.classList.remove("open");
  answer.classList.remove("open");
}
$("#close-detail").onclick = closePanels;
$("#close-answer").onclick = closePanels;
addEventListener("keydown", (e) => e.key === "Escape" && closePanels());
function openDetail(id) {
  const s = services[id];
  if (!s) return;
  const st = health.get(id) || s.manual || "warning";
  $("#detail-category").textContent = s.category;
  $("#detail-title").textContent = s.name;
  $("#detail-body").innerHTML =
    `<div class="drawer-hero">${badge(st)}<h3>Purpose</h3><p>${s.purpose}</p></div><dl class="detail-list"><div><dt>Key detail</dt><dd>${s.metric}</dd></div><div><dt>Last checked</dt><dd>${health.has(id) ? "Just now" : "No live check exposed"}</dd></div><div><dt>Endpoint</dt><dd><code>${s.protocol === "tcp" ? `${host}:${s.port}` : url(s)}</code></dd></div><div><dt>Port</dt><dd><code>${s.port}</code></dd></div><div><dt>Dependencies</dt><dd>${s.dependencies}</dd></div></dl><p class="honest-note">Unknown means this portal has no live health endpoint for the service.</p>`;
  $("#detail-actions").innerHTML =
    `${s.protocol !== "tcp" ? `<a class="button secondary" href="${url(s)}" target="_blank" rel="noopener">Open service ↗</a>` : "<span></span>"}<button class="button primary" data-ask="${s.name}">✦ Ask Copilot</button>`;
  $(`[data-ask]`).onclick = (e) => {
    $("#quick-question").value = `Tell me about ${e.currentTarget.dataset.ask}`;
    closePanels();
    $("#quick-question").focus();
  };
  answer.classList.remove("open");
  detail.classList.add("open");
}
$$(`[data-node]`).forEach(
  (b) =>
    (b.onclick = () =>
      b.dataset.node === "layers"
        ? (location.hash = "data")
        : services[b.dataset.node]
          ? openDetail(b.dataset.node)
          : null),
);
$$(`[data-dataset]`).forEach(
  (b) =>
    (b.onclick = () => {
      $("#detail-category").textContent = "Data product · Demo";
      $("#detail-title").textContent = b.dataset.dataset.replaceAll("_", " ");
      $("#detail-body").innerHTML =
        `<div class="drawer-hero">${badge("healthy")}<h3>Published Iceberg dataset</h3><p>Live schema, freshness, quality, and lineage APIs are not connected to this POC yet.</p></div><dl class="detail-list"><div><dt>Table</dt><dd><code>${b.dataset.dataset}</code></dd></div><div><dt>Format</dt><dd>Apache Iceberg</dd></div></dl>`;
      $("#detail-actions").innerHTML =
        `<button class="button primary" data-ask="${b.dataset.dataset}">✦ Ask Copilot</button>`;
      $(`[data-ask]`).onclick = (e) => {
        $("#quick-question").value =
          `Tell me about ${e.currentTarget.dataset.ask}`;
        closePanels();
      };
      detail.classList.add("open");
    }),
);
$("#quick-copilot-form").onsubmit = async (e) => {
  e.preventDefault();
  const input = $("#quick-question"),
    q = input.value.trim();
  if (!q) return;
  detail.classList.remove("open");
  answer.classList.add("open");
  const thread = $("#answer-thread");
  if ($(".copilot-welcome", thread)) thread.innerHTML = "";
  thread.insertAdjacentHTML(
    "beforeend",
    `<div class="chat-message user">${esc(q)}</div><div class="chat-message assistant" data-loading><span class="spinner"></span> Reviewing evidence…</div>`,
  );
  input.value = "";
  try {
    const r = await fetch("/api/copilot/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: `Context: ${current}. ${q}` }),
      }),
      d = await r.json();
    if (!r.ok) throw Error(d.detail || `Request failed (${r.status})`);
    $(`[data-loading]`, thread).outerHTML =
      `<div class="chat-message assistant">${esc(d.answer)}<small>${d.confidence} confidence · ${d.citations.length} source${d.citations.length === 1 ? "" : "s"}</small></div>`;
  } catch (x) {
    $(`[data-loading]`, thread).outerHTML =
      `<div class="chat-message error">${esc(x.message)}<small>No platform action was taken.</small></div>`;
  }
  thread.scrollTop = thread.scrollHeight;
};
let zoom = 1,
  pan = { x: 0, y: 0 },
  drag = false,
  start;
const stage = $("#canvas-stage"),
  work = $("#workspace");
function move() {
  stage.style.transform = `translate(${pan.x}px,${pan.y}px) scale(${zoom})`;
}
function fit() {
  const w = innerWidth,
    h = innerHeight;
  zoom = Math.min((w - 30) / 1600, (h - 80) / 760, 0.98);
  pan = { x: -800 * zoom, y: -380 * zoom };
  stage.style.left = "50%";
  stage.style.top = "50%";
  move();
}
$("#zoom-in").onclick = () => {
  zoom = Math.min(1.4, zoom + 0.1);
  move();
};
$("#zoom-out").onclick = () => {
  zoom = Math.max(0.5, zoom - 0.1);
  move();
};
$("#fit-view").onclick = fit;
work.onpointerdown = (e) => {
  if (current !== "workflow" || e.target.closest("button,a,form")) return;
  drag = true;
  start = { x: e.clientX - pan.x, y: e.clientY - pan.y };
};
work.onpointermove = (e) => {
  if (drag) {
    pan = { x: e.clientX - start.x, y: e.clientY - start.y };
    move();
  }
};
work.onpointerup = () => (drag = false);
addEventListener("resize", () => current === "workflow" && fit());
$$(`[data-port]`).forEach((a) => {
  a.href = `${a.dataset.protocol || "http"}://${host}:${a.dataset.port}${a.dataset.path || ""}`;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
});
renderServices();
