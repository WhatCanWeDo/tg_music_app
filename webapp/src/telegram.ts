// Thin wrapper over the global Telegram.WebApp object loaded by
// telegram-web-app.js in index.html. Keeps the rest of the app
// framework-agnostic and easy to test (no peer dep on a WebApp SDK package).

declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp;
    };
  }
}

export interface TelegramWebApp {
  initData: string;
  initDataUnsafe: {
    user?: { id: number; first_name?: string; username?: string };
  };
  colorScheme: "light" | "dark";
  themeParams: Record<string, string>;
  ready: () => void;
  expand: () => void;
  HapticFeedback: {
    impactOccurred: (style: "light" | "medium" | "heavy" | "rigid" | "soft") => void;
    notificationOccurred: (type: "error" | "success" | "warning") => void;
  };
  MainButton: {
    text: string;
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
  };
  BackButton: {
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  };
  close: () => void;
}

export function tg(): TelegramWebApp | null {
  return window.Telegram?.WebApp ?? null;
}

export function getInitData(): string {
  return tg()?.initData ?? "";
}

export function isInsideTelegram(): boolean {
  return Boolean(tg()?.initData);
}
