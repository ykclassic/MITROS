import IntelligencePanel from "./intelligence-panel";

export default function IntelligencePage() {
  return (
    <main className="main">
      <div className="eyebrow">Institutional market intelligence</div>
      <h1>Market Intelligence</h1>
      <p className="subtle">A deterministic workspace for verified market observations, quantitative state, structure, liquidity, SMC, CRT, regime and strategy evidence.</p>
      <IntelligencePanel />
    </main>
  );
}
