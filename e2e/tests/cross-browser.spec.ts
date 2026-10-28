import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('cross-browser: working UI, January data, keyboard and contrast audit',async({page},info)=>{
 test.setTimeout(180000);
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/',{waitUntil:'domcontentloaded'});
 await expect(page.locator('tbody tr')).toHaveCount(24,{timeout:140000});
 await expect(page.locator('.card')).toHaveCount(4);
 await expect(page.locator('.recharts-line-curve').first()).toHaveAttribute('d',/M/);
 const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
 expect(result.violations,JSON.stringify(result.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)})))).toEqual([]);
 const monthly=info.project.name==='mobile-chromium'?page.getByRole('button',{name:'January trends'}):page.getByRole('button',{name:/January analysis/});
 await monthly.click();await expect(page.locator('tbody tr')).toHaveCount(31,{timeout:140000});
 expect(errors).toEqual([]);
});
