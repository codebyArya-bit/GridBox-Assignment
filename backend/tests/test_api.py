import asyncio
from datetime import date
import httpx
from fastapi.testclient import TestClient
import app.main as api
from app.core import fetch_dataset

client=TestClient(api.app)

def test_health():
    assert client.get('/api/health').json()['status']=='ok'

def test_validation():
    assert client.get('/api/analysis?decision_date=2026-02-01').status_code==422
    assert client.get('/api/analysis?cutoff_hour=33').status_code==422

def test_analysis_fixture(monkeypatch):
    async def fake(dataset,start,end):
        if dataset=='FUELHH': return [{'startTime':'2026-01-16T00:00:00Z','fuelType':'WIND','generation':130}]
        return [{'startTime':'2026-01-16T00:00:00Z','publishTime':'2026-01-15T10:00:00Z','generation':125}]
    monkeypatch.setattr(api,'fetch_dataset',fake)
    r=client.get('/api/analysis?decision_date=2026-01-15')
    assert r.status_code==200 and r.json()['biasMW']==-5

def test_upstream_error(monkeypatch):
    async def fake(dataset,start,end): raise httpx.TimeoutException('timeout')
    monkeypatch.setattr(api,'fetch_dataset',fake)
    assert client.get('/api/analysis').status_code==502

def test_request_filter_names():
    urls=[]
    async def handler(request):
        urls.append(str(request.url))
        return httpx.Response(200,json=[])
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            start=api.decision_cutoff(date(2026,1,15),11)
            await fetch_dataset('WINDFOR',start,start,client)
            await fetch_dataset('FUELHH',start,start,client)
    asyncio.run(run())
    assert 'publishDateTimeFrom=' in urls[0]
    assert 'settlementDateFrom=2026-01-15' in urls[1]
    assert 'settlementDateTo=2026-01-15' in urls[1]
