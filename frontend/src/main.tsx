import React,{useState,useEffect} from 'react';
import{createRoot}from'react-dom/client';
import{AreaChart,Area,CartesianGrid,XAxis,YAxis,Tooltip,Legend,ResponsiveContainer,BarChart,Bar,ReferenceLine}from'recharts';
import './style.css';

type Point={startTime:string;forecastMW:number|null;actualMW:number|null;errorMW:number|null;publishedAt:string|null};
type Analysis={decisionDate:string;deliveryDate:string;decisionCutoff:string;cutoffAssumption:string;expectedIntervals:number;forecastIntervals:number;actualIntervals:number;matchedIntervals:number;maeMW:number|null;rmseMW:number|null;biasMW:number|null;series:Point[];dataSource:string};
const API=import.meta.env.VITE_API_URL||'';
const pretty=(n:number|null|undefined)=>n==null?'—':n.toLocaleString('en-GB',{maximumFractionDigits:2});
const local=(iso:string)=>new Date(iso).toLocaleString('en-GB',{timeZone:'Europe/London',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
const hhmm=(iso:string)=>new Date(iso).toLocaleTimeString('en-GB',{timeZone:'Europe/London',hour:'2-digit',minute:'2-digit'});
function App(){
  const[date,setDate]=useState('2026-01-15');
  const[hour,setHour]=useState(11);
  const[data,setData]=useState<Analysis|null>(null);
  const[loading,setLoading]=useState(true);
  const[error,setError]=useState('');
  useEffect(()=>{
    const controller=new AbortController();
    setLoading(true);setError('');setData(null);
    fetch(`${API}/api/analysis?decision_date=${date}&cutoff_hour=${hour}`,{signal:controller.signal})
      .then(async response=>{if(!response.ok){let detail='';try{detail=(await response.json()).detail||''}catch{}throw Error(`Request failed (${response.status}). ${detail}`)}return response.json()})
      .then((result:Analysis)=>setData(result))
      .catch(e=>{if(e.name!=='AbortError')setError(e.message)})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false)});
    return()=>controller.abort();
  },[date,hour]);
  const points=(data?.series||[]).map(p=>({...p,time:hhmm(p.startTime)}));
  return <div className="shell">
    <aside><div className="brand"><span className="mark">◈</span> GRIDBOX<small>ENERGY INTELLIGENCE</small></div>
      <nav><a href="#overview" className="active">▦ &nbsp; Overview</a><a href="#accuracy">⌁ &nbsp; Forecast accuracy</a><a href="#intervals">▤ &nbsp; Interval evidence</a></nav>
      <div className="sidefoot">SOURCE OF TRUTH<strong>Elexon BMRS</strong><p>FUELHH + WINDFOR<br/>January 2026 decisions</p></div>
    </aside>
    <main id="overview">
      <header><div><div className="eyebrow">UK ENERGY MARKETS / RESEARCH PILOT</div><h1>Wind Generation Intelligence</h1><p>Reconstruct what procurement teams knew when the day-ahead decision was made.</p></div><div className="status"><i/> ELEXON HISTORICAL DATA</div></header>
      <section className="controls">
        <label htmlFor="decision-date">PURCHASING DECISION DATE<input id="decision-date" type="date" value={date} min="2026-01-01" max="2026-01-31" onChange={e=>setDate(e.target.value)}/></label>
        <label htmlFor="cutoff">ASSUMED UK DECISION CUTOFF<select id="cutoff" value={hour} onChange={e=>setHour(Number(e.target.value))}>{[8,9,10,11,12,13,14,15,16,17].map(h=><option value={h} key={h}>{String(h).padStart(2,'0')}:00 on decision day</option>)}</select></label>
        <div className="scope">Half-hourly national wind generation<br/><strong>Latest eligible forecast as-of cutoff</strong></div>
      </section>
      {loading&&<div className="notice" role="status">Loading historic forecast revisions and metered wind generation from Elexon…</div>}
      {error&&<div className="notice danger" role="alert"><strong>Live source unavailable.</strong> {error} We do not invent or substitute production values.</div>}
      {data&&<>
        <section className="metrics">
          <div className="card"><span>MEAN ABSOLUTE ERROR</span><b>{pretty(data.maeMW)} <small>MW</small></b><em>Average magnitude of error</em></div>
          <div className="card"><span>ROOT MEAN SQUARED ERROR</span><b>{pretty(data.rmseMW)} <small>MW</small></b><em>Large misses count more</em></div>
          <div className="card"><span>FORECAST BIAS</span><b>{pretty(data.biasMW)} <small>MW</small></b><em>Positive means over-forecast</em></div>
          <div className="card"><span>MATCHED INTERVALS</span><b>{data.matchedIntervals} <small>/ {data.expectedIntervals}</small></b><em>{data.forecastIntervals} forecast / {data.actualIntervals} actual</em></div>
        </section>
        <section className="panel"><div className="panelhead"><div><div className="eyebrow">01 / WIND GENERATION</div><h2>Forecast versus actual generation</h2><p>Half-hourly British wind generation in megawatts</p></div><span className="pill">Delivery {data.deliveryDate}</span></div>
          <div className="chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={points}><defs><linearGradient id="fade" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#24b891" stopOpacity={0.18}/><stop offset="100%" stopColor="#24b891" stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke="#e9eef0" vertical={false}/><XAxis dataKey="time" interval={5} tick={{fontSize:11}}/><YAxis tick={{fontSize:11}}/><Tooltip/><Legend/><Area dataKey="forecastMW" name="Forecast MW" stroke="#10a98a" fill="url(#fade)" strokeWidth={2} connectNulls={false}/><Area dataKey="actualMW" name="Actual MW" stroke="#526eb2" fill="transparent" strokeWidth={2} connectNulls={false}/></AreaChart></ResponsiveContainer></div>
        </section>
        <div className="twocol">
          <section id="accuracy" className="panel"><div className="eyebrow">02 / QUANTIFIED ACCURACY</div><h2>Interval error</h2><p>Forecast minus actual (MW)</p>
          <div className="chart short"><ResponsiveContainer width="100%" height="100%"><BarChart data={points}><CartesianGrid stroke="#e9eef0" vertical={false}/><XAxis dataKey="time" interval={7} tick={{fontSize:10}}/><YAxis tick={{fontSize:10}}/><Tooltip/><ReferenceLine y={0} stroke="#81949f"/><Bar dataKey="errorMW" name="Signed error MW" fill="#468eb5"/></BarChart></ResponsiveContainer></div>
          </section>
          <section className="panel"><div className="eyebrow">03 / AS-OF DECISION</div><h2>What was knowable?</h2><p>Forecast revisions after the selected decision time are excluded.</p>
          <div className="detail"><span>Decision cutoff</span><strong>{local(data.decisionCutoff)} UK</strong></div>
          <div className="detail"><span>Delivery date</span><strong>{data.deliveryDate}</strong></div>
          <div className="detail"><span>Available forecasts</span><strong>{data.forecastIntervals} / {data.expectedIntervals}</strong></div>
          <div className="detail"><span>Matched with actuals</span><strong>{data.matchedIntervals} / {data.expectedIntervals}</strong></div>
          <div className="explain">The cutoff is an illustrative purchasing-time assumption, not a verified market gate. Missing intervals are excluded from accuracy calculations. Without demand data, procurement volumes cannot be inferred.</div>
          </section>
        </div>
        <section id="intervals" className="panel"><div className="eyebrow">04 / FULL AUDIT TRAIL</div><h2>Half-hourly evidence</h2><p>Exact UTC timestamps and forecast publication times for review</p>
          <div className="tablewrap"><table><thead><tr><th>TARGET UTC</th><th>FORECAST MW</th><th>ACTUAL MW</th><th>ERROR MW</th><th>PUBLISHED UTC</th></tr></thead>
          <tbody>{data.series.map(r=><tr key={r.startTime}><td>{r.startTime}</td><td>{pretty(r.forecastMW)}</td><td>{pretty(r.actualMW)}</td><td>{pretty(r.errorMW)}</td><td>{r.publishedAt||'—'}</td></tr>)}</tbody></table></div>
        </section>
      </>}
      <footer>GRIDBOX / ELEXON BMRS DATA / HISTORICAL RESEARCH PILOT — NOT A POWER PURCHASE RECOMMENDATION</footer>
    </main>
  </div>
}
createRoot(document.getElementById('root')!).render(<App/>);
