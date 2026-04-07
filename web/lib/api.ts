const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export interface Event {
  id: number;
  artist: string;
  title: string | null;
  date: string;
  time: string | null;
  genre: string | null;
  subgenre: string | null;
  image_url: string | null;
  ticket_url: string | null;
  ticket_status: string;
  price_min: number | null;
  price_max: number | null;
  on_sale_date: string | null;
  source: string;
  venue_name: string | null;
  city: string | null;
  venue_slug: string | null;
  venue_type: string | null;
  list_status: string | null;
  list_id: number | null;
}

export interface Venue {
  id: number;
  name: string;
  city: string;
  slug: string;
  venue_type: string;
  capacity: number | null;
  website_url: string | null;
}

export interface ListItem extends Event {
  status: string;
  ticket_count: number;
  notes: string | null;
  remind_before_days: number;
  added_at: string;
}

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// Events
export async function getEvents(params?: Record<string, string>): Promise<Event[]> {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return fetchJSON(`/api/events${qs}`);
}

// Venues
export async function getVenues(city?: string): Promise<Venue[]> {
  const qs = city ? `?city=${city}` : "";
  return fetchJSON(`/api/venues${qs}`);
}

// Min lista
export async function getMyList(): Promise<ListItem[]> {
  return fetchJSON("/api/list");
}

export async function addToList(eventId: number, status = "interested") {
  return fetchJSON("/api/list/add", {
    method: "POST",
    body: JSON.stringify({ event_id: eventId, status }),
  });
}

export async function updateListItem(listId: number, updates: Record<string, unknown>) {
  return fetchJSON("/api/list/update", {
    method: "POST",
    body: JSON.stringify({ list_id: listId, ...updates }),
  });
}

export async function removeFromList(listId: number) {
  return fetchJSON("/api/list/remove", {
    method: "POST",
    body: JSON.stringify({ list_id: listId }),
  });
}

export async function followArtist(artistName: string) {
  return fetchJSON("/api/artists/follow", {
    method: "POST",
    body: JSON.stringify({ artist_name: artistName }),
  });
}

// Formatering
export function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  const days = ["sön", "mån", "tis", "ons", "tor", "fre", "lör"];
  const months = ["jan", "feb", "mar", "apr", "maj", "jun",
                   "jul", "aug", "sep", "okt", "nov", "dec"];
  return `${days[d.getDay()]} ${d.getDate()} ${months[d.getMonth()]}`;
}

export function formatPrice(min: number | null, max: number | null): string {
  if (!min && !max) return "";
  if (min && max && min !== max) return `${min}–${max} kr`;
  return `${min || max} kr`;
}
