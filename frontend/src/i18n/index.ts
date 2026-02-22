import en from "./en.json";
import zh from "./zh.json";
import ja from "./ja.json";
import ko from "./ko.json";
import es from "./es.json";
import fr from "./fr.json";
import pt from "./pt.json";
import de from "./de.json";

export type Locale = "en" | "zh" | "ja" | "ko" | "es" | "fr" | "pt" | "de";

export const LOCALES: { code: Locale; label: string; flag: string }[] = [
  { code: "en", label: "English",    flag: "🇺🇸" },
  { code: "zh", label: "中文",        flag: "🇨🇳" },
  { code: "ja", label: "日本語",      flag: "🇯🇵" },
  { code: "ko", label: "한국어",      flag: "🇰🇷" },
  { code: "es", label: "Español",    flag: "🇪🇸" },
  { code: "fr", label: "Français",   flag: "🇫🇷" },
  { code: "pt", label: "Português",  flag: "🇧🇷" },
  { code: "de", label: "Deutsch",    flag: "🇩🇪" },
];

export const translations: Record<Locale, typeof en> = { en, zh, ja, ko, es, fr, pt, de };

export type TranslationKeys = typeof en;
