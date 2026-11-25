/* Small progressive enhancements. Loaded as an external file so the
   Content-Security-Policy can forbid inline scripts. */
(function () {
  "use strict";

  var root = document.documentElement;

  function setTheme(theme, remember) {
    root.setAttribute("data-bs-theme", theme);
    if (remember) {
      try { window.localStorage.setItem("gd-theme", theme); } catch (e) { /* ignore */ }
    }
  }

  // Print, back and theme buttons.
  document.addEventListener("click", function (event) {
    var target = event.target.closest("[data-action]");
    if (!target) return;
    if (target.dataset.action === "print") {
      window.print();
    } else if (target.dataset.action === "back") {
      window.history.back();
    } else if (target.dataset.action === "toggle-theme") {
      setTheme(root.getAttribute("data-bs-theme") === "dark" ? "light" : "dark", true);
    }
  });

  // Paper is white: print in light mode, then restore the screen theme.
  var themeBeforePrint = null;
  window.addEventListener("beforeprint", function () {
    themeBeforePrint = root.getAttribute("data-bs-theme");
    setTheme("light", false);
  });
  window.addEventListener("afterprint", function () {
    if (themeBeforePrint) setTheme(themeBeforePrint, false);
  });

  // Ask before destructive submits: <form data-confirm="Are you sure?">
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (form.dataset && form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);

  // Type-to-filter for long <select> lists (learners, staff).
  function enhanceSelect(select) {
    if (select.dataset.filterReady) return;
    select.dataset.filterReady = "1";
    var input = document.createElement("input");
    input.type = "search";
    input.className = "form-control form-control-sm select-filter";
    input.placeholder = "Type to filter…";
    input.setAttribute("aria-label", "Filter options");
    select.parentNode.insertBefore(input, select);
    input.addEventListener("input", function () {
      var term = input.value.trim().toLowerCase();
      Array.prototype.forEach.call(select.options, function (option) {
        if (!option.value) return;
        option.hidden = term !== "" && option.text.toLowerCase().indexOf(term) === -1 && !option.selected;
      });
    });
  }

  function init(scope) {
    scope.querySelectorAll("select[data-filterable]").forEach(enhanceSelect);
    // Bar widths from data-width="42" (percent). Set via the CSSOM because the
    // Content-Security-Policy blocks inline style attributes.
    scope.querySelectorAll("[data-width]").forEach(function (el) {
      var pct = Math.max(0, Math.min(100, parseFloat(el.dataset.width) || 0));
      el.style.width = pct + "%";
    });
  }

  document.addEventListener("DOMContentLoaded", function () { init(document); });
  document.addEventListener("htmx:afterSwap", function (event) { init(event.target); });
})();
