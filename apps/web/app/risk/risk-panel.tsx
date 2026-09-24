"use client";

import { useState } from "react";
import { fetchJson } from "../../lib/api";

type Assessment={approved:boolean;requested_size:string;approved_size:string;checks:string[];reasons:string[];risk_score:string};

const initial={equity:"10000",daily_pnl:"0",peak_equity:"10000",existing_exposure:"0",requested_size:"100",stop_distance_fraction:"0.01",spread_fraction:"0.001",correlated_exposure:"0",max_position_fraction:"0.02",max_gross_exposure:"1",max_daily_loss_fraction:"0.03",max_drawdown_fraction:"0.10",max_concentration_fraction:"0.25",max_leverage:"2",max_spread_fraction:"0.005",max_risk_fraction:"0.01",max_correlation_exposure:"0.50",asset:"BTC/USD"};

export default function RiskPanel(){
 const [form,setForm]=useState(initial); const [data,setData]=useState<Assessment|null>(null); const [loading,setLoading]=useState(false); const [error,setError]=useState<string|null>(null);
 const set=(key:string,value:string)=>setForm(current=>({...current,[key]:value}));
 async function assess(){setLoading(true);setError(null);try{const params=new URLSearchParams(form);setData(await fetchJson<Assessment>("/api/v1/risk/assessment?"+params.toString()));}catch(e){setError(e instanceof Error?e.message:"Risk assessment unavailable");}finally{setLoading(false);}}
 return <div className="stack">
  <section className="card panel"><div className="eyebrow">Scenario simulator</div><h2>Independent risk assessment</h2><p className="subtle">Inputs below are an explicit scenario, not production account state. MITROS does not invent or silently apply production risk limits.</p>
   <div className="form-grid">{["equity","daily_pnl","peak_equity","existing_exposure","requested_size","stop_distance_fraction","spread_fraction","correlated_exposure","max_position_fraction","max_gross_exposure","max_daily_loss_fraction","max_drawdown_fraction","max_concentration_fraction","max_leverage","max_spread_fraction","max_risk_fraction","max_correlation_exposure"].map(key=><label key={key}>{key}<input type="number" step="any" value={form[key as keyof typeof form]} onChange={e=>set(key,e.target.value)}/></label>)}<label>asset<select value={form.asset} onChange={e=>set("asset",e.target.value)}><option>BTC/USD</option><option>ETH/USD</option></select></label></div>
   <button className="secondary-button" type="button" onClick={()=>void assess()} disabled={loading}>{loading?"Assessing…":"Run risk assessment"}</button>{error&&<p className="quote-error">{error}</p>}
  </section>
  {data&&<section className="grid"><div className="card"><div className="eyebrow">Decision</div><div className="metric">{data.approved?"APPROVED":"REJECTED"}</div><p className="subtle">This assessment grants no execution authority.</p></div><div className="card"><div className="eyebrow">Approved size</div><div className="metric">{data.approved_size}</div><p className="subtle">Requested {data.requested_size}</p></div><div className="card"><div className="eyebrow">Risk score</div><div className="metric">{data.risk_score}</div></div><div className="card"><h2>Reasons</h2>{data.reasons.map(reason=><div className="status" key={reason}>{reason}</div>)}</div></section>}
 </div>;
}
