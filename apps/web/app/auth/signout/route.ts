import { revalidatePath } from "next/cache";
import { NextResponse } from "next/server";
import { createClient } from "../../../lib/supabase/server";

export async function POST(request: Request) {
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();
  if (data?.claims?.sub) await supabase.auth.signOut();
  revalidatePath("/", "layout");
  return NextResponse.redirect(new URL("/login", request.url), { status: 303 });
}
