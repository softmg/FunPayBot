import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { sessionCookie } from "@/lib/auth";

export async function POST() {
  const cookieStore = await cookies();
  cookieStore.delete(sessionCookie);
  return NextResponse.redirect(new URL("/login", process.env.NEXTAUTH_URL ?? "http://localhost:3000"));
}

