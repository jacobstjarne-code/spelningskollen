"use client";

import { useEffect, useState } from "react";
import { UserProfile, getProfile, updateGenres, updateVenues } from "@/lib/api";

const GENRE_LABELS: Record<string, string> = {
  rock: "Rock", pop: "Pop", elektroniskt: "Elektroniskt", jazz: "Jazz",
  hiphop: "Hip-hop", klassiskt: "Klassiskt", metal: "Metal",
  "singer-songwriter": "Singer-songwriter", världsmusik: "Världsmusik", övrigt: "Övrigt",
};

export default function ProfilPage() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getProfile().then(setProfile).catch(() => {});
  }, []);

  if (!profile) {
    return <div style={{ padding: "40px 0", color: "var(--text-muted)", textAlign: "center" }}>Laddar...</div>;
  }

  const genreMap = Object.fromEntries(profile.genres.map((g) => [g.genre, g.weight]));
  const venueMap = Object.fromEntries(profile.venues.map((v) => [v.slug, v.weight]));

  const handleGenreChange = (genre: string, value: number) => {
    setProfile((p) => {
      if (!p) return p;
      const existing = p.genres.find((g) => g.genre === genre);
      if (existing) {
        return { ...p, genres: p.genres.map((g) => g.genre === genre ? { ...g, weight: value } : g) };
      }
      return { ...p, genres: [...p.genres, { genre, weight: value }] };
    });
  };

  const handleVenueChange = (slug: string, value: number) => {
    setProfile((p) => {
      if (!p) return p;
      const existing = p.venues.find((v) => v.slug === slug);
      if (existing) {
        return { ...p, venues: p.venues.map((v) => v.slug === slug ? { ...v, weight: value } : v) };
      }
      return p;
    });
  };

  const handleSave = async () => {
    if (!profile) return;
    setSaving(true);
    try {
      const gMap: Record<string, number> = {};
      profile.genres.forEach((g) => { gMap[g.genre] = g.weight; });
      const vMap: Record<string, number> = {};
      profile.venues.forEach((v) => { vMap[v.slug] = v.weight; });
      await Promise.all([updateGenres(gMap), updateVenues(vMap)]);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      // tyst
    } finally {
      setSaving(false);
    }
  };

  const allGenres = Object.keys(GENRE_LABELS);

  return (
    <div style={{ paddingTop: 16 }}>
      <div style={{ marginBottom: 20 }}>
        <div className="section-label" style={{ marginBottom: 4 }}>⭐ MIN PROFIL</div>
        <h1 style={{ fontFamily: "var(--font-display)", fontSize: 22, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
          Preferenser
        </h1>
      </div>

      {/* Genresliders */}
      <div className="card" style={{ padding: "12px 14px", marginBottom: 10 }}>
        <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 12 }}>Musikgenrer</div>
        {allGenres.map((genre) => {
          const weight = profile.genres.find((g) => g.genre === genre)?.weight ?? 0;
          return (
            <div key={genre} style={{ marginBottom: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
                <span style={{ color: "var(--text-primary)" }}>{GENRE_LABELS[genre]}</span>
                <span style={{ color: "var(--text-muted)" }}>{Math.round(weight * 100)}%</span>
              </div>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={weight}
                onChange={(e) => handleGenreChange(genre, parseFloat(e.target.value))}
                style={{ width: "100%", accentColor: "var(--accent)" }}
              />
            </div>
          );
        })}
      </div>

      {/* Venue-preferenser */}
      {profile.venues.length > 0 && (
        <div className="card" style={{ padding: "12px 14px", marginBottom: 10 }}>
          <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 12 }}>Favoritscener</div>
          {profile.venues.map((v) => (
            <div key={v.slug} style={{ marginBottom: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
                <span style={{ color: "var(--text-primary)" }}>{v.name} <span style={{ color: "var(--text-muted)" }}>· {v.city}</span></span>
                <span style={{ color: "var(--text-muted)" }}>{Math.round(v.weight * 100)}%</span>
              </div>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={v.weight}
                onChange={(e) => handleVenueChange(v.slug, parseFloat(e.target.value))}
                style={{ width: "100%", accentColor: "var(--accent)" }}
              />
            </div>
          ))}
        </div>
      )}

      {/* Följda artister */}
      {profile.followed_artists.length > 0 && (
        <div className="card" style={{ padding: "12px 14px", marginBottom: 16 }}>
          <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 10 }}>Bevakade artister</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {profile.followed_artists.map((a) => (
              <span
                key={a}
                style={{
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border)",
                  borderRadius: 16,
                  padding: "4px 10px",
                  fontSize: 11,
                  color: "var(--text-secondary)",
                }}
              >
                {a}
              </span>
            ))}
          </div>
        </div>
      )}

      <button
        onClick={handleSave}
        disabled={saving}
        style={{
          width: "100%",
          padding: "12px",
          background: saved ? "rgba(52,211,153,0.15)" : "var(--accent)",
          border: saved ? "1px solid rgba(52,211,153,0.3)" : "none",
          borderRadius: "var(--radius-sm)",
          color: saved ? "var(--accent-bright)" : "#fff",
          fontSize: 14,
          fontWeight: 700,
          cursor: saving ? "default" : "pointer",
          transition: "all 200ms",
        }}
      >
        {saved ? "Sparat!" : saving ? "Sparar..." : "Spara preferenser"}
      </button>
    </div>
  );
}
