import MarketTable from "./market-table";

export default function MarketsPage() {
  return <main className="main"><div className="eyebrow">Authoritative market data</div><h1>Markets</h1><p className="subtle">Quotes come from the backend router. Provider keys never reach the browser.</p><MarketTable /></main>;
}
