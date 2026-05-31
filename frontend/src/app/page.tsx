"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import CharacterCard from "@/components/CharacterCard";
import { fetchCharacters, fetchCategories, type CharacterCard as CharacterCardType } from "@/lib/api";
import { useT, useI18n } from "@/contexts/I18nContext";

const categoryIcons: Record<string, string> = {
  Featured: "\uD83D\uDD25", Romance: "\uD83D\uDC8B", Anime: "\uD83C\uDF38", Fantasy: "\u2694\uFE0F",
  Modern: "\uD83C\uDFD9\uFE0F", Roleplay: "\uD83C\uDFAD", "Sci-Fi": "\uD83D\uDD2C", Wellness: "\uD83D\uDD6F\uFE0F",
  NSFW: "\uD83D\uDD1E", School: "\uD83C\uDF93", Drama: "\uD83C\uDFAC", Horror: "\uD83D\uDC7B",
};

export default function HomePage() {
  const t = useT();
  const { locale } = useI18n();
  const [characters, setCharacters] = useState<CharacterCardType[]>([]);
  const [categories, setCategories] = useState<string[]>(["Featured"]);
  const [activeCategory, setActiveCategory] = useState("Featured");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { fetchCategories().then(setCategories).catch(() => {}); }, []);

  useEffect(() => {
    let cancelled = false;
    // Run the fetch in an async flow so state updates happen in callbacks,
    // not synchronously in the effect body (avoids cascading renders).
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchCharacters(activeCategory, searchQuery, locale);
        if (!cancelled) { setCharacters(data); setLoading(false); }
      } catch (err) {
        if (!cancelled) { setError((err as Error).message); setLoading(false); }
      }
    })();
    return () => { cancelled = true; };
  }, [activeCategory, searchQuery, locale]);

  return (
    <div className="h-full overflow-y-auto">
      {/* Banner */}
      <div className="px-6 pt-6">
        <div className="banner-gradient rounded-2xl p-6 flex items-center gap-6 overflow-hidden relative">
          <div className="absolute -right-8 -top-8 w-32 h-32 rounded-full opacity-20" style={{ background: "radial-gradient(circle, #e8607a, transparent)" }} />
          <div className="absolute right-16 -bottom-6 w-20 h-20 rounded-full opacity-10" style={{ background: "radial-gradient(circle, #f4a0b0, transparent)" }} />
          <div className="flex -space-x-3 flex-shrink-0 relative z-10">
            {characters.slice(0, 4).map((char) => (
              <div key={char.id} className="w-12 h-12 rounded-full border-2 overflow-hidden flex-shrink-0"
                style={{ borderColor: "#2e1f26" }}>
                <img src={char.avatar_url} alt={char.name} className="w-full h-full object-cover object-top" />
              </div>
            ))}
            {/* Skeleton placeholders while characters load */}
            {characters.length === 0 && [0,1,2,3].map((i) => (
              <div key={i} className="w-12 h-12 rounded-full border-2 animate-pulse"
                style={{ borderColor: "#2e1f26", background: ["linear-gradient(135deg,#e8607a,#d0405a)","linear-gradient(135deg,#f4a0b0,#e8607a)","linear-gradient(135deg,#d0405a,#b03050)","linear-gradient(135deg,#f07b90,#e8607a)"][i] }} />
            ))}
          </div>
          <div className="flex-1 min-w-0 relative z-10">
            <h2 className="text-lg font-bold text-white mb-0.5">{t.home.bannerTitle}</h2>
            <p className="text-xs" style={{ color: "rgba(240,232,236,0.5)" }}>{t.home.bannerDesc}</p>
          </div>
          <Link href="/create" className="accent-btn px-5 py-2.5 rounded-xl text-sm font-medium text-white flex-shrink-0 relative z-10">
            {t.home.createNow}
          </Link>
        </div>
      </div>

      {/* Search + Categories */}
      <div className="px-6 pt-5 pb-2">
        <div className="mb-4">
          <input type="text" placeholder={t.home.searchPlaceholder} value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full max-w-xs rounded-xl border px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500/40 focus:border-rose-500/40 placeholder:text-[var(--muted)]"
            style={{ background: "var(--card-bg)", borderColor: "var(--card-border)" }}
          />
        </div>
        <div className="flex gap-1.5 flex-wrap">
          {categories.map((cat) => (
            <button key={cat} onClick={() => setActiveCategory(cat)}
              className={`category-pill px-3.5 py-1.5 rounded-full text-sm border ${activeCategory === cat ? "active" : ""}`}
              style={activeCategory !== cat ? { borderColor: "var(--card-border)", color: "var(--muted)" } : { border: "none" }}
            >
              {categoryIcons[cat] ? `${categoryIcons[cat]} ${cat}` : cat}
            </button>
          ))}
        </div>
      </div>

      {/* Character Grid */}
      <div className="px-6 pb-8 pt-4">
        {error && (
          <div className="text-center py-12">
            <p className="text-red-400 text-lg mb-2">{t.home.connectionError}</p>
            <p style={{ color: "var(--muted)" }} className="text-sm">{t.home.backendOffline}</p>
          </div>
        )}
        {loading && !error && (
          <div className="flex items-center justify-center py-16">
            <div className="flex items-center gap-3">
              <div className="w-6 h-6 border-2 border-rose-500 border-t-transparent rounded-full animate-spin" />
              <span style={{ color: "var(--muted)" }}>{t.home.loading}</span>
            </div>
          </div>
        )}
        {!loading && !error && characters.length === 0 && (
          <div className="text-center py-16">
            <p className="text-lg mb-2">{t.home.noCharacters}</p>
            <p style={{ color: "var(--muted)" }} className="text-sm">{t.home.tryDifferent}</p>
          </div>
        )}
        {!loading && !error && characters.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {characters.map((char) => <CharacterCard key={char.id} character={char} />)}
          </div>
        )}
      </div>
    </div>
  );
}
