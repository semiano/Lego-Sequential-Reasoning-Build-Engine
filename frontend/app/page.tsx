"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { Workspace } from "@/lib/types";

export default function HomePage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [name, setName] = useState("hummingbird-test");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    try {
      setWorkspaces(await api.listWorkspaces());
    } catch (err) {
      setError((err as Error).message);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const onCreate = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.createWorkspace(name);
      setName("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main style={{ padding: 24, maxWidth: 980, margin: "0 auto" }}>
      <h1>LeoCAD Tool Kit v0</h1>
      <p>Backend: {api.base}</p>

      <form onSubmit={onCreate} style={{ display: "flex", gap: 8, marginBottom: 24 }}>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="workspace name"
          style={{ flex: 1, padding: 10, borderRadius: 6, border: "1px solid #2e3540", background: "#161b22", color: "#e8edf2" }}
          required
        />
        <button
          type="submit"
          disabled={loading}
          style={{ padding: "10px 16px", borderRadius: 6, border: "1px solid #3d7dff", background: "#245fe6", color: "white" }}
        >
          {loading ? "Creating..." : "Create Workspace"}
        </button>
      </form>

      {error && <p style={{ color: "#ff6b6b" }}>{error}</p>}

      <h2>Workspaces</h2>
      <ul style={{ display: "grid", gap: 8, listStyle: "none", padding: 0 }}>
        {workspaces.map((workspace) => (
          <li key={workspace.id} style={{ background: "#161b22", padding: 12, borderRadius: 8, border: "1px solid #2e3540" }}>
            <Link href={`/models/${workspace.id}`}>{workspace.name}</Link>
            <div style={{ fontSize: 12, opacity: 0.8 }}>
              step {workspace.current_step} · created {new Date(workspace.created_at).toLocaleString()}
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}
