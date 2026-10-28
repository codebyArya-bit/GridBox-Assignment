"""FastAPI endpoints for time-correct day-ahead wind-generation analysis."""
import asyncio
import json
from datetime import date, timedelta
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from .core import (FIRST_DECISION, LAST_DECISION, DEFAULT_CUTOFF, delivery_day,
                   decision_cutoff, half_hour_intervals, parse_cutoff, fetch_dataset, evaluate)

app = FastAPI(title="GridBox Wind Intelligence", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["https://gridbox-wind-web.vercel.app", "http://localhost:5173"], allow_methods=["GET"], allow_headers=["*"])
MONTHLY_FILE = Path(__file__).resolve().parents[1] / "data" / "january_0950.json"

@app.get("/api/health")
def health():
    return {"status": "ok", "source": "Elexon BMRS", "mode": "historical-on-demand", "version": "2.0.0"}

@app.get("/api/analysis")
async def analysis(
    decision_date: date = Query(default=date(2026, 1, 15)),
    cutoff_time: str = Query(default=DEFAULT_CUTOFF, min_length=5, max_length=5),
    cutoff_hour: int | None = Query(default=None, ge=0, le=23, deprecated=True),
):
    if not FIRST_DECISION <= decision_date <= LAST_DECISION:
        raise HTTPException(status_code=422, detail="Decision date must be January 1–31, 2026")
    if cutoff_hour is not None:
        cutoff_time = f"{cutoff_hour:02d}:00"  # compatibility with legacy links
    try:
        parse_cutoff(cutoff_time)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    slots = half_hour_intervals(delivery_day(decision_date))
    cutoff = decision_cutoff(decision_date, cutoff_time)
    try:
        actuals, forecasts = await asyncio.gather(
            fetch_dataset("FUELHH", slots[0], slots[-1] + timedelta(minutes=30)),
            fetch_dataset("WINDFOR", cutoff - timedelta(days=3), cutoff),
        )
        return evaluate(actuals, forecasts, decision_date, cutoff_time)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Elexon data retrieval failed: {type(exc).__name__}") from exc

@app.get("/api/monthly")
def monthly():
    """Verified, reproducibly-generated January dataset at N2EX 09:50 UK cutoff."""
    if not MONTHLY_FILE.exists():
        raise HTTPException(status_code=503, detail="January summary is being generated; daily analysis remains available")
    try:
        result = json.loads(MONTHLY_FILE.read_text(encoding="utf-8"))
        if result.get("daysCount") != 31:
            raise ValueError("Incomplete summary")
        return result
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="Historical January summary unavailable") from exc
