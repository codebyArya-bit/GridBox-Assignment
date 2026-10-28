"""Inspect actual Elexon API semantics and records, not synthetic fixtures."""
import asyncio
from datetime import datetime, timezone
from collections import Counter
from app.core import fetch_dataset

async def main():
    a=datetime(2026,1,16,0,tzinfo=timezone.utc)
    b=datetime(2026,1,17,0,tzinfo=timezone.utc)
    c=datetime(2026,1,15,9,tzinfo=timezone.utc)
    d=datetime(2026,1,15,13,tzinfo=timezone.utc)
    for dataset,start,end in [('FUELHH',a,b),('WINDFOR',c,d)]:
        rows=await fetch_dataset(dataset,start,end)
        print(dataset,'rows=',len(rows))
        if not rows:raise RuntimeError(dataset+' returned no rows')
        print('KEYS:',sorted(rows[0]))
        print('FIRST 3:',rows[:3])
        print('FUEL COUNTS:',Counter(str(row.get('fuelType')) for row in rows).most_common())
        print('START MIN MAX:',min(str(x.get('startTime')) for x in rows),max(str(x.get('startTime')) for x in rows))
        print('PUBLISH MIN MAX:',min(str(x.get('publishTime')) for x in rows),max(str(x.get('publishTime')) for x in rows))
        required=({'startTime','fuelType','generation'} if dataset=='FUELHH' else {'startTime','publishTime','generation'})
        assert required.issubset(rows[0]),'Unexpected schema'

asyncio.run(main())
