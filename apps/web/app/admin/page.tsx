import { requireAdmin } from "@/lib/auth";
import Nav from "../components/nav";
import AdminPanel from "./admin-panel";

export default async function AdminPage() {
  const user = await requireAdmin();

  return (
    <div className="shell">
      <Nav displayName={user.display_name} role={user.role} />
      <main className="main grid">
        <section>
          <h1>Администрирование</h1>
          <p className="muted">Управление пользователями, запрещёнными словами и системными настройками.</p>
        </section>
        <AdminPanel />
      </main>
    </div>
  );
}
