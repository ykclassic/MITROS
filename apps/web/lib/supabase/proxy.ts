import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export async function updateSession(request: NextRequest) {
  const requestHeaders = new Headers(request.headers);
  let response = NextResponse.next({ request: { headers: requestHeaders } });

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  const pathname = request.nextUrl.pathname;
  const isPublic = pathname === "/login" || pathname.startsWith("/auth/");
  const isApi = pathname.startsWith("/api/");

  // Tell the root layout whether this request is a public auth route so the
  // authenticated application navigation is not rendered around the login UI.
  if (isPublic) {
    requestHeaders.set("x-mitros-public-route", "1");
  } else {
    requestHeaders.delete("x-mitros-public-route");
  }
  response = NextResponse.next({ request: { headers: requestHeaders } });

  if (!url || !key) {
    if (!isPublic) return new NextResponse("Authentication configuration is unavailable", { status: 503 });
    return response;
  }

  const supabase = createServerClient(url, key, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request: { headers: requestHeaders } });
        cookiesToSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
      },
    },
  });

  const { data: claimsData } = await supabase.auth.getClaims();
  const claims = claimsData?.claims;

  if (!isPublic && !isApi && !claims?.sub) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return response;
}
