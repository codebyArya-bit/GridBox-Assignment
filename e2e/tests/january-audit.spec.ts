import {test,expect} from '@playwright/test';

test('extended audit: mobile production display, controls and responsive scrolling',async ({page},info)=>{
  test.skip(info.project.name !== 'mobile-chromium','Audit mobile separately from desktop');
  test.setTimeout(180000);
  const errors:string[]=[];
  page.on('pageerror',e=>errors.push(e.message));
  const responses:number[]=[];
  page.on('response',r=>{ if(r.url().includes('/api/analysis'))responses.push(r.status()); });
  await page.goto('/',{waitUntil:'domcontentloaded',timeout:90000});
  await expect(page.locator('tbody tr')).toHaveCount(48,{timeout:140000});
  await expect(page.locator('.metrics .card')).toHaveCount(4);
  await expect(page.locator('.recharts-area-curve').first()).toHaveAttribute('d',/M/);
  await expect(page.locator('aside')).toBeHidden();
  await expect(page.locator('.mobilehint')).toBeVisible();
  await expect(page.locator('input[type=date]')).toHaveAttribute('max','2026-01-31');
  const noGlobalOverflow=await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2);
  expect(noGlobalOverflow,'Unexpected horizontal page overflow').toBeTruthy();
  expect(errors).toEqual([]);
  expect(responses).toContain(200);
  await page.screenshot({path:info.outputPath('mobile-production-audit.png'),fullPage:true,animations:'disabled'});
});

test('extended audit: desktop keyboard focus, controls, chart and links',async ({page},info)=>{
  test.skip(info.project.name!=='desktop-chromium','Desktop-only navigation audit');
  const errors:string[]=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');
  await expect(page.locator('tbody tr')).toHaveCount(48,{timeout:140000});
  await expect(page.locator('nav a')).toHaveCount(3);
  await page.locator('nav a[href="#intervals"]').click();
  await expect(page).toHaveURL(/#intervals$/);
  await expect(page.locator('#intervals')).toBeVisible();
  await page.locator('#cutoff').focus();
  await expect(page.locator('#cutoff')).toBeFocused();
  expect(errors).toEqual([]);
});
