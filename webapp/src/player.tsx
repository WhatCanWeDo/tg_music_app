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
  thumbUrl: string | null;
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
  const [thumbUrl, setThumbUrl] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [position, setPosition] = useState(0);
  const [duration, setDuration] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const play = useCallback(async (t: TrackDTO) => {
    setError(null);
    setLoading(true);
    try {
      const { url, thumb_url } = await api.playUrl(t.id);
      const a = audioRef.current;
      if (!a) return;
      // preload="auto" once we know what to play — iOS keeps buffering on
      // background more reliably when data is already cached.
      a.preload = "auto";
      a.src = url;
      a.load();
      await a.play();
      setTrack(t);
      setThumbUrl(thumb_url);
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
    setThumbUrl(null);
    setIsPlaying(false);
    setPosition(0);
    setDuration(0);
    if ("mediaSession" in navigator) {
      navigator.mediaSession.metadata = null;
      navigator.mediaSession.playbackState = "none";
    }
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

  // Media Session: tell the OS this is real media so it gets lockscreen
  // controls (iOS Control Center, AirPods, Apple Watch, Android notif).
  useEffect(() => {
    if (!("mediaSession" in navigator)) return;
    if (!track) {
      navigator.mediaSession.metadata = null;
      return;
    }
    navigator.mediaSession.metadata = new MediaMetadata({
      title: track.title || track.file_name || "Untitled",
      artist: track.artist || "Unknown Artist",
      album: track.album || "",
      artwork: thumbUrl
        ? [
            { src: thumbUrl, sizes: "320x320", type: "image/jpeg" },
            { src: thumbUrl, sizes: "640x640", type: "image/jpeg" },
          ]
        : [],
    });

    const a = audioRef.current;
    const set = navigator.mediaSession.setActionHandler.bind(navigator.mediaSession);
    set("play", () => a?.play().catch(() => {}));
    set("pause", () => a?.pause());
    set("seekbackward", (d) => {
      if (a) a.currentTime = Math.max(0, a.currentTime - (d.seekOffset || 10));
    });
    set("seekforward", (d) => {
      if (a) a.currentTime = Math.min(a.duration || 0, a.currentTime + (d.seekOffset || 10));
    });
    set("seekto", (d) => {
      if (a && d.seekTime != null) a.currentTime = d.seekTime;
    });
    set("stop", () => {
      a?.pause();
    });
    // nexttrack/previoustrack left for when we have queue support.
  }, [track, thumbUrl]);

  useEffect(() => {
    if (!("mediaSession" in navigator)) return;
    navigator.mediaSession.playbackState = isPlaying ? "playing" : "paused";
  }, [isPlaying]);

  // setPositionState lets the OS render an accurate scrubber on lockscreen.
  useEffect(() => {
    if (!("mediaSession" in navigator) || !("setPositionState" in navigator.mediaSession)) {
      return;
    }
    if (!duration || !isFinite(duration)) return;
    try {
      navigator.mediaSession.setPositionState({
        duration,
        playbackRate: audioRef.current?.playbackRate || 1,
        position: Math.min(position, duration),
      });
    } catch {
      /* iOS can throw on weird values during transitions */
    }
  }, [position, duration]);

  return (
    <PlayerCtx.Provider
      value={{
        track,
        thumbUrl,
        isPlaying,
        position,
        duration,
        loading,
        error,
        play,
        toggle,
        seek,
        close,
      }}
    >
      {children}
      <audio ref={audioRef} preload="none" playsInline />
    </PlayerCtx.Provider>
  );
}
