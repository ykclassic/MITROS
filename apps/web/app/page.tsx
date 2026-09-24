export default function Home() {
  return <main className="main">
    <div className="eyebrow">Market Intelligence & Trading Operating System</div>
    <h1>MITROS command center</h1>
    <p className="subtle">A single workspace for verified market data, intelligence, research, risk and human-gated trading.</p>
    <div className="grid">
      <section className="card"><div className="eyebrow">Market data</div><div className="metric">Verified</div><p className="subtle">Provider provenance and quote timestamps remain visible.</p></section>
      <section className="card"><div className="eyebrow">Execution</div><div className="metric">Paper</div><p className="subtle">Live trading remains disabled by default.</p></section>
      <section className="card"><div className="eyebrow">Approval</div><div className="metric">Human</div><p className="subtle">No UI action bypasses explicit approval.</p></section>
    </div>
    <section className="card panel"><div className="eyebrow">Workspace</div><h2>Product surfaces</h2><div className="feature-grid">
      <a className="feature-link" href="/markets"><strong>Markets</strong><span>Quotes, provenance and freshness.</span></a>
      <a className="feature-link" href="/intelligence"><strong>Intelligence</strong><span>Features, regime and statistical state.</span></a>
      <a className="feature-link" href="/strategies"><strong>Strategies</strong><span>SMC, CRT and consensus evidence.</span></a>
      <a className="feature-link" href="/signals"><strong>Signals</strong><span>Signal lifecycle and monitoring.</span></a>
      <a className="feature-link" href="/risk"><strong>Risk</strong><span>Portfolio constraints and assessments.</span></a>
      <a className="feature-link" href="/research"><strong>Research</strong><span>Backtests, replay and grounded analysis.</span></a>
      <a className="feature-link" href="/trading"><strong>Trading</strong><span>Proposal, approval, execution and ledger.</span></a>
      <a className="feature-link" href="/operations"><strong>Operations</strong><span>Readiness, provider and deployment state.</span></a>
    </div></section>
  </main>;
}
