"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { createClient } from "../lib/supabase/client";

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

function isPublicAuthRoute(pathname: string) {
  return pathname === "/login" || pathname.startsWith("/auth/");
}

export default function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  const pathname = usePathname();
  const [email, setEmail] = useState("Account");

  useEffect(() => {
    if (isPublicAuthRoute(pathname)) return;

    const supabase = createClient();
    void supabase.auth.getClaims().then(({ data }) => {
      const claimEmail = data?.claims?.email;
      if (typeof claimEmail === "string") setEmail(claimEmail);
    });
  }, [pathname]);

  if (isPublicAuthRoute(pathname)) {
    return <>{children}</>;
  }

  return (
    <>
      <nav className="nav">
        <Link className="brand" href="/">MITROS</Link>
        <div className="navlinks" aria-label="Primary navigation">
          {primary.map(([href, label]) => (
            <Link key={href} href={href}>{label}</Link>
          ))}
          <Link href="/account">{email}</Link>
        </div>
      </nav>
      {children}
    </>
  );
}
