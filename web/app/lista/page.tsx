"use client";

import { useEffect, useState } from "react";
import { ListItem, getMyList, updateListItem, removeFromList, formatDate } from "@/lib/api";

const STATUS_OPTIONS = [
  { value: "interested", label: "Intresserad", icon: "♡" },
  { value: "going", label: "Ska gå", icon: "✓" },
  { value: "bought_ticket", label: "Biljett köpt", icon: "🎫" },
];

const FILTER_TABS = [
  { key: "all", label: "Alla" },
  { key: "bought_ticket", label: "🎫 Biljetter" },
  { key: "going", label: "✓ Ska gå" },
  { key: "interested", label: "♡ Sparade" },
];

export default function ListaPage() {
  const [items, setItems] = useState<ListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  const loadList = async () => {
    try {
      const data = await getMyList();
      setItems(data);
    } catch (err) {
      console.error("Kunde inte ladda listan:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadList(); }, []);

  const handleStatusChange = async (listId: number, newStatus: string) => {
    await updateListItem(listId, { status: newStatus });
    loadList();
  };

  const handleRemove = async (listId: number) => {
    await removeFromList(listId);
    loadList();
  };

  const filtered = filter === "all" ? items : items.filter((i) => i.status === filter);
  const ticketCount = items.filter((i) => i.status === "bought_ticket").length;
  const goingCount = items.filter((i) => i.status === "going").length;

  return (
    <div style={{ paddingTop: 16 }}>
      <div style={{ marginBottom: 20 }}>
        <div className="section-label" style={{ marginBottom: 6 }}>♡ MIN LISTA</div>
        <h1 style={{ fontFamily: "var(--font-display)", fontSize: 24, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
          Sparade spelningar
        </h1>
        <div style={{ display: "flex", gap: 12, marginTop: 6, fontSize: 11 }}>
          <span style={{ color: "var(--accent-bright)" }}>🎫 {ticketCount} biljetter</span>
          <span style={{ color: "var(--text-secondary)" }}>✓ {goingCount} ska gå</span>
          <span style={{ color: "var(--text-muted)" }}>♡ {items.length} totalt</span>
        </div>
      </div>

      {/* Filterflikar */}
      <div style={{ display: "flex", gap: 6, marginBottom: 16, overflowX: "auto" }}>
        {FILTER_TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={filter === key ? "btn btn-accent" : "btn btn-ghost"}
            style={{ whiteSpace: "nowrap", fontSize: 11, padding: "6px 12px" }}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "48px 0" }}>Laddar...</div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: "center", padding: "48px 0" }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>📋</div>
          <p style={{ color: "var(--text-muted)" }}>
            {filter === "all" ? "Din lista är tom. Hitta spelningar att spara!" : "Inga med den statusen."}
          </p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {filtered.map((item, i) => (
            <div
              key={item.list_id}
              className={`card animate-in stagger-${Math.min(i + 1, 5)}`}
              style={{ display: "flex", gap: 10, padding: "10px 12px" }}
            >
              {/* Datum */}
              <div style={{ flexShrink: 0, width: 40, textAlign: "center", paddingTop: 2 }}>
                <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: 1.5, textTransform: "uppercase" as const, color: "var(--text-muted)" }}>
                  {formatDate(item.date).split(" ")[0]}
                </div>
                <div style={{ fontFamily: "var(--font-display)", fontSize: 22, fontWeight: 700, color: "var(--text-primary)", lineHeight: 1.1 }}>
                  {new Date(item.date + "T00:00:00").getDate()}
                </div>
                <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase" as const }}>
                  {formatDate(item.date).split(" ")[2]}
                </div>
              </div>

              {/* Info */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 700, fontSize: 14, color: "var(--text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {item.artist}
                </div>
                <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>
                  {item.venue_name} · {item.city}
                  {item.time && ` · ${item.time.slice(0, 5)}`}
                </div>
                {item.ticket_url && (
                  <a
                    href={item.ticket_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ fontSize: 10, color: "var(--accent)", textDecoration: "none", marginTop: 4, display: "inline-block" }}
                  >
                    Biljettlänk →
                  </a>
                )}
              </div>

              {/* Status + ta bort */}
              <div style={{ display: "flex", flexDirection: "column", gap: 4, flexShrink: 0, alignItems: "flex-end" }}>
                <select
                  value={item.status}
                  onChange={(e) => handleStatusChange(item.list_id!, e.target.value)}
                  style={{
                    background: "var(--bg-elevated)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-xs)",
                    padding: "4px 6px",
                    fontSize: 10,
                    color: "var(--text-primary)",
                    outline: "none",
                  }}
                >
                  {STATUS_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.icon} {opt.label}
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => handleRemove(item.list_id!)}
                  style={{
                    background: "none",
                    border: "none",
                    color: "var(--text-muted)",
                    fontSize: 10,
                    cursor: "pointer",
                    padding: "2px 4px",
                  }}
                >
                  Ta bort
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
