import { requireUser } from "@/lib/auth";
import Nav from "./components/nav";
import SearchPanel from "./search-panel";

export default async function HomePage() {
  const user = await requireUser();

  return (
    <div className="shell">
      <Nav displayName={user.display_name} role={user.role} />
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

