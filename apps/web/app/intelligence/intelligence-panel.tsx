"use client";

import { useEffect, useState } from "react";
import { fetchJson } from "../../lib/api";

type Provenance = {
  data_quality: string;
  batch_checksum: string;
  observation_count: number;
  observations: {
    provider: string;
    provider_version: string | null;
    request_id: string | null;
    observation_checksum: string;
    observed_at: string;
    received_at: string;
  }[];
};

type Snapshot = {
  asset: string;
  venue: string;
  symbol: string;
  timeframe: string;
  as_of: string;
  observation_window: [string, string];
  engine_version: string;
  configuration_version: string;
  input_checksums: string[];
  snapshot_checksum: string;
  candle_count: number;
  latest_close: string;
  feature_set_version: string;
  features: Record<string, string>;
  quantitative: {
    return_1: string;
    return_window: string;
    atr: string;
    realized_volatility: string;
    momentum: string;
    volume_mean: string;
    volume_ratio: string;
    return_skew: string;
    return_kurtosis_excess: string;
    autocorrelation_1: string;
    correlation: string | null;
  };
  structure: {
    kind: string;
    bias: string;
    swing_highs: string[];
    swing_lows: string[];
    bos: string[];
    choch: string[];
    trend_strength: string;
    range_high: string | null;
    range_low: string | null;
  };
  liquidity: {
    levels: [string, string][];
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
    reference_high: string;
    reference_low: string;
    swept: boolean;
    confirmation_index: number | null;
    target: string | null;
    score: string;
    reasons: string[];
  };
  regime: {
    regime: string;
    confidence: string;
    trend_strength: string;
    volatility: string;
    sample_size: number;
    model_version: string;
    observation_window: [string, string];
    timestamp: string;
    reasons: string[];
  };
  context: {
    session: string;
    news_active: boolean;
    external_bias: string | null;
    notes: string[];
  };
  strategy_votes: {
    strategy_id: string;
    direction: string | null;
    confidence: string;
    reasons: string[];
  }[];
  consensus: {
    direction: string;
    confidence: string;
    strategy_count: number;
    aligned_strategy_count: number;
    reasons: string[];
  };
  mtf: {
    direction: string;
    confidence: string;
    alignment: string;
    timeframes: { timeframe: string; direction: string; confidence: string }[];
  };
  provenance: Provenance;
  generated_at: string;
};

const ASSETS = ["BTC/USD", "ETH/USD", "SOL/USD"];
const TIMEFRAMES = ["15m", "1h", "4h"];

const pct = (value: string) => (Number(value) * 100).toFixed(2) + "%";
const fmt = (value: string | number | null) => value === null ? "—" : String(value);
const shortHash = (value: string) => value.length > 18 ? value.slice(0, 10) + "…" + value.slice(-8) : value;
const time = (value: string) => new Date(value).toLocaleString();

function Evidence({ title, items }: { title: string; items: string[] }) {
  return (
    <details className="evidence-panel">
      <summary>{title}</summary>
      <div className="evidence-body">
        {items.length ? items.map((item, index) => <div className="evidence" key={index}>{item}</div>) : <div className="subtle">No evidence recorded.</div>}
      </div>
    </details>
  );
}

export default function IntelligencePanel() {
  const [asset, setAsset] = useState("BTC/USD");
  const [timeframe, setTimeframe] = useState("1h");
  const [data, setData] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setData(null);
    const query = new URLSearchParams({ asset, venue: "spot", timeframe });
    void fetchJson<Snapshot>("/api/v1/intelligence/snapshot?" + query.toString(), { timeoutMs: 60000 })
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Intelligence unavailable"))
      .finally(() => setLoading(false));
  }, [asset, timeframe]);

  return (
    <div className="stack">
      <section className="card workspace-controls">
        <div>
          <div className="eyebrow">Market intelligence workspace</div>
          <h2>Verified market snapshot</h2>
          <p className="subtle">All intelligence is computed server-side from the Phase 1 verified-data trust boundary. Trade probability is intentionally not displayed.</p>
        </div>
        <div className="form-row">
          <label>Asset<select value={asset} onChange={(e) => setAsset(e.target.value)}>{ASSETS.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label>Timeframe<select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>{TIMEFRAMES.map((item) => <option key={item}>{item}</option>)}</select></label>
        </div>
      </section>

      {loading && <section className="card panel"><div className="metric">Loading…</div><p className="subtle">Verifying provider observations and computing the deterministic snapshot.</p></section>}
      {error && <section className="card panel"><div className="quote-error">{error}</div><p className="subtle">The workspace is fail-closed when verified market data or authoritative provider routing is unavailable.</p></section>}

      {data && (
        <>
          <section className="grid">
            <div className="card"><div className="eyebrow">Latest close</div><div className="metric">{data.latest_close}</div><p className="subtle">{data.asset} · {data.timeframe} · {data.candle_count} verified candles</p></div>
            <div className="card"><div className="eyebrow">Regime</div><div className="metric">{data.regime.regime}</div><p className="subtle">Regime confidence {pct(data.regime.confidence)}</p></div>
            <div className="card"><div className="eyebrow">Strategy consensus</div><div className="metric">{data.consensus.direction}</div><p className="subtle">Strategy confidence {pct(data.consensus.confidence)} · {data.consensus.aligned_strategy_count}/{data.consensus.strategy_count} aligned</p></div>
            <div className="card"><div className="eyebrow">MTF context</div><div className="metric">{data.mtf.direction}</div><p className="subtle">Alignment {pct(data.mtf.alignment)} · confidence {pct(data.mtf.confidence)}</p></div>
          </section>

          <section className="card panel">
            <div className="panel-header"><div><h2>Snapshot integrity</h2><p className="subtle">Reproducibility and provenance identifiers for this exact intelligence computation.</p></div><span className="status"><span className="dot" /> {data.provenance.data_quality}</span></div>
            <div className="data-grid">
              <div className="data-cell"><span>Engine</span><strong>{data.engine_version}</strong></div>
              <div className="data-cell"><span>Configuration</span><strong>{data.configuration_version}</strong></div>
              <div className="data-cell"><span>Observation window</span><strong>{time(data.observation_window[0])}</strong><small>to {time(data.observation_window[1])}</small></div>
              <div className="data-cell"><span>Generated</span><strong>{time(data.generated_at)}</strong></div>
              <div className="data-cell"><span>Snapshot checksum</span><code>{data.snapshot_checksum}</code></div>
              <div className="data-cell"><span>Batch checksum</span><code>{data.provenance.batch_checksum}</code></div>
            </div>
          </section>

          <section className="card panel"><h2>Quantitative intelligence</h2><div className="data-grid">
            {Object.entries(data.quantitative).map(([name, value]) => <div className="data-cell" key={name}><span>{name.replaceAll("_", " ")}</span><strong>{fmt(value)}</strong></div>)}
          </div></section>

          <section className="grid">
            <div className="card"><h2>Market structure</h2><div className="data-list"><span>Kind <strong>{data.structure.kind}</strong></span><span>Bias <strong>{data.structure.bias}</strong></span><span>Trend strength <strong>{pct(data.structure.trend_strength)}</strong></span><span>BOS <strong>{data.structure.bos.length}</strong></span><span>CHOCH <strong>{data.structure.choch.length}</strong></span></div><Evidence title="Inspect structure evidence" items={[...data.structure.bos.map((x) => "BOS: " + x), ...data.structure.choch.map((x) => "CHOCH: " + x), ...data.structure.swing_highs.map((x) => "Swing high: " + x), ...data.structure.swing_lows.map((x) => "Swing low: " + x)]} /></div>
            <div className="card"><h2>Liquidity</h2><div className="data-list">{data.liquidity.levels.map(([kind, value]) => <span key={kind + value}>{kind} <strong>{value}</strong></span>)}</div><Evidence title="Inspect liquidity evidence" items={[...data.liquidity.sweeps, ...data.liquidity.pools.map((x) => "Liquidity pool: " + x)]} /></div>
            <div className="card"><h2>SMC context</h2><div className="data-list"><span>Premium / discount <strong>{data.smc_context.premium_discount}</strong></span><span>Displacement <strong>{data.smc_context.displacement ? "YES" : "NO"}</strong></span><span>Mitigation <strong>{data.smc_context.mitigation.length}</strong></span></div><Evidence title="Inspect SMC evidence" items={[...data.smc_context.fvg.map((x) => "FVG " + x[0] + ": " + x[1] + " → " + x[2]), ...data.smc_context.order_blocks.map((x) => "Order block " + x[0] + ": " + x[1] + " → " + x[2]), ...data.smc_context.mitigation.map((x) => "Mitigation: " + x)]} /></div>
          </section>

          <section className="grid">
            <div className="card"><h2>CRT</h2><div className="data-list"><span>Direction <strong>{data.crt_analysis.direction}</strong></span><span>Reference high <strong>{data.crt_analysis.reference_high}</strong></span><span>Reference low <strong>{data.crt_analysis.reference_low}</strong></span><span>Swept <strong>{data.crt_analysis.swept ? "YES" : "NO"}</strong></span><span>Score <strong>{pct(data.crt_analysis.score)}</strong></span><span>Target <strong>{fmt(data.crt_analysis.target)}</strong></span></div><Evidence title="Inspect CRT evidence" items={data.crt_analysis.reasons} /></div>
            <div className="card"><h2>Regime evidence</h2><div className="data-list"><span>Model <strong>{data.regime.model_version}</strong></span><span>Sample <strong>{data.regime.sample_size}</strong></span><span>Volatility <strong>{data.regime.volatility}</strong></span></div><Evidence title="Inspect regime evidence" items={data.regime.reasons} /></div>
            <div className="card"><h2>Strategy evidence</h2>{data.strategy_votes.map((vote) => <div className="evidence" key={vote.strategy_id}><span>{vote.strategy_id}</span><strong>{vote.direction ?? "NEUTRAL"} · {pct(vote.confidence)}</strong><small>{vote.reasons.join(" · ") || "No additional reasons."}</small></div>)}<Evidence title="Inspect consensus evidence" items={data.consensus.reasons} /></div>
          </section>

          <section className="card panel"><h2>Multi-timeframe state</h2><div className="data-grid">{data.mtf.timeframes.map((tf) => <div className="data-cell" key={tf.timeframe}><span>{tf.timeframe}</span><strong>{tf.direction}</strong><small>{pct(tf.confidence)} confidence</small></div>)}</div></section>

          <section className="card panel">
            <div className="panel-header"><div><h2>Data provenance</h2><p className="subtle">{data.provenance.observation_count} verified observations contributed to this snapshot.</p></div></div>
            <div className="data-grid">{data.provenance.observations.slice(0, 12).map((item, index) => <div className="data-cell" key={item.observation_checksum}><span>Observation {index + 1}</span><strong>{item.provider} {item.provider_version ?? ""}</strong><small>{time(item.observed_at)}</small><code>{shortHash(item.observation_checksum)}</code></div>)}</div>
            {data.provenance.observation_count > 12 && <p className="subtle">Showing the first 12 observation records in the workspace. The complete observation checksum set is available through the snapshot API.</p>}
            <Evidence title="Inspect input checksums" items={data.input_checksums.map((checksum, index) => index + 1 + ". " + checksum)} />
          </section>
        </>
      )}
    </div>
  );
}
