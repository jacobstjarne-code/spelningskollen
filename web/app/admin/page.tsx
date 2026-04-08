"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface MatchEvent {
  id: number;
  artist: string;
  date: string;
  venue: string;
  source: string;
}

interface MatchCandidate {
  match_id: number;
  confidence: number;
  match_method: string;
  canonical: MatchEvent;
  candidate: MatchEvent;
}

interface CollectLogEntry {
  source: string;
  run_count: number;
  last_run: string;
  total_events: number;
  last_count: number;
  error_count: number;
  last_error: string | null;
  avg_duration_ms: number;
}

export default function AdminPage() {
  return (
    <Suspense fallback={<div style={{ padding: "40px", color: "var(--text-secondary)" }}>Laddar...</div>}>
      <AdminContent />
    </Suspense>
  );
}

function AdminContent() {
  const searchParams = useSearchParams();
  const key = searchParams.get("key") || "";

  const [candidates, setCandidates] = useState<MatchCandidate[]>([]);
  const [collectLog, setCollectLog] = useState<CollectLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [tab, setTab] = useState<"dedup" | "log">("dedup");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [dedupRes, logRes] = await Promise.all([
        fetch(`${API_BASE}/api/admin/match-candidates?key=${key}`),
        fetch(`${API_BASE}/api/admin/collect-log?key=${key}`),
      ]);
      if (dedupRes.status === 401) {
        setMessage("Ej behörig — ange ?key=xxx i URL:en");
        return;
      }
      setCandidates(await dedupRes.json());
      if (logRes.ok) setCollectLog(await logRes.json());
    } catch {
      setMessage("Kunde inte ladda data");
    } finally {
      setLoading(false);
    }
  }, [key]);

  useEffect(() => {
    load();
  }, [load]);

  const verify = async (match_id: number, action: "merge" | "reject") => {
    try {
      await fetch(`${API_BASE}/api/admin/match-verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ match_id, action, key }),
      });
      setCandidates((prev) => prev.filter((c) => c.match_id !== match_id));
    } catch {
      setMessage("Åtgärd misslyckades");
    }
  };

  if (message) {
    return (
      <div style={{ padding: "40px", color: "var(--text-secondary)", fontFamily: "monospace" }}>
        {message}
      </div>
    );
  }

  return (
    <div style={{ padding: "16px", maxWidth: "800px", margin: "0 auto" }}>
      <h1 style={{ fontSize: "18px", fontWeight: 700, marginBottom: "12px" }}>
        Admin
      </h1>

      <div style={{ display: "flex", gap: 6, marginBottom: 16 }}>
        {([["dedup", "Dedup-granskning"], ["log", "Insamlingslogg"]] as const).map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            style={{
              padding: "6px 14px",
              fontSize: 12,
              fontWeight: tab === id ? 700 : 400,
              borderRadius: 20,
              border: "none",
              cursor: "pointer",
              background: tab === id ? "var(--accent)" : "var(--card-bg)",
              color: tab === id ? "#fff" : "var(--text-secondary)",
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {loading && (
        <p style={{ color: "var(--text-secondary)", fontSize: "14px" }}>Laddar...</p>
      )}

      {!loading && tab === "log" && (
        <div>
          {collectLog.length === 0 ? (
            <p style={{ color: "var(--text-secondary)", fontSize: "14px" }}>Ingen logg ännu.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {collectLog.map((entry) => (
                <div key={entry.source} className="card-sharp" style={{ padding: "12px 14px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: 13 }}>{entry.source}</div>
                      <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>
                        Senast: {new Date(entry.last_run).toLocaleString("sv-SE")}
                        {" · "}
                        {entry.run_count} körningar
                        {" · "}
                        ~{Math.round(entry.avg_duration_ms / 1000)}s snitt
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text-primary)" }}>
                        {entry.last_count}
                      </div>
                      <div style={{ fontSize: 10, color: "var(--text-muted)" }}>events</div>
                    </div>
                  </div>
                  {entry.error_count > 0 && (
                    <div style={{
                      marginTop: 8,
                      padding: "6px 8px",
                      background: "rgba(239,68,68,0.08)",
                      borderRadius: 4,
                      fontSize: 11,
                      color: "#ef4444",
                    }}>
                      {entry.error_count} fel · {entry.last_error}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {!loading && tab === "dedup" && candidates.length === 0 && (
        <p style={{ color: "var(--text-secondary)", fontSize: "14px" }}>
          Inga kandidater att granska.
        </p>
      )}

      {tab === "dedup" && candidates.map((c) => (
        <div
          key={c.match_id}
          className="card-sharp"
          style={{ marginBottom: "12px", padding: "14px 16px" }}
        >
          <div
            style={{
              display: "flex",
              gap: "8px",
              alignItems: "center",
              marginBottom: "12px",
              fontSize: "11px",
              color: "var(--text-secondary)",
            }}
          >
            <span
              style={{
                background: c.confidence >= 0.95 ? "var(--accent)" : "var(--card-border)",
                color: c.confidence >= 0.95 ? "#fff" : "var(--text-primary)",
                padding: "2px 8px",
                borderRadius: "4px",
                fontWeight: 700,
              }}
            >
              {Math.round(c.confidence * 100)}%
            </span>
            <span>{c.match_method}</span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
            <EventBlock label="Kanonisk" ev={c.canonical} />
            <EventBlock label="Kandidat" ev={c.candidate} />
          </div>

          <div style={{ display: "flex", gap: "8px", marginTop: "12px" }}>
            <button
              className="btn-accent"
              style={{ flex: 1, padding: "8px", fontSize: "13px" }}
              onClick={() => verify(c.match_id, "merge")}
            >
              Slå ihop
            </button>
            <button
              style={{
                flex: 1,
                padding: "8px",
                fontSize: "13px",
                background: "var(--card-border)",
                color: "var(--text-primary)",
                border: "none",
                borderRadius: "4px",
                cursor: "pointer",
              }}
              onClick={() => verify(c.match_id, "reject")}
            >
              Inte samma
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

function EventBlock({ label, ev }: { label: string; ev: MatchEvent }) {
  return (
    <div>
      <div
        style={{
          fontSize: "10px",
          color: "var(--text-secondary)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: "4px",
        }}
      >
        {label}
      </div>
      <div style={{ fontWeight: 600, fontSize: "13px", marginBottom: "2px" }}>
        {ev.artist}
      </div>
      <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
        {ev.date} · {ev.venue || "—"}
      </div>
      <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "2px" }}>
        {ev.source}
      </div>
    </div>
  );
}
