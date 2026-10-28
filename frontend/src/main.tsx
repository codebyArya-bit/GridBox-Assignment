import React, {useState, useEffect} from 'react';
import {createRoot} from 'react-dom/client';
import {BarChart, Bar, CartesianGrid, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer,
        LineChart, Line, ReferenceLine} from 'recharts';
import './style.css';

type Point={startTime:string;forecastMW:number|null;actualMW:number|null;actualHalfHoursMW:(number|null)[];actualHalfHourSamples:number;errorMW:number|null;publishedAt:string|null};
type Analysis={decisionDate:string;deliveryDate:string;decisionCutoff:string;cutoffTimeUK:string;cutoffReference:string;resolution:string;aggregationMethod:string;expectedIntervals:number;forecastIntervals:number;actualIntervals:number;matchedIntervals:number;expectedHalfHourIntervals:number;observedHalfHourIntervals:number;maeMW:number|null;rmseMW:number|null;biasMW:number|null;series:Point[];dataSource:string};
type MonthDay={decisionDate:string;deliveryDate:string;forecastIntervals:number;actualIntervals:number;matchedIntervals:number;expectedIntervals:number;maeMW:number;rmseMW:number;biasMW:number;maxAbsErrorMW:number};
type Month={period:string;daysCount:number;cutoffTimeUK:string;cutoffReference:string;methodology:string;aggregate:{matchedHours:number;expectedHours:number;observedHalfHours:number;maeMW:number;rmseMW:number;biasMW:number;bestDay:string;worstDay:string};days:MonthDay[];errorDistribution:{band:string;count:number}[]};
const API=import.meta.env.VITE_API_URL || '';
const fmt=(n:number|null|undefined)=>n==null?'—':n.toLocaleString('en-GB',{maximumFractionDigits:2});
const local=(s:string)=>new Date(s).toLocaleString('en-GB',{timeZone:'Europe/London',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
const hhmm=(s:string)=>new Date(s).toLocaleTimeString('en-GB',{timeZone:'Europe/London',hour:'2-digit',minute:'2-digit'});
const labelDay=(s:string)=>new Date(s+'T12:00:00Z').toLocaleDateString('en-GB',{month:'short',day:'numeric',timeZone:'UTC'});
const readError=async(r:Response)=>{if(r.ok)return r.json();let detail='';try{detail=(await r.json()).detail||''}catch{}throw new Error(`HTTP ${r.status}${detail?`: ${detail}`:''}`)};
const isN2EX=(time:string)=>time==='09:50';
function Metric({label,value,unit,description}:{label:string;value:number|string|null|undefined;unit?:string;description?:string}){
  return <div className="card"><span>{label}</span><b>{typeof value==='number'?fmt(value):value??'—'}{unit&&<small> {unit}</small>}</b><em>{description}</em></div>;
}
function App(){
 const [tab,setTab]=useState<'daily'|'month'>('daily');
 const [date,setDate]=useState('2026-01-15');
 const [cutoff,setCutoff]=useState('09:50');
 const [data,setData]=useState<Analysis|null>(null);
 const [error,setError]=useState('');
 const [loading,setLoading]=useState(true);
 const [month,setMonth]=useState<Month|null>(null);
 const [monthError,setMonthError]=useState('');
 const [monthLoading,setMonthLoading]=useState(false);
 const [monthRefresh,setMonthRefresh]=useState(0);
 const [mobile,setMobile]=useState(()=>window.matchMedia('(max-width: 700px)').matches);
 useEffect(()=>{const mq=window.matchMedia('(max-width: 700px)');const update=()=>setMobile(mq.matches);mq.addEventListener('change',update);return()=>mq.removeEventListener('change',update)},[]);
 useEffect(()=>{
   if(tab!=='daily')return;
   const ctl=new AbortController();setLoading(true);setError('');setData(null);
   fetch(`${API}/api/analysis?decision_date=${date}&cutoff_time=${encodeURIComponent(cutoff)}`,{signal:ctl.signal})
     .then(readError).then((r:Analysis)=>setData(r))
     .catch(e=>{if(e.name!=='AbortError')setError(e.message)})
     .finally(()=>{if(!ctl.signal.aborted)setLoading(false)});
   return()=>ctl.abort();
 },[date,cutoff,tab]);
 useEffect(()=>{
   if(tab!=='month'||month)return;
   const ctl=new AbortController();setMonthLoading(true);setMonthError('');
   fetch(`${API}/api/monthly`,{signal:ctl.signal}).then(readError).then((r:Month)=>setMonth(r))
     .catch(e=>{if(e.name!=='AbortError')setMonthError(e.message)})
     .finally(()=>{if(!ctl.signal.aborted)setMonthLoading(false)});
   return()=>ctl.abort();
 },[tab,month,monthRefresh]);
 function selectDay(day:string){setDate(day);setTab('daily');window.scrollTo({top:0,behavior:'smooth'})}
 function exportCsv(){
   if(!month)return;
   const head='decisionDate,deliveryDate,maeMW,rmseMW,biasMW,matchedHours,forecastHours';
   const rows=month.days.map(d=>[d.decisionDate,d.deliveryDate,d.maeMW,d.rmseMW,d.biasMW,d.matchedIntervals,d.forecastIntervals].join(','));
   const blob=new Blob([[head,...rows].join('\n')+'\n'],{type:'text/csv;charset=utf-8'});
   const url=URL.createObjectURL(blob);const anchor=document.createElement('a');anchor.href=url;anchor.download='gridbox-january-2026-hourly-accuracy.csv';anchor.click();URL.revokeObjectURL(url);
 }
 const points=(data?.series||[]).map(p=>({...p,time:hhmm(p.startTime)}));
 const monthPoints=(month?.days||[]).map(d=>({...d,day:labelDay(d.decisionDate)}));
 return <div className="shell">
   <aside aria-label="Primary navigation"><div className="brand"><span className="mark" aria-hidden="true">◈</span> GRIDBOX<small>ENERGY INTELLIGENCE</small></div>
     <nav aria-label="Dashboard sections"><button className={tab==='daily'?'active':''} onClick={()=>setTab('daily')}>▦ &nbsp; Daily decision</button><button className={tab==='month'?'active':''} onClick={()=>setTab('month')}>⌁ &nbsp; January analysis</button><a href="#methodology">▤ &nbsp; Methodology</a></nav>
     <div className="sidefoot">SOURCE OF TRUTH<strong>Elexon BMRS</strong><p>FUELHH + WINDFOR<br/>January 2026 decisions</p></div>
   </aside>
   <main id="overview">
     <header><div><div className="eyebrow">UK ENERGY MARKETS / DAY-AHEAD WIND PLANNING</div><h1>Wind Generation Intelligence</h1><p>Know the wind forecast available before procurement—and how accurately it performed.</p></div><div className="status"><i aria-hidden="true"/> HISTORICAL ELEXON DATA</div></header>
     <div className="mobiletabs" aria-label="Analysis view"><button aria-pressed={tab==='daily'} onClick={()=>setTab('daily')} className={tab==='daily'?'active':''}>Daily decision</button><button aria-pressed={tab==='month'} onClick={()=>setTab('month')} className={tab==='month'?'active':''}>January trends</button></div>
     {tab==='daily'?<>
       <section className="controls" aria-label="Purchasing scenario controls">
         <label htmlFor="decision-date">PURCHASING DECISION DATE<input id="decision-date" type="date" value={date} min="2026-01-01" max="2026-01-31" onChange={e=>setDate(e.target.value)}/></label>
         <label htmlFor="cutoff">UK PURCHASING CUTOFF (HH:MM)<input id="cutoff" type="time" step={60} value={cutoff} onChange={e=>setCutoff(e.target.value)} aria-describedby="cutoff-explanation"/></label>
         <div className="scope" id="cutoff-explanation">{isN2EX(cutoff)?<><strong>N2EX day-ahead auction reference</strong><br/>09:50 GMT gate closure, January 2026</>:<><strong>Custom hypothetical cutoff</strong><br/>Not necessarily an auction deadline</>}</div>
         {!isN2EX(cutoff)&&<button className="reset" onClick={()=>setCutoff('09:50')}>Reset N2EX 09:50</button>}
       </section>
       {loading&&<div className="notice" role="status">Loading historical Elexon data and hourly wind forecasts…</div>}
       {error&&<div className="notice danger" role="alert"><strong>Elexon analysis unavailable.</strong> {error}. No substitute data is shown.</div>}
       {data&&<>
         <section className="metrics" aria-label="Hourly forecast accuracy statistics">
           <Metric label="MEAN ABSOLUTE ERROR" value={data.maeMW} unit="MW" description="Average hourly forecast miss"/>
           <Metric label="ROOT MEAN SQUARED ERROR" value={data.rmseMW} unit="MW" description="Larger deviations count more"/>
           <Metric label="SIGNED FORECAST BIAS" value={data.biasMW} unit="MW" description="Positive means over-forecast"/>
           <Metric label="MATCHED HOURS" value={`${data.matchedIntervals} / ${data.expectedIntervals}`} description={`${data.forecastIntervals}/24 forecast • ${data.observedHalfHourIntervals}/48 actual half-hours`}/>
         </section>
         <section className="panel"><div className="panelhead"><div><div className="eyebrow">01 / HOURLY GENERATION</div><h2>Forecast versus actual wind generation</h2><p>WINDFOR hourly MW vs mean of two FUELHH half-hourly readings</p></div><span className="pill">Delivery {data.deliveryDate}</span></div>
           <div className="chart" role="img" aria-label="Hourly forecast wind generation and actual hourly-mean wind generation line chart">
             <ResponsiveContainer width="100%" height="100%"><LineChart data={points} margin={{top:10,right:12,bottom:4,left:mobile?-22:0}}><CartesianGrid stroke="#e1e9ed" vertical={false}/><XAxis dataKey="time" interval={mobile?5:2} tick={{fontSize:11,fill:'#52616c'}}/><YAxis tick={{fontSize:11,fill:'#52616c'}}/><Tooltip formatter={(v)=>`${fmt(Number(v))} MW`}/><Legend/><Line type="monotone" dataKey="forecastMW" name="Forecast MW" stroke="#067f65" strokeWidth={2.5} dot={false} connectNulls={false}/><Line type="monotone" dataKey="actualMW" name="Hourly-mean actual MW" stroke="#4060ab" strokeWidth={2.5} dot={false} connectNulls={false}/></LineChart></ResponsiveContainer>
           </div>
         </section>
         <div className="twocol"><section id="accuracy" className="panel"><div className="eyebrow">02 / FORECAST ACCURACY</div><h2>Hourly signed forecast error</h2><p>Forecast minus actual hourly mean (MW)</p>
           <div className="chart short" role="img" aria-label="Signed hourly forecast error bar chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={points} margin={{top:10,right:7,bottom:0,left:mobile?-22:0}}><CartesianGrid stroke="#e1e9ed" vertical={false}/><XAxis dataKey="time" interval={mobile?5:3} tick={{fontSize:10,fill:'#52616c'}}/><YAxis tick={{fontSize:10,fill:'#52616c'}}/><Tooltip formatter={(v)=>`${fmt(Number(v))} MW`}/><ReferenceLine y={0} stroke="#647785"/><Bar dataKey="errorMW" name="Signed error MW" fill="#377f9f"/></BarChart></ResponsiveContainer></div>
           </section><section id="methodology" className="panel"><div className="eyebrow">03 / POINT-IN-TIME AUDIT</div><h2>What was knowable?</h2><p>Forecast revisions published after cutoff are excluded.</p>
             <div className="detail"><span>Decision cutoff</span><strong>{local(data.decisionCutoff)} UK</strong></div>
             <div className="detail"><span>Delivery date</span><strong>{data.deliveryDate}</strong></div>
             <div className="detail"><span>Hourly forecast availability</span><strong>{data.forecastIntervals} / 24</strong></div>
             <div className="detail"><span>Half-hour actual observations</span><strong>{data.observedHalfHourIntervals} / 48</strong></div>
             <div className="detail"><span>Paired hourly comparisons</span><strong>{data.matchedIntervals} / 24</strong></div>
             <div className="explain"><strong>Hourly alignment:</strong> Each WINDFOR hourly MW value is compared against the arithmetic mean of two FUELHH WIND readings at HH:00 and HH:30. Both must exist; missing values are never filled in. This is an explicit aggregation assumption for this pilot—not an assertion about hourly energy procurement.</div>
           </section></div>
         <section id="intervals" className="panel"><div className="eyebrow">04 / SOURCE AUDIT TRAIL</div><h2>24 hourly forecast and outturn pairs</h2><p>Historical UTC timestamps, raw half-hourly readings, aggregated actuals and forecast publication time</p><p className="mobilehint">Swipe the table sideways to see all columns.</p>
           <div className="tablewrap" role="region" aria-label="Hourly wind generation evidence table" tabIndex={0}><table><thead><tr><th scope="col">TARGET UTC</th><th scope="col">FORECAST MW</th><th scope="col">ACTUAL HH:00</th><th scope="col">ACTUAL HH:30</th><th scope="col">HOURLY MEAN MW</th><th scope="col">ERROR MW</th><th scope="col">PUBLISHED UTC</th></tr></thead><tbody>{data.series.map(r=><tr key={r.startTime}><td>{r.startTime}</td><td>{fmt(r.forecastMW)}</td><td>{fmt(r.actualHalfHoursMW?.[0])}</td><td>{fmt(r.actualHalfHoursMW?.[1])}</td><td>{fmt(r.actualMW)}</td><td>{fmt(r.errorMW)}</td><td>{r.publishedAt||'—'}</td></tr>)}</tbody></table></div>
         </section>
       </>}
     </>:<>
       <section className="panel paneltop"><div className="panelhead"><div><div className="eyebrow">MONTHLY / PROCUREMENT DECISIONS</div><h2>January 2026 — forecast reliability</h2><p>All 31 decision dates, evaluated at the N2EX reference time of 09:50 GMT</p></div>{month&&<button className="actionbutton" onClick={exportCsv}>Export daily metrics CSV</button>}</div></section>
       {monthLoading&&<div className="notice" role="status">Loading verified January historical summary…</div>}
       {monthError&&<div className="notice danger" role="alert"><strong>January summary unavailable.</strong> {monthError}. <button className="retry" onClick={()=>{setMonth(null);setMonthRefresh(n=>n+1)}}>Try again</button></div>}
       {month&&<>
         <section className="metrics" aria-label="January accuracy statistics"><Metric label="JANUARY MAE" value={month.aggregate.maeMW} unit="MW" description="Across all matched hourly pairs"/><Metric label="JANUARY RMSE" value={month.aggregate.rmseMW} unit="MW" description="Weighted across all intervals"/><Metric label="JANUARY BIAS" value={month.aggregate.biasMW} unit="MW" description="Positive is over-forecast"/><Metric label="MATCHED HOURS" value={`${month.aggregate.matchedHours} / ${month.aggregate.expectedHours}`} description={`${month.daysCount} January purchasing decisions`}/></section>
         <section className="panel"><div className="panelhead"><div><div className="eyebrow">01 / RELIABILITY ACROSS THE MONTH</div><h2>Day-by-day forecast error</h2><p>Daily MAE and RMSE in MW; the chart shows how reliability changes with the day</p></div><span className="pill">31 decisions</span></div>
           <div className="chart" role="img" aria-label="January 31 day mean absolute error and root mean squared error line chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={monthPoints} margin={{top:12,right:10,bottom:8,left:mobile?-20:0}}><CartesianGrid stroke="#e1e9ed" vertical={false}/><XAxis dataKey="day" interval={mobile?5:3} tick={{fontSize:10,fill:'#52616c'}}/><YAxis tick={{fontSize:10,fill:'#52616c'}}/><Tooltip formatter={(v)=>`${fmt(Number(v))} MW`}/><Legend/><Line type="monotone" dataKey="maeMW" name="MAE MW" stroke="#087f64" dot={false} strokeWidth={2.5}/><Line type="monotone" dataKey="rmseMW" name="RMSE MW" stroke="#405cab" dot={false} strokeWidth={2.5}/></LineChart></ResponsiveContainer></div>
         </section>
         <div className="twocol"><section className="panel"><div className="eyebrow">02 / BIAS</div><h2>Over- and under-forecast by day</h2><p>Positive = forecast above actual; negative = below (MW)</p><div className="chart short" role="img" aria-label="January forecast bias bar chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={monthPoints} margin={{top:10,right:0,bottom:0,left:mobile?-20:0}}><CartesianGrid vertical={false} stroke="#e1e9ed"/><XAxis dataKey="day" interval={mobile?8:5} tick={{fontSize:10,fill:'#52616c'}}/><YAxis tick={{fontSize:10,fill:'#52616c'}}/><Tooltip formatter={(v)=>`${fmt(Number(v))} MW`}/><ReferenceLine y={0} stroke="#647785"/><Bar dataKey="biasMW" name="Bias MW" fill="#377f9f"/></BarChart></ResponsiveContainer></div></section>
         <section className="panel"><div className="eyebrow">03 / ERROR FREQUENCY</div><h2>Distribution of hourly errors</h2><p>Number of matched hour readings in signed error bands (MW)</p><div className="chart short" role="img" aria-label="Distribution of January hourly forecast errors"><ResponsiveContainer width="100%" height="100%"><BarChart data={month.errorDistribution} layout="vertical" margin={{top:8,right:5,bottom:0,left:mobile?4:15}}><CartesianGrid horizontal={false} stroke="#e1e9ed"/><XAxis type="number" tick={{fontSize:10,fill:'#52616c'}}/><YAxis type="category" dataKey="band" width={mobile?98:120} tick={{fontSize:mobile?8:10,fill:'#52616c'}}/><Tooltip/><Bar dataKey="count" name="Hourly pairs" fill="#087f64"/></BarChart></ResponsiveContainer></div></section></div>
         <section className="panel"><div className="panelhead"><div><div className="eyebrow">04 / AUDITABLE DAILY METRICS</div><h2>Explore all 31 purchasing decisions</h2><p>Select any day to inspect the exact forecasts and publication times</p></div><span className="pill">09:50 UK</span></div>
           <p className="mobilehint">Swipe the table sideways to see all columns.</p><div className="tablewrap" role="region" aria-label="January daily accuracy table" tabIndex={0}><table><thead><tr><th scope="col">DECISION DATE</th><th scope="col">MAE MW</th><th scope="col">RMSE MW</th><th scope="col">BIAS MW</th><th scope="col">MATCHED / 24</th><th scope="col">DETAIL</th></tr></thead><tbody>{month.days.map(d=><tr key={d.decisionDate}><td>{d.decisionDate}</td><td>{fmt(d.maeMW)}</td><td>{fmt(d.rmseMW)}</td><td>{fmt(d.biasMW)}</td><td>{d.matchedIntervals} / 24</td><td><button className="tablelink" onClick={()=>{setCutoff('09:50');selectDay(d.decisionDate)}} aria-label={`Inspect ${d.decisionDate}`}>Inspect day</button></td></tr>)}</tbody></table></div>
         </section>
         <section id="methodology" className="panel"><div className="eyebrow">05 / METHODOLOGY</div><h2>What the monthly results mean</h2><p>This is a fixed historical snapshot for January purchasing dates at 09:50 GMT—not intraday or live forecasts.</p><div className="explain">{month.methodology} The cut-off references Nord Pool N2EX; other markets and auctions may use different deadlines. Data comes exclusively from Elexon BMRS FUELHH and WINDFOR. Actual demand and electricity procurement quantities are out of scope.</div></section>
       </>}
     </>}
     <footer>GRIDBOX / ELEXON BMRS / JANUARY 2026 HISTORICAL RESEARCH — NOT A POWER PURCHASE INSTRUCTION</footer>
   </main>
 </div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
