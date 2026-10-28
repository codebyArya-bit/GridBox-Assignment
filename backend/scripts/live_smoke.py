"""Real upstream schema smoke test; runs separately from deterministic CI."""
import asyncio
from datetime import datetime, timezone
from app.core import fetch_dataset

async def main():
    from_time=datetime(2026,1,15,9,tzinfo=timezone.utc)
    to_time=datetime(2026,1,15,13,tzinfo=timezone.utc)
    for dataset in ('FUELHH','WINDFOR'):
        rows=await fetch_dataset(dataset,from_time,to_time)
        print(f'{dataset}: {len(rows)} rows')
        if not rows: raise RuntimeError(f'{dataset} returned no rows; check API filters, service status, and historical coverage')
        print(f'{dataset}: response keys: {sorted(rows[0])}')
        fields=({'startTime','fuelType','generation'} if dataset=='FUELHH' else {'startTime','publishTime','generation'})
        if not fields.issubset(rows[0]): raise RuntimeError(f'{dataset} schema mismatch: {fields-rows[0].keys()}')

if __name__=='__main__': asyncio.run(main())
