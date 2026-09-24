"use client";

import { useEffect, useState } from "react";
import { fetchJson } from "../../lib/api";

type Snapshot={smc:{bias:string;reasons:string[];structure_events:unknown[];liquidity_sweeps:unknown[];fair_value_gaps:unknown[];order_blocks:unknown[]};crt:{direction:string;reasons:string[];sweep?:unknown};strategy_votes:{strategy_id:string;strategy_version?:string;direction:string|null;confidence:string;reasons:string[]}[];consensus:{direction:string;confidence:string;aligned_strategy_count:number;strategy_count:number};mtf:{direction:string;confidence:string;alignment:string;timeframes:{timeframe:string;direction:string;confidence:string}[]}};
const pct=(value:string)=>(Number(value)*100).toFixed(1)+"%";

export default function StrategiesPanel(){
 const [data,setData]=useState<Snapshot|null>(null); const [error,setError]=useState<string|null>(null);
 useEffect(()=>{void fetchJson<Snapshot>("/api/v1/intelligence/snapshot?asset=BTC%2FUSD&venue=spot&timeframe=1h",{timeoutMs:30000}).then(setData).catch(e=>setError(e instanceof Error?e.message:"Strategy intelligence unavailable"));},[]);
 if(error)return <section className="card panel"><div className="quote-error">{error}</div></section>;
 if(!data)return <section className="card panel"><div className="metric">Loading…</div><p className="subtle">Evaluating strategies against verified candles.</p></section>;
 return <div className="stack">
  <section className="grid">
   <div className="card"><div className="eyebrow">Consensus</div><div className="metric">{data.consensus.direction}</div><p className="subtle">{pct(data.consensus.confidence)} confidence · {data.consensus.aligned_strategy_count}/{data.consensus.strategy_count} aligned</p></div>
   <div className="card"><div className="eyebrow">MTF consensus</div><div className="metric">{data.mtf.direction}</div><p className="subtle">Alignment {pct(data.mtf.alignment)}</p></div>
   <div className="card"><div className="eyebrow">SMC</div><div className="metric">{data.smc.bias}</div><p className="subtle">Structure {data.smc.structure_events.length} · FVG {data.smc.fair_value_gaps.length}</p></div>
   <div className="card"><div className="eyebrow">CRT</div><div className="metric">{data.crt.direction}</div><p className="subtle">{data.crt.sweep ? "Sweep confirmed" : "No sweep confirmed"}</p></div>
  </section>
  <section className="card panel"><h2>Strategy votes</h2><div className="data-grid">{data.strategy_votes.map(v=><div className="data-cell" key={v.strategy_id}><span>{v.strategy_id}</span><strong>{v.direction ?? "NEUTRAL"}</strong><small>{pct(v.confidence)} confidence</small></div>)}</div></section>
  <section className="grid"><div className="card"><h2>SMC evidence</h2><p className="subtle">{data.smc.reasons.join(" · ")}</p></div><div className="card"><h2>CRT evidence</h2><p className="subtle">{data.crt.reasons.join(" · ")}</p></div></section>
  <section className="card panel"><h2>Timeframes</h2><div className="data-grid">{data.mtf.timeframes.map(tf=><div className="data-cell" key={tf.timeframe}><span>{tf.timeframe}</span><strong>{tf.direction}</strong><small>{pct(tf.confidence)}</small></div>)}</div></section>
 </div>;
}
