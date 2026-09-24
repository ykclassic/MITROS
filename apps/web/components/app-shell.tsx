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
  const configured = Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY);
  let email = "Account";

  if (configured) {
    const supabase = await createClient();
    const { data } = await supabase.auth.getClaims();
    if (typeof data?.claims?.email === "string") email = data.claims.email;
  }

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
