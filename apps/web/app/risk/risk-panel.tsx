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
type Response = { scope: "SCENARIO_ONLY"; audit_id: string; decision: Decision };

const initial = {
  asset: "BTC/USD",
  correlated_group: "BTC-beta",
  direction: "LONG",
  equity: "10000",
  daily_pnl: "0",
  peak_equity: "10000",
  requested_notional: "1000",
  entry: "100",
  stop_loss: "95",
  take_profit: "110",
  spread_fraction: "0.001",
  expected_slippage_fraction: "0.0005",
  data_quality: "0.99",
  data_verified: true,
  open_positions: "[]",
};

export default function RiskPanel() {
  const [form, setForm] = useState(initial);
  const [result, setResult] = useState<Response | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (key: keyof typeof initial, value: string | boolean) =>
    setForm((current) => ({ ...current, [key]: value }));

  async function assess() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      let openPositions: unknown;
      try {
        openPositions = JSON.parse(form.open_positions);
      } catch {
        throw new Error("Open positions must be valid JSON.");
      }
      if (!Array.isArray(openPositions)) {
        throw new Error("Open positions must be a JSON array.");
      }
      const now = new Date();
      const request = {
        proposal_id: crypto.randomUUID(),
        asset: form.asset,
        correlated_group: form.correlated_group,
        direction: form.direction,
        as_of: now.toISOString(),
        quote_observed_at: new Date(now.getTime() - 5000).toISOString(),
        data_verified: form.data_verified,
        data_quality: form.data_quality,
        equity: form.equity,
        daily_pnl: form.daily_pnl,
        peak_equity: form.peak_equity,
        open_positions: openPositions,
        requested_notional: form.requested_notional,
        entry: form.entry,
        stop_loss: form.stop_loss,
        take_profit: form.take_profit,
        spread_fraction: form.spread_fraction,
        expected_slippage_fraction: form.expected_slippage_fraction,
      };
      const response = await fetchJson<Response>("/api/v1/risk/phase4/scenario", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          idempotency_key: crypto.randomUUID(),
          request,
        }),
      });
      setResult(response);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Phase 4 risk evaluation unavailable");
    } finally {
      setLoading(false);
    }
  }

  const fields: { key: keyof typeof initial; label: string; type?: string }[] = [
    { key: "asset", label: "Asset" },
    { key: "correlated_group", label: "Correlation group" },
    { key: "equity", label: "Scenario equity" },
    { key: "daily_pnl", label: "Daily P&L" },
    { key: "peak_equity", label: "Peak equity" },
    { key: "requested_notional", label: "Requested notional" },
    { key: "entry", label: "Entry price" },
    { key: "stop_loss", label: "Stop-loss" },
    { key: "take_profit", label: "Take-profit" },
    { key: "spread_fraction", label: "Spread fraction" },
    { key: "expected_slippage_fraction", label: "Expected slippage fraction" },
    { key: "data_quality", label: "Scenario data quality" },
  ];

  return (
    <div className="stack">
      <section className="card panel">
        <div className="eyebrow">Phase 4 · audited scenario</div>
        <h2>Independent risk gate</h2>
        <p className="subtle">
          This screen evaluates an explicitly supplied scenario and records the decision in the
          audit store. These inputs are not authenticated live account state or an executable
          order. The endpoint is disabled in live mode until authoritative account-state wiring
          is deployed. Risk approval never authorizes execution.
        </p>
        <div className="form-grid">
          {fields.map(({ key, label }) => (
            <label key={key}>
              {label}
              <input
                type={key === "asset" || key === "correlated_group" ? "text" : "number"}
                step="any"
                value={String(form[key])}
                onChange={(event) => set(key, event.target.value)}
              />
            </label>
          ))}
          <label>
            Direction
            <select value={form.direction} onChange={(event) => set("direction", event.target.value)}>
              <option value="LONG">LONG</option>
              <option value="SHORT">SHORT</option>
            </select>
          </label>
          <label>
            Data verification assertion
            <select
              value={String(form.data_verified)}
              onChange={(event) => set("data_verified", event.target.value === "true")}
            >
              <option value="true">Verified (scenario only)</option>
              <option value="false">Unverified</option>
            </select>
          </label>
          <label className="wide">
            Open positions JSON
            <textarea
              rows={3}
              value={form.open_positions}
              onChange={(event) => set("open_positions", event.target.value)}
              spellCheck={false}
            />
          </label>
        </div>
        <button className="secondary-button" type="button" onClick={() => void assess()} disabled={loading}>
          {loading ? "Evaluating and auditing…" : "Evaluate Phase 4 scenario"}
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
              <p className="subtle">Requested size is rejected, not silently resized.</p>
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
            <div className="eyebrow">Durable audit</div>
            <p>Decision ID: <code>{result.audit_id}</code></p>
            <p className="subtle">Engine {result.decision.risk_engine_version} · {result.decision.evaluated_at}</p>
            <h2>Hard checks</h2>
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
