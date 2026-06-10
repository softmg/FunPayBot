import { requireUser } from "@/lib/auth";
import { query } from "@/lib/db";
import Nav from "../components/nav";
import AccountsTable from "./accounts-table";

type AccountRow = {
  id: string;
  credentials: string;
  status: string;
  confirmed_at: string;
  confirmed_by: string | null;
  chat_url: string | null;
  seller_name: string | null;
};

export default async function AccountsPage() {
  const user = await requireUser();
  const accounts = await query<AccountRow>(`
    SELECT
      accounts.id,
      accounts.credentials,
      accounts.status,
      accounts.confirmed_at,
      users.display_name AS confirmed_by,
      funpay_chats.chat_url,
      funpay_chats.seller_name
    FROM accounts
    LEFT JOIN users ON users.id = accounts.confirmed_by
    LEFT JOIN funpay_chats ON funpay_chats.id = accounts.chat_id
    ORDER BY accounts.created_at DESC
    LIMIT 100
  `);

  return (
    <div className="shell">
      <Nav displayName={user.display_name} role={user.role} />
      <main className="main grid">
        <section>
          <h1>База аккаунтов</h1>
          <p className="muted">Подтверждённые данные аккаунтов, связанные чаты FunPay и статусы возврата.</p>
        </section>
        <AccountsTable initialAccounts={accounts} />
      </main>
    </div>
  );
}
