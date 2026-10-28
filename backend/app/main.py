"""FastAPI routes: date-scoped, point-in-time, and explicit upstream errors."""
import asyncio
from datetime import date, timedelta
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from .core import FIRST_DECISION, LAST_DECISION, decision_cutoff, delivery_day, intervals, fetch_dataset, evaluate

app=FastAPI(title='GridBox Wind Intelligence',version='1.2.0')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_methods=['GET'],allow_headers=['*'])

@app.get('/api/health')
def health(): return {'status':'ok','source':'Elexon BMRS','mode':'historical-on-demand'}

@app.get('/api/analysis')
async def analysis(decision_date:date=Query(default=date(2026,1,15)), cutoff_hour:int=Query(default=11,ge=0,le=23)):
    if not FIRST_DECISION<=decision_date<=LAST_DECISION:
        raise HTTPException(422,'Decision date must be January 1–31, 2026')
    slots=intervals(delivery_day(decision_date))
    cutoff=decision_cutoff(decision_date,cutoff_hour)
    try:
        actuals,forecasts=await asyncio.gather(
            fetch_dataset('FUELHH',slots[0],slots[-1]+timedelta(minutes=30)),
            fetch_dataset('WINDFOR',cutoff-timedelta(days=3),cutoff))
    except Exception as exc:
        raise HTTPException(502,f'Elexon request failed ({type(exc).__name__})') from exc
    return evaluate(actuals,forecasts,decision_date,cutoff_hour)
