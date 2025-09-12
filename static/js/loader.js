// static/js/loader.js
(() => {
  const ID = "page-loader";
  let el;

  function ensure() {
    if (el) return el;
    el = document.getElementById(ID);
    if (!el) {
      el = document.createElement("div");
      el.id = ID;
      el.innerHTML = `
        <div class="loader-backdrop"></div>
        <div class="loader-spinner" aria-label="Loading" role="status"></div>
      `;
      document.body.appendChild(el);
    }
    return el;
  }

  function show() { ensure().classList.add("on"); }
  function hide() { ensure().classList.remove("on"); }

  // Show on user-driven navigations
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a");
    if (!a) return;
    const href = a.getAttribute("href");
    const tgt  = a.getAttribute("target");
    if (!href || href.startsWith("#") || href.startsWith("javascript:") || tgt === "_blank") return;
    show();
  });

  document.addEventListener("submit", () => show());

  // Show while leaving
  window.addEventListener("beforeunload", () => show());

  // IMPORTANT: When returning via BFCache, pageshow fires with persisted=true.
  // Always hide overlay on pageshow & popstate.
  window.addEventListener("pageshow", () => hide());
  window.addEventListener("popstate", () => hide());

  // Safety nets
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") hide();
  });
  document.addEventListener("DOMContentLoaded", () => hide());
})();
