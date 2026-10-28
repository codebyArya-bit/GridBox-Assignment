"""Generate deterministic January 2026 Elexon-derived month summary at N2EX 09:50 UK.

Re-run with: cd backend && python -m scripts.build_monthly
No synthetic data, no replacement of missing records, no external data source.
"""
from __future__ import annotations
import asyncio
import json
import math
from datetime import date, timedelta
from pathlib import Path

from app.core import (DEFAULT_CUTOFF, decision_cutoff, delivery_day,
                      evaluate, fetch_dataset, half_hour_intervals)

OUT = Path(__file__).resolve().parents[1] / 'data' / 'january_0950.json'

async def get_one(day: int, semaphore: asyncio.Semaphore):
    async with semaphore:
        decision = date(2026, 1, day)
        hours = half_hour_intervals(delivery_day(decision))
        cutoff = decision_cutoff(decision)
        actual, forecasts = await asyncio.gather(
            fetch_dataset('FUELHH', hours[0], hours[-1] + timedelta(minutes=30)),
            fetch_dataset('WINDFOR', cutoff-timedelta(days=3), cutoff))
        result = evaluate(actual, forecasts, decision)
        if result['matchedIntervals'] < 20 or result['observedHalfHourIntervals'] < 44:
            raise ValueError(f"Incomplete data for {decision}: {result['matchedIntervals']} matched hours")
        metrics = {k: result[k] for k in (
            'decisionDate','deliveryDate','cutoffTimeUK','expectedIntervals',
            'forecastIntervals','actualIntervals','matchedIntervals',
            'expectedHalfHourIntervals','observedHalfHourIntervals',
            'maeMW','rmseMW','biasMW')}
        metrics['maxAbsErrorMW'] = round(max(abs(r['errorMW']) for r in result['series'] if r['errorMW'] is not None),2)
        metrics['errorsMW'] = [r['errorMW'] for r in result['series'] if r['errorMW'] is not None]
        print(f"{decision}: forecast {metrics['forecastIntervals']}/24, actual {metrics['observedHalfHourIntervals']}/48, MAE {metrics['maeMW']} MW", flush=True)
        return metrics

async def main():
    semaphore = asyncio.Semaphore(6)
    daily = await asyncio.gather(*(get_one(i, semaphore) for i in range(1, 32)))
    daily.sort(key=lambda r:r['decisionDate'])
    all_errors=[e for day in daily for e in day.pop('errorsMW')]
    n=len(all_errors)
    assert len(daily)==31 and n >= 620, 'Insufficient January coverage'
    daily_mae = [r['maeMW'] for r in daily]
    histogram_edges=[-float('inf'),-3000,-1500,-500,0,500,1500,3000,float('inf')]
    histogram_labels=['< -3,000','-3,000 to -1,500','-1,500 to -500','-500 to 0','0 to +500','+500 to +1,500','+1,500 to +3,000','> +3,000']
    distribution=[{'band':label,'count':sum(a<=e<b for e in all_errors)} for a,b,label in zip(histogram_edges,histogram_edges[1:],histogram_labels)]
    summary={
        'period':'January 2026',
        'daysCount':31,
        'decisionStart':'2026-01-01',
        'decisionEnd':'2026-01-31',
        'cutoffTimeUK':DEFAULT_CUTOFF,
        'cutoffReference':'Nord Pool N2EX day-ahead gate closure 09:50 GMT (January)',
        'resolution':'WINDFOR hourly vs FUELHH mean of two half-hourly WIND values',
        'methodology':'Hourly forecast compared to arithmetic mean of the two half-hourly actual measurements; all errors in MW; no imputation.',
        'source':'Elexon BMRS WINDFOR + FUELHH',
        'aggregate':{
            'matchedHours':n,
            'expectedHours':31*24,
            'forecastHours':sum(x['forecastIntervals'] for x in daily),
            'observedHalfHours':sum(x['observedHalfHourIntervals'] for x in daily),
            'maeMW':round(sum(abs(e) for e in all_errors)/n,2),
            'rmseMW':round(math.sqrt(sum(e*e for e in all_errors)/n),2),
            'biasMW':round(sum(all_errors)/n,2),
            'bestDay':daily[daily_mae.index(min(daily_mae))]['decisionDate'],
            'worstDay':daily[daily_mae.index(max(daily_mae))]['decisionDate'],
        },
        'errorDistribution':distribution,
        'days':daily,
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'WROTE {OUT}: {n} matched hourly forecast/actual pairs')

if __name__ == '__main__':
    asyncio.run(main())
