"use client";

import { useState } from "react";
import { fetchJson } from "../../lib/api";

type Report={query:{asset:string;venue:string;timeframe:string;start:string;end:string};artifacts:{id:string;artifact_type:string;name:string;version:string;checksum:string;created_at:string;metadata:Record<string,string>}[];metrics:{name:string;value:string;sample_size:number}[];findings:string[];generated_at:string};
type Answer={answer:string;grounded:boolean;evidence:{kind:string;title:string;checksum:string;excerpt:string}[];generated_at:string};

export default function ResearchPanel(){
 const [asset,setAsset]=useState("BTC/USD"); const [report,setReport]=useState<Report|null>(null); const [answer,setAnswer]=useState<Answer|null>(null); const [loading,setLoading]=useState(false); const [error,setError]=useState<string|null>(null);
 async function run(){setLoading(true);setError(null);try{const query="?asset="+encodeURIComponent(asset)+"&venue=spot&timeframe=1h";const [r,a]=await Promise.all([fetchJson<Report>("/api/v1/research/report"+query,{timeoutMs:30000}),fetchJson<Answer>("/api/v1/research/copilot"+query,{timeoutMs:30000})]);setReport(r);setAnswer(a);}catch(e){setError(e instanceof Error?e.message:"Research unavailable");}finally{setLoading(false);}}
 return <div className="stack">
  <section className="card panel"><div className="form-row"><label>Asset<select value={asset} onChange={e=>setAsset(e.target.value)}><option>BTC/USD</option><option>ETH/USD</option></select></label><button className="secondary-button" type="button" onClick={()=>void run()} disabled={loading}>{loading?"Running…":"Run research"}</button></div>{error&&<p className="quote-error">{error}</p>}</section>
  {report&&<><section className="card panel"><div className="eyebrow">Deterministic research</div><h2>{report.query.asset} · {report.query.timeframe}</h2><p className="subtle">{new Date(report.query.start).toLocaleString()} → {new Date(report.query.end).toLocaleString()}</p><div className="data-grid">{report.metrics.map(m=><div className="data-cell" key={m.name}><span>{m.name}</span><strong>{Number(m.value).toPrecision(6)}</strong><small>n={m.sample_size}</small></div>)}</div></section>
  <section className="card panel"><h2>Provenance</h2>{report.artifacts.map(a=><div className="evidence" key={a.id}><strong>{a.name}</strong><span>{a.artifact_type} · v{a.version}</span><code>{a.checksum}</code></div>)}{report.findings.map(f=><p className="subtle" key={f}>{f}</p>)}</section></>}
  {answer&&<section className="card panel"><div className="eyebrow">Grounded research copilot</div><div className="metric-sm">{answer.grounded?"GROUNDED":"NO VERIFIED EVIDENCE"}</div><p className="subtle preline">{answer.answer}</p>{answer.evidence.map(e=><div className="evidence" key={e.checksum}><strong>{e.title}</strong><span>{e.kind}</span><code>{e.checksum}</code></div>)}</section>}
 </div>;
}
