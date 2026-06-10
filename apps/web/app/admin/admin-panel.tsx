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

const ROLE_LABELS: Record<string, string> = {
  admin: "Администратор",
  manager: "Менеджер",
};

export default function AdminPanel() {
  const [tab, setTab] = useState<Tab>("users");

  return (
    <div className="grid">
      <div className="tab-bar">
        <button className={`tab ${tab === "users" ? "tab-active" : ""}`} onClick={() => setTab("users")}>
          <Users size={16} /> Пользователи
        </button>
        <button className={`tab ${tab === "words" ? "tab-active" : ""}`} onClick={() => setTab("words")}>
          <Ban size={16} /> Запрещённые слова
        </button>
        <button className={`tab ${tab === "settings" ? "tab-active" : ""}`} onClick={() => setTab("settings")}>
          <Shield size={16} /> Настройки
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
    if (!res.ok) { setError("Не удалось обновить пользователя."); return; }
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
      setError(data.error ?? "Не удалось создать пользователя.");
      return;
    }
    setShowCreate(false);
    await load();
  }

  return (
    <div className="panel grid">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Пользователи</h2>
        <button className="button" onClick={() => setShowCreate(!showCreate)}>
          <UserPlus size={16} /> Добавить
        </button>
      </div>

      {error ? <div className="error-text">{error}</div> : null}

      {showCreate ? (
        <form action={createUser} className="create-form">
          <input className="input" name="email" type="email" placeholder="Почта" required />
          <input className="input" name="password" type="password" placeholder="Пароль (мин. 6)" required />
          <input className="input" name="display_name" placeholder="Отображаемое имя" required />
          <select className="input" name="role" defaultValue="manager">
            <option value="manager">Менеджер</option>
            <option value="admin">Администратор</option>
          </select>
          <input className="input" name="telegram_user_id" type="number" placeholder="Telegram ID (необязательно)" />
          <button className="button" type="submit">Создать</button>
        </form>
      ) : null}

      <table className="table">
        <thead>
          <tr>
            <th>Имя</th>
            <th>Почта</th>
            <th>Роль</th>
            <th>Telegram ID</th>
            <th>Статус</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.display_name}</td>
              <td>{u.email}</td>
              <td><span className="status">{ROLE_LABELS[u.role] ?? u.role}</span></td>
              <td>{u.telegram_user_id ?? <span className="muted">—</span>}</td>
              <td><span className={`status ${u.is_active ? "status-active" : "status-blocked"}`}>{u.is_active ? "Активен" : "Отключён"}</span></td>
              <td>
                <button className="button secondary" onClick={() => toggleActive(u)}>
                  {u.is_active ? "Отключить" : "Включить"}
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
      setError(data.error ?? "Не удалось добавить слово.");
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
    if (!res.ok) { setError("Не удалось удалить слово."); return; }
    await load();
  }

  return (
    <div className="panel grid">
      <h2>Запрещённые слова</h2>
      <p className="muted">Эти слова автоматически исключаются из каждого поиска лотов.</p>

      {error ? <div className="error-text">{error}</div> : null}

      <form action={addWord} style={{ display: "flex", gap: "8px" }}>
        <input className="input" id="word-input" name="word" placeholder="Добавить запрещённое слово" required style={{ flex: 1 }} />
        <button className="button" type="submit">Добавить</button>
      </form>

      <div className="word-list">
        {words.map((w) => (
          <span className="word-chip" key={w.id}>
            {w.word}
            <button className="chip-delete" onClick={() => removeWord(w.id)} title="Удалить">
              <Trash2 size={14} />
            </button>
          </span>
        ))}
        {words.length === 0 ? <span className="muted">Запрещённые слова не настроены.</span> : null}
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
    { key: "funpay_user_agent", label: "User Agent для FunPay", sensitive: false },
    { key: "funpay_base_url", label: "Базовый URL FunPay", sensitive: false },
    { key: "funpay_category_path", label: "Путь категории FunPay", sensitive: false },
    { key: "funpay_max_actions_per_minute", label: "Макс. действий в минуту", sensitive: false },
    { key: "telegram_bot_token", label: "Токен Telegram-бота", sensitive: true },
    { key: "admin_telegram_ids", label: "Telegram ID админов", sensitive: false },
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
      setMessage("Настройки сохранены.");
      setDraft({});
      await load();
    } else {
      setMessage("Не удалось сохранить настройки.");
    }
  }

  return (
    <div className="panel grid">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Настройки</h2>
        <button className="button" disabled={saving || Object.keys(draft).length === 0} onClick={save}>
          <Save size={16} /> {saving ? "Сохраняем" : "Сохранить"}
        </button>
      </div>

      {message ? <div className={message.includes("Не удалось") ? "error-text" : "success-text"}>{message}</div> : null}

      <div className="settings-grid">
        {SETTING_KEYS.map(({ key, label, sensitive }) => (
          <label className="field" key={key}>
            <span className="label">{label}</span>
            <input
              className="input"
              type={sensitive ? "password" : "text"}
              placeholder={settings[key]?.value ?? "Не задано"}
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
                Обновлено: {new Date(settings[key].updated_at).toLocaleString()}
              </span>
            ) : null}
          </label>
        ))}
      </div>
    </div>
  );
}
