import MarketTable from "./market-table";

export default function MarketsPage() {
  return (
    <div>
      <nav className="nav"><div className="brand">MITROS</div><div className="navlinks"><a href="/">Overview</a><a href="/markets">Markets</a><a href="/operations">Operations</a></div></nav>
      <main className="main"><div className="eyebrow">Authoritative market data</div><h1>Markets</h1><p className="subtle">Quotes come from the backend router. Provider keys never reach the browser.</p><MarketTable /></main>
    </div>
  );
}
