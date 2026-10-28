"""Read-only January 2026 historical coverage and calculation audit against PUBLIC deployment."""
from __future__ import annotations
import asyncio
import json
import math
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import httpx

WEB = os.environ.get("GRIDBOX_WEB", "https://gridbox-wind-web.vercel.app")
# Cover all 31 purchasing dates as well as alternative cutoff hours.
DATES = [(f"2026-01-{day:02d}",11) for day in range(1,32)] + [
    ("2026-01-15",8),("2026-01-15",17)
]

def verify(payload, decision_date, cutoff_hour):
    assert payload["decisionDate"] == decision_date
    series = payload["series"]
    assert len(series) == payload["expectedIntervals"] == 48
    assert len({r["startTime"] for r in series}) == len(series)
    cutoff = datetime.fromisoformat(payload["decisionCutoff"].replace("Z","+00:00"))
    assert cutoff.hour == cutoff_hour
    assert payload["actualIntervals"] == sum(r["actualMW"] is not None for r in series)
    assert payload["forecastIntervals"] == sum(r["forecastMW"] is not None for r in series)
    assert payload["matchedIntervals"] == sum(r["errorMW"] is not None for r in series)
    assert payload["actualIntervals"] >= 40, f"Actuals incomplete: {decision_date}: {payload['actualIntervals']}"
    assert payload["forecastIntervals"] > 0, f"No as-of forecasts: {decision_date} at {cutoff_hour}"
    assert payload["matchedIntervals"] > 0, f"No paired observations: {decision_date}"
    for row in series:
        start = datetime.fromisoformat(row["startTime"].replace("Z","+00:00"))
        assert start.date().isoformat() == payload["deliveryDate"]
        pub = row["publishedAt"]
        if pub is not None:
            assert datetime.fromisoformat(pub.replace("Z","+00:00")) <= cutoff, "Look-ahead leakage"
        if row["errorMW"] is not None:
            assert row["forecastMW"] is not None and row["actualMW"] is not None
            assert math.isclose(row["errorMW"],row["forecastMW"]-row["actualMW"],abs_tol=.002)
    errors = [r["errorMW"] for r in series if r["errorMW"] is not None]
    mae=round(sum(abs(x) for x in errors)/len(errors),2)
    rmse=round(math.sqrt(sum(x*x for x in errors)/len(errors)),2)
    bias=round(sum(errors)/len(errors),2)
    assert math.isclose(mae,payload["maeMW"],abs_tol=.02)
    assert math.isclose(rmse,payload["rmseMW"],abs_tol=.02)
    assert math.isclose(bias,payload["biasMW"],abs_tol=.02)
    return {
       "decisionDate":decision_date,"deliveryDate":payload["deliveryDate"],"cutoffHourUK":cutoff_hour,
       "actualIntervals":payload["actualIntervals"],"forecastIntervals":payload["forecastIntervals"],
       "matchedIntervals":payload["matchedIntervals"],"coveragePctOf30MinSlots":round(100*payload["matchedIntervals"]/48,1),
       "forecastMinuteCounts":dict(Counter(r["startTime"][14:16] for r in series if r["forecastMW"] is not None)),
       "forecastPublicationTimes":sorted(set(r["publishedAt"] for r in series if r["publishedAt"] is not None)),
       "maeMW":payload["maeMW"],"rmseMW":payload["rmseMW"],"biasMW":payload["biasMW"]
    }

async def main():
    results = []
    async with httpx.AsyncClient(follow_redirects=True,timeout=100) as client:
        for decision_date, hour in DATES:
            url = f"{WEB}/api/analysis"
            params={"decision_date":decision_date,"cutoff_hour":hour}
            last=None
            for attempt in range(2):
                try:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    result=verify(response.json(), decision_date, hour)
                    print(json.dumps(result))
                    results.append(result)
                    break
                except Exception as exc:
                    last=exc
                    if attempt==0:
                        print("Retrying",params,type(exc).__name__,str(exc)[:100])
                        await asyncio.sleep(5)
            else:
                raise RuntimeError(f"Audit failed at {params}: {last}") from last
    # Changing the decision cutoff should never reduce the set of eligible forecasts
    by_hour={r["cutoffHourUK"]:r for r in results if r["decisionDate"]=="2026-01-15"}
    assert by_hour[8]["forecastIntervals"] <= by_hour[11]["forecastIntervals"] <= by_hour[17]["forecastIntervals"]
    Path("audit-results.json").write_text(json.dumps(results,indent=2)+"\n",encoding="utf-8")
    assert len(results)==33
    days_at_11=[r for r in results if r["cutoffHourUK"]==11]
    assert len({r["decisionDate"] for r in days_at_11})==31
    print("ALL 31 JANUARY DATES AUDITED",len(days_at_11))
    print("FORECAST COVERAGE DISTRIBUTION",dict(Counter(r["forecastIntervals"] for r in days_at_11)))
    print("MATCHED INTERVAL DISTRIBUTION",dict(Counter(r["matchedIntervals"] for r in days_at_11)))
    print("DATE BOUNDARIES AND CUTOFF AUDIT PASSED")

if __name__=="__main__":
    asyncio.run(main())
