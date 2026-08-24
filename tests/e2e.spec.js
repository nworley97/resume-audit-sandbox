import { test, expect } from '@playwright/test';


async function login(page) {
  await page.goto('/playwright/login');
  await page.getByLabel('Email').fill('playwright@example.com');
  await page.getByLabel('Password').fill('PlaywrightPass123!');
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/playwright\/recruiter/);
}


async function expectNoPageOverflow(page) {
  const dimensions = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
    offenders: Array.from(document.querySelectorAll('body *'))
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          element: `${element.tagName.toLowerCase()}${element.id ? `#${element.id}` : ''}.${Array.from(element.classList).join('.')}`,
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          width: Math.round(rect.width),
        };
      })
      .filter(({ left, right }) => left < 0 || right > window.innerWidth)
      .slice(0, 12),
  }));
  const detail = JSON.stringify(dimensions.offenders, null, 2);
  expect(dimensions.document, detail).toBeLessThanOrEqual(dimensions.viewport);
  expect(dimensions.body, detail).toBeLessThanOrEqual(dimensions.viewport);
}


test('landing page fits the viewport', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  const demoSource = await page.locator('#demo-video-preview source').getAttribute('src');
  expect(demoSource).not.toContain('%23');
  expect(demoSource).not.toContain('#');
  await expectNoPageOverflow(page);
});


test('recruiter, AI resume, PDF, and analytics paths work', async ({ page }) => {
  await login(page);
  await expect(page.getByRole('heading', { name: 'Job Posting' })).toBeVisible();
  await expectNoPageOverflow(page);

  await page.goto('/playwright/recruiter/candidate/playwright-candidate');
  await expect(page.getByRole('heading', { name: 'Candidate Details' })).toBeVisible();
  await expect(page.getByText('Test engineer focused on reliable systems.')).toBeVisible();
  await expect(page.getByText('4.5/5').first()).toBeVisible();
  await expectNoPageOverflow(page);

  await page.getByRole('button', { name: 'Original' }).click();
  await expect(page.locator('#resumeOriginalView canvas')).toBeVisible();

  await page.goto('/playwright/recruiter/analytics/PW-1');
  const analytics = page.frameLocator('iframe[title="Analytics Dashboard"]');
  await expect(analytics.getByText('Ada Playwright').first()).toBeVisible();
  await expect(analytics.getByText('4.5/5').first()).toBeVisible();
  await expect(analytics.getByText('90.0/5')).toHaveCount(0);
});
