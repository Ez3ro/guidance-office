/* Small progressive enhancements. Loaded as an external file so the
   Content-Security-Policy can forbid inline scripts. */
(function () {
  "use strict";

  // Print and back buttons on report and form pages.
  document.addEventListener("click", function (event) {
    var target = event.target.closest("[data-action]");
    if (!target) return;
    if (target.dataset.action === "print") {
      window.print();
    } else if (target.dataset.action === "back") {
      window.history.back();
    }
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

  function init(root) {
    root.querySelectorAll("select[data-filterable]").forEach(enhanceSelect);
  }

  document.addEventListener("DOMContentLoaded", function () { init(document); });
  document.addEventListener("htmx:afterSwap", function (event) { init(event.target); });
})();
