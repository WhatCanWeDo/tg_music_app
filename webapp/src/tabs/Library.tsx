import { useEffect, useState } from "react";
import { api, type ArtistDTO, type TrackDTO } from "../api";
import { TrackRow } from "../components/TrackRow";

export function LibraryTab() {
  const [recent, setRecent] = useState<TrackDTO[] | null>(null);
  const [artists, setArtists] = useState<ArtistDTO[] | null>(null);

  useEffect(() => {
    api.recent(30).then(setRecent).catch(console.error);
    api.artists(50).then(setArtists).catch(console.error);
  }, []);

  return (
    <div>
      <Section title="Недавнее">
        {recent === null ? (
          <Loading />
        ) : recent.length === 0 ? (
          <Empty msg="Перешли боту трек — появится здесь." />
        ) : (
          recent.map((t) => <TrackRow key={t.id} track={t} />)
        )}
      </Section>

      <Section title="Артисты">
        {artists === null ? (
          <Loading />
        ) : artists.length === 0 ? (
          <Empty msg="Артистов пока нет." />
        ) : (
          <ul className="px-5 space-y-1.5 pb-4">
            {artists.map((a) => (
              <li
                key={a.name}
                className="flex justify-between items-center py-1.5 text-sm"
              >
                <span className="truncate">{a.name}</span>
                <span className="opacity-50 tabular-nums">{a.track_count}</span>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-6">
      <h2 className="px-5 mb-2 text-xs font-semibold uppercase tracking-wider opacity-60">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Loading() {
  return <div className="px-5 py-4 opacity-50 text-sm">Загрузка…</div>;
}

function Empty({ msg }: { msg: string }) {
  return <div className="px-5 py-4 opacity-50 text-sm">{msg}</div>;
}
