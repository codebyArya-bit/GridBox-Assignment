import { test, expect, type Page, type Route } from '@playwright/test';

type AnalysisRow = { startTime: string; forecastMW: number; actualMW: number; errorMW: number; publishedAt: string };
function fixture(decisionDate = '2026-01-15', cutoffHour = 11) {
  const delivery = new Date(decisionDate + 'T00:00:00.000Z');
  delivery.setUTCDate(delivery.getUTCDate() + 1);
  const deliveryDate = delivery.toISOString().slice(0, 10);
  const publishedAt = decisionDate + 'T10:00:00Z';
  const series: AnalysisRow[] = Array.from({ length: 48 }, (_, index) => {
    const ts = new Date(delivery.getTime() + index * 30 * 60_000).toISOString().replace('.000Z', 'Z');
    const actualMW = 12_000 + index * 33 + Math.sin(index / 4) * 350;
    const errorMW = index % 2 === 0 ? 150 : -150;
    return {
      startTime: ts,
      forecastMW: Math.round(actualMW + errorMW),
      actualMW: Math.round(actualMW),
      errorMW,
      publishedAt
    };
  });
  return {
    decisionDate, deliveryDate,
    decisionCutoff: decisionDate + 'T' + String(cutoffHour).padStart(2, '0') + ':00:00Z',
    cutoffAssumption: 'Illustrative 11:00 UK purchasing cutoff',
    expectedIntervals: 48, forecastIntervals: 48, actualIntervals: 48, matchedIntervals: 48,
    maeMW: 150, rmseMW: 150, biasMW: 0,
    dataSource: 'Elexon BMRS FUELHH + WINDFOR',
    series
  };
}

async function interceptHistoricalData(page: Page) {
  await page.route('**/api/analysis?**', async (route: Route) => {
    const url = new URL(route.request().url());
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(fixture(
        url.searchParams.get('decision_date') || '2026-01-15',
        Number(url.searchParams.get('cutoff_hour') || '11')
      ))
    });
  });
}
async function stableScreenshot(page: Page) {
  // Prevent transient React chart animations and async webfont swaps in visual baselines.
  await page.waitForTimeout(2200);
  await page.evaluate(async () => { await document.fonts.ready; });
}

test('visual: deterministic dashboard and wind-generation charts', async ({ page }, testInfo) => {
  await interceptHistoricalData(page);
  const pageErrors: string[] = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'Wind Generation Intelligence' })).toBeVisible();
  await expect(page.locator('.card')).toHaveCount(4);
  await expect(page.locator('tbody tr')).toHaveCount(48);
  await expect.poll(() => page.locator('svg.recharts-surface').count()).toBeGreaterThanOrEqual(2);
  // The forecast series must have a real visible path despite alternating missing half-hour slots.
  // Without connectNulls, Recharts drew only isolated 1-point segments and no forecast line.
  await expect.poll(async () => (await page.locator('.recharts-area-curve').first().getAttribute('d') || '').length)
    .toBeGreaterThan(40);
  await expect(page.locator('.metrics')).toContainText('150');
  await expect(page.locator('header')).toBeVisible();
  await stableScreenshot(page);
  expect(pageErrors).toEqual([]);
  await expect(page).toHaveScreenshot('dashboard.png', {
    fullPage: true,
    animations: 'disabled',
    caret: 'hide',
    maxDiffPixelRatio: 0.003
  });
  const dimensions = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    cardCount: document.querySelectorAll('.card').length,
    rows: document.querySelectorAll('tbody tr').length
  }));
  expect(dimensions.document, JSON.stringify(dimensions)).toBeLessThanOrEqual(dimensions.viewport + 2);
  if (testInfo.project.name === 'mobile-chromium') {
    await expect(page.locator('aside')).toBeHidden();
    await expect(page.locator('.metrics')).toHaveCSS('grid-template-columns', /\d+px/);
  }
});

test('visual: upstream error is shown without fabricated metrics', async ({ page }) => {
  await page.route('**/api/analysis?**', async route =>
    route.fulfill({ status: 502, contentType: 'application/json', body: JSON.stringify({detail: 'Elexon unavailable'}) })
  );
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('alert')).toContainText('Live source unavailable');
  await expect(page.getByRole('alert')).toContainText('Elexon unavailable');
  await expect(page.locator('.card')).toHaveCount(0);
  await expect(page.locator('tbody tr')).toHaveCount(0);
  await stableScreenshot(page);
  await expect(page).toHaveScreenshot('upstream-error.png', {
    fullPage: true, animations: 'disabled', caret: 'hide', maxDiffPixelRatio: 0.003
  });
});

test('behavior: changing date and decision cutoff refreshes charts and rows', async ({ page }) => {
  const requestedUrls: string[] = [];
  await page.route('**/api/analysis?**', async route => {
    requestedUrls.push(route.request().url());
    const url = new URL(route.request().url());
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify(fixture(url.searchParams.get('decision_date') || '2026-01-15',
        Number(url.searchParams.get('cutoff_hour') || '11')))
    });
  });
  await page.goto('/');
  await expect(page.locator('tbody tr')).toHaveCount(48);
  await page.locator('#decision-date').fill('2026-01-20');
  await expect(page.getByText('Delivery 2026-01-21')).toBeVisible();
  await expect(page.locator('tbody tr').first()).toContainText('2026-01-21');
  await page.locator('#cutoff').selectOption('14');
  await expect.poll(() => requestedUrls.some(url => url.includes('decision_date=2026-01-20') && url.includes('cutoff_hour=14'))).toBe(true);
  await expect(page.locator('tbody tr')).toHaveCount(48);
  await expect.poll(() => page.locator('svg.recharts-surface').count()).toBeGreaterThanOrEqual(2);
});

test('production: public browser loads actual wind and forecast readings', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'Single production smoke run is sufficient');
  test.setTimeout(180_000);
  const pageErrors: string[] = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 90_000 });
  await expect(page.getByRole('heading', { name: 'Wind Generation Intelligence' })).toBeVisible();
  await expect(page.locator('tbody tr')).toHaveCount(48, { timeout: 140_000 });
  await expect.poll(() => page.locator('svg.recharts-surface').count()).toBeGreaterThanOrEqual(2);
  await expect(page.locator('.card')).toHaveCount(4);
  await expect(page.locator('.card').nth(3)).toContainText('24');
  await expect(page.getByRole('alert')).toHaveCount(0);
  const actualCells = await page.locator('tbody tr td:nth-child(3)').allTextContents();
  const matched = actualCells.filter(value => value.trim() !== '—').length;
  expect(matched).toBe(48);
  expect(pageErrors).toEqual([]);
  await stableScreenshot(page);
  await page.screenshot({ path: testInfo.outputPath('live-production-desktop.png'), fullPage: true, animations: 'disabled' });
});
