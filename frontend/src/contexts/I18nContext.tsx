"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { Locale, translations, TranslationKeys } from "@/i18n";

const STORAGE_KEY = "clawfans_locale";
const DEFAULT_LOCALE: Locale = "en";

// ── Context ──────────────────────────────────────────────────────────────────
interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: TranslationKeys;
}

const I18nContext = createContext<I18nContextValue | null>(null);

// Resolve the initial locale from localStorage / browser language.
// Runs lazily on first render; guarded for SSR where window is undefined.
function getInitialLocale(): Locale {
  if (typeof window === "undefined") return DEFAULT_LOCALE;
  try {
    const saved = localStorage.getItem(STORAGE_KEY) as Locale | null;
    if (saved && saved in translations) return saved;
    // Try to detect browser language
    const browserLang = navigator.language.split("-")[0] as Locale;
    if (browserLang in translations) return browserLang;
  } catch {
    // localStorage not available
  }
  return DEFAULT_LOCALE;
}

// ── Provider ─────────────────────────────────────────────────────────────────
export function I18nProvider({ children }: { children: React.ReactNode }) {
  // Lazy initializer avoids a synchronous setState-in-effect on mount.
  const [locale, setLocaleState] = useState<Locale>(getInitialLocale);

  // Keep <html lang> in sync with the locale (external system update).
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((newLocale: Locale) => {
    // <html lang> is updated by the effect above when `locale` changes.
    setLocaleState(newLocale);
    try {
      localStorage.setItem(STORAGE_KEY, newLocale);
    } catch {
      // ignore
    }
  }, []);

  return (
    <I18nContext.Provider value={{ locale, setLocale, t: translations[locale] }}>
      {children}
    </I18nContext.Provider>
  );
}

// ── Hook ─────────────────────────────────────────────────────────────────────
export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}

/** Shorthand: just grab the translation object */
export function useT() {
  return useI18n().t;
}
