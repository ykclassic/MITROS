"use client";

import { useEffect, useState } from "react";

type Quote = { asset:string; price:string; provider:string; observed_at:string; quality:string };
const assets=["BTC/USD","ETH/USD"];

export default function MarketTable() {
  const base=process.env.NEXT_PUBLIC_MITROS_API_URL ?? "http://localhost:8000";
  const [quotes,setQuotes]=useState<Record<string,Quote>>({});
  const [loading,setLoading]=useState(true);

  useEffect(() => {
    let cancelled=false;
    Promise.all(assets.map(async asset => {
      const response=await fetch(`${base}/api/v1/market/quote?asset=${encodeURIComponent(asset)}&venue=spot`,{cache:"no-store"});
      if (!response.ok) return null;
      return response.json() as Promise<Quote>;
    })).then(rows => {
      if (!cancelled) setQuotes(Object.fromEntries(rows.filter(Boolean).map(q => [q!.asset,q!])));
    }).catch(() => undefined).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled=true; };
  }, [base]);

  return <div className="card panel"><table className="table"><thead><tr><th>Asset</th><th>Price</th><th>Provider</th><th>Quote time</th><th>Quality</th></tr></thead><tbody>{assets.map(asset => {
    const q=quotes[asset];
    return <tr key={asset}><td>{asset}</td><td>{loading ? "Loading…" : q?.price ?? "Unavailable"}</td><td>{q?.provider ?? "—"}</td><td>{q ? new Date(q.observed_at).toLocaleString() : "—"}</td><td>{q?.quality ?? "—"}</td></tr>;
  })}</tbody></table></div>;
}
