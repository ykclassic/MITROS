import OperationsPanel from "./operations-panel";

export default function OperationsPage() {
  return <main className="main"><div className="eyebrow">Production hardening</div><h1>Operations</h1><p className="subtle">Operational state is observable here; it cannot be changed from the dashboard.</p><OperationsPanel /></main>;
}
