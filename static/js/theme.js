/* Applies the user's saved colour theme before the page is painted.
   Dark is the default (set on <html> by the server); a saved "light" overrides it.
   Kept tiny and render-blocking on purpose so light-mode users don't see a flash. */
(function () {
  "use strict";
  try {
    var saved = window.localStorage.getItem("gd-theme");
    if (saved === "light" || saved === "dark") {
      document.documentElement.setAttribute("data-bs-theme", saved);
    }
  } catch (e) {
    /* Storage blocked (private mode etc.): keep the default. */
  }
})();
