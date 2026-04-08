"use client";

import { useEffect, useState, useCallback } from "react";
import { Event, Venue, getEvents, getVenues } from "@/lib/api";
import EventCard from "@/components/EventCard";
import Filters from "@/components/Filters";

type TimeTab = "ikväll" | "vecka" | "kommande";

function getDateRange(tab: TimeTab): { from: string; to: string } {
  const today = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const fmt = (d: Date) =>
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

  const todayStr = fmt(today);

  if (tab === "ikväll") return { from: todayStr, to: todayStr };

  const week = new Date(today);
  week.setDate(today.getDate() + 7);
  if (tab === "vecka") return { from: todayStr, to: fmt(week) };

  const far = new Date(today);
  far.setDate(today.getDate() + 180);
  return { from: fmt(week), to: fmt(far) };
}

const TABS: { id: TimeTab; label: string }[] = [
  { id: "ikväll", label: "Ikväll" },
  { id: "vecka", label: "Denna vecka" },
  { id: "kommande", label: "Kommande" },
];

const formatGroupDate = (dateStr: string) => {
  const d = new Date(dateStr + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.floor((d.getTime() - today.getTime()) / 86400000);
  if (diff === 0) return "Idag";
  if (diff === 1) return "Imorgon";
  const days = ["Sön", "Mån", "Tis", "Ons", "Tor", "Fre", "Lör"];
  const months = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];
  return `${days[d.getDay()]} ${d.getDate()} ${months[d.getMonth()]}`;
};

export default function Home() {
  const [events, setEvents] = useState<Event[]>([]);
  const [venues, setVenues] = useState<Venue[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TimeTab>("vecka");
  const [city, setCity] = useState("");
  const [venue, setVenue] = useState("");
  const [search, setSearch] = useState("");

  const loadEvents = useCallback(async () => {
    setLoading(true);
    try {
      const range = getDateRange(tab);
      const params: Record<string, string> = { from: range.from, to: range.to };
      if (city) params.city = city;
      if (venue) params.venue = venue;
      if (search) params.search = search;
      const data = await getEvents(params);
      setEvents(data);
    } catch {
      // tyst fel
    } finally {
      setLoading(false);
    }
  }, [tab, city, venue, search]);

  useEffect(() => {
    getVenues().then(setVenues).catch(() => {});
  }, []);

  useEffect(() => {
    const timer = setTimeout(loadEvents, search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [loadEvents, search]);

  const grouped = events.reduce<Record<string, Event[]>>((acc, ev) => {
    if (!acc[ev.date]) acc[ev.date] = [];
    acc[ev.date].push(ev);
    return acc;
  }, {});

  return (
    <div style={{ paddingTop: 16 }}>
      {/* Hero */}
      <div style={{ marginBottom: 14 }}>
        <div className="section-label" style={{ marginBottom: 4 }}>🎵 KONSERTER & KLUBB</div>
        <h1 style={{
          fontFamily: "var(--font-display)", fontSize: 22, fontWeight: 700,
          color: "var(--text-primary)", margin: 0, lineHeight: 1.2,
        }}>
          {city || "Stockholm & Uppsala"}
        </h1>
      </div>

      {/* Tids-tabs */}
      <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              padding: "6px 12px",
              fontSize: 12,
              fontWeight: tab === t.id ? 700 : 400,
              borderRadius: 20,
              border: "none",
              cursor: "pointer",
              background: tab === t.id ? "var(--accent)" : "var(--card-bg)",
              color: tab === t.id ? "#fff" : "var(--text-secondary)",
              transition: "all 0.15s",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <Filters
        venues={venues}
        city={city}
        venue={venue}
        search={search}
        onCityChange={setCity}
        onVenueChange={setVenue}
        onSearchChange={setSearch}
      />

      {/* Event-count */}
      <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "4px 0 12px" }}>
        {loading ? "Laddar..." : `${events.length} spelningar`}
      </p>

      {loading ? (
        <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "40px 0" }}>
          <div style={{ fontSize: 24, marginBottom: 8 }}>🎵</div>
          Laddar...
        </div>
      ) : events.length === 0 ? (
        <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "40px 0" }}>
          <div style={{ fontSize: 32, marginBottom: 10 }}>🔇</div>
          <p>Inga spelningar {tab === "ikväll" ? "ikväll" : "den här perioden"}.</p>
          {search && <p style={{ fontSize: 12, marginTop: 4 }}>Prova ett annat sökord.</p>}
        </div>
      ) : (
        <div>
          {Object.entries(grouped).map(([dateStr, dateEvents]) => (
            <div key={dateStr} style={{ marginBottom: 16 }}>
              <div className="date-header">{formatGroupDate(dateStr)}</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {dateEvents.map((ev, i) => (
                  <div key={ev.id} className={`animate-in stagger-${Math.min(i + 1, 5)}`}>
                    <EventCard event={ev} />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
