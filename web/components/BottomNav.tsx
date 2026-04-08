"use client";

import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Spelningar", icon: "🎵" },
  { href: "/lista", label: "Min lista", icon: "♡" },
  { href: "/paningar", label: "Påningar", icon: "🔔" },
  { href: "/profil", label: "Profil", icon: "⭐" },
];

export default function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      style={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 50,
        background: "rgba(12,11,15,0.92)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        borderTop: "1px solid var(--border)",
      }}
    >
      <div
        style={{
          maxWidth: 430,
          margin: "0 auto",
          display: "flex",
          justifyContent: "space-around",
          padding: "8px 0 env(safe-area-inset-bottom, 8px)",
        }}
      >
        {NAV_ITEMS.map(({ href, label, icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <a
              key={href}
              href={href}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 2,
                padding: "4px 16px",
                textDecoration: "none",
                color: active ? "var(--accent-bright)" : "var(--text-muted)",
                fontSize: 10,
                fontWeight: active ? 700 : 500,
                letterSpacing: 0.3,
                position: "relative",
                transition: "color 150ms",
              }}
            >
              <span style={{ fontSize: 18 }}>{icon}</span>
              <span>{label}</span>
              {active && (
                <span
                  style={{
                    position: "absolute",
                    top: 0,
                    left: "50%",
                    transform: "translateX(-50%)",
                    width: 16,
                    height: 2,
                    background: "var(--accent)",
                    borderRadius: 1,
                    boxShadow: "0 0 6px var(--accent-glow)",
                  }}
                />
              )}
            </a>
          );
        })}
      </div>
    </nav>
  );
}
