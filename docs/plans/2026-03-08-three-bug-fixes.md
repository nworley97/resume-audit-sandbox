# Three Bug Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix three bugs: restore camera UI on camera_gate page, fix duplicated dashboard images on landing page, fix analytics dashboard "invalid route" in user portal.

**Architecture:** Each bug is independent — fix in sequence, commit after each. Camera fix adds HTML+JS to existing template. Dashboard fix crops an image and updates template references. Analytics fix adds query-param routing to serve the SPA at the correct path.

**Tech Stack:** Flask, Jinja2, Tailwind CSS, Python/Pillow (image crop), JavaScript (getUserMedia)

---

### Task 1: Create feature branch

**Step 1: Create and switch to new branch**

```bash
git checkout -b fix/three-bugs-camera-dashboard-analytics
```

**Step 2: Verify branch**

```bash
git branch --show-current
```
Expected: `fix/three-bugs-camera-dashboard-analytics`

---

### Task 2: Restore Camera UI to `camera_gate.html`

**Files:**
- Modify: `templates/camera_gate.html:72-95` (insert camera card, update agreement, rewrite JS)

**Step 1: Add "Allow Camera Access" card after "Before You Begin" (line 72) and before "Agreement" (line 74)**

Insert this new card between the closing `</div>` on line 72 and the `<!-- Agreement -->` comment on line 74:

```html
  <!-- Camera Access -->
  <div class="bg-white rounded-xl ring-1 ring-gray-200 p-4 md:p-5 mb-4">
    <div class="font-semibold text-gray-900 mb-2">Allow Camera Access</div>
    <p class="text-xs text-gray-500 mb-3">
      To ensure fairness and authenticity for all candidates, please allow access to your camera before starting.
    </p>

    <div class="divide-y divide-gray-200">
      <div class="py-2 flex items-start gap-3">
        <span class="inline-flex h-5 w-5 items-center justify-center rounded-full bg-[#ecfdf5] ring-1 ring-[#99f6e4]">
          <svg class="h-3.5 w-3.5 text-primary" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fill-rule="evenodd" d="M16.704 5.29a1 1 0 00-1.408-1.418L8.5 10.67 5.7 7.87a1 1 0 10-1.4 1.43l3.5 3.5a1 1 0 001.42 0l7.484-7.51z" clip-rule="evenodd"/>
          </svg>
        </span>
        <div class="flex-grow">
          <div class="text-primary text-sm font-medium">Camera Access</div>
          <div class="text-xs text-gray-500 mb-3">
            Your video and activity data will only be used for identity verification and evaluation integrity purposes.
            They will not be stored or shared externally.
          </div>

          <!-- Browser prompt mock -->
          <div class="max-w-[280px] mx-auto border border-gray-200 rounded-xl p-3 shadow-sm bg-white">
            <div class="text-xs font-semibold text-gray-400 mb-1">alterasf.com wants to</div>
            <div class="text-sm text-gray-700 mb-3">Use your camera</div>
            <div class="flex flex-col gap-2">
              <div class="text-center text-xs py-1.5 border border-gray-200 rounded-lg text-gray-600 bg-gray-50">Allow this time</div>
              <div class="text-center text-xs py-1.5 border border-gray-200 rounded-lg text-gray-600 bg-gray-50">Allow on every visit</div>
              <div class="text-center text-xs py-1.5 border border-gray-200 rounded-lg text-gray-600 bg-gray-50">Don't allow</div>
            </div>
          </div>

          <p class="text-xs text-gray-500 mt-3">
            <span class="font-medium">Note:</span> You can proceed even if you choose "Don't allow," but doing so may void your application.
          </p>
        </div>
      </div>
    </div>
  </div>
```

**Step 2: Update the agreement checkbox text (line 81)**

Change:
```html
<span>I understand that not responding to questions may forfeit my opportunity</span>
```
To:
```html
<span>I understand that not responding to questions may forfeit my opportunity, and that declining camera access may void my application</span>
```

**Step 3: Replace the form and JS (lines 85-128)**

Replace the existing `<!-- Start -->` form (lines 85-94) with this form that uses JS submission:

```html
  <!-- Start -->
  <form id="cam-form" method="get" action="{{ next_url }}">
    <div class="text-center">
      <button id="btnStart" type="submit"
              class="inline-flex items-center justify-center rounded-lg bg-gray-300 px-4 py-2 text-sm font-semibold text-white cursor-not-allowed"
              disabled>
        Start
      </button>
    </div>
  </form>
```

Replace the entire `{% block body_extra %}` script section (lines 98-128) with:

```html
{% block body_extra %}
<script>
  const agree    = document.getElementById('agree');
  const btnStart = document.getElementById('btnStart');
  const camForm  = document.getElementById('cam-form');

  function updateStartState() {
    const ok = !!agree.checked;
    btnStart.disabled = !ok;
    btnStart.className =
      'inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-semibold ' +
      (ok ? 'bg-primary text-white hover:bg-[#0b7c70] cursor-pointer'
          : 'bg-gray-300 text-white cursor-not-allowed');
  }

  agree?.addEventListener('change', updateStartState);
  updateStartState();

  // Request camera permission before navigating to questions
  btnStart.addEventListener('click', async function (e) {
    if (btnStart.disabled) return;
    e.preventDefault();
    try {
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        stream.getTracks().forEach(t => t.stop());
      }
    } catch (err) {
      // Permission denied or no device — intentionally ignored
    }
    window.location.href = camForm.action;
  });
</script>
<script>
(function () {
  const flagUrl = "{{ url_for('flag_tab_switch', tenant=tenant_slug, code=code, cid=cid) }}";
  function sendFlag() {
    try { navigator.sendBeacon(flagUrl); }
    catch { fetch(flagUrl, { method: 'POST', keepalive: true }); }
  }
  document.addEventListener('visibilitychange', () => { if (document.hidden) sendFlag(); });
  window.addEventListener('pagehide', sendFlag);
})();
</script>
{% endblock %}
```

**Step 4: Verify template renders**

Manually check that the Jinja template has no syntax errors by visually reviewing the file. Confirm:
- `{% extends "base_public.html" %}` at top
- `{% block content %}` ... `{% endblock %}` balanced
- `{% block body_extra %}` ... `{% endblock %}` balanced
- No unclosed HTML tags

**Step 5: Commit**

```bash
git add templates/camera_gate.html
git commit -m "fix: restore camera access UI and getUserMedia prompt to camera gate page"
```

---

### Task 3: Crop dashboard image and fix duplication

**Files:**
- Create: `static/img/landing/dashboard-matrix.png`
- Create: `static/img/landing/dashboard-detail.png`
- Modify: `templates/landing/sections/dashboard_look.html:24-30`

**Step 1: Create a Python script to crop the image**

Create a temporary script `crop_dashboard.py` in project root:

```python
from PIL import Image

img = Image.open('static/img/landing/dashboard-overview.png')
w, h = img.size  # 4144 x 1916

# Main image: Cross Validation Matrix (left portion, full height)
# Crop to remove the overlapping detail card area
matrix = img.crop((0, 0, int(w * 0.62), h))  # ~2569 x 1916
matrix.save('static/img/landing/dashboard-matrix.png', optimize=True)

# Detail image: Software Development Associate card (bottom-right)
detail = img.crop((int(w * 0.42), int(h * 0.38), w, h))  # ~2404 x 1189
detail.save('static/img/landing/dashboard-detail.png', optimize=True)

print(f"Original: {w}x{h}")
print(f"Matrix:   {matrix.size}")
print(f"Detail:   {detail.size}")
```

**Step 2: Run the crop script**

```bash
python crop_dashboard.py
```

Expected output: Three lines showing dimensions.

**Step 3: Verify the cropped images look correct**

Check files exist and have reasonable sizes:
```bash
ls -la static/img/landing/dashboard-matrix.png static/img/landing/dashboard-detail.png
```

**Step 4: Update `dashboard_look.html` image sources**

In `templates/landing/sections/dashboard_look.html`, change line 25:
```html
<img src="{{ url_for('static', filename='img/landing/dashboard-overview.png') }}" alt="Analytics Dashboard" class="rounded-[12px] w-full h-full object-cover">
```
To:
```html
<img src="{{ url_for('static', filename='img/landing/dashboard-matrix.png') }}" alt="Cross Validation Matrix" class="rounded-[12px] w-full h-full object-cover">
```

Change line 29:
```html
<img src="{{ url_for('static', filename='img/landing/dashboard-overview.png') }}" alt="Dashboard Detail" class="rounded-[12px] w-full h-full object-cover">
```
To:
```html
<img src="{{ url_for('static', filename='img/landing/dashboard-detail.png') }}" alt="Diamonds in the Rough" class="rounded-[12px] w-full h-full object-cover">
```

**Step 5: Remove temporary crop script**

```bash
rm crop_dashboard.py
```

**Step 6: Commit**

```bash
git add static/img/landing/dashboard-matrix.png static/img/landing/dashboard-detail.png templates/landing/sections/dashboard_look.html
git commit -m "fix: split dashboard screenshot into two distinct images to fix duplication"
```

---

### Task 4: Fix analytics dashboard iframe route

**Files:**
- Modify: `app.py:1720-1756` (analytics routes)

**Step 1: Modify `analytics_overview_nextjs` to serve SPA when `?raw=1`**

In `app.py`, replace lines 1720-1734 with:

```python
@app.route("/<tenant>/recruiter/analytics", strict_slashes=False)
@app.route("/<tenant>/recruiter/analytics/", strict_slashes=False)
@login_required
@require_feature("analytics_dashboard")
def analytics_overview_nextjs(tenant=None):
    """Serve analytics SPA within Flask layout (preserves sidebar)"""
    t = load_tenant_by_slug(tenant) if tenant else current_tenant()
    if not t:
        slug = session.get("tenant_slug")
        if slug:
            return redirect(url_for("analytics_overview_nextjs", tenant=slug))
        return redirect(url_for("login"))

    # When raw=1, serve the SPA HTML directly (used by iframe)
    if request.args.get('raw') == '1':
        return send_from_directory('analytics_ui/dashboard/dist', 'index.html')

    spa_url = url_for('analytics_overview_nextjs', tenant=t.slug) + '?raw=1'
    return render_template('analytics_embed.html', title='Analytics', spa_url=spa_url, tenant=t)
```

**Step 2: Modify `analytics_detail_nextjs` to serve SPA when `?raw=1`**

In `app.py`, replace lines 1736-1750 with:

```python
@app.route("/<tenant>/recruiter/analytics/<jobCode>", strict_slashes=False)
@app.route("/<tenant>/recruiter/analytics/<jobCode>/", strict_slashes=False)
@login_required
@require_feature("analytics_dashboard")
def analytics_detail_nextjs(tenant=None, jobCode=None):
    """Serve analytics SPA detail page within Flask layout"""
    t = load_tenant_by_slug(tenant) if tenant else current_tenant()
    if not t:
        slug = session.get("tenant_slug")
        if slug:
            return redirect(url_for("analytics_detail_nextjs", tenant=slug, jobCode=jobCode))
        return redirect(url_for("login"))

    # When raw=1, serve the SPA HTML directly (used by iframe)
    if request.args.get('raw') == '1':
        return send_from_directory('analytics_ui/dashboard/dist', 'index.html')

    spa_url = url_for('analytics_detail_nextjs', tenant=t.slug, jobCode=jobCode) + '?raw=1'
    return render_template('analytics_embed.html', title='Analytics', spa_url=spa_url, tenant=t)
```

**Step 3: Verify `request` is imported**

Check that `from flask import request` is already imported at the top of `app.py`. It should be — search for it:

```bash
grep "from flask import" app.py | head -5
```

**Step 4: Commit**

```bash
git add app.py
git commit -m "fix: serve analytics SPA at correct path via ?raw=1 to fix iframe route mismatch"
```

---

### Task 5: Final verification

**Step 1: Review all changes on the branch**

```bash
git log --oneline main..HEAD
```

Expected: 4 commits (design doc + 3 bug fixes)

**Step 2: Check for syntax issues in modified files**

```bash
python -c "import py_compile; py_compile.compile('app.py', doraise=True)"
```

Expected: No errors.

**Step 3: Verify template files parse**

```bash
python -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates'))
for t in ['camera_gate.html', 'landing/sections/dashboard_look.html', 'analytics_embed.html']:
    env.get_template(t)
    print(f'OK: {t}')
"
```

Expected: All three print OK.
