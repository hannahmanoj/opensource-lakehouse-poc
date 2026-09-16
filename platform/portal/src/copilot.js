const $ = (s, r = document) => r.querySelector(s),
  $$ = (s, r = document) => [...r.querySelectorAll(s)];
function escapeHtml(value = "") {
  const node = document.createElement("div");
  node.textContent = String(value);
  return node.innerHTML;
}
const form = $("#copilot-form"),
  question = $("#question"),
  conversation = $("#conversation"),
  empty = $("#copilot-empty"),
  scroll = $("#chat-scroll"),
  submit = $("#submit-button");
$("#context-button").onclick = () =>
  ($("#context-panel").hidden = !$("#context-panel").hidden);
$$(`#suggested-prompts button`).forEach(
  (button) =>
    (button.onclick = () => {
      question.value = button.textContent;
      if (button.dataset.component)
        $("#component").value = button.dataset.component;
      question.focus();
    }),
);
function payload() {
  const data = { question: question.value.trim() };
  for (const id of ["component", "severity"]) {
    const value = $(`#${id}`).value;
    if (value) data[id] = value;
  }
  for (const [id, key] of [
    ["from-time", "from_time"],
    ["to-time", "to_time"],
  ]) {
    const value = $(`#${id}`).value;
    if (value) data[key] = new Date(value).toISOString();
  }
  return data;
}
function citations(items) {
  if (!items.length) return "";
  return `<details class="evidence-disclosure"><summary>View evidence · ${items.length} source${items.length === 1 ? "" : "s"}</summary>${items.map((c, i) => `<article class="citation-card"><strong>${i + 1}. ${escapeHtml(c.title)}</strong><small>${escapeHtml(c.component || "Unspecified")}</small><p>${escapeHtml(c.excerpt)}</p><code>${escapeHtml(c.source_uri)}</code></article>`).join("")}</details>`;
}
function answerHtml(data) {
  const findings = (data.findings || []).length
      ? `<section class="response-section" data-stream-section><h4>Likely cause / findings</h4><ul>${data.findings.map(() => `<li data-stream-finding></li>`).join("")}</ul></section>`
      : "",
    checks = (data.recommended_checks || []).length
      ? `<section class="response-section" data-stream-section><h4>Recommended checks</h4><ol>${data.recommended_checks.map(() => `<li data-stream-check></li>`).join("")}</ol></section>`
      : "";
  const evidence = (data.citations || []).length
    ? `<section class="response-section" data-stream-section>${citations(data.citations)}</section>`
    : "";
  return `<div class="message assistant answer-arriving"><div class="answer-meta"><span class="status-badge ${data.insufficient_evidence ? "warning" : "healthy"}"><i></i>${escapeHtml(data.classification.replaceAll("_", " "))}</span><span class="status-badge neutral"><i></i>${escapeHtml(data.confidence)} confidence</span></div><div class="answer-block"><h4>Direct answer</h4><p data-stream-answer></p><div class="answer-followup">${findings}${checks}${evidence}</div></div></div>`;
}
function loadingHtml() {
  return `<div class="message assistant copilot-thinking" data-loading>
    <span class="thinking-dots" aria-label="Thinking"><i></i><i></i><i></i></span>
  </div>`;
}
function cleanDirectAnswer(value = "") {
  return String(value)
    .replace(/\\([*_`#])/g, "$1")
    .replace(/^\s*#{1,6}\s*Direct answer\s*/i, "")
    .split(/\n\s*#{1,6}\s*(?:Likely cause|Findings|Recommended checks|View evidence)/i)[0]
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/\s{2,}(?=\d+\.\s)/g, "\n\n")
    .replace(/\s{2,}(?=[-•]\s)/g, "\n")
    .trim();
}
function typeInto(target, value, instant = false) {
  const words = String(value || "").match(/\S+\s*/g) || [];
  if (instant) {
    target.textContent = value;
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    let index = 0;
    const typeNext = () => {
      target.textContent += words[index++] || "";
      scroll.scrollTop = scroll.scrollHeight;
      if (index < words.length) setTimeout(typeNext, 22);
      else resolve();
    };
    typeNext();
  });
}
async function revealAnswer(data) {
  const answer = $(".answer-arriving:last-child", conversation),
    target = $("[data-stream-answer]", answer),
    directAnswer = cleanDirectAnswer(data.answer),
    instant = matchMedia("(prefers-reduced-motion: reduce)").matches;
  answer.classList.add("ready");
  await typeInto(target, directAnswer, instant);
  const sections = $$(`[data-stream-section]`, answer);
  for (const section of sections) {
    section.classList.add("visible");
    const findings = $$(`[data-stream-finding]`, section),
      checks = $$(`[data-stream-check]`, section);
    for (let index = 0; index < findings.length; index++)
      await typeInto(findings[index], data.findings[index], instant);
    for (let index = 0; index < checks.length; index++)
      await typeInto(checks[index], data.recommended_checks[index], instant);
  }
}
form.onsubmit = async (event) => {
  event.preventDefault();
  if (!question.value.trim()) return;
  const data = payload(),
    text = question.value.trim();
  empty.hidden = true;
  conversation.insertAdjacentHTML(
    "beforeend",
    `<div class="message user">${escapeHtml(text)}</div>${loadingHtml()}`,
  );
  question.value = "";
  submit.disabled = true;
  scroll.scrollTop = scroll.scrollHeight;
  try {
    const response = await fetch("/api/copilot/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
      result = await response.json();
    if (!response.ok)
      throw Error(result.detail || `Request failed (${response.status})`);
    $(`[data-loading]`).outerHTML = answerHtml(result);
    requestAnimationFrame(() => revealAnswer(result));
  } catch (error) {
    $(`[data-loading]`).outerHTML =
      `<div class="message assistant"><div class="chat-message error"><strong>Request failed</strong><p>${escapeHtml(error.message)}</p><small>No platform action was taken.</small></div></div>`;
  } finally {
    submit.disabled = false;
    scroll.scrollTop = scroll.scrollHeight;
    question.focus();
  }
};
