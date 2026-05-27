import { getInitData } from "./telegram";

const API = import.meta.env.VITE_API_URL || "";

export interface TrackDTO {
  id: number;
  title: string | null;
  artist: string | null;
  album: string | null;
  duration_s: number | null;
  file_name: string | null;
  thumb_file_id: string | null;
}

export interface ArtistDTO {
  name: string;
  track_count: number;
}

export interface MeDTO {
  user_id: number;
  counts: {
    tracks: number;
    artists: number;
    albums: number;
    total_seconds: number;
  };
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!API) {
    throw new Error("VITE_API_URL is not configured at build time");
  }
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `tma ${getInitData()}`,
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${path} ${res.status}: ${text}`);
  }
  return (await res.json()) as T;
}

export const api = {
  me: () => call<MeDTO>("/api/me"),
  recent: (limit = 30) => call<TrackDTO[]>(`/api/tracks/recent?limit=${limit}`),
  search: (q: string, limit = 30) =>
    call<TrackDTO[]>(`/api/tracks/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  artists: (limit = 100) => call<ArtistDTO[]>(`/api/artists?limit=${limit}`),
  /** Get signed URLs for streaming + cover art. */
  playUrl: (track_id: number) =>
    call<{ url: string; thumb_url: string | null; track_id: number }>("/api/play/url", {
      method: "POST",
      body: JSON.stringify({ track_id }),
    }),
  /** Send the track to the owner's chat with the bot so the native Telegram
   *  player picks it up (lockscreen, AirPods, background — full iOS support). */
  playToChat: (track_id: number) =>
    call<{ ok: true; track_id: number }>("/api/play/to-chat", {
      method: "POST",
      body: JSON.stringify({ track_id }),
    }),
};
