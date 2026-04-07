"use client";

import { useEffect, useState, useCallback } from "react";
import { Event, Venue, getEvents, getVenues, formatDate } from "@/lib/api";
import EventCard from "@/components/EventCard";
import Filters from "@/components/Filters";

export default function Home() {
  const [events, setEvents] = useState<Event[]>([]);
  const [venues, setVenues] = useState<Venue[]>([]);
  const [loading, setLoading] = useState(true);
  const [city, setCity] = useState("");
  const [venue, setVenue] = useState("");
  const [search, setSearch] = useState("");

  const loadEvents = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (city) params.city = city;
      if (venue) params.venue = venue;
      if (search) params.search = search;
      const data = await getEvents(params);
      setEvents(data);
    } catch (err) {
      console.error("Kunde inte ladda events:", err);
    } finally {
      setLoading(false);
    }
  }, [city, venue, search]);

  useEffect(() => {
    getVenues().then(setVenues).catch(console.error);
  }, []);

  useEffect(() => {
    const timer = setTimeout(loadEvents, search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [loadEvents, search]);

  // Gruppera per datum
  const grouped = events.reduce<Record<string, Event[]>>((acc, ev) => {
    const key = ev.date;
    if (!acc[key]) acc[key] = [];
    acc[key].push(ev);
    return acc;
  }, {});

  const formatGroupDate = (dateStr: string) => {
    const d = new Date(dateStr + "T00:00:00");
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const diff = Math.floor((d.getTime() - today.getTime()) / 86400000);

    if (diff === 0) return "Idag";
    if (diff === 1) return "Imorgon";

    const days = ["Söndag", "Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag", "Lördag"];
    const months = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];
    return `${days[d.getDay()]} ${d.getDate()} ${months[d.getMonth()]}`;
  };

  return (
    <div style={{ paddingTop: 16 }}>
      {/* Hero-sektion */}
      <div style={{ marginBottom: 20 }}>
        <div className="section-label" style={{ marginBottom: 6 }}>
          🎵 KONSERTER & KLUBB
        </div>
        <h1 style={{
          fontFamily: "var(--font-display)",
          fontSize: 24,
          fontWeight: 700,
          color: "var(--text-primary)",
          margin: 0,
          lineHeight: 1.2,
        }}>
          {city || "Stockholm & Uppsala"}
        </h1>
        <p style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 4 }}>
          {loading ? "Laddar..." : `${events.length} kommande spelningar`}
        </p>
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

      {loading ? (
        <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "48px 0" }}>
          <div style={{ fontSize: 24, marginBottom: 8, animation: "breathe 2s infinite" }}>🎵</div>
          Laddar spelningar...
        </div>
      ) : events.length === 0 ? (
        <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "48px 0" }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>🔇</div>
          <p>Inga spelningar hittades.</p>
          {search && <p style={{ fontSize: 12, marginTop: 4 }}>Prova ett annat sökord.</p>}
        </div>
      ) : (
        <div>
          {Object.entries(grouped).map(([dateStr, dateEvents]) => (
            <div key={dateStr} style={{ marginBottom: 16 }}>
              <div className="date-header">
                {formatGroupDate(dateStr)}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {dateEvents.map((ev, i) => (
                  <div key={ev.id} className={`animate-in stagger-${Math.min(i + 1, 5)}`}>
                    <EventCard event={ev} onSaved={loadEvents} />
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
