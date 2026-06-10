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
          <h1>Поиск лотов</h1>
          <p className="muted">Ищите в настроенной категории или подбирайте подходящие категории FunPay по всему сайту перед фильтрацией лотов.</p>
        </section>
        <SearchPanel />
      </main>
    </div>
  );
}
