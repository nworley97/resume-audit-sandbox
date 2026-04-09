# Contact Form → Resend → info@alterasf.com

**Date:** 2026-04-09
**Scope:** Wire the contact page form to send submissions to info@alterasf.com via Resend API

---

## Flow

1. User fills out contact form on `/contact` page and clicks "Send Message"
2. Frontend JS collects form data and POSTs to `/contact` as JSON
3. Flask POST handler validates required fields, calls Resend API
4. Resend sends email to info@alterasf.com with all form data
5. Flask returns JSON `{ "success": true }` or `{ "success": false, "error": "..." }`
6. Frontend shows success modal on 200, or displays error message on failure
7. Submit button is disabled during send to prevent double-submits

## Backend

**Route:** Add POST method to existing `/contact` route in `app.py`

- Accept JSON body with fields: `first_name`, `last_name`, `email`, `phone`, `company_name`, `country`, `role`, `company_size`, `hiring`, `subject`, `message`
- Validate required fields: `first_name`, `last_name`, `email`, `company_name`, `country`, `role`, `company_size`, `hiring`, `subject`, `message`
- Call `resend.Emails.send()` with:
  - `from`: `onboarding@resend.dev` (Resend default sender, no domain verification needed)
  - `to`: `info@alterasf.com`
  - `subject`: `[Contact Form] {subject}`
  - `html`: formatted HTML table with all submitted fields
- Return JSON response with appropriate status code (200 on success, 400 on validation error, 500 on send failure)

**Environment variable:** `RESEND_API_KEY` — set in Render dashboard

**Package:** `resend` added to `requirements.txt`

## Frontend

**File:** `templates/contact.html` inline `<script>`

- Replace the current form submit handler (which does `e.preventDefault()`, shows modal, resets form without sending data)
- New handler:
  1. Prevent default
  2. Collect all form fields into a JSON object
  3. Disable submit button, update text to "Sending..."
  4. `fetch('/contact', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })`
  5. On success (200): show success modal, reset form
  6. On error: show inline error message below the form
  7. Re-enable submit button in all cases

## Email Format

```
Subject: [Contact Form] {subject}

From: {first_name} {last_name} <{email}>

Name: {first_name} {last_name}
Email: {email}
Phone: {phone}
Company: {company_name}
Country: {country}
Role: {role}
Company Size: {company_size}
Hiring: {hiring}

Subject: {subject}

Message:
{message}
```

The `reply-to` header will be set to the submitter's email so you can reply directly from your inbox.

## Files to Modify

| File | Changes |
|------|---------|
| `requirements.txt` | Add `resend` package |
| `app.py` | Add POST handler to `/contact` route with Resend API call |
| `templates/contact.html` | Update form submit JS to POST data and handle response |

## Setup Steps (Manual)

1. Create a Resend account at resend.com
2. Get API key from Resend dashboard
3. Add `RESEND_API_KEY` environment variable in Render dashboard

## Success Criteria

1. Submitting the contact form sends an email to info@alterasf.com with all form data
2. The email has a reply-to header set to the submitter's email
3. The success modal appears after successful submission
4. Validation errors show a user-friendly message
5. API/network errors show a generic error message
6. The submit button is disabled during send
