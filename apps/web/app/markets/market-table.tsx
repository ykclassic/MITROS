"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchJson } from "../../lib/api";

type Quote = { asset: string; price: string; provider: string; observed_at: string; quality: string };
type QuoteState = { quote?: Quote; error?: string };
const assets = ["BTC/USD", "ETH/USD"];

export default function MarketTable() {
  const [quotes, setQuotes] = useState<Record<string, QuoteState>>({});
  const [loading, setLoading] = useState(true);

  const loadQuotes = useCallback(async () => {
    setLoading(true);
    const results = await Promise.all(assets.map(async (asset): Promise<[string, QuoteState]> => {
      try {
        const quote = await fetchJson<Quote>("/api/v1/market/quote?asset=" + encodeURIComponent(asset) + "&venue=spot");
        return [asset, { quote }];
      } catch (error) {
        return [asset, { error: error instanceof Error ? error.message : "Quote request failed" }];
      }
    }));
    setQuotes(Object.fromEntries(results));
    setLoading(false);
  }, []);

  useEffect(() => { void loadQuotes(); }, [loadQuotes]);

  return <div className="card panel">
    <div className="panel-header">
      <div><h2>Live market quotes</h2><p className="subtle">Browser requests use the same-origin API boundary; provider credentials stay server-side.</p></div>
      <button className="secondary-button" type="button" onClick={() => void loadQuotes()}>Refresh</button>
    </div>
    <table className="table"><thead><tr><th>Asset</th><th>Price</th><th>Provider</th><th>Quote time</th><th>Quality</th></tr></thead>
      <tbody>{assets.map((asset) => { const state=quotes[asset]; const q=state?.quote; return <tr key={asset}>
        <td>{asset}</td><td>{loading && !state ? "Loading…" : q ? q.price : <span className="quote-error">{state?.error ?? "Unavailable"}</span>}</td>
        <td>{q?.provider ?? (state?.error ? "Error" : "—")}</td><td>{q ? new Date(q.observed_at).toLocaleString() : "—"}</td><td>{q?.quality ?? (state?.error ? "UNAVAILABLE" : "—")}</td>
      </tr>; })}</tbody>
    </table>
  </div>;
}
