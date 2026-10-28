from datetime import date,datetime,timezone
from app.core import decision_cutoff, delivery_day, intervals, evaluate

def test_purchasing_dates():
    assert delivery_day(date(2026,1,1))==date(2026,1,2)
    assert delivery_day(date(2026,1,31))==date(2026,2,1)

def test_local_cutoff_timezone():
    assert decision_cutoff(date(2026,1,15),11)==datetime(2026,1,15,11,tzinfo=timezone.utc)
    assert decision_cutoff(date(2026,7,15),11)==datetime(2026,7,15,10,tzinfo=timezone.utc)

def test_empty_day_shows_missing_intervals():
    result=evaluate([],[],date(2026,1,15))
    assert result['expectedIntervals']==len(result['series'])==48
    assert result['matchedIntervals']==0 and result['maeMW'] is None

def test_latest_publication_before_cutoff():
    start='2026-01-16T00:00:00Z'
    forecasts=[{'startTime':start,'publishTime':f'2026-01-15T{hour}:00:00Z','generation':power}
               for hour,power in [('09',100),('10',110),('12',1000)]]
    actual=[{'startTime':start,'fuelType':'WIND','generation':120}]
    data=evaluate(actual,forecasts,date(2026,1,15))
    assert data['matchedIntervals']==1
    assert data['series'][0]['forecastMW']==110
    assert data['maeMW']==10 and data['rmseMW']==10 and data['biasMW']==-10

def test_no_solar_or_nan_values():
    start='2026-01-16T00:00:00Z'
    a=[{'startTime':start,'fuelType':'SOLAR','generation':999},
       {'startTime':start,'fuelType':'WIND','generation':float('nan')}]
    f=[{'startTime':start,'publishTime':'2026-01-15T09:00:00Z','generation':100}]
    assert evaluate(a,f,date(2026,1,15))['matchedIntervals']==0

def test_daylight_saving_transitions():
    assert len(intervals(date(2026,3,29)))==46
    assert len(intervals(date(2026,10,25)))==50
