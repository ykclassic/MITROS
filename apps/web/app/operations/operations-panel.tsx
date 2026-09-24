"use client";

import { useEffect, useState } from "react";
import { fetchJson } from "../../lib/api";

type Readiness={status:string;execution_mode:string;live_trading_enabled:boolean;checks:Record<string,string>};

export default function OperationsPanel() {
  const [data,setData]=useState<Readiness|null>(null);
  const [error,setError]=useState<string|null>(null);
  useEffect(()=>{void fetchJson<Readiness>("/api/v1/operations/readiness").then(setData).catch((e)=>setError(e instanceof Error?e.message:"Backend unavailable"));},[]);
  return <div className="grid">
    <section className="card"><div className="status"><span className="dot"/>{data?.status ?? (error ? "Unavailable" : "Loading")}</div><div className="metric">{data?.execution_mode ?? "—"}</div><p className="subtle">Execution mode</p></section>
    <section className="card"><div className="status"><span className="dot"/>{data?.live_trading_enabled ? "Enabled" : "Disabled"}</div><div className="metric">Human approval</div><p className="subtle">Required before execution</p></section>
    <section className="card"><h2>Checks</h2>{data ? Object.entries(data.checks).map(([k,v])=><div className="status" key={k}>{k}: {v}</div>) : <p className="subtle">{error ?? "Backend unavailable"}</p>}</section>
  </div>;
}
