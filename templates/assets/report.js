/* deep-research-os — report interactivity (no dependencies).
   Progressive enhancement only: the report is fully readable without JS. */
(function () {
  "use strict";
  var root = document.documentElement;
  var KEY = "dro.theme";

  function readStored() {
    try { return window.localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function writeStored(value) {
    try {
      if (value) { window.localStorage.setItem(KEY, value); }
      else { window.localStorage.removeItem(KEY); }
    } catch (e) { /* private mode */ }
  }

  /* ---------------------------------------------------------------- theme */
  var themeBtn = document.getElementById("theme-toggle");
  function currentTheme() {
    var attr = root.getAttribute("data-theme");
    if (attr) { return attr; }
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark" : "light";
  }
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      writeStored(next);
      themeBtn.setAttribute("aria-pressed", next === "dark" ? "true" : "false");
    });
  }

  /* ---------------------------------------------------------------- print */
  var printBtn = document.getElementById("print-btn");
  if (printBtn) {
    printBtn.addEventListener("click", function () { window.print(); });
  }

  /* ------------------------------------------------------------ scrollspy */
  var links = Array.prototype.slice.call(document.querySelectorAll(".toc-rail a[href^='#']"));
  if (links.length && "IntersectionObserver" in window) {
    var byId = {};
    links.forEach(function (a) { byId[a.getAttribute("href").slice(1)] = a; });
    var current = null;
    var setActive = function (id) {
      if (current === id) { return; }
      current = id;
      links.forEach(function (a) { a.classList.remove("active"); });
      if (byId[id]) {
        byId[id].classList.add("active");
        byId[id].setAttribute("aria-current", "true");
      }
      links.forEach(function (a) {
        if (a !== byId[id]) { a.removeAttribute("aria-current"); }
      });
    };
    var targets = Object.keys(byId)
      .map(function (id) { return document.getElementById(id); })
      .filter(Boolean);
    var visible = {};
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) { visible[entry.target.id] = entry.isIntersecting; });
      var firstVisible = targets.filter(function (t) { return visible[t.id]; })[0];
      if (firstVisible) { setActive(firstVisible.id); }
    }, { rootMargin: "-45% 0px -50% 0px", threshold: 0 });
    targets.forEach(function (t) { observer.observe(t); });
  }

  /* ------------------------------------------------------------ backlinks */
  document.addEventListener("click", function (event) {
    var link = event.target.closest ? event.target.closest("a.backlink[href^='#']") : null;
    if (!link) { return; }
    var target = document.getElementById(link.getAttribute("href").slice(1));
    if (!target) { return; }
    target.classList.remove("flash");
    /* restart the flash animation */
    void target.offsetWidth;
    target.classList.add("flash");
  });
})();
