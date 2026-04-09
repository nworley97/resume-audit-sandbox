# Contact Form → Resend Email Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the contact page form to send submissions to info@alterasf.com via the Resend API.

**Architecture:** Frontend POSTs form data as JSON to the existing `/contact` Flask route (new POST handler). The route validates fields, calls Resend's Python SDK, and returns JSON. Frontend shows the existing success modal on 200 or an error message on failure.

**Tech Stack:** Flask, Resend Python SDK, vanilla JavaScript fetch API

**Spec:** `docs/superpowers/specs/2026-04-09-contact-form-resend-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `requirements.txt` | Modify | Add `resend` package |
| `app.py` | Modify | Add POST handler to `/contact` route with Resend API call |
| `templates/contact.html` | Modify | Update form submit JS to POST data and handle response |

---

### Task 1: Add resend package to requirements

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add resend to requirements.txt**

Add `resend>=2.0` to the end of `requirements.txt`:

```
resend>=2.0
```

- [ ] **Step 2: Install the package**

Run: `pip install resend>=2.0`

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add resend package for contact form email

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Add POST handler to /contact route

**Files:**
- Modify: `app.py:540-542`

**Context:** The current `/contact` route is GET-only and just renders the template. We need to add a POST handler that receives JSON form data, validates required fields, calls the Resend API, and returns a JSON response. The app already imports `jsonify`, `request`, and `os` at the top of the file.

- [ ] **Step 1: Add resend import at the top of app.py**

Add after the existing imports (around line 30, after `from dateutil import parser as dtparse`):

```python
import resend
```

- [ ] **Step 2: Replace the /contact route with GET+POST handler**

Replace lines 540-542:

```python
@app.route("/contact")
def contact_page():
    return render_template("contact.html")
```

with:

```python
@app.route("/contact", methods=["GET", "POST"])
def contact_page():
    if request.method == "GET":
        return render_template("contact.html")

    # POST: handle contact form submission
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "Invalid request"}), 400

    required = [
        "first_name", "last_name", "email", "company_name",
        "country", "role", "company_size", "hiring", "subject", "message",
    ]
    missing = [f for f in required if not data.get(f, "").strip()]
    if missing:
        return jsonify({"success": False, "error": f"Missing required fields: {', '.join(missing)}"}), 400

    resend.api_key = os.environ.get("RESEND_API_KEY", "")
    if not resend.api_key:
        app.logger.error("RESEND_API_KEY not configured")
        return jsonify({"success": False, "error": "Email service not configured"}), 500

    email_html = f"""
    <h2>New Contact Form Submission</h2>
    <table style="border-collapse:collapse;width:100%;max-width:600px;">
      <tr><td style="padding:8px;font-weight:bold;border-bottom:1px solid #eee;">Name</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{html.escape(data['first_name'])} {html.escape(data['last_name'])}</td></tr>
      <tr><td style="padding:8px;font-weight:bold;border-bottom:1px solid #eee;">Email</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{html.escape(data['email'])}</td></tr>
      <tr><td style="padding:8px;font-weight:bold;border-bottom:1px solid #eee;">Phone</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{html.escape(data.get('phone', 'N/A'))}</td></tr>
      <tr><td style="padding:8px;font-weight:bold;border-bottom:1px solid #eee;">Company</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{html.escape(data['company_name'])}</td></tr>
      <tr><td style="padding:8px;font-weight:bold;border-bottom:1px solid #eee;">Country</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{html.escape(data['country'])}</td></tr>
      <tr><td style="padding:8px;font-weight:bold;border-bottom:1px solid #eee;">Role</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{html.escape(data['role'])}</td></tr>
      <tr><td style="padding:8px;font-weight:bold;border-bottom:1px solid #eee;">Company Size</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{html.escape(data['company_size'])}</td></tr>
      <tr><td style="padding:8px;font-weight:bold;border-bottom:1px solid #eee;">Hiring</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{html.escape(data['hiring'])}</td></tr>
      <tr><td style="padding:8px;font-weight:bold;border-bottom:1px solid #eee;">Subject</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{html.escape(data['subject'])}</td></tr>
      <tr><td style="padding:8px;font-weight:bold;vertical-align:top;">Message</td>
          <td style="padding:8px;white-space:pre-wrap;">{html.escape(data['message'])}</td></tr>
    </table>
    """

    try:
        resend.Emails.send({
            "from": "AlteraSF Contact Form <onboarding@resend.dev>",
            "to": ["info@alterasf.com"],
            "reply_to": data["email"],
            "subject": f"[Contact Form] {data['subject']}",
            "html": email_html,
        })
    except Exception as e:
        app.logger.error(f"Resend API error: {e}")
        return jsonify({"success": False, "error": "Failed to send message. Please try again."}), 500

    return jsonify({"success": True})
```

Note: `html` is already imported at line 2 of app.py (`import os, json, uuid, logging, tempfile, mimetypes, re, io, csv, html`).

- [ ] **Step 3: Verify the route**

Read `app.py` and confirm:
- `import resend` is present near the top
- The `/contact` route accepts GET and POST
- GET returns `render_template("contact.html")`
- POST validates JSON body, checks required fields, calls `resend.Emails.send()`, returns JSON
- `reply_to` is set to the submitter's email
- All user input is escaped with `html.escape()`

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: add POST handler to /contact route for Resend email

Validates form fields, sends HTML email to info@alterasf.com via
Resend API with reply-to set to submitter's email. Returns JSON
success/error response.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Update frontend JS to POST form data

**Files:**
- Modify: `templates/contact.html` (inline script, around lines 354-366)

**Context:** The current form submit handler does `e.preventDefault()`, shows the success modal, and resets the form — without ever sending data to the server. We need to replace it with a `fetch` POST, disable the button during send, and handle success/error responses.

- [ ] **Step 1: Replace the form submit handler**

In `templates/contact.html`, find the inline script section. Replace the form submission block (lines 354-366):

```javascript
  if (form) {
    form.addEventListener('submit', function(e) {
      e.preventDefault();
      modal.classList.remove('hidden');
      modal.classList.add('flex');
      form.reset();
      if (closeBtn) closeBtn.focus();
    });
  }
```

with:

```javascript
  var submitBtn = form ? form.querySelector('[type="submit"]') : null;
  var submitText = submitBtn ? submitBtn.querySelector('span') : null;
  var errorMsg = document.getElementById('contact-error');

  if (form) {
    form.addEventListener('submit', function(e) {
      e.preventDefault();

      // Collect form data
      var data = {
        first_name: form.first_name.value.trim(),
        last_name: form.last_name.value.trim(),
        email: form.email.value.trim(),
        phone: form.phone ? form.phone.value.trim() : '',
        company_name: form.company_name.value.trim(),
        country: form.country.value,
        role: form.role.value,
        company_size: form.company_size.value,
        hiring: form.querySelector('input[name="hiring"]:checked') ? form.querySelector('input[name="hiring"]:checked').value : '',
        subject: form.subject.value.trim(),
        message: form.message.value.trim()
      };

      // Disable button
      if (submitBtn) { submitBtn.disabled = true; submitBtn.style.opacity = '0.6'; }
      if (submitText) submitText.textContent = 'Sending...';
      if (errorMsg) { errorMsg.classList.add('hidden'); errorMsg.textContent = ''; }

      fetch('/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      .then(function(res) { return res.json().then(function(body) { return { ok: res.ok, body: body }; }); })
      .then(function(result) {
        if (result.ok && result.body.success) {
          modal.classList.remove('hidden');
          modal.classList.add('flex');
          form.reset();
          if (closeBtn) closeBtn.focus();
        } else {
          var msg = result.body.error || 'Something went wrong. Please try again.';
          if (errorMsg) { errorMsg.textContent = msg; errorMsg.classList.remove('hidden'); }
        }
      })
      .catch(function() {
        if (errorMsg) { errorMsg.textContent = 'Network error. Please check your connection and try again.'; errorMsg.classList.remove('hidden'); }
      })
      .finally(function() {
        if (submitBtn) { submitBtn.disabled = false; submitBtn.style.opacity = ''; }
        if (submitText) submitText.textContent = 'Send Message';
      });
    });
  }
```

- [ ] **Step 2: Add error message element to the HTML form**

In `templates/contact.html`, find the submit button section (around line 284-288):

```html
          <!-- Submit Button -->
          <div class="flex justify-end">
            <button type="submit" ...>
```

Add an error message div **before** the submit button div:

```html
          <!-- Error Message -->
          <p id="contact-error" class="hidden text-red-500 font-ibm-sans text-[14px]"></p>

          <!-- Submit Button -->
          <div class="flex justify-end">
```

- [ ] **Step 3: Verify the frontend changes**

Read `templates/contact.html` and confirm:
- The `#contact-error` paragraph exists before the submit button
- The form submit handler collects all fields into a JSON object
- `fetch` POSTs to `/contact` with `Content-Type: application/json`
- On success: shows modal, resets form, focuses close button
- On error: shows error message in `#contact-error`
- On network error: shows "Network error" message
- Submit button is disabled during send and re-enabled in `finally`
- Submit text changes to "Sending..." and back to "Send Message"

- [ ] **Step 4: Commit**

```bash
git add templates/contact.html
git commit -m "feat: wire contact form to POST data with loading state and error handling

Replaces no-op form handler with fetch POST to /contact.
Disables button and shows 'Sending...' during request.
Shows success modal on 200 or inline error message on failure.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Verification

After all tasks are complete:

- [ ] **Local test with valid API key:** Set `RESEND_API_KEY` environment variable, run the Flask app, submit the form, confirm email arrives at info@alterasf.com
- [ ] **Test validation:** Submit with empty required fields, confirm error message appears
- [ ] **Test without API key:** Unset `RESEND_API_KEY`, submit, confirm "Email service not configured" error
- [ ] **Test button state:** Submit and verify button shows "Sending..." and is disabled during request
- [ ] **Deploy:** Push to main, add `RESEND_API_KEY` in Render environment variables, verify on production
