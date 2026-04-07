"use client";

import { Event, formatDate, formatPrice, addToList } from "@/lib/api";
import { useState } from "react";

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

export default function EventCard({ event, onSaved }: { event: Event; onSaved?: () => void }) {
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(!!event.list_status);

  const handleSave = async () => {
    if (saved) return;
    setSaving(true);
    try {
      await addToList(event.id);
      setSaved(true);
      onSaved?.();
    } catch {
      // retry
    } finally {
      setSaving(false);
    }
  };

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
      <div style={{ display: "flex", flexDirection: "column", gap: 6, flexShrink: 0, alignItems: "flex-end", justifyContent: "center" }}>
        <button
          onClick={handleSave}
          disabled={saving || saved}
          style={{
            background: saved ? "rgba(212,60,126,0.12)" : "rgba(255,255,255,0.04)",
            color: saved ? "var(--accent-bright)" : "var(--text-muted)",
            border: saved ? "1px solid rgba(212,60,126,0.25)" : "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            padding: "5px 10px",
            fontSize: 11,
            fontWeight: 600,
            cursor: saved ? "default" : "pointer",
            transition: "all 150ms",
          }}
        >
          {saved ? "✓" : saving ? "·" : "♡"}
        </button>
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
