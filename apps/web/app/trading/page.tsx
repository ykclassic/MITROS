import TradingPanel from "./trading-panel";

export default function TradingPage() {
  return <main className="main"><div className="eyebrow">Proposal and execution boundary</div><h1>Trading</h1><p className="subtle">Inspect current decision context without bypassing Risk → Human Approval → Execution Gateway.</p><TradingPanel /></main>;
}
