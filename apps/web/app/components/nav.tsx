"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type NavProps = {
  displayName: string;
  role: string;
};

export default function Nav({ displayName, role }: NavProps) {
  const pathname = usePathname();

  return (
    <header className="topbar">
      <div>
        <strong>FunPayBot</strong>
        <div className="muted">{displayName} · {role}</div>
      </div>
      <nav className="nav">
        <Link href="/" className={pathname === "/" ? "nav-active" : ""}>Search</Link>
        <Link href="/accounts" className={pathname === "/accounts" ? "nav-active" : ""}>Accounts</Link>
        {role === "admin" ? (
          <Link href="/admin" className={pathname.startsWith("/admin") ? "nav-active" : ""}>Admin</Link>
        ) : null}
        <form action="/api/auth/logout" method="post">
          <button className="button secondary" type="submit">Sign out</button>
        </form>
      </nav>
    </header>
  );
}
