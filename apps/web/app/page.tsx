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
          <p className="muted">Search in the configured category or discover matching FunPay categories across the site before filtering lots.</p>
        </section>
        <SearchPanel />
      </main>
    </div>
  );
}
