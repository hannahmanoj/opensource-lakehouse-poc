const host = location.hostname || "localhost",
  state = new Map(),
  root = document.documentElement,
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
function url(el) {
  return `${el.dataset.protocol || "http"}://${host}:${el.dataset.port}${el.dataset.path || ""}`;
}
document.querySelectorAll("[data-port]").forEach((el) => {
  if (el.tagName === "A") {
    el.href = url(el);
    el.target = "_blank";
    el.rel = "noopener noreferrer";
  } else el.textContent = url(el);
});
function count() {
  document.querySelector("#health-count").textContent =
    `${String([...state.values()].filter(Boolean).length).padStart(2, "0")}/04`;
}
async function check(name) {
  const badge = document.querySelector(`[data-health="${name}"] .status`);
  try {
    const r = await fetch(`/health/${name}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });
    if (!r.ok) throw 0;
    badge.innerHTML = "<i></i> Active";
    badge.className = "status active";
    state.set(name, true);
  } catch (e) {
    badge.innerHTML = "<i></i> Offline";
    badge.className = "status offline";
    state.set(name, false);
  }
  count();
}
function refresh() {
  ["minio", "airflow", "trino", "openmetadata"].forEach((n) => {
    const b = document.querySelector(`[data-health="${n}"] .status`);
    b.innerHTML = "<i></i> Checking";
    b.className = "status checking";
    check(n);
  });
}
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
document.querySelector("#refresh").onclick = refresh;
refresh();
clock();
setInterval(refresh, 30000);
setInterval(clock, 1000);
