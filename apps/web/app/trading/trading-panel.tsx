"use client";

import { useEffect, useState } from "react";
import { fetchJson } from "../../lib/api";

type Ready={status:string;execution_mode:string;live_trading_enabled:boolean;checks:Record<string,string>};
type Snapshot={asset:string;latest_close:string;regime:{regime:string;confidence:string};strategy_votes:{strategy_id:string;direction:string|null;confidence:string;reasons:string[]}[];consensus:{direction:string;confidence:string};mtf:{direction:string;confidence:string;alignment:string};smc:{bias:string;reasons:string[]};crt:{direction:string;reasons:string[]}};
const pct=(v:string)=>(Number(v)*100).toFixed(1)+"%";

export default function TradingPanel(){
 const [ready,setReady]=useState<Ready|null>(null); const [snapshot,setSnapshot]=useState<Snapshot|null>(null); const [error,setError]=useState<string|null>(null);
 useEffect(()=>{void Promise.all([fetchJson<Ready>("/api/v1/operations/readiness"),fetchJson<Snapshot>("/api/v1/intelligence/snapshot?asset=BTC%2FUSD&venue=spot&timeframe=1h",{timeoutMs:30000})]).then(([r,s])=>{setReady(r);setSnapshot(s);}).catch(e=>setError(e instanceof Error?e.message:"Trading context unavailable"));},[]);
 if(error)return <section className="card panel"><div className="quote-error">{error}</div></section>;
 if(!ready||!snapshot)return <section className="card panel"><div className="metric">Loading…</div><p className="subtle">Loading verified trading context.</p></section>;
 return <div className="stack">
  <section className="grid"><div className="card"><div className="eyebrow">Execution mode</div><div className="metric">{ready.execution_mode.toUpperCase()}</div><p className="subtle">Live trading {ready.live_trading_enabled?"enabled":"disabled"}</p></div><div className="card"><div className="eyebrow">Human gate</div><div className="metric">REQUIRED</div><p className="subtle">Approval must be durable and auditable.</p></div><div className="card"><div className="eyebrow">Execution authority</div><div className="metric">NONE</div><p className="subtle">This browser surface cannot submit an order.</p></div></section>
  <section className="card panel"><div className="eyebrow">Proposal preview</div><h2>{snapshot.asset}</h2><p className="subtle">This is current intelligence context only. No TradeProposal is persisted and no execution token is created by the dashboard.</p><div className="data-grid"><div className="data-cell"><span>Latest close</span><strong>{snapshot.latest_close}</strong></div><div className="data-cell"><span>Consensus</span><strong>{snapshot.consensus.direction}</strong><small>{pct(snapshot.consensus.confidence)} confidence</small></div><div className="data-cell"><span>MTF</span><strong>{snapshot.mtf.direction}</strong><small>{pct(snapshot.mtf.alignment)} alignment</small></div><div className="data-cell"><span>Regime</span><strong>{snapshot.regime.regime}</strong><small>{pct(snapshot.regime.confidence)} confidence</small></div></div></section>
  <section className="grid"><div className="card"><h2>Strategy evidence</h2>{snapshot.strategy_votes.map(v=><div className="evidence" key={v.strategy_id}><strong>{v.strategy_id}: {v.direction??"NEUTRAL"}</strong><span>{pct(v.confidence)} confidence</span><small>{v.reasons.join(" · ")}</small></div>)}</div><div className="card"><h2>Execution boundary</h2><div className="status"><span className="dot"/>Risk assessment must pass</div><div className="status"><span className="dot"/>Human approval must be durable</div><div className="status"><span className="dot"/>Pre-execution revalidation required</div><div className="status"><span className="dot"/>Execution gateway alone may submit</div></div></section>
  <section className="card panel"><h2>Current state</h2><div className="status"><span className="dot"/>Proposal preview only — NOT AUTHORIZED</div><p className="subtle">Use the Risk workspace to evaluate explicit scenario inputs. Approval and order submission are intentionally not exposed by this unauthenticated read-only UI.</p></section>
 </div>;
}
