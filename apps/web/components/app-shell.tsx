import Link from "next/link";

const primary = [
  ["/", "Overview"],
  ["/markets", "Markets"],
  ["/intelligence", "Intelligence"],
  ["/strategies", "Strategies"],
  ["/signals", "Signals"],
  ["/risk", "Risk"],
  ["/research", "Research"],
  ["/trading", "Trading"],
  ["/operations", "Operations"],
] as const;

export default function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <>
      <nav className="nav">
        <Link className="brand" href="/">MITROS</Link>
        <div className="navlinks" aria-label="Primary navigation">
          {primary.map(([href, label]) => <Link key={href} href={href}>{label}</Link>)}
        </div>
      </nav>
      {children}
    </>
  );
}
