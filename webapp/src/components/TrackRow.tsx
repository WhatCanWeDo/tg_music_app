import type { TrackDTO } from "../api";

export function TrackRow({
  track,
  onPlay,
}: {
  track: TrackDTO;
  onPlay: (id: number) => void;
}) {
  const title = track.title || track.file_name || "Untitled";
  const artist = track.artist || "Unknown Artist";
  const duration = fmtSec(track.duration_s ?? 0);

  return (
    <button
      onClick={() => onPlay(track.id)}
      className="w-full flex items-center gap-3 px-5 py-3 active:bg-white/5 transition text-left"
    >
      <div className="size-12 rounded bg-(--color-surface) flex items-center justify-center text-(--color-hint) shrink-0">
        ♪
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate">{title}</div>
        <div className="text-xs opacity-60 truncate">{artist}</div>
      </div>
      <div className="text-xs opacity-50 tabular-nums">{duration}</div>
    </button>
  );
}

function fmtSec(s: number): string {
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}
