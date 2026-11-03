"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type SavedSearch = {
  id: number;
  name: string;
  query: {
    source: string;
    board: string;
    company_name?: string | null;
    keywords?: string[];
    location?: string | null;
    remote_only?: boolean;
  };
};

function csrf() {
  return decodeURIComponent(
    document.cookie.split("; ").find((item) => item.startsWith("jobseeker_csrf="))
      ?.split("=").slice(1).join("=") || "",
  );
}

async function api(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  if (init.method) headers.set("X-CSRF-Token", csrf());
  const response = await fetch(API + path, {
    ...init, headers, credentials: "include", cache: "no-store",
  });
  if (response.status === 401) window.location.assign("/login");
  return response;
}

export default function Discovery() {
  const [source, setSource] = useState<"greenhouse" | "lever">("greenhouse");
  const [board, setBoard] = useState("");
  const [company, setCompany] = useState("");
  const [name, setName] = useState("");
  const [keywords, setKeywords] = useState("");
  const [location, setLocation] = useState("");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [saved, setSaved] = useState<SavedSearch[]>([]);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const normalizedKeywords = () => [...new Set(
    keywords.split(/[,
]/).map((item) => item.trim()).filter(Boolean),
  )].slice(0, 20);

  async function load() {
    const response = await api("/api/v1/saved-searches");
    if (response.ok) setSaved(await response.json());
    else setError("Unable to load saved searches.");
  }

  useEffect(() => { void load(); }, []);

  async function discover(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    setResult(null);
    try {
      const response = await api("/api/v1/opportunities/discover", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source, board, company_name: company || null, limit: 100,
          keywords: normalizedKeywords(), location: location || null,
          remote_only: remoteOnly,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Discovery failed.");
      setResult(data);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Discovery failed.");
    } finally {
      setLoading(false);
    }
  }

  async function saveSearch(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setSaving(true);
    try {
      const response = await api("/api/v1/saved-searches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source, board, company_name: company || null,
          name: name.trim() || board + " job feed",
          keywords: normalizedKeywords(), location: location || null,
          remote_only: remoteOnly,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Unable to save search.");
      setName("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save search.");
    } finally {
      setSaving(false);
    }
  }

  async function removeSearch(id: number) {
    setError("");
    const response = await api("/api/v1/saved-searches/" + id, { method: "DELETE" });
    if (response.ok) await load();
    else setError("Unable to remove saved search.");
  }

  return (
    <main style={{ maxWidth: 1040, margin: "0 auto", padding: 32, color: "#edf5ef" }}>
      <a href="/dashboard" style={{ color: "#54d69a" }}>← Workspace</a>
      <header style={{ margin: "26px 0" }}>
        <p style={{ color: "#54d69a", letterSpacing: 2, fontSize: 11, fontWeight: 700 }}>CAREER INTELLIGENCE</p>
        <h1 style={{ fontSize: 34, margin: "8px 0" }}>Opportunity Radar</h1>
        <p style={{ color: "#9aaba2", maxWidth: 700 }}>
          Discover roles from public Greenhouse and Lever boards. Apply transparent filters,
          save recurring searches and keep original listing links with every opportunity.
        </p>
      </header>

      <form onSubmit={discover} style={panel}>
        <h2 style={sectionTitle}>Discover opportunities</h2>
        <div style={grid}>
          <label style={label}>Source
            <select style={input} value={source} onChange={(event) => setSource(event.target.value as "greenhouse" | "lever")}>
              <option value="greenhouse">Greenhouse</option>
              <option value="lever">Lever</option>
            </select>
          </label>
          <label style={label}>Board identifier
            <input style={input} required maxLength={80} placeholder="e.g. stripe" value={board} onChange={(event) => setBoard(event.target.value)} />
          </label>
          <label style={label}>Company display name
            <input style={input} maxLength={250} placeholder="Optional" value={company} onChange={(event) => setCompany(event.target.value)} />
          </label>
          <label style={label}>Location contains
            <input style={input} maxLength={120} placeholder="e.g. Nairobi, Africa" value={location} onChange={(event) => setLocation(event.target.value)} />
          </label>
        </div>
        <label style={{ ...label, marginTop: 14 }}>Keywords (comma or line separated)
          <input style={input} placeholder="Data Engineer, Python, Spark, dbt" value={keywords} onChange={(event) => setKeywords(event.target.value)} />
        </label>
        <label style={{ display: "flex", gap: 10, alignItems: "center", color: "#c2d1c8", marginTop: 16 }}>
          <input type="checkbox" checked={remoteOnly} onChange={(event) => setRemoteOnly(event.target.checked)} />
          Remote or distributed roles only
        </label>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 18 }}>
          <button style={primary} disabled={loading}>{loading ? "Searching…" : "Discover roles"}</button>
          <button type="button" style={secondary} disabled={saving} onClick={(event) => {
            const form = event.currentTarget.form;
            if (form) void saveSearch({ preventDefault: () => undefined } as React.FormEvent);
          }}>{saving ? "Saving…" : "Save these filters"}</button>
        </div>
        {error && <p role="alert" style={{ color: "#ff9b87" }}>{error}</p>}
        {result && <p role="status" style={{ color: "#8fe2b5" }}>
          Retrieved {result.fetched} roles, {result.matched_filters} matched your filters,
          {result.saved} saved and {result.duplicates_or_invalid} duplicates or invalid listings skipped.
        </p>}
      </form>

      <section style={{ ...panel, marginTop: 18 }}>
        <h2 style={sectionTitle}>Recurring searches</h2>
        <p style={{ color: "#9aaba2" }}>The local scheduler refreshes configured feeds every six hours when discovery is enabled and automation is unpaused.</p>
        {saved.map((item) => (
          <article key={item.id} style={savedRow}>
            <div>
              <strong>{item.name}</strong>
              <div style={{ color: "#9aaba2", fontSize: 13, marginTop: 5 }}>
                {item.query.source} · {item.query.board}
                {item.query.location ? " · " + item.query.location : ""}
                {item.query.remote_only ? " · Remote only" : ""}
              </div>
              {!!item.query.keywords?.length && (
                <div style={{ color: "#8fe2b5", fontSize: 12, marginTop: 5 }}>
                  {item.query.keywords.join(" · ")}
                </div>
              )}
            </div>
            <button type="button" onClick={() => void removeSearch(item.id)} style={removeButton}>Remove</button>
          </article>
        ))}
        {saved.length === 0 && <p style={{ color: "#9aaba2" }}>No recurring searches configured.</p>}
      </section>
    </main>
  );
}

const panel: React.CSSProperties = { background: "#111a16", border: "1px solid #25352d", borderRadius: 16, padding: 22 };
const sectionTitle: React.CSSProperties = { margin: "0 0 16px", fontSize: 19 };
const grid: React.CSSProperties = { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 14 };
const label: React.CSSProperties = { display: "block", color: "#a7b8ad", fontSize: 13 };
const input: React.CSSProperties = { display: "block", width: "100%", boxSizing: "border-box", padding: 12, marginTop: 7, background: "#09110d", border: "1px solid #34483c", borderRadius: 9, color: "#edf5ef" };
const primary: React.CSSProperties = { background: "#54d69a", color: "#07110c", border: 0, padding: "12px 16px", borderRadius: 9, fontWeight: 700, cursor: "pointer", marginTop: 4 };
const secondary: React.CSSProperties = { background: "#1c3829", color: "#54d69a", border: "1px solid #345744", padding: "12px 16px", borderRadius: 9, cursor: "pointer", marginTop: 4 };
const removeButton: React.CSSProperties = { background: "transparent", color: "#d79b91", border: "1px solid #63423e", padding: "7px 10px", borderRadius: 8, cursor: "pointer" };
const savedRow: React.CSSProperties = { display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, padding: "14px 0", borderTop: "1px solid #25352d" };
