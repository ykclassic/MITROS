import RiskPanel from "./risk-panel";

export default function RiskPage() {
  return <main className="main"><div className="eyebrow">Independent portfolio risk</div><h1>Risk</h1><p className="subtle">Risk is an independent gate. The dashboard can inspect a scenario but cannot authorize execution.</p><RiskPanel /></main>;
}
