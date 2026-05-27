import { useEffect, useState } from "react";
import { api, type TrackDTO } from "../api";
import { TrackRow } from "../components/TrackRow";

export function SearchTab({ onPlay }: { onPlay: (id: number) => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<TrackDTO[] | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!q.trim()) {
      setResults(null);
      return;
    }
    const t = setTimeout(() => {
      setLoading(true);
      api
        .search(q.trim(), 50)
        .then(setResults)
        .catch(console.error)
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <div>
      <div className="px-5 pt-2 pb-4 sticky top-0 bg-(--color-bg) z-10">
        <input
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Артист, трек, имя файла…"
          className="w-full rounded-lg bg-(--color-surface) px-4 py-3 text-sm outline-none focus:ring-2 ring-(--color-accent)/40"
        />
      </div>

      {loading && q && (
        <div className="px-5 py-2 opacity-50 text-xs">Ищу…</div>
      )}

      {results === null && !q && (
        <div className="px-5 py-4 opacity-50 text-sm">
          Введи запрос — поиск по title, артисту, имени файла.
        </div>
      )}

      {results !== null && results.length === 0 && !loading && (
        <div className="px-5 py-4 opacity-50 text-sm">
          Ничего не нашлось.
        </div>
      )}

      {results &&
        results.map((t) => <TrackRow key={t.id} track={t} onPlay={onPlay} />)}
    </div>
  );
}
