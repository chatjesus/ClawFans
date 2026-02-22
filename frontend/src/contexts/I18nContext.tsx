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

// ── Provider ─────────────────────────────────────────────────────────────────
export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) as Locale | null;
      if (saved && saved in translations) {
        setLocaleState(saved);
        document.documentElement.lang = saved;
      } else {
        // Try to detect browser language
        const browserLang = navigator.language.split("-")[0] as Locale;
        if (browserLang in translations) {
          setLocaleState(browserLang);
          document.documentElement.lang = browserLang;
        }
      }
    } catch {
      // localStorage not available
    }
  }, []);

  const setLocale = useCallback((newLocale: Locale) => {
    setLocaleState(newLocale);
    document.documentElement.lang = newLocale;
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
