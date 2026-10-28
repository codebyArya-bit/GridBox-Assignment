from datetime import date
import asyncio
import httpx
from fastapi.testclient import TestClient
import app.main as api
from app.core import fetch_dataset, _CACHE

client = TestClient(api.app)

def test_health():
    assert client.get('/api/health').json()['version'] == '2.0.0'

def test_validations():
    assert client.get('/api/analysis?decision_date=2026-02-01').status_code == 422
    assert client.get('/api/analysis?cutoff_time=25:00').status_code == 422
    assert client.get('/api/analysis?cutoff_time=10:72').status_code == 422

def test_analysis_route(monkeypatch):
    async def fake(dataset, start, end):
        if dataset == 'FUELHH':
            return [
                {'startTime':'2026-01-16T00:00:00Z','fuelType':'WIND','generation':130},
                {'startTime':'2026-01-16T00:30:00Z','fuelType':'WIND','generation':150}
            ]
        return [{'startTime':'2026-01-16T00:00:00Z','publishTime':'2026-01-15T09:30:00Z','generation':125}]
    monkeypatch.setattr(api, 'fetch_dataset', fake)
    response = client.get('/api/analysis?decision_date=2026-01-15&cutoff_time=09:50')
    assert response.status_code == 200
    out = response.json()
    assert out['biasMW'] == -15
    assert out['matchedIntervals'] == 1
    assert out['expectedIntervals'] == 24

def test_legacy_cutoff_hour_parameter(monkeypatch):
    async def fake(dataset, start, end): return []
    monkeypatch.setattr(api,'fetch_dataset',fake)
    assert client.get('/api/analysis?cutoff_hour=11').json()['cutoffTimeUK'] == '11:00'

def test_502_on_upstream_timeout(monkeypatch):
    async def fail(dataset, start, end): raise httpx.TimeoutException('timed out')
    monkeypatch.setattr(api,'fetch_dataset',fail)
    assert client.get('/api/analysis').status_code == 502

def test_elexon_filter_names_and_retry(monkeypatch):
    urls = []
    async def reply(request):
        urls.append(str(request.url))
        if len(urls) == 1:
            return httpx.Response(503, text='temporary')
        return httpx.Response(200,json=[])
    async def quick_sleep(_): return None
    monkeypatch.setattr(asyncio,'sleep',quick_sleep)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as session:
            start=api.decision_cutoff(date(2026,1,15))
            await fetch_dataset('WINDFOR',start,start,session)
            await fetch_dataset('FUELHH',start,start,session)
    asyncio.run(run())
    assert len(urls) == 3
    assert 'publishDateTimeFrom=' in urls[0]
    assert 'settlementDateFrom=2026-01-15' in urls[2]

def test_monthly_missing_is_explicit(monkeypatch,tmp_path):
    monkeypatch.setattr(api,'MONTHLY_FILE',tmp_path/'absent.json')
    assert client.get('/api/monthly').status_code == 503

def test_monthly_snapshot_validation(monkeypatch,tmp_path):
    p=tmp_path/'month.json'
    p.write_text('{"daysCount":31,"days":[]}',encoding='utf-8')
    monkeypatch.setattr(api,'MONTHLY_FILE',p)
    assert client.get('/api/monthly').status_code == 200
    p.write_text('{"daysCount":30}',encoding='utf-8')
    assert client.get('/api/monthly').status_code == 503
