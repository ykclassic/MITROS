"use client";

import { useState } from "react";
import { fetchJson } from "../../lib/api";

type RiskCheck = {
  name: string;
  passed: boolean;
  observed: string | boolean;
  threshold: string | boolean;
  reason: string;
};
type Decision = {
  proposal_id: string;
  disposition: "APPROVED" | "REJECTED";
  approved_notional: string;
  risk_budget_notional: string;
  size_cap_notional: string;
  risk_amount: string;
  risk_fraction: string;
  reward_risk_ratio: string;
  checks: RiskCheck[];
  rejection_reasons: string[];
  invalidation_conditions: string[];
  evaluated_at: string;
  risk_engine_version: string;
  execution_authorized: boolean;
};
type MarketEvidence = {
  provider: string;
  provider_version: string;
  asset: string;
  venue: string;
  timeframe: string;
  latest_verified_close: string;
  candle_observed_at: string;
  candle_received_at: string;
  batch_checksum: string;
  xt_bid: string;
  xt_ask: string;
  xt_last: string;
  spread_fraction: string;
  quote_observed_at: string;
};
type Response = {
  scope: "XT_ACCOUNT";
  audit_id: string;
  account_snapshot_id: string;
  market_evidence: MarketEvidence;
  decision: Decision;
};

const initial = {
  asset: "BTC/USDT",
  direction: "LONG",
  entry: "",
  stop_loss: "60000",
  take_profit: "63000",
  requested_notional: "100",
};

export default function RiskPanel() {
  const [form, setForm] = useState(initial);
  const [result, setResult] = useState<Response | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (key: keyof typeof initial, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  async function assess() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await fetchJson<Response>("/api/v1/risk/phase4/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          proposal_id: crypto.randomUUID(),
          idempotency_key: crypto.randomUUID(),
          asset: form.asset.trim().toUpperCase(),
          direction: form.direction,
          entry: form.entry.trim() ? form.entry : null,
          stop_loss: form.stop_loss,
          take_profit: form.take_profit,
          requested_notional: form.requested_notional,
        }),
      });
      setResult(response);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Phase 4 risk evaluation unavailable");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="stack">
      <section className="card panel">
        <div className="eyebrow">Phase 4 · XT account-backed evaluation</div>
        <h2>Independent risk gate</h2>
        <p className="subtle">
          Portfolio equity, balances, positions, daily P&amp;L, and peak equity are loaded from
          XT.com and MITROS portfolio snapshots. Market candles must pass the verified market-data
          pipeline; XT bid/ask data is used for spread checks. Account figures cannot be entered
          or overridden in this form. This screen evaluates risk; it does not place an order.
        </p>
        <div className="form-grid">
          <label>
            Asset (USDT spot)
            <input value={form.asset} onChange={(event) => set("asset", event.target.value)} />
          </label>
          <label>
            Direction
            <select value={form.direction} onChange={(event) => set("direction", event.target.value)}>
              <option value="LONG">LONG</option>
              <option value="SHORT">SHORT</option>
            </select>
          </label>
          <label>
            Entry price (blank = current XT ticker)
            <input type="number" min="0" step="any" value={form.entry} onChange={(event) => set("entry", event.target.value)} />
          </label>
          <label>
            Requested notional (USDT)
            <input type="number" min="0" step="any" value={form.requested_notional} onChange={(event) => set("requested_notional", event.target.value)} />
          </label>
          <label>
            Stop-loss
            <input type="number" min="0" step="any" value={form.stop_loss} onChange={(event) => set("stop_loss", event.target.value)} />
          </label>
          <label>
            Take-profit
            <input type="number" min="0" step="any" value={form.take_profit} onChange={(event) => set("take_profit", event.target.value)} />
          </label>
        </div>
        <button className="secondary-button" type="button" onClick={() => void assess()} disabled={loading}>
          {loading ? "Loading XT account and verifying market data…" : "Evaluate risk"}
        </button>
        {error && <p className="quote-error">{error}</p>}
      </section>

      {result && (
        <>
          <section className="grid">
            <div className="card">
              <div className="eyebrow">Independent decision</div>
              <div className="metric">{result.decision.disposition}</div>
              <p className="subtle">Scope: {result.scope}. Execution authorized: no.</p>
            </div>
            <div className="card">
              <div className="eyebrow">Approved notional</div>
              <div className="metric">{result.decision.approved_notional}</div>
            </div>
            <div className="card">
              <div className="eyebrow">Risk budget notional</div>
              <div className="metric">{result.decision.risk_budget_notional}</div>
            </div>
            <div className="card">
              <div className="eyebrow">Size cap</div>
              <div className="metric">{result.decision.size_cap_notional}</div>
              <p className="subtle">Risk fraction: {result.decision.risk_fraction}</p>
            </div>
          </section>
          <section className="card">
            <div className="eyebrow">Audit and account snapshot</div>
            <p>Risk decision ID: <code>{result.audit_id}</code></p>
            <p>Portfolio snapshot ID: <code>{result.account_snapshot_id}</code></p>
            <p className="subtle">Engine {result.decision.risk_engine_version} · {result.decision.evaluated_at}</p>
            <h2>Verified market evidence</h2>
            <p>{result.market_evidence.asset} · {result.market_evidence.provider} {result.market_evidence.provider_version}</p>
            <p>Verified close: {result.market_evidence.latest_verified_close} · XT last: {result.market_evidence.xt_last}</p>
            <p>Bid / ask: {result.market_evidence.xt_bid} / {result.market_evidence.xt_ask} · spread: {result.market_evidence.spread_fraction}</p>
            <p className="subtle">Checksum: <code>{result.market_evidence.batch_checksum}</code></p>
            <h2>Independent hard checks</h2>
            <div className="stack">
              {result.decision.checks.map((check) => (
                <div className="status" key={check.name}>
                  <strong>{check.passed ? "PASS" : "FAIL"} · {check.name}</strong>
                  <div>{check.reason}</div>
                  <small>Observed: {String(check.observed)} · Threshold: {String(check.threshold)}</small>
                </div>
              ))}
            </div>
            {result.decision.rejection_reasons.length > 0 && (
              <>
                <h2>Rejection reasons</h2>
                {result.decision.rejection_reasons.map((reason) => <p key={reason}>{reason}</p>)}
              </>
            )}
            <h2>Invalidation conditions</h2>
            {result.decision.invalidation_conditions.map((condition) => <p key={condition}>{condition}</p>)}
          </section>
        </>
      )}
    </div>
  );
}
