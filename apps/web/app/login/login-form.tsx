"use client";

import { useState } from "react";

export default function LoginForm() {
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(formData: FormData) {
    setPending(true);
    setError("");
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        email: formData.get("email"),
        password: formData.get("password")
      })
    });
    setPending(false);
    if (!response.ok) {
      setError("Неверный email или пароль.");
      return;
    }
    window.location.href = "/";
  }

  return (
    <form action={submit} className="grid">
      <label className="field">
        <span className="label">Почта</span>
        <input className="input" name="email" type="email" required />
      </label>
      <label className="field">
        <span className="label">Пароль</span>
        <input className="input" name="password" type="password" required />
      </label>
      {error ? <p style={{ color: "#b42318" }}>{error}</p> : null}
      <button className="button" disabled={pending} type="submit">
        {pending ? "Входим" : "Войти"}
      </button>
    </form>
  );
}
