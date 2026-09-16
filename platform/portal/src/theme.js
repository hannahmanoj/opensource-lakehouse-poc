(function () {
  const storageKey = "madayn-theme";

  function applyTheme(theme) {
    const selected = theme === "light" ? "light" : "dark";
    document.documentElement.dataset.theme = selected;
    document.body?.classList.toggle("theme-light", selected === "light");
    localStorage.setItem(storageKey, selected);

    const toggle = document.querySelector("#theme-toggle");
    if (toggle) {
      toggle.textContent = selected === "dark" ? "☼" : "◐";
      toggle.setAttribute(
        "aria-label",
        `Switch to ${selected === "dark" ? "light" : "dark"} mode`,
      );
    }
  }

  window.setMadaynTheme = applyTheme;
  window.toggleMadaynTheme = function () {
    applyTheme(
      document.documentElement.dataset.theme === "light" ? "dark" : "light",
    );
  };

  applyTheme(localStorage.getItem(storageKey) || "dark");
  document.addEventListener("DOMContentLoaded", () =>
    applyTheme(document.documentElement.dataset.theme),
  );
})();
