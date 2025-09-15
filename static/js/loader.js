// static/js/loader.js
(() => {
  const ID = "page-loader";
  const STYLE_ID = "page-loader-style";
  let el;

  // ----- Minimal CSS fallback (only injected if you haven't styled it elsewhere) -----
  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const css = `
      #${ID} { position: fixed; inset: 0; pointer-events: none; opacity: 0; transition: opacity .15s ease; z-index: 9999; }
      #${ID}.on { pointer-events: auto; opacity: 1; }
      #${ID} .loader-backdrop { position: absolute; inset: 0; background: rgba(15,23,42,.24); backdrop-filter: blur(1px); }
      #${ID} .loader-spinner {
        position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%);
        width: 48px; height: 48px; border-radius: 9999px;
        border: 4px solid rgba(255,255,255,.6); border-top-color: rgba(37,99,235,1);
        animation: page-loader-spin 0.8s linear infinite;
      }
      @keyframes page-loader-spin { to { transform: translate(-50%,-50%) rotate(360deg); } }
    `;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = css;
    document.head.appendChild(style);
  }

  // ----- Overlay element -----
  function ensure() {
    if (el) return el;
    ensureStyle();
    el = document.getElementById(ID);
    if (!el) {
      el = document.createElement("div");
      el.id = ID;
      el.setAttribute("aria-live", "polite");
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

  // ----- Helper: should this click show the spinner? -----
  function shouldShowForAnchor(a) {
    if (!a) return false;

    // Explicit opt-out flag from templates
    if (a.hasAttribute("data-noload")) return false;

    // New tab / downloads shouldn't trigger spinner
    if (a.target === "_blank" || a.hasAttribute("download")) return false;

    const href = a.getAttribute("href") || "";
    if (!href) return false;

    // Ignore in-page anchors / JS pseudo-links
    if (href === "#" || href.startsWith("#") || href.toLowerCase().startsWith("javascript:")) return false;

    // Ignore mailto/tel
    if (/^(mailto:|tel:)/i.test(href)) return false;

    // Modifier keys (open in new tab/window), or middle/aux click
    // Note: listener uses capture so we still see these
    if (lastClickEvent &&
        (lastClickEvent.metaKey || lastClickEvent.ctrlKey || lastClickEvent.shiftKey || lastClickEvent.altKey ||
         lastClickEvent.button === 1)) return false;

    // External links
    try {
      const u = new URL(href, window.location.href);
      if (u.origin !== window.location.origin) return false;

      // Static assets or file-like paths: likely downloads; don’t spin
      if (u.pathname.startsWith("/static/")) return false;
      if (/\.(pdf|docx?|xlsx?|csv|zip|png|jpe?g|gif|webp|svg)$/i.test(u.pathname)) return false;
    } catch {
      // If URL parsing fails, play it safe and don't show
      return false;
    }

    // Otherwise this is a normal in-app navigation
    return true;
  }

  // Track last click for modifier/middle button checks
  let lastClickEvent = null;
  document.addEventListener("mousedown", (e) => { lastClickEvent = e; }, true);
  document.addEventListener("mouseup",   () => { lastClickEvent = null; }, true);

  // ----- Show on user-driven navigations (anchors) -----
  document.addEventListener("click", (e) => {
    const a = e.target && e.target.closest ? e.target.closest("a") : null;
    if (!shouldShowForAnchor(a)) return;
    show();
  }, true); // capture to run before route changes

  // ----- Show on form submits (unless opted out) -----
  document.addEventListener("submit", (e) => {
    const form = e.target;
    if (form && form.hasAttribute("data-noload")) return;
    show();
  }, true);

  // ----- Show while leaving the page -----
  window.addEventListener("beforeunload", () => show());

  // ----- Always hide on coming back from bfcache or navigating history -----
  window.addEventListener("pageshow", () => hide());
  window.addEventListener("popstate", () => hide());

  // ----- Safety nets -----
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") hide();
  });
  // Hide after initial DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", hide, { once: true });
  } else {
    hide();
  }
})();
