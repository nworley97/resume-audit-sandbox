document.addEventListener("DOMContentLoaded", () => {
  const overlay = document.getElementById("loading-overlay");
  if (!overlay) return;

  function showLoader() {
    overlay.classList.remove("hidden", "opacity-0");
    overlay.classList.add("opacity-100");

    const start = Date.now();

    window.addEventListener("load", () => {
      const elapsed = Date.now() - start;
      const remaining = Math.max(0, 500 - elapsed); // enforce min 500ms
      setTimeout(() => {
        overlay.classList.remove("opacity-100");
        overlay.classList.add("opacity-0");
        setTimeout(() => overlay.classList.add("hidden"), 200); // match fade duration
      }, remaining);
    }, { once: true });
  }

  // Trigger on link clicks
  document.querySelectorAll("a[href]").forEach(link => {
    link.addEventListener("click", e => {
      const target = e.currentTarget.getAttribute("href");
      if (target && !target.startsWith("#") && !target.startsWith("mailto:")) {
        showLoader();
      }
    });
  });

  // Trigger on form submits
  document.querySelectorAll("form").forEach(form => {
    form.addEventListener("submit", () => {
      showLoader();
    });
  });
});
