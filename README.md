# Spelningskollen

Samlad konsertkalender för Stockholm och Uppsala. Aggregerar spelningar från Ticketmaster, Songkick och venue-scrapers till en mörk, snygg mobilapp.

## Funktioner
- **Samlad spelningslista** — filtrering på datum, scen, genre, stad
- **Min lista** — spara spelningar du vill gå på
- **Påningar** — påminnelser inför biljettsläpp och konserter
- **Biljettspårning** — markera köpta biljetter, få påminnelse innan spelning

## Datakällor
- Ticketmaster Discovery API (stora scener + många klubbar)
- Songkick API (turnéartister, kompletterande)
- Venue-scrapers: Nalen, Slaktkyrkan, Södra Teatern, Debaser, Katalin

## Scener (26 st)
**Stockholm:** Avicii Arena, Tele2, Strawberry Arena, Gröna Lund, Skansen Solliden, Cirkus, Annexet, Nalen, Slaktkyrkan, Södra Teatern, Under Bron, Debaser, Berns, Münchenbryggeriet, Fasching, Fållan, Hus 7, Bryggarsalen, Kraken, Orionteatern

**Uppsala:** Katalin, Flustret, Parksnäckan, Botaniska, IFU Arena, Uppsala Konsert & Kongress

## Tech stack
- **Datainsamling:** Python 3, SQLite, requests, BeautifulSoup
- **Frontend:** Next.js 14, TypeScript, Tailwind CSS
- **Schemaläggning:** GitHub Actions (2x dagligen)
- **Design:** Mörk klubb-estetik, neonrosa accent, tight mobile-first layout

## Kom igång

```bash
# 1. Datainsamling
cd collector
pip install -r requirements.txt
cp ../.env.example ../.env   # Fyll i API-nycklar
python -m collector.main --init

# 2. API-server (utveckling)
python -m collector.api      # Kör på localhost:3001

# 3. Frontend
cd ../web
npm install
npm run dev                  # Kör på localhost:3000
```

## Projektstruktur
```
spelningskollen/
├── collector/           # Python — datainsamling & API
│   ├── sources/         # En modul per datakälla
│   ├── db/              # SQLite-schema och queries
│   ├── api.py           # JSON API-server
│   └── main.py          # Entry point
├── web/                 # Next.js frontend
│   ├── app/             # Sidor (page.tsx)
│   ├── components/      # EventCard, Filters, BottomNav
│   └── lib/             # API-klient
└── .github/workflows/   # Schemalagd insamling
```
