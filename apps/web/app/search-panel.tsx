"use client";

import { LoaderCircle, Search } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";

type Lot = {
  title: string;
  url: string;
  price: string | null;
  reviews: number;
  warranty: string | null;
};

export default function SearchPanel() {
  const [lots, setLots] = useState<Lot[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    const forbidden = String(formData.get("forbidden_words") ?? "")
      .split(",")
      .map((word) => word.trim())
      .filter(Boolean);

    const response = await fetch("/api/lots/search", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        query: formData.get("query"),
        search_scope: formData.get("search_scope"),
        max_price: formData.get("max_price") || undefined,
        min_reviews: formData.get("min_reviews") || 0,
        forbidden_words: forbidden
      })
    });
    setPending(false);
    if (!response.ok) {
      setError("Search failed. Check funpay-api logs and network access.");
      return;
    }
    const data = await response.json();
    setLots(data.results ?? []);
  }

  return (
    <div className="grid">
      <form className="panel search-grid" onSubmit={submit}>
        <label className="field">
          <span className="label">Query</span>
          <input className="input" name="query" placeholder="steam, gmail, ..." />
        </label>
        <label className="field">
          <span className="label">Search scope</span>
          <select className="input" defaultValue="category" name="search_scope">
            <option value="category">Current category</option>
            <option value="site">Whole site</option>
          </select>
        </label>
        <label className="field">
          <span className="label">Max price</span>
          <input className="input" name="max_price" min="0" step="0.01" type="number" />
        </label>
        <label className="field">
          <span className="label">Min reviews</span>
          <input className="input" defaultValue="0" min="0" name="min_reviews" type="number" />
        </label>
        <label className="field">
          <span className="label">Forbidden words</span>
          <input className="input" name="forbidden_words" placeholder="no warranty, banned" />
        </label>
        <button className="button" disabled={pending} type="submit">
          {pending ? <LoaderCircle className="spin" size={18} /> : <Search size={18} />}
          {pending ? "Searching" : "Search"}
        </button>
      </form>

      {pending ? (
        <div aria-live="polite" className="search-status">
          <span className="search-pulse" />
          Searching FunPay lots
        </div>
      ) : null}

      {error ? <div className="panel" style={{ color: "#b42318" }}>{error}</div> : null}

      <div className="panel">
        <table className="table">
          <thead>
            <tr>
              <th>Lot</th>
              <th>Price</th>
              <th>Reviews</th>
              <th>Warranty</th>
            </tr>
          </thead>
          <tbody>
            {lots.map((lot) => (
              <tr key={lot.url}>
                <td><a href={lot.url} rel="noreferrer" target="_blank">{lot.title}</a></td>
                <td>{lot.price ?? "Unknown"}</td>
                <td>{lot.reviews}</td>
                <td>{lot.warranty ?? <span className="muted">Not detected</span>}</td>
              </tr>
            ))}
            {lots.length === 0 ? (
              <tr><td className="muted" colSpan={4}>No results yet.</td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
