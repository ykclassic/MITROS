"use client";

import { useEffect, useState } from "react";
import { fetchJson } from "../../lib/api";

type Snapshot = {
  asset:string; timeframe:string; candle_count:number; latest_close:string; feature_set_version:string;
  features:Record<string,string>;
  regime:{regime:string;confidence:string;trend_strength:string;volatility:string;sample_size:number;reasons:string[]};
  statistics:{sample_size:number;mean_return:string;volatility:string;win_rate:string;downside_deviation:string;z_score:string;reasons:string[]};
  smc:{bias:string;structure_events:unknown[];liquidity_sweeps:unknown[];fair_value_gaps:unknown[];order_blocks:unknown[];reasons:string[]};
  crt:{direction:string;sweep?:unknown;reasons:string[]};
  strategy_votes:{strategy_id:string;direction:string|null;confidence:string;reasons:string[]}[];
  consensus:{direction:string;confidence:string;strategy_count:number;aligned_strategy_count:number;reasons:string[]};
  mtf:{direction:string;confidence:string;alignment:string;timeframes:{timeframe:string;direction:string;confidence:string}[]};
};

const pct=(value:string)=>(Number(value)*100).toFixed(2)+"%";

export default function IntelligencePanel(){
  const [data,setData]=useState<Snapshot|null>(null);
  const [error,setError]=useState<string|null>(null);
  useEffect(()=>{void fetchJson<Snapshot>("/api/v1/intelligence/snapshot?asset=BTC%2FUSD&venue=spot&timeframe=1h",{timeoutMs:30000}).then(setData).catch(e=>setError(e instanceof Error?e.message:"Intelligence unavailable"));},[]);
  if(error) return <section className="card panel"><div className="quote-error">{error}</div><p className="subtle">The page is fail-closed when verified candles or provider routing are unavailable.</p></section>;
  if(!data) return <section className="card panel"><div className="metric">Loading…</div><p className="subtle">Computing intelligence from verified provider candles.</p></section>;
  return <div className="stack">
    <section className="grid">
      <div className="card"><div className="eyebrow">Latest close</div><div className="metric">{data.latest_close}</div><p className="subtle">{data.asset} · {data.timeframe} · {data.candle_count} candles</p></div>
      <div className="card"><div className="eyebrow">Regime</div><div className="metric">{data.regime.regime}</div><p className="subtle">Confidence {pct(data.regime.confidence)} · volatility {data.regime.volatility}</p></div>
      <div className="card"><div className="eyebrow">Consensus</div><div className="metric">{data.consensus.direction}</div><p className="subtle">Confidence {pct(data.consensus.confidence)} · {data.consensus.aligned_strategy_count}/{data.consensus.strategy_count} aligned</p></div>
      <div className="card"><div className="eyebrow">MTF</div><div className="metric">{data.mtf.direction}</div><p className="subtle">Alignment {pct(data.mtf.alignment)} · confidence {pct(data.mtf.confidence)}</p></div>
    </section>
    <section className="card panel"><h2>Feature snapshot</h2><p className="subtle">Version {data.feature_set_version}; deterministic feature engine.</p>
      <div className="data-grid">{Object.entries(data.features).map(([name,value])=><div className="data-cell" key={name}><span>{name}</span><strong>{value}</strong></div>)}</div>
    </section>
    <section className="grid">
      <div className="card"><h2>Market regime</h2><p className="metric-sm">{data.regime.regime}</p><p className="subtle">{data.regime.reasons.join(" · ")}</p></div>
      <div className="card"><h2>Statistics</h2><div className="data-list"><span>Mean return <strong>{data.statistics.mean_return}</strong></span><span>Volatility <strong>{data.statistics.volatility}</strong></span><span>Win rate <strong>{pct(data.statistics.win_rate)}</strong></span><span>Z-score <strong>{data.statistics.z_score}</strong></span></div></div>
      <div className="card"><h2>SMC</h2><p className="metric-sm">{data.smc.bias}</p><p className="subtle">Structure {data.smc.structure_events.length} · sweeps {data.smc.liquidity_sweeps.length} · FVG {data.smc.fair_value_gaps.length} · OB {data.smc.order_blocks.length}</p></div>
      <div className="card"><h2>CRT</h2><p className="metric-sm">{data.crt.direction}</p><p className="subtle">{data.crt.sweep ? "Confirmed sweep and reclaim" : "No confirmed sweep and reclaim"}</p></div>
    </section>
    <section className="card panel"><h2>Multi-timeframe state</h2><div className="data-grid">{data.mtf.timeframes.map(tf=><div className="data-cell" key={tf.timeframe}><span>{tf.timeframe}</span><strong>{tf.direction}</strong><small>{pct(tf.confidence)} confidence</small></div>)}</div></section>
  </div>;
}
