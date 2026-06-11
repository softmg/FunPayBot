import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { sessionCookie } from "@/lib/auth";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  cookieStore.delete(sessionCookie);
  // 303 so the browser issues a GET to /login instead of replaying the POST.
  return NextResponse.redirect(new URL("/login", request.url), 303);
}

