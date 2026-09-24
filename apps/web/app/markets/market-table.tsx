"use client";

import { useCallback, useEffect, useState } from "react";

type Quote = {
  asset: string;
  price: string;
  provider: string;
  observed_at: string;
  quality: string;
};

type QuoteState = {
  quote?: Quote;
  error?: string;
};

const assets = ["BTC/USD", "ETH/USD"];

function describeFetchFailure(response: Response): string {
  return response.status
    ? `Quote request failed (HTTP ${response.status})`
    : "Quote request failed";
}

export default function MarketTable() {
  const base = process.env.NEXT_PUBLIC_MITROS_API_URL ?? "http://localhost:8000";
  const [quotes, setQuotes] = useState<Record<string, QuoteState>>({});
  const [loading, setLoading] = useState(true);

  const loadQuotes = useCallback(async () => {
    setLoading(true);

    const results = await Promise.all(
      assets.map(async (asset): Promise<[string, QuoteState]> => {
        try {
          const response = await fetch(
            `${base}/api/v1/market/quote?asset=${encodeURIComponent(asset)}&venue=spot`,
            { cache: "no-store" },
          );
          if (!response.ok) {
            return [asset, { error: describeFetchFailure(response) }];
          }

          const quote = (await response.json()) as Quote;
          return [asset, { quote }];
        } catch {
          return [asset, { error: "Quote request failed — check the API connection" }];
        }
      }),
    );

    setQuotes(Object.fromEntries(results));
    setLoading(false);
  }, [base]);

  useEffect(() => {
    let cancelled = false;

    void loadQuotes().catch(() => {
      if (!cancelled) {
        setQuotes(
          Object.fromEntries(
            assets.map((asset) => [asset, { error: "Quote request failed" }]),
          ),
        );
        setLoading(false);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [loadQuotes]);

  return (
    <div className="card panel">
      <div className="panel-header">
        <div>
          <h2>Live market quotes</h2>
          <p className="subtle">Each asset is fetched independently from the backend router.</p>
        </div>
        <button className="secondary-button" type="button" onClick={() => void loadQuotes()}>
          Refresh
        </button>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Asset</th>
            <th>Price</th>
            <th>Provider</th>
            <th>Quote time</th>
            <th>Quality</th>
          </tr>
        </thead>
        <tbody>
          {assets.map((asset) => {
            const state = quotes[asset];
            const q = state?.quote;
            return (
              <tr key={asset}>
                <td>{asset}</td>
                <td>
                  {loading && !state ? (
                    "Loading…"
                  ) : q ? (
                    q.price
                  ) : (
                    <span className="quote-error">{state?.error ?? "Unavailable"}</span>
                  )}
                </td>
                <td>{q?.provider ?? (state?.error ? "Error" : "—")}</td>
                <td>{q ? new Date(q.observed_at).toLocaleString() : "—"}</td>
                <td>{q?.quality ?? (state?.error ? "UNAVAILABLE" : "—")}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
