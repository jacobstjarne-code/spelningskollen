"use client";

import { Venue } from "@/lib/api";

interface FiltersProps {
  venues: Venue[];
  city: string;
  venue: string;
  search: string;
  onCityChange: (city: string) => void;
  onVenueChange: (venue: string) => void;
  onSearchChange: (search: string) => void;
}

const selectStyle: React.CSSProperties = {
  background: "var(--bg-surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-sm)",
  padding: "7px 12px",
  fontSize: 12,
  color: "var(--text-primary)",
  outline: "none",
  appearance: "none",
  WebkitAppearance: "none",
};

export default function Filters({
  venues,
  city,
  venue,
  search,
  onCityChange,
  onVenueChange,
  onSearchChange,
}: FiltersProps) {
  const filteredVenues = city
    ? venues.filter((v) => v.city === city)
    : venues;

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
      <input
        type="text"
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
        placeholder="Sök artist..."
        style={{
          ...selectStyle,
          flex: "1 1 140px",
          minWidth: 0,
        }}
      />

      <select
        value={city}
        onChange={(e) => {
          onCityChange(e.target.value);
          onVenueChange("");
        }}
        style={{ ...selectStyle, flex: "0 0 auto" }}
      >
        <option value="">Alla städer</option>
        <option value="Stockholm">Stockholm</option>
        <option value="Uppsala">Uppsala</option>
      </select>

      <select
        value={venue}
        onChange={(e) => onVenueChange(e.target.value)}
        style={{ ...selectStyle, flex: "0 0 auto" }}
      >
        <option value="">Alla scener</option>
        {filteredVenues.map((v) => (
          <option key={v.slug} value={v.slug}>
            {v.name}
          </option>
        ))}
      </select>
    </div>
  );
}
