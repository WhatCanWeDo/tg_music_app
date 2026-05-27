import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { api, type TrackDTO } from "./api";
import { tg } from "./telegram";

interface PlayerState {
  track: TrackDTO | null;
  isPlaying: boolean;
  position: number;
  duration: number;
  loading: boolean;
  error: string | null;
  play: (t: TrackDTO) => Promise<void>;
  toggle: () => void;
  seek: (seconds: number) => void;
  close: () => void;
}

const PlayerCtx = createContext<PlayerState | null>(null);

export function usePlayer(): PlayerState {
  const ctx = useContext(PlayerCtx);
  if (!ctx) throw new Error("PlayerProvider missing");
  return ctx;
}

export function PlayerProvider({ children }: { children: React.ReactNode }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [track, setTrack] = useState<TrackDTO | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [position, setPosition] = useState(0);
  const [duration, setDuration] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const play = useCallback(async (t: TrackDTO) => {
    setError(null);
    setLoading(true);
    try {
      const { url } = await api.playUrl(t.id);
      const a = audioRef.current;
      if (!a) return;
      a.src = url;
      a.load();
      await a.play();
      setTrack(t);
      tg()?.HapticFeedback.impactOccurred("light");
    } catch (e) {
      setError(String(e));
      tg()?.HapticFeedback.notificationOccurred("error");
    } finally {
      setLoading(false);
    }
  }, []);

  const toggle = useCallback(() => {
    const a = audioRef.current;
    if (!a) return;
    if (a.paused) {
      a.play().catch((e) => setError(String(e)));
    } else {
      a.pause();
    }
  }, []);

  const seek = useCallback((seconds: number) => {
    const a = audioRef.current;
    if (!a) return;
    a.currentTime = Math.max(0, Math.min(a.duration || 0, seconds));
  }, []);

  const close = useCallback(() => {
    const a = audioRef.current;
    if (a) {
      a.pause();
      a.removeAttribute("src");
      a.load();
    }
    setTrack(null);
    setIsPlaying(false);
    setPosition(0);
    setDuration(0);
  }, []);

  // Bind audio element events to React state.
  useEffect(() => {
    const a = audioRef.current;
    if (!a) return;
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    const onTime = () => setPosition(a.currentTime);
    const onMeta = () => setDuration(a.duration || 0);
    const onEnd = () => {
      setIsPlaying(false);
      setPosition(0);
    };
    a.addEventListener("play", onPlay);
    a.addEventListener("pause", onPause);
    a.addEventListener("timeupdate", onTime);
    a.addEventListener("loadedmetadata", onMeta);
    a.addEventListener("durationchange", onMeta);
    a.addEventListener("ended", onEnd);
    return () => {
      a.removeEventListener("play", onPlay);
      a.removeEventListener("pause", onPause);
      a.removeEventListener("timeupdate", onTime);
      a.removeEventListener("loadedmetadata", onMeta);
      a.removeEventListener("durationchange", onMeta);
      a.removeEventListener("ended", onEnd);
    };
  }, []);

  return (
    <PlayerCtx.Provider
      value={{ track, isPlaying, position, duration, loading, error, play, toggle, seek, close }}
    >
      {children}
      <audio ref={audioRef} preload="none" playsInline />
    </PlayerCtx.Provider>
  );
}
