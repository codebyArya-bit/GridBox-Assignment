import {test,expect,type Page} from '@playwright/test';

type Row={startTime:string;forecastMW:number;actualMW:number;actualHalfHoursMW:number[];actualHalfHourSamples:number;errorMW:number;publishedAt:string};
function dailyFixture(decisionDate='2026-01-15',cutoffTime='09:50'){
 const delivery=new Date(decisionDate+'T00:00:00Z');delivery.setUTCDate(delivery.getUTCDate()+1);
 const date=delivery.toISOString().slice(0,10);
 const rows:Row[]=Array.from({length:24},(_,i)=>{const start=new Date(delivery.getTime()+i*3600000).toISOString().replace('.000Z','Z');const actual=9000+i*12;
  return{startTime:start,forecastMW:actual+150,actualMW:actual,actualHalfHoursMW:[actual-50,actual+50],actualHalfHourSamples:2,errorMW:150,publishedAt:decisionDate+'T09:30:00Z'};});
 return{decisionDate,deliveryDate:date,decisionCutoff:decisionDate+'T'+cutoffTime+':00Z',cutoffTimeUK:cutoffTime,
 cutoffReference:'N2EX 09:50 GMT',resolution:'Hourly WINDFOR vs mean of 2 FUELHH actuals',aggregationMethod:'Arithmetic mean',
 expectedIntervals:24,forecastIntervals:24,actualIntervals:24,matchedIntervals:24,expectedHalfHourIntervals:48,observedHalfHourIntervals:48,
 maeMW:150,rmseMW:150,biasMW:150,series:rows,dataSource:'Elexon BMRS'};
}
function monthFixture(){const days=Array.from({length:31},(_,i)=>{const day=String(i+1).padStart(2,'0');return{
 decisionDate:'2026-01-'+day,deliveryDate:'2026-01-'+day,forecastIntervals:24,actualIntervals:24,matchedIntervals:24,expectedIntervals:24,
 maeMW:100+i*10,rmseMW:150+i*10,biasMW:-100+i*10,maxAbsErrorMW:600
 };});return{period:'January 2026',daysCount:31,cutoffTimeUK:'09:50',cutoffReference:'N2EX 09:50 GMT',methodology:'Hourly aligned actual means.',
 aggregate:{matchedHours:744,expectedHours:744,observedHalfHours:1488,maeMW:250,rmseMW:320,biasMW:60,bestDay:'2026-01-01',worstDay:'2026-01-31'},
 errorDistribution:[{band:'-500 to 0',count:100},{band:'0 to +500',count:644}],days};}
async function fixtures(page:Page){
 await page.route('**/api/analysis?**',async route=>{const p=new URL(route.request().url()).searchParams;
 await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(dailyFixture(p.get('decision_date')||'2026-01-15',p.get('cutoff_time')||'09:50'))});});
 await page.route('**/api/monthly',async route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(monthFixture())}));
}
async function stabilize(page:Page){await page.evaluate(async()=>document.fonts.ready);await page.waitForTimeout(1400)}

test('visual: daily dashboard hourly comparisons',async({page},info)=>{
 test.skip(!info.project.name.includes('chromium'),'Screenshot baselines only for Chromium');
 await fixtures(page);const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await expect(page.locator('tbody tr')).toHaveCount(24);
 await expect(page.locator('.card')).toHaveCount(4);
 await expect(page.getByText('24 / 24',{exact:false}).first()).toBeVisible();
 await expect(page.locator('.recharts-line-curve').first()).toHaveAttribute('d',/M/);
 await stabilize(page);expect(errors).toEqual([]);
 await expect(page).toHaveScreenshot('daily-dashboard.png',{fullPage:true,animations:'disabled',maxDiffPixelRatio:.003});
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-window.innerWidth);
 expect(overflow).toBeLessThanOrEqual(2);
});

test('visual: monthly analysis, error distribution and 31 daily rows',async({page},info)=>{
 test.skip(!info.project.name.includes('chromium'),'Screenshot baselines only for Chromium');
 await fixtures(page);await page.goto('/');
 const button=info.project.name==='mobile-chromium'?page.getByRole('button',{name:'January trends'}):page.getByRole('button',{name:/January analysis/});
 await button.click();await expect(page.getByText('January 2026 — forecast reliability')).toBeVisible();
 await expect(page.locator('tbody tr')).toHaveCount(31);
 await expect(page.locator('.chart')).toHaveCount(3);
 await stabilize(page);
 await expect(page).toHaveScreenshot('january-overview.png',{fullPage:true,animations:'disabled',maxDiffPixelRatio:.003});
});

test('visual: explicit Elexon failure state',async({page},info)=>{
 test.skip(!info.project.name.includes('chromium'),'Screenshot baselines only for Chromium');
 await page.route('**/api/analysis?**',route=>route.fulfill({status:502,contentType:'application/json',body:JSON.stringify({detail:'Elexon not available'})}));
 await page.goto('/');await expect(page.getByRole('alert')).toContainText('Elexon not available');
 await expect(page.locator('tbody tr')).toHaveCount(0);await stabilize(page);
 await expect(page).toHaveScreenshot('upstream-error.png',{fullPage:true,animations:'disabled',maxDiffPixelRatio:.003});
});

test('behavior: minute cutoff changes and daily navigation',async({page},info)=>{
 test.skip(!info.project.name.includes('chromium'),'Chromium controls test');
 await fixtures(page);await page.goto('/');await expect(page.locator('tbody tr')).toHaveCount(24);
 await page.locator('#decision-date').fill('2026-01-22');
 await expect(page.getByText('Delivery 2026-01-23')).toBeVisible();
 await page.locator('#cutoff').fill('10:17');
 await expect(page.getByText('Custom hypothetical cutoff')).toBeVisible();
 await page.getByRole('button',{name:'Reset N2EX 09:50'}).click();
 await expect(page.locator('#cutoff')).toHaveValue('09:50');
});

test('production: live hourly data and month snapshot available',async({page},info)=>{
 test.skip(info.project.name!=='desktop-chromium','One live production check; mobile separately');
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await expect(page.locator('tbody tr')).toHaveCount(24,{timeout:140_000});
 await expect(page.locator('.recharts-line-curve').first()).toHaveAttribute('d',/M/);
 const halfhour=await page.locator('tbody tr td:nth-child(3)').allTextContents();expect(halfhour.filter(x=>x!=='—').length).toBe(24);
 await page.getByRole('button',{name:/January analysis/}).click();
 await expect(page.locator('tbody tr')).toHaveCount(31,{timeout:140_000});
 expect(errors).toEqual([]);
 await page.screenshot({path:info.outputPath('live-january-overview.png'),fullPage:true,animations:'disabled'});
});
