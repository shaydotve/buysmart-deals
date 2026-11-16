(function () {
  var sun = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="2"/><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4"/></svg>';
  var moon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M16.5 3.2a8.8 8.8 0 1 0 4.3 14.8A8 8 0 0 1 16.5 3.2z"/></svg>';

  function explicitTheme() {
    try {
      return localStorage.getItem("theme");
    } catch (error) {
      return null;
    }
  }

  function systemDark() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function appliedTheme() {
    var chosen = explicitTheme();
    if (chosen === "light" || chosen === "dark") return chosen;
    var attr = document.documentElement.getAttribute("data-theme");
    if (attr === "light" || attr === "dark") return attr;
    return systemDark() ? "dark" : "light";
  }

  function paintThemeButton() {
    var button = document.getElementById("theme-toggle");
    if (!button) return;
    var dark = appliedTheme() === "dark";
    button.innerHTML = dark ? sun : moon;
    button.setAttribute("aria-label", dark ? "מעבר למצב בהיר" : "מעבר למצב כהה");
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", dark ? "#161616" : "#ffffff");
  }

  function setTheme(theme) {
    if (theme === "light" || theme === "dark") {
      document.documentElement.setAttribute("data-theme", theme);
      try { localStorage.setItem("theme", theme); } catch (error) {}
    } else {
      document.documentElement.removeAttribute("data-theme");
      try { localStorage.removeItem("theme"); } catch (error) {}
    }
    paintThemeButton();
  }

  var toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      setTheme(appliedTheme() === "dark" ? "light" : "dark");
    });
  }
  paintThemeButton();
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
    if (!explicitTheme()) paintThemeButton();
  });

  var toastTimer = 0;
  function toast(message) {
    var node = document.getElementById("toast");
    if (!node) return;
    node.textContent = message;
    node.classList.add("show");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () { node.classList.remove("show"); }, 1600);
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (error) {
      var area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      var ok = false;
      try { ok = document.execCommand("copy"); } catch (copyError) { ok = false; }
      area.remove();
      return ok;
    }
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest(".coupon");
    if (!button) return;
    var code = button.getAttribute("data-code") || "";
    if (!code) return;
    copyText(code).then(function (ok) {
      var hint = button.querySelector(".coupon-hint");
      if (hint) hint.textContent = ok ? "הועתק!" : "העתקה";
      toast(ok ? "הועתק!" : "לא הצלחנו להעתיק");
      window.setTimeout(function () {
        if (hint) hint.textContent = "העתקה";
      }, 1600);
    });
  });

  window.BuySmart = { toast: toast, copyText: copyText, formatDate: formatDate };

  function formatDate(iso) {
    if (!iso) return "";
    var date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "";
    return new Intl.DateTimeFormat("he-IL", {
      day: "numeric",
      month: "long",
      year: "numeric"
    }).format(date);
  }
})();
