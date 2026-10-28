"""Real public deployment checks executed from GitHub's network."""
import asyncio
import os
import httpx

FRONTEND=os.getenv("GRIDBOX_WEB","https://gridbox-wind-web.vercel.app")
BACKEND=os.getenv("GRIDBOX_API","https://gridbox-wind-api.vercel.app")

async def get_ready(client,url):
    latest=None
    for attempt in range(6):
        try:
            r=await client.get(url,timeout=80)
            print(url,"=>",r.status_code,"content-type:",r.headers.get("content-type",""),"bytes:",len(r.content))
            if r.status_code==200: return r
            latest=f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as exc:
            latest=f"{type(exc).__name__}: {exc}"
        await asyncio.sleep(12)
    raise AssertionError(f"Endpoint failed: {url} ({latest})")

async def main():
    async with httpx.AsyncClient(follow_redirects=True) as client:
        page=await get_ready(client,FRONTEND+"/")
        assert "GridBox" in page.text, "Unexpected frontend HTML"
        health=await get_ready(client,BACKEND+"/api/health")
        assert health.json()["status"]=="ok",health.text[:250]
        proxied=await get_ready(client,FRONTEND+"/api/health")
        assert proxied.json()["status"]=="ok",proxied.text[:250]
        data=await get_ready(client,BACKEND+"/api/analysis?decision_date=2026-01-15")
        payload=data.json()
        print("Analysis:",{k:v for k,v in payload.items() if k!="series"})
        assert payload["decisionDate"]=="2026-01-15"
        assert payload["deliveryDate"]=="2026-01-16"
        assert payload["expectedIntervals"]==24
        assert payload["forecastIntervals"]>0,"No historical forecasts available"
        assert payload["observedHalfHourIntervals"]==48,"No actual wind records available"
        assert payload["matchedIntervals"]>0,"Missing matched actual and forecast readings"
        assert all(row["publishedAt"] is None or row["publishedAt"] <= payload["decisionCutoff"] for row in payload["series"])
        print("Public deployment smoke test passed.")

if __name__=="__main__":
    asyncio.run(main())
