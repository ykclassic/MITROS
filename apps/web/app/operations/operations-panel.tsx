"use client";

import { useEffect, useState } from "react";

type Readiness={status:string;execution_mode:string;live_trading_enabled:boolean;checks:Record<string,string>};

export default function OperationsPanel() {
  const base=process.env.NEXT_PUBLIC_MITROS_API_URL ?? "http://localhost:8000";
  const [data,setData]=useState<Readiness|null>(null);
  useEffect(()=>{fetch(`${base}/api/v1/operations/readiness`,{cache:"no-store"}).then(r=>r.ok?r.json():null).then(setData).catch(()=>setData(null));},[base]);
  return <div className="grid">
    <section className="card"><div className="status"><span className="dot"/>{data?.status ?? "Unavailable"}</div><div className="metric">{data?.execution_mode ?? "—"}</div><p className="subtle">Execution mode</p></section>
    <section className="card"><div className="status"><span className="dot"/>{data?.live_trading_enabled ? "Enabled" : "Disabled"}</div><div className="metric">Human approval</div><p className="subtle">Required before execution</p></section>
    <section className="card"><h2>Checks</h2>{data ? Object.entries(data.checks).map(([k,v])=><div className="status" key={k}>{k}: {v}</div>) : <p className="subtle">Backend unavailable</p>}</section>
  </div>;
}
