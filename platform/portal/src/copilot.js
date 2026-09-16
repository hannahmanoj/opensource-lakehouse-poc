const root = document.documentElement,
  themeButton = document.querySelector("#theme-toggle");
function setTheme(theme) {
  root.dataset.theme = theme;
  const light = theme === "light";
  themeButton.innerHTML = light
    ? "<span>◐</span> DARK"
    : "<span>☼</span> LIGHT";
  themeButton.setAttribute(
    "aria-label",
    light ? "Switch to dark mode" : "Switch to light mode",
  );
  themeButton.setAttribute("aria-pressed", String(light));
}
setTheme(localStorage.getItem("madayn-theme") || "dark");
themeButton.onclick = () => {
  const next = root.dataset.theme === "light" ? "dark" : "light";
  localStorage.setItem("madayn-theme", next);
  setTheme(next);
};
function clock() {
  document.querySelector("#clock").textContent =
    new Intl.DateTimeFormat("en-GB", {
      timeZone: "Asia/Muscat",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(new Date()) + " GST";
}
clock();
setInterval(clock, 1000);

const form = document.querySelector("#copilot-form"),
  question = document.querySelector("#question"),
  answerPanel = document.querySelector("#answer-panel"),
  evidencePanel = document.querySelector("#evidence-panel"),
  evidenceList = document.querySelector("#evidence-list"),
  submitButton = form.querySelector("button[type=submit]");
document.querySelectorAll("#suggested-questions button").forEach(
  (button) =>
    (button.onclick = () => {
      question.value = button.textContent;
      document.querySelector("#component").value = button.dataset.component;
      question.focus();
    }),
);

function escapeHtml(value = "") {
  const node = document.createElement("div");
  node.textContent = String(value);
  return node.innerHTML;
}
function formatDate(value) {
  if (!value) return "Not timestamped";
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Muscat",
  }).format(new Date(value));
}
function payload() {
  const data = { question: question.value.trim() };
  for (const id of ["component", "severity"]) {
    const value = document.querySelector(`#${id}`).value;
    if (value) data[id] = value;
  }
  for (const [id, key] of [
    ["from-time", "from_time"],
    ["to-time", "to_time"],
  ]) {
    const value = document.querySelector(`#${id}`).value;
    if (value) data[key] = new Date(value).toISOString();
  }
  return data;
}
function copyButton(text) {
  return `<button class="copy-check" type="button" data-copy="${encodeURIComponent(text)}">COPY</button>`;
}
function renderAnswer(data) {
  const warning = data.insufficient_evidence
    ? `<div class="evidence-warning"><b>INSUFFICIENT EVIDENCE</b><span>${escapeHtml((data.missing_evidence || []).join(" · "))}</span></div>`
    : "";
  const findings = (data.findings || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  const checks = (data.recommended_checks || [])
    .map(
      (item) => `<li><span>${escapeHtml(item)}</span>${copyButton(item)}</li>`,
    )
    .join("");
  answerPanel.className = "answer-panel panel";
  answerPanel.innerHTML = `${warning}<div class="answer-meta"><span class="classification">${escapeHtml((data.classification || "unknown").replaceAll("_", " "))}</span><span class="confidence ${escapeHtml(data.confidence || "low")}"><i></i>${escapeHtml(data.confidence || "low")} confidence</span></div><label>ASSESSED RESPONSE</label><div class="answer-copy">${escapeHtml(data.answer || "No answer returned.")}</div>${findings ? `<div class="answer-section"><label>FINDINGS</label><ul>${findings}</ul></div>` : ""}${checks ? `<div class="answer-section"><label>RECOMMENDED CHECKS</label><ol class="checks">${checks}</ol></div>` : ""}`;
  answerPanel.querySelectorAll("[data-copy]").forEach(
    (button) =>
      (button.onclick = async () => {
        await navigator.clipboard.writeText(
          decodeURIComponent(button.dataset.copy),
        );
        button.textContent = "COPIED";
        setTimeout(() => (button.textContent = "COPY"), 1200);
      }),
  );
  renderEvidence(data.citations || []);
}
function renderEvidence(citations) {
  evidencePanel.hidden = citations.length === 0;
  document.querySelector("#evidence-count").textContent =
    `${String(citations.length).padStart(2, "0")} ${citations.length === 1 ? "SOURCE" : "SOURCES"}`;
  evidenceList.innerHTML = citations
    .map(
      (citation, index) =>
        `<details class="citation" ${index === 0 ? "open" : ""}><summary><span><b>${String(index + 1).padStart(2, "0")}</b><span><strong>${escapeHtml(citation.title)}</strong><small>${escapeHtml(citation.component || "Unspecified")} · ${escapeHtml(formatDate(citation.occurred_at))}</small></span></span><em>EXPAND</em></summary><div class="citation-body"><label>EXACT PASSAGE</label><blockquote>${escapeHtml(citation.excerpt)}</blockquote><div><label>SOURCE URI / LOG LOCATION</label><code>${escapeHtml(citation.source_uri)}</code></div></div></details>`,
    )
    .join("");
}
function renderError(message) {
  answerPanel.className = "answer-panel panel";
  answerPanel.innerHTML = `<div class="evidence-warning"><b>REQUEST FAILED</b><span>${escapeHtml(message)}</span></div><p class="error-help">No platform action was taken. Check the copilot API and try again.</p>`;
  evidencePanel.hidden = true;
}

form.onsubmit = async (event) => {
  event.preventDefault();
  if (!question.value.trim()) return;
  submitButton.disabled = true;
  submitButton.innerHTML = "<span>◌</span> ANALYZING…";
  answerPanel.className = "answer-panel panel loading-state";
  answerPanel.innerHTML =
    '<div><span class="loader"></span><h2>Reviewing evidence</h2><p>Retrieving sources and checking sufficiency before generation.</p></div>';
  evidencePanel.hidden = true;
  try {
    const response = await fetch("/api/copilot/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload()),
    });
    const data = await response.json();
    if (!response.ok)
      throw new Error(data.detail || `Request failed (${response.status})`);
    renderAnswer(data);
  } catch (error) {
    renderError(error.message);
  } finally {
    submitButton.disabled = false;
    submitButton.innerHTML = "<span>◎</span> ANALYZE EVIDENCE";
  }
};
