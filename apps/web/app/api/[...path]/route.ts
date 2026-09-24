import { NextResponse } from "next/server";
import { createClient } from "../../../lib/supabase/server";

export const dynamic = "force-dynamic";

function upstreamBaseUrl(): string {
  return process.env.MITROS_API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_MITROS_API_URL ?? "https://mitros.onrender.com";
}

export async function GET(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  const supabase = await createClient();
  const { data: claimsData } = await supabase.auth.getClaims();
  if (!claimsData?.claims?.sub) {
    return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  }

  const { data: sessionData } = await supabase.auth.getSession();
  const accessToken = sessionData.session?.access_token;
  if (!accessToken) {
    return NextResponse.json({ detail: "Authenticated session unavailable" }, { status: 401 });
  }

  const { path } = await context.params;
  const incoming = new URL(request.url);
  const target = new URL("/api/" + path.join("/"), upstreamBaseUrl());
  target.search = incoming.search;

  const response = await fetch(target, {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: "Bearer " + accessToken,
      "X-MITROS-Request-ID": crypto.randomUUID(),
    },
    cache: "no-store",
  });

  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
  });
}
