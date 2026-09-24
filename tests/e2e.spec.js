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
  await expect(page.getByText('Test Engineer', { exact: true })).toBeVisible();
  await expect(page.getByText('Example Labs', { exact: true })).toBeVisible();
  await expect(page.getByText('2022–Present', { exact: true })).toBeVisible();
  await expect(page.getByText('Built reliable browser and API test systems.')).toBeVisible();
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


test('slug-gated mobile demo supports its primary walkthrough', async ({ page }) => {
  const missing = await page.goto('/mobile-demo/not-the-demo-slug');
  expect(missing.status()).toBe(404);
  await page.goto('/mobile-demo/preview-61d7c4a9f2e8');
  await expect(page.getByRole('heading', { name: 'Job Posting', exact: true })).toBeVisible();
  await expectNoPageOverflow(page);

  await page.getByRole('button', { name: 'Candidates', exact: true }).click();
  await page.getByRole('searchbox', { name: 'Search candidates' }).fill('Ketaki');
  await expect(page.locator('[data-candidate]')).toHaveCount(1);
  await page.getByRole('button', { name: /KK Ketaki Kulkarni/ }).click();
  await expect(page.getByRole('dialog')).toContainText('Diamond in the Rough');
  await page.getByRole('button', { name: 'View full profile' }).click();
  await page.getByRole('button', { name: 'Original', exact: true }).click();
  await expect(page.locator('#paper-name')).toHaveText('KETAKI KULKARNI');

  await page.getByRole('combobox', { name: 'Figma screen' }).selectOption('39');
  await page.getByRole('button', { name: 'Add Yafei Zhang to finalists' }).click();
  await page.getByRole('button', { name: 'Done', exact: true }).click();
  await page.getByRole('button', { name: 'Edit note for Yafei Zhang' }).click();
  await page.getByRole('textbox', { name: 'Private note' }).fill('Follow up on assessment.');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await page.getByRole('button', { name: 'Edit note for Yafei Zhang' }).click();
  await expect(page.getByRole('textbox', { name: 'Private note' })).toHaveValue('Follow up on assessment.');
  await page.keyboard.press('Escape');

  await page.getByRole('combobox', { name: 'Figma screen' }).selectOption('41');
  await page.getByRole('button', { name: '10', exact: true }).click();
  await page.getByRole('button', { name: 'Done', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Start date', exact: true })).toHaveText('Aug 10, 2026');

  await page.getByRole('combobox', { name: 'Figma screen' }).selectOption('14');
  await expect(page.locator('.phone')).toHaveClass(/dark/);
  await page.getByRole('button', { name: 'Dark mode', exact: true }).click();
  await expect(page.locator('.phone')).not.toHaveClass(/dark/);
});

test('all mobile design states render without script errors or overflow', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/mobile-demo/preview-61d7c4a9f2e8');
  for (let screen = 1; screen <= 43; screen++) {
    await page.getByRole('combobox', { name: 'Figma screen' }).selectOption(String(screen));
    await expect(page.locator('#app')).not.toBeEmpty();
    expect(await page.locator('.phone').evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
  }
  expect(errors).toEqual([]);
});

test('mobile sheets return focus and preserve date selection until committed', async ({ page }) => {
  await page.goto('/mobile-demo/preview-61d7c4a9f2e8');
  const trigger = page.getByRole('button', { name: 'Add Dept', exact: true });
  await trigger.click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(trigger).toBeFocused();

  await page.getByRole('combobox', { name: 'Figma screen' }).selectOption('41');
  const day = page.getByRole('button', { name: '10', exact: true });
  await day.click();
  await expect(day).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Start date', exact: true })).toHaveText('Aug 5, 2026');
});
