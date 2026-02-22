"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect, useCallback, useRef } from "react";
import {
  fetchHealth,
  fetchConversations,
  deleteAllConversationsForCharacter,
  type HealthStatus,
  type Conversation,
} from "@/lib/api";
import { useI18n } from "@/contexts/I18nContext";
import { LOCALES, type Locale } from "@/i18n";

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { t, locale, setLocale } = useI18n();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [recentChats, setRecentChats] = useState<Conversation[]>([]);
  const [openMenuId, setOpenMenuId] = useState<number | null>(null);
  const [deletingCharId, setDeletingCharId] = useState<number | null>(null);
  const [showLangPicker, setShowLangPicker] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const langRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setOpenMenuId(null);
      if (langRef.current && !langRef.current.contains(e.target as Node)) setShowLangPicker(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const loadChats = useCallback(() => {
    fetchConversations()
      .then((convs) => {
        const seen = new Map<number, Conversation>();
        for (const conv of convs) {
          const ex = seen.get(conv.character_id);
          if (!ex || conv.id > ex.id) seen.set(conv.character_id, conv);
        }
        const deduped = Array.from(seen.values()).sort((a, b) => b.id - a.id).slice(0, 8);
        setRecentChats(deduped);
      })
      .catch(() => {});
  }, []);

  useEffect(() => { loadChats(); }, [pathname, loadChats]);

  useEffect(() => {
    const handler = () => loadChats();
    window.addEventListener("conversation-ready", handler);
    return () => window.removeEventListener("conversation-ready", handler);
  }, [loadChats]);

  const handleDelete = async (conv: Conversation) => {
    setOpenMenuId(null);
    setDeletingCharId(conv.character_id);
    try {
      await deleteAllConversationsForCharacter(conv.character_id);
      if (pathname === `/chat/${conv.character_id}`) router.push("/");
      loadChats();
    } catch { /* ignore */ } finally {
      setDeletingCharId(null);
    }
  };

  const currentLang = LOCALES.find(l => l.code === locale);
  const isActive = (href: string) => href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <aside
      className={`${collapsed ? "w-16" : "w-56"} h-screen flex flex-col border-r transition-all duration-200 flex-shrink-0`}
      style={{ background: "var(--sidebar-bg)", borderColor: "var(--card-border)" }}
    >
      {/* Logo */}
      <div className="p-4 flex items-center gap-2.5 flex-shrink-0">
        <button onClick={() => setCollapsed(!collapsed)} className="text-xl hover:opacity-70 transition flex-shrink-0" title={t.sidebar.toggleSidebar}>
          🦞
        </button>
        {!collapsed && (
          <Link href="/" className="font-bold text-lg gradient-text tracking-tight">{t.sidebar.brand}</Link>
        )}
      </div>

      {/* Nav */}
      <nav className="px-2 space-y-0.5 flex-shrink-0">
        {[
          { href: "/", label: t.sidebar.home, icon: "🏠" },
          { href: "/create", label: t.sidebar.createCharacter, icon: "✨" },
        ].map((item) => (
          <Link key={item.href} href={item.href}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all ${isActive(item.href) ? "font-medium nav-active" : "hover:bg-white/5"}`}
            style={!isActive(item.href) ? { color: "var(--muted)" } : undefined}
          >
            <span className="text-base flex-shrink-0">{item.icon}</span>
            {!collapsed && <span>{item.label}</span>}
          </Link>
        ))}
      </nav>

      {/* Recent Chats */}
      {!collapsed && recentChats.length > 0 && (
        <div className="flex-1 overflow-y-auto mt-4 px-2" ref={menuRef}>
          <p className="text-[10px] uppercase tracking-wider px-2 mb-2" style={{ color: "var(--muted)" }}>{t.sidebar.chats}</p>
          <div className="space-y-0.5">
            {recentChats.map((conv) => {
              const chatPath = `/chat/${conv.character_id}`;
              const active = pathname === chatPath;
              const isMenuOpen = openMenuId === conv.id;
              const isDeleting = deletingCharId === conv.character_id;
              return (
                <div key={conv.id} className="relative group">
                  <Link href={chatPath}
                    className={`flex items-center justify-between px-3 py-2 rounded-lg transition-all ${active ? "nav-active font-medium" : "hover:bg-white/5"}`}
                    style={!active ? { color: "var(--muted)" } : undefined}
                  >
                    <span className="truncate text-[12px] flex-1 pr-1">
                      {isDeleting ? (
                        <span className="flex items-center gap-1.5">
                          <span className="w-2 h-2 border border-current border-t-transparent rounded-full animate-spin" />
                          {t.sidebar.deleting}
                        </span>
                      ) : conv.title}
                    </span>
                    {!isDeleting && (
                      <button onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpenMenuId(isMenuOpen ? null : conv.id); }}
                        className="opacity-0 group-hover:opacity-100 flex-shrink-0 w-5 h-5 rounded flex items-center justify-center transition-all hover:bg-white/10"
                        style={{ color: "var(--muted)" }} title={t.sidebar.moreOptions}
                      >
                        <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor"><circle cx="3" cy="8" r="1.5"/><circle cx="8" cy="8" r="1.5"/><circle cx="13" cy="8" r="1.5"/></svg>
                      </button>
                    )}
                  </Link>
                  {isMenuOpen && (
                    <div className="absolute right-0 top-full mt-0.5 z-50 rounded-lg border py-1 shadow-xl min-w-[140px]"
                      style={{ background: "var(--card-bg)", borderColor: "var(--card-border)", boxShadow: "0 8px 24px rgba(0,0,0,0.4)" }}
                    >
                      <button onClick={() => handleDelete(conv)}
                        className="w-full flex items-center gap-2.5 px-3 py-2 text-[12px] text-left transition-all hover:bg-red-500/10"
                        style={{ color: "#f87171" }}
                      >
                        <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                          <polyline points="3 6 13 6"/><path d="M5 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/><path d="M4 6l1 8h6l1-8"/>
                        </svg>
                        {t.sidebar.deleteChat}
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {(collapsed || recentChats.length === 0) && <div className="flex-1" />}

      {/* Language Picker */}
      {!collapsed && (
        <div className="px-3 mb-2 flex-shrink-0 relative" ref={langRef}>
          <button
            onClick={() => setShowLangPicker(!showLangPicker)}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] transition-all hover:bg-white/5"
            style={{ color: "var(--muted)", border: "1px solid var(--card-border)" }}
          >
            <span>{currentLang?.flag}</span>
            <span className="flex-1 text-left">{currentLang?.label}</span>
            <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 11L2 5h12z"/>
            </svg>
          </button>
          {showLangPicker && (
            <div className="absolute bottom-full left-0 right-0 mx-3 mb-1 rounded-xl border shadow-xl overflow-hidden z-50"
              style={{ background: "var(--card-bg)", borderColor: "var(--card-border)", boxShadow: "0 -8px 24px rgba(0,0,0,0.4)" }}
            >
              {LOCALES.map((loc) => (
                <button key={loc.code} onClick={() => { setLocale(loc.code as Locale); setShowLangPicker(false); }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-[12px] text-left transition-all hover:bg-white/5"
                  style={{ color: locale === loc.code ? "var(--accent)" : "var(--text)", background: locale === loc.code ? "rgba(244,63,94,0.06)" : undefined }}
                >
                  <span>{loc.flag}</span>
                  <span>{loc.label}</span>
                  {locale === loc.code && <span className="ml-auto text-[10px]">✓</span>}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 18+ Badge */}
      {!collapsed && (
        <div className="px-3 mb-2 flex-shrink-0">
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg text-[11px]" style={{ background: "rgba(239, 68, 68, 0.08)", color: "#f87171" }}>
            <span className="font-bold text-[9px] px-1.5 py-0.5 rounded" style={{ background: "rgba(239, 68, 68, 0.2)" }}>18+</span>
            <span>{t.sidebar.adultsOnly}</span>
          </div>
        </div>
      )}

      {/* Status footer */}
      <div className="p-3 border-t text-xs flex-shrink-0" style={{ borderColor: "var(--card-border)" }}>
        {!collapsed ? (
          <div className="flex items-center gap-2">
            <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${health?.ollama === "connected" ? "bg-green-500" : "bg-red-500"}`}
              style={health?.ollama === "connected" ? { boxShadow: "0 0 4px rgba(34,197,94,0.5)" } : undefined}
            />
            <span className="text-[10px] truncate" style={{ color: "var(--muted)" }}>
              {health?.models?.[0] ?? (health?.ollama === "connected" ? t.sidebar.online : t.sidebar.offline)}
            </span>
          </div>
        ) : (
          <div className="flex justify-center">
            <span className={`w-1.5 h-1.5 rounded-full ${health?.ollama === "connected" ? "bg-green-500" : "bg-red-500"}`} />
          </div>
        )}
      </div>
    </aside>
  );
}
