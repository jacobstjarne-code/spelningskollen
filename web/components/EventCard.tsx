"use client";

import { Event, formatDate, formatPrice, addToList, updateListItem } from "@/lib/api";
import { useState, useRef } from "react";

const VENUE_BAR_CLASS: Record<string, string> = {
  arena: "venue-bar-arena",
  club: "venue-bar-club",
  outdoor: "venue-bar-outdoor",
  festival: "venue-bar-festival",
};

const STATUS_PILL: Record<string, string> = {
  on_sale: "pill-on-sale",
  sold_out: "pill-sold-out",
  presale: "pill-presale",
};

const STATUS_LABEL: Record<string, string> = {
  on_sale: "Biljetter",
  sold_out: "Slutsålt",
  presale: "Förköp",
  announced: "Annonserad",
  unknown: "Biljetter",
};

const SAVE_OPTIONS = [
  { value: "interested", label: "Intresserad", icon: "♡" },
  { value: "going", label: "Köp biljett", icon: "🎟" },
  { value: "bought_ticket", label: "Har biljett", icon: "🎫" },
];

export default function EventCard({ event }: { event: Event }) {
  const [status, setStatus] = useState<string | null>(event.list_status);
  const [listId, setListId] = useState<number | null>(event.list_id);
  const [showMenu, setShowMenu] = useState(false);
  const [saving, setSaving] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const handleSave = async (newStatus: string) => {
    setSaving(true);
    setShowMenu(false);
    try {
      if (listId) {
        await updateListItem(listId, { status: newStatus });
      } else {
        await addToList(event.id, newStatus);
      }
      setStatus(newStatus);
      // Sätt listId om vi inte hade ett (för framtida uppdateringar)
      if (!listId) setListId(-1);
    } catch {
      // tyst retry
    } finally {
      setSaving(false);
    }
  };

  const currentOption = SAVE_OPTIONS.find((o) => o.value === status);
  const price = formatPrice(event.price_min, event.price_max);
  const barClass = VENUE_BAR_CLASS[event.venue_type || ""] || "venue-bar-club";
  const pillClass = STATUS_PILL[event.ticket_status] || "";

  return (
    <div className="card" style={{ display: "flex", gap: 10, padding: "10px 12px" }}>
      {/* Venue-typ bar */}
      <div className={`venue-bar ${barClass}`} />

      {/* Datum */}
      <div style={{ flexShrink: 0, width: 40, textAlign: "center", paddingTop: 2 }}>
        <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: 1.5, textTransform: "uppercase" as const, color: "var(--text-muted)" }}>
          {formatDate(event.date).split(" ")[0]}
        </div>
        <div style={{ fontFamily: "var(--font-display)", fontSize: 22, fontWeight: 700, color: "var(--text-primary)", lineHeight: 1.1 }}>
          {new Date(event.date + "T00:00:00").getDate()}
        </div>
        <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase" as const, letterSpacing: 0.5 }}>
          {formatDate(event.date).split(" ")[2]}
        </div>
      </div>

      {/* Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 700, fontSize: 14, color: "var(--text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {event.artist}
        </div>
        {event.title && event.title !== event.artist && (
          <div style={{ fontSize: 11, color: "var(--text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", marginTop: 1 }}>
            {event.title}
          </div>
        )}
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4, fontSize: 11, color: "var(--text-secondary)" }}>
          <span>{event.venue_name || "Okänd scen"}</span>
          {event.time && (
            <>
              <span style={{ color: "var(--text-muted)", fontSize: 8 }}>●</span>
              <span>{event.time.slice(0, 5)}</span>
            </>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 6 }}>
          {event.genre && (
            <span className="tag tag-ghost">{event.genre}</span>
          )}
          {price && (
            <span style={{ fontSize: 10, color: "var(--text-muted)" }}>{price}</span>
          )}
        </div>
      </div>

      {/* Knappar */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6, flexShrink: 0, alignItems: "flex-end", justifyContent: "center", position: "relative" }}>
        {/* Spara-knapp med meny */}
        <button
          onClick={() => status ? setShowMenu(!showMenu) : handleSave("interested")}
          disabled={saving}
          style={{
            background: status ? "rgba(212,60,126,0.12)" : "rgba(255,255,255,0.04)",
            color: status ? "var(--accent-bright)" : "var(--text-muted)",
            border: status ? "1px solid rgba(212,60,126,0.25)" : "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            padding: "5px 10px",
            fontSize: 11,
            fontWeight: 600,
            cursor: "pointer",
            transition: "all 150ms",
            whiteSpace: "nowrap",
          }}
        >
          {saving ? "·" : currentOption ? `${currentOption.icon} ${currentOption.label}` : "♡"}
        </button>

        {/* Dropdown-meny */}
        {showMenu && (
          <div
            ref={menuRef}
            style={{
              position: "absolute",
              top: "100%",
              right: 0,
              marginTop: 4,
              background: "var(--bg-elevated)",
              border: "1px solid var(--border-hover)",
              borderRadius: "var(--radius-sm)",
              overflow: "hidden",
              zIndex: 20,
              minWidth: 140,
              boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
            }}
          >
            {SAVE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => handleSave(opt.value)}
                style={{
                  display: "block",
                  width: "100%",
                  padding: "8px 12px",
                  fontSize: 11,
                  fontWeight: status === opt.value ? 700 : 500,
                  color: status === opt.value ? "var(--accent-bright)" : "var(--text-primary)",
                  background: status === opt.value ? "rgba(212,60,126,0.08)" : "transparent",
                  border: "none",
                  textAlign: "left",
                  cursor: "pointer",
                }}
              >
                {opt.icon} {opt.label}
              </button>
            ))}
          </div>
        )}

        {/* Biljettlänk */}
        {event.ticket_url && event.ticket_status !== "sold_out" && (
          <a
            href={event.ticket_url}
            target="_blank"
            rel="noopener noreferrer"
            className={pillClass}
            style={{
              borderRadius: "var(--radius-sm)",
              padding: "5px 10px",
              fontSize: 10,
              fontWeight: 600,
              textDecoration: "none",
              textAlign: "center",
              ...(pillClass ? {} : { background: "rgba(255,255,255,0.04)", color: "var(--text-secondary)", border: "1px solid var(--border)" }),
            }}
          >
            {STATUS_LABEL[event.ticket_status] || "Biljetter"}
          </a>
        )}
        {event.ticket_status === "sold_out" && (
          <span className="pill-sold-out" style={{ borderRadius: "var(--radius-sm)", padding: "5px 10px", fontSize: 10, fontWeight: 600 }}>
            Slutsålt
          </span>
        )}
      </div>
    </div>
  );
}
