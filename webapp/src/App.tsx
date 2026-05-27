import { useEffect, useState } from "react";
import { api, type MeDTO } from "./api";
import { isInsideTelegram, tg } from "./telegram";
import { LibraryTab } from "./tabs/Library";
import { SearchTab } from "./tabs/Search";

type Tab = "library" | "search";

export default function App() {
  const [tab, setTab] = useState<Tab>("library");
  const [me, setMe] = useState<MeDTO | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isInsideTelegram()) {
      setError("Open this app from inside Telegram — no initData detected.");
      return;
    }
    api.me().then(setMe).catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return (
      <div className="p-6 text-sm">
        <p className="text-red-400 font-mono whitespace-pre-wrap">{error}</p>
        <p className="mt-4 opacity-60">
          Если ты открыл это из браузера, а не из Telegram — initData
          отсутствует и backend отвечает 401. Это ожидаемо.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <Header me={me} />
      <main className="flex-1 overflow-y-auto pb-20">
        {tab === "library" && <LibraryTab onPlay={onPlay} />}
        {tab === "search" && <SearchTab onPlay={onPlay} />}
      </main>
      <TabBar tab={tab} setTab={setTab} />
    </div>
  );
}

async function onPlay(trackId: number) {
  tg()?.HapticFeedback.impactOccurred("light");
  try {
    await api.play(trackId);
    tg()?.HapticFeedback.notificationOccurred("success");
  } catch (e) {
    tg()?.HapticFeedback.notificationOccurred("error");
    alert(String(e));
  }
}

function Header({ me }: { me: MeDTO | null }) {
  return (
    <header className="px-5 pt-5 pb-3">
      <h1 className="text-2xl font-semibold tracking-tight">tgmusic</h1>
      {me && (
        <p className="text-sm opacity-60 mt-1">
          {me.counts.tracks} треков · {me.counts.artists} артистов ·{" "}
          {fmtDuration(me.counts.total_seconds)}
        </p>
      )}
    </header>
  );
}

function TabBar({ tab, setTab }: { tab: Tab; setTab: (t: Tab) => void }) {
  return (
    <nav className="fixed bottom-0 inset-x-0 border-t border-white/10 bg-(--color-bg) backdrop-blur-md">
      <div className="flex">
        <TabButton active={tab === "library"} onClick={() => setTab("library")}>
          Библиотека
        </TabButton>
        <TabButton active={tab === "search"} onClick={() => setTab("search")}>
          Поиск
        </TabButton>
      </div>
    </nav>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 py-4 text-sm font-medium transition ${
        active ? "text-(--color-accent)" : "opacity-50"
      }`}
    >
      {children}
    </button>
  );
}

function fmtDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h ? `${h}ч ${m}м` : `${m}м`;
}
