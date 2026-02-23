import en    from "./en.json";
import zh    from "./zh.json";
import zhTW  from "./zh-TW.json";
import ja    from "./ja.json";
import ko    from "./ko.json";
import es    from "./es.json";
import fr    from "./fr.json";
import pt    from "./pt.json";
import de    from "./de.json";
import ru    from "./ru.json";
import it    from "./it.json";
import th    from "./th.json";
import vi    from "./vi.json";
import id    from "./id.json";
import ar    from "./ar.json";

export type Locale =
  | "en" | "zh" | "zh-TW"
  | "ja" | "ko"
  | "es" | "fr" | "pt" | "de" | "it" | "ru"
  | "th" | "vi" | "id" | "ar";

export const LOCALES: { code: Locale; label: string; flag: string }[] = [
  { code: "en",    label: "English",    flag: "\uD83C\uDDFA\uD83C\uDDF8" },
  { code: "zh",    label: "\u4e2d\u6587(\u7b80)",  flag: "\uD83C\uDDE8\uD83C\uDDF3" },
  { code: "zh-TW", label: "\u4e2d\u6587(\u7e41)",  flag: "\uD83C\uDDF9\uD83C\uDDFC" },
  { code: "ja",    label: "\u65e5\u672c\u8a9e",    flag: "\uD83C\uDDEF\uD83C\uDDF5" },
  { code: "ko",    label: "\ud55c\uad6d\uc5b4",    flag: "\uD83C\uDDF0\uD83C\uDDF7" },
  { code: "es",    label: "Espa\u00f1ol",  flag: "\uD83C\uDDEA\uD83C\uDDF8" },
  { code: "fr",    label: "Fran\u00e7ais", flag: "\uD83C\uDDEB\uD83C\uDDF7" },
  { code: "pt",    label: "Portugu\u00eas",flag: "\uD83C\uDDE7\uD83C\uDDF7" },
  { code: "de",    label: "Deutsch",    flag: "\uD83C\uDDE9\uD83C\uDDEA" },
  { code: "ru",    label: "\u0420\u0443\u0441\u0441\u043a\u0438\u0439", flag: "\uD83C\uDDF7\uD83C\uDDFA" },
  { code: "it",    label: "Italiano",   flag: "\uD83C\uDDEE\uD83C\uDDF9" },
  { code: "th",    label: "\u0e44\u0e17\u0e22",       flag: "\uD83C\uDDF9\uD83C\uDDED" },
  { code: "vi",    label: "Ti\u1ebfng Vi\u1ec7t", flag: "\uD83C\uDDFB\uD83C\uDDF3" },
  { code: "id",    label: "Indonesia",  flag: "\uD83C\uDDEE\uD83C\uDDE9" },
  { code: "ar",    label: "\u0639\u0631\u0628\u064a",      flag: "\uD83C\uDDF8\uD83C\uDDE6" },
];

export const translations: Record<Locale, typeof en> = {
  en, zh, "zh-TW": zhTW, ja, ko, es, fr, pt, de, ru, it, th, vi, id, ar,
};

export type TranslationKeys = typeof en;
