import OperationsPanel from "./operations-panel";

export default function OperationsPage() {
  return (
    <div>
      <nav className="nav"><div className="brand">MITROS</div><div className="navlinks"><a href="/">Overview</a><a href="/markets">Markets</a><a href="/operations">Operations</a></div></nav>
      <main className="main"><div className="eyebrow">Production hardening</div><h1>Operations</h1><p className="subtle">Operational state is observable here; it cannot be changed from the dashboard.</p><OperationsPanel /></main>
    </div>
  );
}
