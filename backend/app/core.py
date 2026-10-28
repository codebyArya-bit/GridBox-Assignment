"""Point-in-time Elexon wind forecast evaluation; no fabricated data."""
from __future__ import annotations
from datetime import date, datetime, time, timedelta, timezone
from math import sqrt, isfinite
from zoneinfo import ZoneInfo
import httpx

UK = ZoneInfo('Europe/London')
BASE = 'https://data.elexon.co.uk/bmrs/api/v1/datasets'
FIRST_DECISION, LAST_DECISION = date(2026,1,1), date(2026,1,31)

def parse_time(value):
    parsed = datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None: raise ValueError('Timestamp has no offset')
    return parsed.astimezone(timezone.utc)

def iso(dt): return dt.astimezone(timezone.utc).isoformat().replace('+00:00','Z')

def delivery_day(decision_date):
    if not FIRST_DECISION <= decision_date <= LAST_DECISION:
        raise ValueError('Decision date must be in January 2026')
    return decision_date + timedelta(days=1)

def decision_cutoff(decision_date, hour=11):
    return datetime.combine(decision_date, time(hour), UK).astimezone(timezone.utc)

def intervals(day):
    start = datetime.combine(day, time.min, UK).astimezone(timezone.utc)
    end = datetime.combine(day+timedelta(days=1), time.min, UK).astimezone(timezone.utc)
    return [start + timedelta(minutes=30*i) for i in range(int((end-start).total_seconds()/1800))]

def generation(value):
    value = float(value)
    if not isfinite(value) or value < 0: raise ValueError('Invalid wind MW')
    return value

def latest_asof(forecasts, cutoff):
    chosen={}
    for row in forecasts:
        try:
            start,published = parse_time(row['startTime']),parse_time(row['publishTime'])
            value=generation(row['generation'])
        except (KeyError,ValueError,TypeError,AttributeError,OverflowError): continue
        if published<=cutoff and (start not in chosen or published>chosen[start]['published']):
            chosen[start]={'published':published,'forecast':value}
    return chosen

def evaluate(actuals, forecasts, decision_date, hour=11):
    day = delivery_day(decision_date)
    cutoff = decision_cutoff(decision_date,hour)
    chosen=latest_asof(forecasts,cutoff)
    measured={}
    for row in actuals:
        if row.get('fuelType')!='WIND': continue
        try: measured[parse_time(row['startTime'])]=generation(row['generation'])
        except (KeyError,ValueError,TypeError,AttributeError,OverflowError): continue
    rows=[]
    for t in intervals(day):
        forecast=chosen.get(t)
        fc=forecast['forecast'] if forecast else None
        ac=measured.get(t)
        error=fc-ac if fc is not None and ac is not None else None
        rows.append({'startTime':iso(t),'forecastMW':fc,'actualMW':ac,
                     'errorMW':round(error,3) if error is not None else None,
                     'publishedAt':iso(forecast['published']) if forecast else None})
    errors=[r['errorMW'] for r in rows if r['errorMW'] is not None]
    n=len(errors)
    return {'decisionDate':decision_date.isoformat(),'deliveryDate':day.isoformat(),
            'decisionCutoff':iso(cutoff),'cutoffAssumption':'UK local previous-day decision hour; not verified market gate closure',
            'expectedIntervals':len(rows),'forecastIntervals':sum(r['forecastMW'] is not None for r in rows),
            'actualIntervals':sum(r['actualMW'] is not None for r in rows),'matchedIntervals':n,
            'maeMW':round(sum(map(abs,errors))/n,2) if n else None,
            'rmseMW':round(sqrt(sum(e**2 for e in errors)/n),2) if n else None,
            'biasMW':round(sum(errors)/n,2) if n else None,'series':rows,
            'dataSource':'Elexon BMRS FUELHH + WINDFOR'}

async def fetch_dataset(dataset, start, end, client=None):
    if dataset not in ('FUELHH','WINDFOR'): raise ValueError('Unsupported dataset')
    # FUELHH filters by settlement date, not the from/to timestamps used by other APIs.
    # The interval end is exclusive; subtract a microsecond to keep the same settlement day.
    params=({'publishDateTimeFrom':iso(start),'publishDateTimeTo':iso(end)}
            if dataset=='WINDFOR' else {
                'settlementDateFrom':start.astimezone(UK).date().isoformat(),
                'settlementDateTo':(end - timedelta(microseconds=1)).astimezone(UK).date().isoformat()
            })
    async def call(session):
        response=await session.get(f'{BASE}/{dataset}/stream',params=params)
        response.raise_for_status()
        payload=response.json()
        if isinstance(payload,list): return payload
        if isinstance(payload,dict) and isinstance(payload.get('data'),list): return payload['data']
        raise ValueError(f'Unexpected Elexon {dataset} response')
    if client is not None: return await call(client)
    async with httpx.AsyncClient(timeout=60,follow_redirects=True) as session:
        return await call(session)
