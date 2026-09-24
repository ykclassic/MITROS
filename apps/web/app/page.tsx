import Link from "next/link";

export default function Home() {
  return (
    <div>
      <nav className="nav"><div className="brand">MITROS</div><div className="navlinks"><Link href="/">Overview</Link><Link href="/markets">Markets</Link><Link href="/operations">Operations</Link></div></nav>
      <main className="main">
        <div className="eyebrow">Market Intelligence & Trading Operating System</div>
        <h1>Decision infrastructure, not a black box.</h1>
        <p className="subtle">Verified system state with a preserved Strategy → Risk → Human Approval → Execution boundary.</p>
        <div className="grid">
          <section className="card"><div className="eyebrow">Market data</div><div className="metric">Verified</div><p className="subtle">Provider provenance and quote timestamps remain visible.</p></section>
          <section className="card"><div className="eyebrow">Execution</div><div className="metric">Paper</div><p className="subtle">Live trading is disabled by default.</p></section>
          <section className="card"><div className="eyebrow">Approval</div><div className="metric">Human</div><p className="subtle">No UI action bypasses explicit approval.</p></section>
        </div>
      </main>
    </div>
  );
}
