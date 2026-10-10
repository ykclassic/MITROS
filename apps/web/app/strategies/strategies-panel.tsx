"use client";

import { useEffect, useState } from "react";
import { fetchJson } from "../../lib/api";

type NumericValue = string | number;
type Snapshot = {
  asset: string;
  timeframe: string;
  latest_close: NumericValue;
  candle_count: number;
  structure: {
    kind: string;
    bias: string;
    bos: string[];
    choch: string[];
    trend_strength: NumericValue;
    swing_highs: string[];
    swing_lows: string[];
  };
  liquidity: {
    sweeps: string[];
    pools: string[];
    session: string;
  };
  smc_context: {
    fvg: [string, string, string][];
    order_blocks: [string, string, string][];
    premium_discount: string;
    displacement: boolean;
    mitigation: string[];
  };
  crt_analysis: {
    direction: string;
    swept: boolean;
    score: NumericValue;
    target: NumericValue | null;
    reasons: string[];
  };
  strategy_votes: {
    strategy_id: string;
    direction: string | null;
    confidence: NumericValue;
    reasons: string[];
  }[];
  consensus: {
    direction: string;
    confidence: NumericValue;
    strategy_count: number;
    aligned_strategy_count: number;
    reasons: string[];
  };
  mtf: {
    direction: string;
    confidence: NumericValue;
    alignment: NumericValue;
    timeframes: { timeframe: string; direction: string; confidence: NumericValue }[];
  };
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isSnapshot(value: unknown): value is Snapshot {
  if (!isRecord(value)) return false;
  const structure = value.structure;
  const liquidity = value.liquidity;
  const smc = value.smc_context;
  const crt = value.crt_analysis;
  const consensus = value.consensus;
  const mtf = value.mtf;
  return (
    typeof value.asset === "string" &&
    typeof value.timeframe === "string" &&
    isRecord(structure) &&
    typeof structure.bias === "string" &&
    isStringArray(structure.bos) &&
    isStringArray(structure.choch) &&
    isRecord(liquidity) &&
    isStringArray(liquidity.sweeps) &&
    isRecord(smc) &&
    Array.isArray(smc.fvg) &&
    Array.isArray(smc.order_blocks) &&
    isRecord(crt) &&
    typeof crt.direction === "string" &&
    Array.isArray(value.strategy_votes) &&
    isRecord(consensus) &&
    typeof consensus.direction === "string" &&
    isRecord(mtf) &&
    Array.isArray(mtf.timeframes)
  );
}

function pct(value: NumericValue): string {
  const number = Number(value);
  return Number.isFinite(number) ? (number * 100).toFixed(1) + "%" : "—";
}

function display(value: NumericValue | null | undefined): string {
  return value === null || value === undefined ? "—" : String(value);
}

function EvidenceList({ title, items }: { title: string; items: string[] }) {
  return (
    <details className="evidence-panel">
      <summary>{title}</summary>
      <div className="evidence-body">
        {items.length ? items.map((item, index) => (
          <div className="evidence" key={index}>{item}</div>
        )) : <div className="subtle">No evidence recorded.</div>}
      </div>
    </details>
  );
}

export default function StrategiesPanel() {
  const [data, setData] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    void fetchJson<unknown>(
      "/api/v1/intelligence/snapshot?asset=BTC%2FUSD&venue=spot&timeframe=1h",
      { timeoutMs: 60000 },
    )
      .then((payload) => {
        if (!active) return;
        if (!isSnapshot(payload)) {
          setData(null);
          setError("The intelligence API returned an unexpected snapshot format. No strategy result was displayed.");
          return;
        }
        setData(payload);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setData(null);
        setError(cause instanceof Error ? cause.message : "Strategy intelligence is unavailable.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [attempt]);

  if (loading) {
    return <section className="card panel"><div className="metric">Loading…</div><p className="subtle">Evaluating strategy evidence from the verified BTC/USD 1h intelligence snapshot.</p></section>;
  }

  if (error || !data) {
    return (
      <section className="card panel">
        <div className="quote-error">{error ?? "Strategy intelligence is unavailable."}</div>
        <p className="subtle">The workspace does not invent or display a strategy result when the verified snapshot cannot be read.</p>
        <button type="button" className="button" onClick={() => setAttempt((value) => value + 1)}>Retry</button>
      </section>
    );
  }

  return (
    <div className="stack">
      <section className="grid">
        <div className="card">
          <div className="eyebrow">Strategy consensus</div>
          <div className="metric">{data.consensus.direction}</div>
          <p className="subtle">{pct(data.consensus.confidence)} confidence · {data.consensus.aligned_strategy_count}/{data.consensus.strategy_count} aligned</p>
        </div>
        <div className="card">
          <div className="eyebrow">Multi-timeframe consensus</div>
          <div className="metric">{data.mtf.direction}</div>
          <p className="subtle">{pct(data.mtf.alignment)} alignment · {pct(data.mtf.confidence)} confidence</p>
        </div>
        <div className="card">
          <div className="eyebrow">Market structure</div>
          <div className="metric">{data.structure.bias}</div>
          <p className="subtle">{data.structure.kind} · trend strength {pct(data.structure.trend_strength)}</p>
        </div>
        <div className="card">
          <div className="eyebrow">CRT</div>
          <div className="metric">{data.crt_analysis.direction}</div>
          <p className="subtle">{data.crt_analysis.swept ? "Liquidity sweep detected" : "No confirmed sweep"} · score {pct(data.crt_analysis.score)}</p>
        </div>
      </section>

      <section className="card panel">
        <div className="panel-header">
          <div>
            <h2>Strategy votes</h2>
            <p className="subtle">{data.asset} · {data.timeframe} · {data.candle_count} verified candles · latest close {display(data.latest_close)}</p>
          </div>
        </div>
        {data.strategy_votes.length ? (
          <div className="data-grid">
            {data.strategy_votes.map((vote) => (
              <div className="data-cell" key={vote.strategy_id}>
                <span>{vote.strategy_id}</span>
                <strong>{vote.direction ?? "NEUTRAL"}</strong>
                <small>{pct(vote.confidence)} confidence</small>
                <p className="subtle">{vote.reasons.length ? vote.reasons.join(" · ") : "No additional reasons recorded."}</p>
              </div>
            ))}
          </div>
        ) : <p className="subtle">No strategy votes were returned for this snapshot.</p>}
        <EvidenceList title="Inspect consensus evidence" items={data.consensus.reasons ?? []} />
      </section>

      <section className="grid">
        <div className="card">
          <h2>Market structure evidence</h2>
          <div className="data-list">
            <span>BOS <strong>{data.structure.bos.length}</strong></span>
            <span>CHOCH <strong>{data.structure.choch.length}</strong></span>
            <span>Swing highs <strong>{data.structure.swing_highs.length}</strong></span>
            <span>Swing lows <strong>{data.structure.swing_lows.length}</strong></span>
          </div>
          <EvidenceList title="Inspect structure events" items={[
            ...data.structure.bos.map((item) => "BOS: " + item),
            ...data.structure.choch.map((item) => "CHOCH: " + item),
            ...data.structure.swing_highs.map((item) => "Swing high: " + item),
            ...data.structure.swing_lows.map((item) => "Swing low: " + item),
          ]} />
        </div>
        <div className="card">
          <h2>SMC evidence</h2>
          <div className="data-list">
            <span>Premium / discount <strong>{data.smc_context.premium_discount}</strong></span>
            <span>Displacement <strong>{data.smc_context.displacement ? "YES" : "NO"}</strong></span>
            <span>Fair value gaps <strong>{data.smc_context.fvg.length}</strong></span>
            <span>Order blocks <strong>{data.smc_context.order_blocks.length}</strong></span>
          </div>
          <EvidenceList title="Inspect SMC evidence" items={[
            ...data.smc_context.fvg.map(([direction, low, high]) => `FVG ${direction}: ${low} → ${high}`),
            ...data.smc_context.order_blocks.map(([direction, low, high]) => `Order block ${direction}: ${low} → ${high}`),
            ...data.smc_context.mitigation.map((item) => "Mitigation: " + item),
          ]} />
        </div>
        <div className="card">
          <h2>Liquidity</h2>
          <div className="data-list">
            <span>Session <strong>{data.liquidity.session}</strong></span>
            <span>Sweeps <strong>{data.liquidity.sweeps.length}</strong></span>
            <span>Liquidity pools <strong>{data.liquidity.pools.length}</strong></span>
          </div>
          <EvidenceList title="Inspect liquidity evidence" items={[
            ...data.liquidity.sweeps.map((item) => "Sweep: " + item),
            ...data.liquidity.pools.map((item) => "Pool: " + item),
          ]} />
        </div>
      </section>

      <section className="card panel">
        <h2>Multi-timeframe state</h2>
        <div className="data-grid">
          {data.mtf.timeframes.map((timeframe) => (
            <div className="data-cell" key={timeframe.timeframe}>
              <span>{timeframe.timeframe}</span>
              <strong>{timeframe.direction}</strong>
              <small>{pct(timeframe.confidence)} confidence</small>
            </div>
          ))}
        </div>
      </section>

      <section className="card panel">
        <h2>CRT evidence</h2>
        <div className="data-list">
          <span>Direction <strong>{data.crt_analysis.direction}</strong></span>
          <span>Sweep confirmed <strong>{data.crt_analysis.swept ? "YES" : "NO"}</strong></span>
          <span>Target <strong>{display(data.crt_analysis.target)}</strong></span>
        </div>
        <EvidenceList title="Inspect CRT reasons" items={data.crt_analysis.reasons ?? []} />
      </section>

      <p className="subtle">This page presents intelligence evidence only. A displayed consensus is not a trade authorization or a calibrated probability of profit.</p>
    </div>
  );
}
