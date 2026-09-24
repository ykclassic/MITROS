import Link from "next/link";
import { createClient } from "../lib/supabase/server";

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

export default async function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();
  const email = typeof data?.claims?.email === "string" ? data.claims.email : "Account";

  return (
    <>
      <nav className="nav">
        <Link className="brand" href="/">MITROS</Link>
        <div className="navlinks" aria-label="Primary navigation">
          {primary.map(([href, label]) => <Link key={href} href={href}>{label}</Link>)}
          <Link href="/account">{email}</Link>
        </div>
      </nav>
      {children}
    </>
  );
}
