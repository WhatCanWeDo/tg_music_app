import type { TrackDTO } from "../api";
import { api } from "../api";
import { usePlayer } from "../player";
import { tg } from "../telegram";

export function TrackRow({ track }: { track: TrackDTO }) {
  const player = usePlayer();
  const title = track.title || track.file_name || "Untitled";
  const artist = track.artist || "Unknown Artist";
  const duration = fmtSec(track.duration_s ?? 0);
  const isCurrent = player.track?.id === track.id;

  return (
    <div
      className={`w-full flex items-center gap-3 px-5 py-3 active:bg-white/5 transition ${
        isCurrent ? "bg-white/[0.03]" : ""
      }`}
    >
      <button
        onClick={() => player.play(track)}
        className="flex flex-1 items-center gap-3 min-w-0 text-left"
      >
        <div
          className={`size-12 rounded flex items-center justify-center text-(--color-hint) shrink-0 ${
            isCurrent
              ? "bg-(--color-accent) text-(--color-accent-text)"
              : "bg-(--color-surface)"
          }`}
        >
          {isCurrent && player.isPlaying ? "♫" : "♪"}
        </div>
        <div className="flex-1 min-w-0">
          <div
            className={`text-sm font-medium truncate ${
              isCurrent ? "text-(--color-accent)" : ""
            }`}
          >
            {title}
          </div>
          <div className="text-xs opacity-60 truncate">{artist}</div>
        </div>
        <div className="text-xs opacity-50 tabular-nums">{duration}</div>
      </button>
      <button
        onClick={() => sendToChat(track.id)}
        className="size-9 rounded-full text-(--color-hint) flex items-center justify-center text-sm shrink-0 active:bg-white/5"
        aria-label="Send to chat for background playback"
        title="Открыть в чате (для фонового воспроизведения)"
      >
        ⤴
      </button>
    </div>
  );
}

async function sendToChat(trackId: number) {
  tg()?.HapticFeedback.impactOccurred("light");
  try {
    await api.playToChat(trackId);
    tg()?.HapticFeedback.notificationOccurred("success");
  } catch (e) {
    tg()?.HapticFeedback.notificationOccurred("error");
    alert(String(e));
  }
}

function fmtSec(s: number): string {
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}
