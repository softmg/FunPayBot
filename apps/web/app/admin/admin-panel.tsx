"use client";

import { useState, useEffect, useCallback } from "react";
import { Trash2, UserPlus, Save, Shield, Users, Ban } from "lucide-react";

type User = {
  id: string;
  email: string;
  role: string;
  display_name: string;
  telegram_user_id: number | null;
  is_active: boolean;
  created_at: string;
};

type ForbiddenWord = {
  id: string;
  word: string;
  created_at: string;
};

type Tab = "users" | "words" | "settings";

export default function AdminPanel() {
  const [tab, setTab] = useState<Tab>("users");

  return (
    <div className="grid">
      <div className="tab-bar">
        <button className={`tab ${tab === "users" ? "tab-active" : ""}`} onClick={() => setTab("users")}>
          <Users size={16} /> Users
        </button>
        <button className={`tab ${tab === "words" ? "tab-active" : ""}`} onClick={() => setTab("words")}>
          <Ban size={16} /> Forbidden Words
        </button>
        <button className={`tab ${tab === "settings" ? "tab-active" : ""}`} onClick={() => setTab("settings")}>
          <Shield size={16} /> Settings
        </button>
      </div>
      {tab === "users" ? <UsersTab /> : null}
      {tab === "words" ? <WordsTab /> : null}
      {tab === "settings" ? <SettingsTab /> : null}
    </div>
  );
}

function UsersTab() {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  const load = useCallback(async () => {
    const res = await fetch("/api/admin/users");
    if (res.ok) {
      const data = await res.json();
      setUsers(data.users);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function toggleActive(user: User) {
    setError("");
    const res = await fetch("/api/admin/users", {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ id: user.id, is_active: !user.is_active }),
    });
    if (!res.ok) { setError("Failed to update user."); return; }
    await load();
  }

  async function createUser(formData: FormData) {
    setError("");
    const telegramId = formData.get("telegram_user_id");
    const res = await fetch("/api/admin/users", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        email: formData.get("email"),
        password: formData.get("password"),
        role: formData.get("role"),
        display_name: formData.get("display_name"),
        telegram_user_id: telegramId ? Number(telegramId) : undefined,
      }),
    });
    if (!res.ok) {
      const data = await res.json();
      setError(data.error ?? "Failed to create user.");
      return;
    }
    setShowCreate(false);
    await load();
  }

  return (
    <div className="panel grid">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Users</h2>
        <button className="button" onClick={() => setShowCreate(!showCreate)}>
          <UserPlus size={16} /> Add User
        </button>
      </div>

      {error ? <div className="error-text">{error}</div> : null}

      {showCreate ? (
        <form action={createUser} className="create-form">
          <input className="input" name="email" type="email" placeholder="Email" required />
          <input className="input" name="password" type="password" placeholder="Password (min 6)" required />
          <input className="input" name="display_name" placeholder="Display Name" required />
          <select className="input" name="role" defaultValue="manager">
            <option value="manager">Manager</option>
            <option value="admin">Admin</option>
          </select>
          <input className="input" name="telegram_user_id" type="number" placeholder="Telegram ID (optional)" />
          <button className="button" type="submit">Create</button>
        </form>
      ) : null}

      <table className="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Role</th>
            <th>Telegram ID</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.display_name}</td>
              <td>{u.email}</td>
              <td><span className="status">{u.role}</span></td>
              <td>{u.telegram_user_id ?? <span className="muted">—</span>}</td>
              <td><span className={`status ${u.is_active ? "status-active" : "status-blocked"}`}>{u.is_active ? "Active" : "Disabled"}</span></td>
              <td>
                <button className="button secondary" onClick={() => toggleActive(u)}>
                  {u.is_active ? "Disable" : "Enable"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function WordsTab() {
  const [words, setWords] = useState<ForbiddenWord[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const res = await fetch("/api/admin/forbidden-words");
    if (res.ok) {
      const data = await res.json();
      setWords(data.words);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function addWord(formData: FormData) {
    setError("");
    const res = await fetch("/api/admin/forbidden-words", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ word: formData.get("word") }),
    });
    if (!res.ok) {
      const data = await res.json();
      setError(data.error ?? "Failed to add word.");
      return;
    }
    (document.getElementById("word-input") as HTMLInputElement).value = "";
    await load();
  }

  async function removeWord(id: string) {
    setError("");
    const res = await fetch("/api/admin/forbidden-words", {
      method: "DELETE",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ id }),
    });
    if (!res.ok) { setError("Failed to delete word."); return; }
    await load();
  }

  return (
    <div className="panel grid">
      <h2>Forbidden Words</h2>
      <p className="muted">These words are automatically excluded from every lot search.</p>

      {error ? <div className="error-text">{error}</div> : null}

      <form action={addWord} style={{ display: "flex", gap: "8px" }}>
        <input className="input" id="word-input" name="word" placeholder="Add a forbidden word" required style={{ flex: 1 }} />
        <button className="button" type="submit">Add</button>
      </form>

      <div className="word-list">
        {words.map((w) => (
          <span className="word-chip" key={w.id}>
            {w.word}
            <button className="chip-delete" onClick={() => removeWord(w.id)} title="Remove">
              <Trash2 size={14} />
            </button>
          </span>
        ))}
        {words.length === 0 ? <span className="muted">No forbidden words configured.</span> : null}
      </div>
    </div>
  );
}

function SettingsTab() {
  const [settings, setSettings] = useState<Record<string, { value: string; updated_at: string }>>({});
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const SETTING_KEYS = [
    { key: "funpay_golden_key", label: "FunPay Golden Key", sensitive: true },
    { key: "funpay_user_agent", label: "FunPay User Agent", sensitive: false },
    { key: "funpay_base_url", label: "FunPay Base URL", sensitive: false },
    { key: "funpay_category_path", label: "FunPay Category Path", sensitive: false },
    { key: "funpay_max_actions_per_minute", label: "Max Actions/Min", sensitive: false },
    { key: "telegram_bot_token", label: "Telegram Bot Token", sensitive: true },
    { key: "admin_telegram_ids", label: "Admin Telegram IDs", sensitive: false },
  ];

  const load = useCallback(async () => {
    const res = await fetch("/api/admin/settings");
    if (res.ok) {
      const data = await res.json();
      setSettings(data.settings);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function save() {
    if (Object.keys(draft).length === 0) return;
    setSaving(true);
    setMessage("");
    const res = await fetch("/api/admin/settings", {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ settings: draft }),
    });
    setSaving(false);
    if (res.ok) {
      setMessage("Settings saved.");
      setDraft({});
      await load();
    } else {
      setMessage("Failed to save settings.");
    }
  }

  return (
    <div className="panel grid">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Settings</h2>
        <button className="button" disabled={saving || Object.keys(draft).length === 0} onClick={save}>
          <Save size={16} /> {saving ? "Saving" : "Save Changes"}
        </button>
      </div>

      {message ? <div className={message.includes("Failed") ? "error-text" : "success-text"}>{message}</div> : null}

      <div className="settings-grid">
        {SETTING_KEYS.map(({ key, label, sensitive }) => (
          <label className="field" key={key}>
            <span className="label">{label}</span>
            <input
              className="input"
              type={sensitive ? "password" : "text"}
              placeholder={settings[key]?.value ?? "Not set"}
              value={draft[key] ?? ""}
              onChange={(e) => {
                const val = e.target.value;
                setDraft((prev) => {
                  if (val === "") {
                    const next = { ...prev };
                    delete next[key];
                    return next;
                  }
                  return { ...prev, [key]: val };
                });
              }}
            />
            {settings[key] ? (
              <span className="muted" style={{ fontSize: "11px" }}>
                Last updated: {new Date(settings[key].updated_at).toLocaleString()}
              </span>
            ) : null}
          </label>
        ))}
      </div>
    </div>
  );
}
