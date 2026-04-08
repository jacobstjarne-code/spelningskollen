import "./globals.css";
import BottomNav from "@/components/BottomNav";
import ServiceWorkerRegistrar from "@/components/ServiceWorkerRegistrar";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Spelningskollen — Stockholm & Uppsala",
  description: "Alla spelningar i Stockholm och Uppsala på ett ställe",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="sv">
      <body className="min-h-screen pb-16">
        {/* Spotlight-effekt */}
        <div className="spotlight" />

        {/* Header */}
        <header
          style={{
            position: "sticky",
            top: 0,
            zIndex: 50,
            background: "rgba(12,11,15,0.85)",
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <div
            style={{
              maxWidth: 430,
              margin: "0 auto",
              padding: "12px 16px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <a href="/" style={{ textDecoration: "none", display: "flex", alignItems: "baseline", gap: 8 }}>
              <span style={{ fontFamily: "var(--font-display)", fontSize: 18, fontWeight: 700, color: "var(--text-primary)" }}>
                Spelningskollen
              </span>
              <span style={{ fontSize: 9, fontWeight: 600, letterSpacing: 2, textTransform: "uppercase" as const, color: "var(--accent)" }}>
                STHLM · UPPSALA
              </span>
            </a>
          </div>
        </header>

        {/* Content */}
        <main style={{ maxWidth: 430, margin: "0 auto", padding: "0 12px", position: "relative", zIndex: 1 }}>
          {children}
        </main>

        <BottomNav />
        <ServiceWorkerRegistrar />
      </body>
    </html>
  );
}
