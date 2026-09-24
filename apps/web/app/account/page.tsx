import { redirect } from "next/navigation";
import { createClient } from "../../lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function AccountPage() {
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();
  if (!data?.claims?.sub) redirect("/login");

  const claims = data.claims as Record<string, unknown>;
  const metadata = (claims.app_metadata ?? {}) as Record<string, unknown>;
  const entitlements = Array.isArray(metadata.entitlements)
    ? metadata.entitlements.filter((v): v is string => typeof v === "string")
    : ["free"];
  const role = typeof metadata.role === "string" ? metadata.role : "user";

  return (
    <main className="main">
      <div className="eyebrow">Identity & access</div>
      <h1>Account</h1>
      <section className="card panel">
        <p><strong>User ID:</strong> {String(claims.sub)}</p>
        <p><strong>Email:</strong> {String(claims.email ?? "not exposed")}</p>
        <p><strong>Role:</strong> {role}</p>
        <p><strong>Entitlements:</strong> {entitlements.join(", ")}</p>
        <p><strong>Assurance:</strong> {String(claims.aal ?? "aal1")}</p>
        <form action="/auth/signout" method="post"><button className="button" type="submit">Sign out</button></form>
      </section>
    </main>
  );
}
