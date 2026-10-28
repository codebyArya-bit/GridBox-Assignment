"""Audit public backend on all January purchasing dates and custom cutoff comparisons."""
import asyncio
import json
import math
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
import httpx

BASE=os.getenv('GRIDBOX_WEB','https://gridbox-wind-web.vercel.app')
DATES=[(f'2026-01-{day:02d}','09:50') for day in range(1,32)] + [
    ('2026-01-15','08:00'),('2026-01-15','17:00'),('2026-01-15','09:49'),('2026-01-15','09:51')]

def check(result,day,cutoff_time):
    assert result['decisionDate']==day
    assert result['cutoffTimeUK']==cutoff_time
    assert result['expectedIntervals']==len(result['series'])==24
    assert result['expectedHalfHourIntervals']==48
    assert result['observedHalfHourIntervals']==48
    assert result['matchedIntervals']>=20
    assert result['forecastIntervals']==24
    assert result['actualIntervals']==24
    cutoff=datetime.fromisoformat(result['decisionCutoff'].replace('Z','+00:00'))
    errors=[]
    for row in result['series']:
        assert row['publishedAt'] is None or datetime.fromisoformat(row['publishedAt'].replace('Z','+00:00'))<=cutoff
        if row['errorMW'] is not None:
            a,b=row['actualHalfHoursMW']
            assert math.isclose(row['actualMW'],(a+b)/2,abs_tol=.002)
            assert math.isclose(row['errorMW'],row['forecastMW']-row['actualMW'],abs_tol=.005)
            errors.append(row['errorMW'])
    assert math.isclose(sum(map(abs,errors))/len(errors),result['maeMW'],abs_tol=.02)
    return {k:result[k] for k in ('decisionDate','deliveryDate','cutoffTimeUK','actualIntervals','forecastIntervals','matchedIntervals','maeMW','rmseMW','biasMW')}

async def main():
    semaphore=asyncio.Semaphore(6)
    async with httpx.AsyncClient(follow_redirects=True,timeout=90) as client:
        async def get(day,cutoff):
            async with semaphore:
                for attempt in range(3):
                    try:
                        r=await client.get(BASE+'/api/analysis',params={'decision_date':day,'cutoff_time':cutoff})
                        r.raise_for_status()
                        return check(r.json(),day,cutoff)
                    except (httpx.HTTPError,AssertionError) as exc:
                        if attempt==2:raise
                        await asyncio.sleep(2*(attempt+1))
        rows=await asyncio.gather(*(get(*item) for item in DATES))
    assert len(rows)==35
    assert len({r['decisionDate'] for r in rows if r['cutoffTimeUK']=='09:50'})==31
    Path('audit-results.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
    print('ALL 31 JANUARY DATES VALIDATED')
    print('HOUR COUNT DISTRIBUTION',dict(Counter(r['matchedIntervals'] for r in rows)))
    print('AUDIT PASSED')

if __name__=='__main__':
    asyncio.run(main())
