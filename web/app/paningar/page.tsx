"use client";

import { useEffect, useState } from "react";
import { ListItem, getMyList, formatDate } from "@/lib/api";

interface Reminder {
  type: "soon" | "ticket_release" | "upcoming";
  event: ListItem;
  daysUntil: number;
  message: string;
}

function calculateReminders(items: ListItem[]): Reminder[] {
  const reminders: Reminder[] = [];
  const now = new Date();
  now.setHours(0, 0, 0, 0);

  for (const item of items) {
    const eventDate = new Date(item.date + "T00:00:00");
    const daysUntil = Math.floor((eventDate.getTime() - now.getTime()) / 86400000);

    if (item.status === "bought_ticket" && daysUntil <= 3 && daysUntil >= 0) {
      reminders.push({
        type: "soon",
        event: item,
        daysUntil,
        message: daysUntil === 0
          ? `${item.artist} spelar IDAG!`
          : daysUntil === 1
          ? `${item.artist} spelar imorgon!`
          : `${item.artist} om ${daysUntil} dagar`,
      });
    }

    if (item.on_sale_date) {
      const saleDate = new Date(item.on_sale_date);
      const daysToSale = Math.floor((saleDate.getTime() - now.getTime()) / 86400000);
      if (daysToSale >= 0 && daysToSale <= 7) {
        reminders.push({
          type: "ticket_release",
          event: item,
          daysUntil: daysToSale,
          message: daysToSale === 0
            ? `Biljettsläpp IDAG — ${item.artist}`
            : `Biljettsläpp om ${daysToSale} dagar — ${item.artist}`,
        });
      }
    }

    if (item.status === "interested" && daysUntil <= 14 && daysUntil >= 0) {
      reminders.push({
        type: "upcoming",
        event: item,
        daysUntil,
        message: `${item.artist} om ${daysUntil} dagar — bestäm dig?`,
      });
    }
  }

  return reminders.sort((a, b) => a.daysUntil - b.daysUntil);
}

const TYPE_STYLES: Record<string, { border: string; icon: string; accent: string }> = {
  soon: { border: "var(--success)", icon: "🎫", accent: "var(--success)" },
  ticket_release: { border: "var(--warning)", icon: "🔔", accent: "var(--warning)" },
  upcoming: { border: "var(--accent)", icon: "📅", accent: "var(--accent)" },
};

export default function PaningarPage() {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getMyList()
      .then((items) => setReminders(calculateReminders(items)))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ paddingTop: 16 }}>
      <div style={{ marginBottom: 20 }}>
        <div className="section-label" style={{ marginBottom: 6 }}>🔔 PÅMINNELSER</div>
        <h1 style={{ fontFamily: "var(--font-display)", fontSize: 24, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
          Påningar
        </h1>
        <p style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 4 }}>
          Biljettsläpp, kommande spelningar, deadlines
        </p>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "48px 0" }}>Laddar...</div>
      ) : reminders.length === 0 ? (
        <div style={{ textAlign: "center", padding: "48px 0" }}>
          <div style={{ fontSize: 36, marginBottom: 12, opacity: 0.5 }}>🔕</div>
          <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Inga aktiva påminnelser</p>
          <p style={{ color: "var(--text-muted)", fontSize: 11, marginTop: 6 }}>
            Spara spelningar och markera &quot;Biljett köpt&quot; för att få påningar.
          </p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {reminders.map((r, i) => {
            const style = TYPE_STYLES[r.type];
            return (
              <div
                key={`${r.event.id}-${r.type}-${i}`}
                className={`card-glow animate-in stagger-${Math.min(i + 1, 5)}`}
                style={{
                  borderLeftWidth: 3,
                  borderLeftColor: style.border,
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 10,
                  padding: "12px 14px",
                }}
              >
                <span style={{ fontSize: 20, flexShrink: 0 }}>{style.icon}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: 13, color: "var(--text-primary)" }}>
                    {r.message}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 3 }}>
                    {r.event.venue_name} · {r.event.city} · {formatDate(r.event.date)}
                    {r.event.time && ` kl ${r.event.time.slice(0, 5)}`}
                  </div>
                </div>
                {r.event.ticket_url && (
                  <a
                    href={r.event.ticket_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      fontSize: 10,
                      color: style.accent,
                      textDecoration: "none",
                      fontWeight: 600,
                      flexShrink: 0,
                      whiteSpace: "nowrap",
                    }}
                  >
                    Biljetter →
                  </a>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
