"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { saveOnboarding, getVenues } from "@/lib/api";
import { useEffect } from "react";

const GENRES = [
  { id: "rock", label: "Rock" },
  { id: "pop", label: "Pop" },
  { id: "elektroniskt", label: "Elektroniskt" },
  { id: "jazz", label: "Jazz" },
  { id: "hiphop", label: "Hip-hop" },
  { id: "klassiskt", label: "Klassiskt" },
  { id: "metal", label: "Metal" },
  { id: "singer-songwriter", label: "Singer-songwriter" },
  { id: "världsmusik", label: "Världsmusik" },
  { id: "övrigt", label: "Övrigt" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [genres, setGenres] = useState<string[]>([]);
  const [venues, setVenues] = useState<string[]>([]);
  const [allVenues, setAllVenues] = useState<{ slug: string; name: string; city: string }[]>([]);
  const [artistInput, setArtistInput] = useState("");
  const [artists, setArtists] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getVenues().then(setAllVenues).catch(() => {});
  }, []);

  const toggleGenre = (id: string) =>
    setGenres((g) => (g.includes(id) ? g.filter((x) => x !== id) : [...g, id]));

  const toggleVenue = (slug: string) =>
    setVenues((v) => (v.includes(slug) ? v.filter((x) => x !== slug) : [...v, slug]));

  const addArtist = () => {
    const a = artistInput.trim();
    if (a && !artists.includes(a)) {
      setArtists((arr) => [...arr, a]);
    }
    setArtistInput("");
  };

  const handleFinish = async () => {
    setSaving(true);
    try {
      await saveOnboarding(genres, venues, artists);
      router.push("/");
    } catch {
      setSaving(false);
    }
  };

  const chipStyle = (active: boolean): React.CSSProperties => ({
    padding: "8px 14px",
    borderRadius: 20,
    border: "none",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: active ? 700 : 400,
    background: active ? "var(--accent)" : "var(--card-bg)",
    color: active ? "#fff" : "var(--text-secondary)",
    transition: "all 150ms",
    margin: "4px 3px",
  });

  const sthlmVenues = allVenues.filter((v) => v.city === "Stockholm");
  const uppsalaVenues = allVenues.filter((v) => v.city === "Uppsala");

  return (
    <div style={{ padding: "24px 0", maxWidth: 480 }}>
      <div style={{ marginBottom: 24 }}>
        <div className="section-label" style={{ marginBottom: 4 }}>
          {step + 1} / 3
        </div>
        <h1 style={{ fontFamily: "var(--font-display)", fontSize: 22, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
          {step === 0 && "Vilken musik gillar du?"}
          {step === 1 && "Vilka scener besöker du?"}
          {step === 2 && "Artister du vill bevaka"}
        </h1>
        <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
          {step === 0 && "Välj en eller flera genrer — justerbara senare."}
          {step === 1 && "Vi visar dina favoritscener högst upp."}
          {step === 2 && "Valfritt — vi notifierar när de spelar."}
        </p>
      </div>

      {step === 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 0 }}>
          {GENRES.map((g) => (
            <button key={g.id} style={chipStyle(genres.includes(g.id))} onClick={() => toggleGenre(g.id)}>
              {g.label}
            </button>
          ))}
        </div>
      )}

      {step === 1 && (
        <div>
          {sthlmVenues.length > 0 && (
            <>
              <div className="section-label" style={{ marginBottom: 8 }}>Stockholm</div>
              <div style={{ display: "flex", flexWrap: "wrap" }}>
                {sthlmVenues.map((v) => (
                  <button key={v.slug} style={chipStyle(venues.includes(v.slug))} onClick={() => toggleVenue(v.slug)}>
                    {v.name}
                  </button>
                ))}
              </div>
            </>
          )}
          {uppsalaVenues.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <div className="section-label" style={{ marginBottom: 8 }}>Uppsala</div>
              <div style={{ display: "flex", flexWrap: "wrap" }}>
                {uppsalaVenues.map((v) => (
                  <button key={v.slug} style={chipStyle(venues.includes(v.slug))} onClick={() => toggleVenue(v.slug)}>
                    {v.name}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {step === 2 && (
        <div>
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            <input
              value={artistInput}
              onChange={(e) => setArtistInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addArtist()}
              placeholder="Skriv artistnamn..."
              style={{
                flex: 1,
                background: "var(--bg-elevated)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-sm)",
                padding: "8px 12px",
                fontSize: 13,
                color: "var(--text-primary)",
                outline: "none",
              }}
            />
            <button
              onClick={addArtist}
              style={{
                background: "var(--accent)",
                color: "#fff",
                border: "none",
                borderRadius: "var(--radius-sm)",
                padding: "8px 14px",
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              +
            </button>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {artists.map((a) => (
              <span
                key={a}
                style={{
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border)",
                  borderRadius: 16,
                  padding: "4px 10px",
                  fontSize: 12,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                {a}
                <button
                  onClick={() => setArtists((arr) => arr.filter((x) => x !== a))}
                  style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: 0, fontSize: 12 }}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: 10, marginTop: 28 }}>
        {step > 0 && (
          <button
            onClick={() => setStep((s) => s - 1)}
            style={{
              flex: 1,
              padding: "12px",
              background: "var(--card-bg)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-sm)",
              color: "var(--text-secondary)",
              fontSize: 14,
              cursor: "pointer",
            }}
          >
            Tillbaka
          </button>
        )}
        {step < 2 ? (
          <button
            onClick={() => setStep((s) => s + 1)}
            style={{
              flex: 2,
              padding: "12px",
              background: "var(--accent)",
              border: "none",
              borderRadius: "var(--radius-sm)",
              color: "#fff",
              fontSize: 14,
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            Nästa
          </button>
        ) : (
          <button
            onClick={handleFinish}
            disabled={saving}
            style={{
              flex: 2,
              padding: "12px",
              background: "var(--accent)",
              border: "none",
              borderRadius: "var(--radius-sm)",
              color: "#fff",
              fontSize: 14,
              fontWeight: 700,
              cursor: saving ? "default" : "pointer",
            }}
          >
            {saving ? "Sparar..." : "Klar — visa spelningar"}
          </button>
        )}
      </div>
    </div>
  );
}
