"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type NavProps = {
  displayName: string;
  role: string;
};

export default function Nav({ displayName, role }: NavProps) {
  const pathname = usePathname();
  const roleLabel = role === "admin" ? "администратор" : "менеджер";

  return (
    <header className="topbar">
      <div>
        <strong>FunPayBot</strong>
        <div className="muted">{displayName} · {roleLabel}</div>
      </div>
      <nav className="nav">
        <Link href="/" className={pathname === "/" ? "nav-active" : ""}>Поиск</Link>
        <Link href="/accounts" className={pathname === "/accounts" ? "nav-active" : ""}>Аккаунты</Link>
        {role === "admin" ? (
          <Link href="/admin" className={pathname.startsWith("/admin") ? "nav-active" : ""}>Админка</Link>
        ) : null}
        <form action="/api/auth/logout" method="post">
          <button className="button secondary" type="submit">Выйти</button>
        </form>
      </nav>
    </header>
  );
}
