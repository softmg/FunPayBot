import Link from "next/link";
import { requireUser } from "@/lib/auth";
import SearchPanel from "./search-panel";

export default async function HomePage() {
  const user = await requireUser();

  return (
    <div className="shell">
      <header className="topbar">
        <div>
          <strong>FunPayBot</strong>
          <div className="muted">{user.display_name} · {user.role}</div>
        </div>
        <nav className="nav">
          <Link href="/">Search</Link>
          <Link href="/accounts">Accounts</Link>
          <form action="/api/auth/logout" method="post">
            <button className="button secondary" type="submit">Sign out</button>
          </form>
        </nav>
      </header>
      <main className="main grid">
        <section>
          <h1>Lot Search</h1>
          <p className="muted">Fixed category: lots/1355. Results are filtered before a manager starts the Telegram buy loop.</p>
        </section>
        <SearchPanel />
      </main>
    </div>
  );
}

