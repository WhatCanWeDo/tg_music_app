import { usePlayer } from "../player";

export function Player() {
  const { track, thumbUrl, isPlaying, position, duration, loading, error, toggle, seek, close } =
    usePlayer();

  if (!track) return null;

  const title = track.title || track.file_name || "Untitled";
  const artist = track.artist || "Unknown Artist";
  const progress = duration > 0 ? position / duration : 0;

  return (
    <div className="fixed bottom-14 inset-x-0 border-t border-white/10 bg-(--color-surface)/95 backdrop-blur-md">
      <div className="px-4 pt-3 pb-2">
        <div className="flex items-center gap-3">
          {thumbUrl ? (
            <img
              src={thumbUrl}
              alt=""
              className="size-11 rounded object-cover shrink-0"
            />
          ) : (
            <div className="size-11 rounded bg-(--color-bg) flex items-center justify-center text-(--color-hint) shrink-0">
              ♪
            </div>
          )}
          <button
            onClick={toggle}
            className="size-11 rounded-full bg-(--color-accent) text-(--color-accent-text) shrink-0 flex items-center justify-center text-lg active:scale-95 transition"
            aria-label={isPlaying ? "Pause" : "Play"}
          >
            {loading ? "…" : isPlaying ? "❚❚" : "▶"}
          </button>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">{title}</div>
            <div className="text-xs opacity-60 truncate">{artist}</div>
          </div>
          <button
            onClick={close}
            className="size-9 rounded-full text-(--color-hint) flex items-center justify-center text-base shrink-0"
            aria-label="Close player"
          >
            ✕
          </button>
        </div>

        {/* progress */}
        <div className="mt-2 flex items-center gap-2 text-[10px] tabular-nums opacity-60">
          <span>{fmt(position)}</span>
          <input
            type="range"
            min={0}
            max={duration || 0}
            step={1}
            value={position}
            onChange={(e) => seek(Number(e.target.value))}
            className="flex-1 accent-(--color-accent) h-1"
            disabled={!duration}
          />
          <span>{duration ? fmt(duration) : "--:--"}</span>
        </div>

        {error && (
          <div className="mt-1 text-[10px] text-(--color-destructive) truncate">
            {error}
          </div>
        )}

        <div
          className="mt-1 h-0.5 bg-white/10 rounded overflow-hidden"
          style={{ display: duration ? "none" : "block" }}
        >
          <div
            className="h-full bg-(--color-accent)"
            style={{ width: `${progress * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
}

function fmt(s: number): string {
  if (!isFinite(s)) return "--:--";
  const m = Math.floor(s / 60);
  const r = Math.floor(s % 60);
  return `${m}:${String(r).padStart(2, "0")}`;
}
