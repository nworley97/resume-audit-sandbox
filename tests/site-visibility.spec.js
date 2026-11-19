import { test, expect } from '@playwright/test';

test.skip(process.env.SITE_HIDDEN !== 'true', 'Run explicitly with SITE_HIDDEN=true');

test('hidden homepage offers existing-user login without marketing or signup', async ({ page }, testInfo) => {
  const response = await page.goto('/');
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('heading', { name: 'Sign in to your account' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Sign up', exact: true })).toHaveCount(0);
  expect(response.headers()['x-robots-tag']).toContain('noindex');
  expect(await page.locator('body').evaluate(el => el.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('hidden-login.png'), fullPage: true });
  await page.getByRole('link', { name: 'Forgot password?' }).click();
  await expect(page.getByRole('button', { name: 'Send reset link' })).toBeVisible();
});

test('marketing and direct registration are closed but job applications remain open', async ({ page, request }) => {
  expect((await page.goto('/pricing')).status()).toBe(404);
  await expect(page.getByText('This page is currently unavailable.')).toBeVisible();
  expect((await page.goto('/billing/signup')).status()).toBe(403);
  await expect(page.getByText('New registrations are temporarily unavailable.')).toBeVisible();
  expect((await request.post('/billing/signup', { form: { plan_tier: 'free' } })).status()).toBe(403);
  expect((await page.goto('/playwright/apply/PW-1')).status()).toBe(200);
  await expect(page.getByText('Senior Test Engineer').first()).toBeVisible();
});

test('existing user can log in and access settings and original resume', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email', { exact: true }).fill('playwright@example.com');
  await page.getByLabel('Password', { exact: true }).fill('PlaywrightPass123!');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(/\/playwright\/recruiter/);
  expect((await page.goto('/playwright/settings')).status()).toBe(200);
  await expect(page.getByRole('button', { name: 'Add user', exact: true })).toBeVisible();
  const resume = await page.request.get('/playwright/resume/playwright-candidate');
  expect(resume.status()).toBe(200);
  expect(resume.headers()['content-type']).toContain('application/pdf');
  expect(resume.headers()['x-robots-tag']).toContain('noindex');
});
