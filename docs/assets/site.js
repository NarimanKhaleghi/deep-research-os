(function () {
  "use strict";
  var root = document.documentElement;
  var reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

  function store(key, value) {
    try { localStorage.setItem(key, value); } catch (e) {}
  }
  function read(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }

  /* ------------------------------------------------------------- theme */
  var themeBtn = document.getElementById("theme-toggle");
  function isDark() {
    var explicit = root.getAttribute("data-theme");
    if (explicit) return explicit === "dark";
    return matchMedia("(prefers-color-scheme: dark)").matches;
  }
  function syncTheme() {
    if (!themeBtn) return;
    themeBtn.setAttribute("aria-pressed", String(isDark()));
  }
  syncTheme();
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var next = isDark() ? "light" : "dark";
      root.setAttribute("data-theme", next);
      store("dro.theme", next);
      syncTheme();
    });
  }
  var scheme = matchMedia("(prefers-color-scheme: dark)");
  if (scheme.addEventListener) scheme.addEventListener("change", syncTheme);

  /* -------------------------------------------------------------- menu */
  var burger = document.getElementById("menu-toggle");
  var links = document.getElementById("navlinks");
  function closeMenu() {
    if (!links || !burger) return;
    links.classList.remove("open");
    burger.setAttribute("aria-expanded", "false");
  }
  if (burger && links) {
    burger.addEventListener("click", function () {
      var open = links.classList.toggle("open");
      burger.setAttribute("aria-expanded", String(open));
    });
    links.addEventListener("click", function (e) {
      if (e.target.closest("a")) closeMenu();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeMenu();
    });
    matchMedia("(min-width: 861px)").addEventListener("change", closeMenu);
  }

  /* ------------------------------------------------- scroll spy + reveal */
  var sections = ["how", "evidence", "validation", "install"]
    .map(function (id) { return document.getElementById(id); })
    .filter(Boolean);
  var navAnchors = Array.prototype.slice.call(document.querySelectorAll(".navlinks a"));
  if ("IntersectionObserver" in window && sections.length) {
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        navAnchors.forEach(function (a) {
          a.classList.toggle("active", a.getAttribute("href") === "#" + entry.target.id);
        });
      });
    }, { rootMargin: "-45% 0px -50% 0px", threshold: 0 });
    sections.forEach(function (s) { spy.observe(s); });
  }

  var reveals = document.querySelectorAll(".reveal");
  if (reduced || !("IntersectionObserver" in window)) {
    reveals.forEach(function (el) { el.classList.add("in"); });
  } else {
    var show = new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("in");
        obs.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    reveals.forEach(function (el) { show.observe(el); });
  }

  /* ----------------------------------------------------------- counters */
  function animate(el) {
    var raw = el.getAttribute("data-count") || "";
    if (!/^\d+$/.test(raw)) return;
    var target = parseInt(raw, 10);
    if (reduced || target > 1000) { el.textContent = raw; return; }
    var start = performance.now();
    var dur = 900;
    function frame(now) {
      var t = Math.min(1, (now - start) / dur);
      var eased = 1 - Math.pow(1 - t, 3);
      el.textContent = String(Math.round(target * eased));
      if (t < 1) requestAnimationFrame(frame);
    }
    el.textContent = "0";
    requestAnimationFrame(frame);
  }
  var counters = document.querySelectorAll("[data-count]");
  if ("IntersectionObserver" in window && !reduced) {
    var countObs = new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        animate(entry.target);
        obs.unobserve(entry.target);
      });
    }, { threshold: 0.6 });
    counters.forEach(function (el) { countObs.observe(el); });
  }

  /* --------------------------------------------------------------- copy */
  document.querySelectorAll(".copy").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var step = btn.closest(".step");
      var code = step && step.querySelector("code");
      if (!code) return;
      var text = code.textContent;
      var label = btn.getAttribute("data-copy") || "Copy";
      var done = btn.getAttribute("data-copied") || "Copied";
      function finish() {
        btn.textContent = done;
        btn.classList.add("done");
        setTimeout(function () {
          btn.textContent = label;
          btn.classList.remove("done");
        }, 1600);
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(finish, fallback);
      } else {
        fallback();
      }
      function fallback() {
        var ta = document.createElement("textarea");
        ta.value = text;
        ta.setAttribute("readonly", "");
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand("copy"); finish(); } catch (e) {}
        document.body.removeChild(ta);
      }
    });
  });
})();
