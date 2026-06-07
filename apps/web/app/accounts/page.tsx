import { requireUser } from "@/lib/auth";
import { query } from "@/lib/db";
import Nav from "../components/nav";

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
          <h1>Accounts DB</h1>
          <p className="muted">Confirmed credentials with FunPay chat context and refund status.</p>
        </section>
        <div className="panel">
          <table className="table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Credentials</th>
                <th>Seller</th>
                <th>Confirmed</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((account) => (
                <tr key={account.id}>
                  <td><span className="status">{account.status}</span></td>
                  <td>{account.credentials}</td>
                  <td>
                    {account.chat_url ? (
                      <a href={account.chat_url} rel="noreferrer" target="_blank">
                        {account.seller_name ?? "Chat"}
                      </a>
                    ) : (
                      <span className="muted">No chat</span>
                    )}
                  </td>
                  <td>{account.confirmed_by ?? "Unknown"}<br /><span className="muted">{new Date(account.confirmed_at).toLocaleString()}</span></td>
                </tr>
              ))}
              {accounts.length === 0 ? (
                <tr><td className="muted" colSpan={4}>No confirmed accounts yet.</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}

