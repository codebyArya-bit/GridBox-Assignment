"""Elexon point-in-time hourly wind accuracy for January 2026 day-ahead decisions.

WINDFOR timestamps are hourly. Each forecast is compared against the arithmetic
mean of two FUELHH half-hourly generation observations. This is an explicitly
stated analytical aggregation assumption, not a claim that WINDFOR predicts an
energy volume. No missing forecast or actual values are imputed.
"""
from __future__ import annotations

import asyncio
import math
import time
from collections import defaultdict
from datetime import date, datetime, time as clock_time, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

UK = ZoneInfo("Europe/London")
BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
FIRST_DECISION, LAST_DECISION = date(2026, 1, 1), date(2026, 1, 31)
DEFAULT_CUTOFF = "09:50"
DEFAULT_SOURCE = "Nord Pool N2EX day-ahead auction (09:50 GMT in January)"
CACHE_TTL_SECONDS = 3600
_CACHE: dict[tuple, tuple[float, list[dict]]] = {}
_LOCK = asyncio.Lock()
RETRYABLE = {408, 425, 429, 500, 502, 503, 504}


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must specify a timezone")
    return parsed.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def delivery_day(decision_date: date) -> date:
    if not FIRST_DECISION <= decision_date <= LAST_DECISION:
        raise ValueError("Decision date must fall within January 2026")
    return decision_date + timedelta(days=1)


def parse_cutoff(value: str) -> clock_time:
    if len(value) != 5 or value[2] != ":" or not (value[:2].isdigit() and value[3:].isdigit()):
        raise ValueError("Cutoff must be HH:MM")
    hour, minute = int(value[:2]), int(value[3:])
    if hour > 23 or minute > 59:
        raise ValueError("Cutoff must be a valid UK local time")
    return clock_time(hour, minute)


def decision_cutoff(decision_date: date, cutoff_time: str = DEFAULT_CUTOFF) -> datetime:
    return datetime.combine(decision_date, parse_cutoff(cutoff_time), tzinfo=UK).astimezone(timezone.utc)


def half_hour_intervals(day: date) -> list[datetime]:
    start = datetime.combine(day, clock_time.min, tzinfo=UK).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), clock_time.min, tzinfo=UK).astimezone(timezone.utc)
    return [start + timedelta(minutes=30 * i) for i in range(int((end - start).total_seconds() // 1800))]


def generation(value: object) -> float:
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError("Invalid generation in MW")
    return result


def latest_asof(forecasts: list[dict], cutoff: datetime) -> dict[datetime, dict]:
    chosen: dict[datetime, dict] = {}
    for row in forecasts:
        try:
            target = parse_time(row["startTime"])
            published = parse_time(row["publishTime"])
            forecast = generation(row["generation"])
        except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
            continue
        if published > cutoff:
            continue
        if target not in chosen or published > chosen[target]["published"]:
            chosen[target] = {"published": published, "forecast": forecast}
    return chosen


def evaluate(actuals: list[dict], forecasts: list[dict], decision_date: date, cutoff_time: str = DEFAULT_CUTOFF) -> dict:
    delivery_date = delivery_day(decision_date)
    cutoff = decision_cutoff(decision_date, cutoff_time)
    slots = half_hour_intervals(delivery_date)
    chosen = latest_asof(forecasts, cutoff)
    measured: dict[datetime, float] = {}
    for row in actuals:
        if row.get("fuelType") != "WIND":
            continue
        try:
            measured[parse_time(row["startTime"])] = generation(row["generation"])
        except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
            continue

    # For January, each hour consists of exactly two half-hour settlement slots.
    # Group in UTC and protect against partial data rather than synthesizing it.
    rows = []
    for i in range(0, len(slots), 2):
        start = slots[i]
        next_half = slots[i + 1]
        raw = [measured.get(start), measured.get(next_half)]
        actual = (raw[0] + raw[1]) / 2 if all(x is not None for x in raw) else None
        item = chosen.get(start)
        forecast = item["forecast"] if item else None
        error = forecast - actual if forecast is not None and actual is not None else None
        rows.append({
            "startTime": iso(start),
            "forecastMW": forecast,
            "actualMW": round(actual, 3) if actual is not None else None,
            "actualHalfHoursMW": raw,
            "actualHalfHourSamples": sum(x is not None for x in raw),
            "errorMW": round(error, 3) if error is not None else None,
            "publishedAt": iso(item["published"]) if item else None,
        })

    errors = [r["errorMW"] for r in rows if r["errorMW"] is not None]
    n = len(errors)
    result = {
        "decisionDate": decision_date.isoformat(),
        "deliveryDate": delivery_date.isoformat(),
        "decisionCutoff": iso(cutoff),
        "cutoffTimeUK": cutoff_time,
        "cutoffReference": DEFAULT_SOURCE if cutoff_time == DEFAULT_CUTOFF else "Custom UK-local purchasing cutoff; client-defined",
        "resolution": "Hourly WINDFOR vs mean of corresponding two half-hourly WIND actuals",
        "aggregationMethod": "(FUELHH at HH:00 + FUELHH at HH:30) / 2, only when both readings exist",
        "expectedIntervals": len(rows),
        "forecastIntervals": sum(r["forecastMW"] is not None for r in rows),
        "actualIntervals": sum(r["actualMW"] is not None for r in rows),
        "matchedIntervals": n,
        "expectedHalfHourIntervals": len(slots),
        "observedHalfHourIntervals": sum(x in measured for x in slots),
        "maeMW": round(sum(abs(e) for e in errors) / n, 2) if n else None,
        "rmseMW": round(math.sqrt(sum(e * e for e in errors) / n), 2) if n else None,
        "biasMW": round(sum(errors) / n, 2) if n else None,
        "series": rows,
        "dataSource": "Elexon BMRS FUELHH + WINDFOR",
    }
    return result


async def fetch_dataset(dataset: str, start: datetime, end: datetime, client: httpx.AsyncClient | None = None) -> list[dict]:
    if dataset not in ("FUELHH", "WINDFOR"):
        raise ValueError("Unsupported dataset")
    params = (
        {"publishDateTimeFrom": iso(start), "publishDateTimeTo": iso(end)}
        if dataset == "WINDFOR" else
        {"settlementDateFrom": start.astimezone(UK).date().isoformat(),
         "settlementDateTo": (end - timedelta(microseconds=1)).astimezone(UK).date().isoformat()}
    )
    key = (dataset, tuple(sorted(params.items())))
    if client is None:
        entry = _CACHE.get(key)
        if entry and entry[0] > time.monotonic():
            return entry[1]

    async def request(session: httpx.AsyncClient) -> list[dict]:
        for attempt in range(4):
            try:
                response = await session.get(f"{BASE}/{dataset}/stream", params=params)
                if response.status_code in RETRYABLE and attempt < 3:
                    await asyncio.sleep(min(0.5 * (2 ** attempt), 3))
                    continue
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, list):
                    return payload
                if isinstance(payload, dict) and isinstance(payload.get("data"), list):
                    return payload["data"]
                raise ValueError(f"Unexpected Elexon {dataset} response format")
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt >= 3:
                    raise
                await asyncio.sleep(min(0.5 * (2 ** attempt), 3))
        raise RuntimeError("Retry loop exhausted")

    if client is not None:
        return await request(client)
    # Brief synchronization avoids stampedes for overlapping requests in one worker.
    async with _LOCK:
        entry = _CACHE.get(key)
        if entry and entry[0] > time.monotonic():
            return entry[1]
        async with httpx.AsyncClient(timeout=35, follow_redirects=True) as session:
            rows = await request(session)
        if len(_CACHE) > 200:
            now = time.monotonic()
            for candidate, entry in list(_CACHE.items()):
                if entry[0] <= now:
                    _CACHE.pop(candidate, None)
            if len(_CACHE) > 200:
                _CACHE.clear()
        _CACHE[key] = (time.monotonic() + CACHE_TTL_SECONDS, rows)
        return rows
