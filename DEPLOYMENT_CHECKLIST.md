# Deployment Checklist: app.alterasf.com

This checklist ensures all configurations are updated for the new Render instance at `https://app.alterasf.com`.

## ✅ Already Completed
- [x] Stripe API keys added to environment variables
- [x] Payment links are shared (same product links, but URLs need updating)
- [x] Database is shared between sandbox and prod

## 🔴 Critical: Stripe Configuration

### 1. Update Stripe Payment Links Success/Cancel URLs

**Action Required:** In Stripe Dashboard → Payment Links, update the Success/Cancel URLs for the existing payment links:

**For each payment link (Free, Starter, Pro, Ultra - Monthly & Yearly):**
- **Success URL:** `https://app.alterasf.com/billing/payment-success`
- **Cancel URL:** `https://app.alterasf.com/billing/payment-cancel`

**How to update:**
1. Go to Stripe Dashboard → Products → Payment Links
2. For each link, click "Edit"
3. Update "After payment" → Success URL
4. Update "After payment" → Cancel URL
5. Save changes

**Payment Links to Update (same links, just update their redirect URLs):**
- Free Monthly: `https://buy.stripe.com/aFa5kDaw79Kyg5C16ScjS03`
- Free Yearly: `https://buy.stripe.com/28E14n8nZ5uicTqbLwcjS05`
- Starter Monthly: `https://buy.stripe.com/9B6bJ133F2i6aLi02OcjS02`
- Starter Yearly: `https://buy.stripe.com/5kQfZh0Vx5ui4mU6rccjS06`
- Pro Monthly: `https://buy.stripe.com/8x200j8nZ6ymbPmaHscjS04`
- Pro Yearly: `https://buy.stripe.com/eVq5kDcEfg8Wg5C8zkcjS07`
- Ultra Monthly: `https://buy.stripe.com/dRm9AT5bNe0O06E5n8cjS00`
- Ultra Yearly: `https://buy.stripe.com/aFa8wP33F6ym6v25n8cjS08`

### 2. Configure Stripe Webhook Endpoint

**Action Required:** Add a new webhook endpoint in Stripe Dashboard for the new domain.

**Steps:**
1. Go to Stripe Dashboard → Developers → Webhooks
2. Click "Add endpoint"
3. **Endpoint URL:** `https://app.alterasf.com/billing/webhooks/stripe`
4. **Events to send:**
   - `checkout.session.completed` ⚠️ **CRITICAL** - Required for account creation
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
   - `payment_method.attached`
   - `customer.created`
5. Copy the **Signing secret** (starts with `whsec_`)
6. Add it to Render environment variables as `STRIPE_WEBHOOK_SECRET` (or `STRIPE_WEBHOOK_SECRET_SNAPSHOT`)

**Note:** If you want to use the same webhook endpoint for both sandbox and prod, you can configure both domains to point to the same webhook URL, or create separate endpoints. The webhook handler will work for both domains.

### 3. Verify Stripe Customer Portal Configuration

**Action Required:** Ensure Stripe Customer Portal is configured (usually works automatically, but verify).

**Steps:**
1. Go to Stripe Dashboard → Settings → Billing → Customer Portal
2. Ensure portal is enabled
3. The return URL is generated dynamically by the code using `url_for('billing.account', _external=True)`, so it should work automatically

## ✅ Code Review - No Changes Needed

The codebase is already configured to work with any domain:

- ✅ **URL Generation:** Uses `url_for(..., _external=True)` which automatically uses the request host
- ✅ **No Hardcoded URLs:** All redirects use Flask's `url_for()` function
- ✅ **Database Schema:** Shared database - schema already exists, no migration needed
- ✅ **Session Configuration:** Works with any domain (no cookie domain restrictions)

## 🔍 Environment Variables to Verify

Ensure these are set in your Render environment:

**Required:**
- `STRIPE_SECRET_KEY` - Your Stripe secret key (sk_live_... or sk_test_...)
- `STRIPE_PUBLISHABLE_KEY` - Your Stripe publishable key (pk_live_... or pk_test_...)
- `STRIPE_WEBHOOK_SECRET` - Webhook signing secret from step 2 above
- `RESUME_APP_SECRET_KEY` - Flask session secret (should be a random string)

**Database (shared with sandbox):**
- `DATABASE_URL` - Should already be configured since database is shared

## 🧪 Testing Checklist

After deployment, test the following flows:

### 1. Signup Flow
- [ ] Visit `/billing/signup`
- [ ] Select a plan and fill out signup form
- [ ] Submit form → Should redirect to Stripe Payment Link
- [ ] Complete payment in Stripe
- [ ] Should redirect back to `/billing/payment-success`
- [ ] Account should be created automatically (check via webhook)
- [ ] User should be auto-logged in

### 2. Webhook Testing
- [ ] In Stripe Dashboard → Webhooks → Your endpoint
- [ ] Click "Send test webhook"
- [ ] Test `checkout.session.completed` event
- [ ] Verify webhook is received (check Render logs)
- [ ] Verify account creation works

### 3. Billing Portal
- [ ] Log in to an account
- [ ] Go to `/billing/account`
- [ ] Click "Manage Payment"
- [ ] Should redirect to Stripe Customer Portal
- [ ] After updating payment method, should return to `/billing/account`

### 4. Plan Changes
- [ ] Log in to an account
- [ ] Go to `/billing/change-plan`
- [ ] Change to a different plan
- [ ] Verify subscription updates in Stripe Dashboard
- [ ] Verify plan change reflects in `/billing/account`

## 🚨 Common Issues & Solutions

### Issue: Users redirected to wrong domain after payment
**Solution:** Update Payment Link Success URLs in Stripe Dashboard (see step 1). The payment links themselves are shared, but their Success/Cancel URLs need to point to the correct domain.

### Issue: Webhooks not received
**Solution:** 
- Verify webhook endpoint URL is correct
- Check webhook secret is set in environment variables
- Verify webhook endpoint is accessible (not behind firewall)
- Check Render logs for webhook errors

### Issue: Account not created after payment
**Solution:**
- Verify `checkout.session.completed` event is enabled in webhook
- Check webhook secret matches
- Verify `PendingSignup` record exists with matching email
- Check Render logs for webhook processing errors

### Issue: Database errors
**Solution:**
- Database is shared, so ensure `DATABASE_URL` environment variable is set correctly
- Verify database connection is accessible from the new Render instance
- Check that database user has appropriate permissions (read/write access)

## 📝 Notes

- **Database:** Shared between sandbox and prod - all data is accessible from both environments. Be careful with data modifications as they affect both.
- **Payment Links:** The payment link URLs (buy.stripe.com/...) are shared, but the Success/Cancel URLs within each link need to be updated to point to the correct domain (prod vs sandbox).
- **Stripe Mode:** Ensure you're using the correct Stripe keys (test vs. live) for your environment.
- **HTTPS:** Render automatically provides HTTPS, which is required for Stripe webhooks.
- **Webhook Endpoints:** You may need separate webhook endpoints for sandbox vs. prod, or use the same endpoint if it can handle both domains.

## 🔗 Quick Links

- **Stripe Dashboard:** https://dashboard.stripe.com
- **Render Dashboard:** https://dashboard.render.com
- **Webhook Endpoint:** `https://app.alterasf.com/billing/webhooks/stripe`

---

**Last Updated:** Based on codebase as of deployment date
**Domain:** https://app.alterasf.com
