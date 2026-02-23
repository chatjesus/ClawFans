"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect, useCallback, useRef } from "react";
import { UserButton, useAuth } from "@clerk/nextjs";
import {
  fetchHealth,
  fetchConversations,
  deleteAllConversationsForCharacter,
  type HealthStatus,
  type Conversation,
} from "@/lib/api";
import { useI18n } from "@/contexts/I18nContext";
import { LOCALES, type Locale } from "@/i18n";

// ── Timeline grouping helpers ──────────────────────────────────────────────

function getTimeLabel(dateStr: string): string {
  const now = new Date();
  const d = new Date(dateStr);
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterdayStart = new Date(todayStart.getTime() - 86400000);
  const weekStart = new Date(todayStart.getTime() - 6 * 86400000);

  if (d >= todayStart) return "today";
  if (d >= yesterdayStart) return "yesterday";
  if (d >= weekStart) return "week";
  return "earlier";
}

const GROUP_LABELS: Record<string, string> = {
  today: "今天",
  yesterday: "昨天",
  week: "本周",
  earlier: "更早",
};

function groupByTimeline(chats: Conversation[]): { label: string; key: string; items: Conversation[] }[] {
  const groups: Record<string, Conversation[]> = {};
  const order = ["today", "yesterday", "week", "earlier"];
  for (const conv of chats) {
    const key = getTimeLabel(conv.updated_at);
    if (!groups[key]) groups[key] = [];
    groups[key].push(conv);
  }
  return order.filter((k) => groups[k]?.length).map((k) => ({ key: k, label: GROUP_LABELS[k], items: groups[k] }));
}

// ── Avatar component ────────────────────────────────────────────────────────

const AVATAR_GRADIENTS = [
  "from-rose-600 to-pink-800",
  "from-pink-600 to-rose-800",
  "from-red-600 to-rose-800",
  "from-fuchsia-600 to-pink-800",
];

function avatarGradient(name: string) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = name.charCodeAt(i) + ((h << 5) - h);
  return AVATAR_GRADIENTS[Math.abs(h) % AVATAR_GRADIENTS.length];
}

function ChatAvatar({ conv, size = 28, active }: { conv: Conversation; size?: number; active?: boolean }) {
  const name = conv.character_name || conv.title;
  const initials = name.slice(0, 1).toUpperCase();
  return (
    <div
      className={`rounded-full flex-shrink-0 overflow-hidden flex items-center justify-center ${active ? "ring-2 ring-rose-400/60" : ""}`}
      style={{ width: size, height: size, minWidth: size }}
    >
      {conv.character_avatar ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={conv.character_avatar} alt={name} className="w-full h-full object-cover" />
      ) : (
        <div className={`w-full h-full bg-gradient-to-br ${avatarGradient(name)} flex items-center justify-center text-white font-bold`}
          style={{ fontSize: size * 0.42 }}
        >
          {initials}
        </div>
      )}
    </div>
  );
}

// ── Timeline component ──────────────────────────────────────────────────────

function ChatTimeline({
  chats, pathname, openMenuId, deletingCharId, onMenuToggle, onDelete, t,
}: {
  chats: Conversation[];
  pathname: string;
  openMenuId: number | null;
  deletingCharId: number | null;
  onMenuToggle: (id: number) => void;
  onDelete: (conv: Conversation) => void;
  t: ReturnType<typeof import("@/contexts/I18nContext").useI18n>["t"];
}) {
  const groups = groupByTimeline(chats);
  return (
    <div className="space-y-3 pb-2">
      {groups.map((group) => (
        <div key={group.key}>
          {/* Timeline label */}
          <p className="text-[10px] uppercase tracking-wider px-2 mb-1 font-medium" style={{ color: "var(--muted)" }}>
            {group.label}
          </p>
          <div className="space-y-0.5">
            {group.items.map((conv) => {
              const chatPath = `/chat/${conv.character_id}`;
              const active = pathname === chatPath;
              const isMenuOpen = openMenuId === conv.id;
              const isDeleting = deletingCharId === conv.character_id;
              const name = conv.character_name || conv.title;
              return (
                <div key={conv.id} className="relative group">
                  <Link
                    href={chatPath}
                    className={`flex items-center gap-2.5 px-2 py-1.5 rounded-lg transition-all ${active ? "nav-active" : "hover:bg-white/5"}`}
                  >
                    {/* Avatar */}
                    {isDeleting ? (
                      <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: "rgba(255,255,255,0.06)" }}>
                        <span className="w-3 h-3 border border-rose-400 border-t-transparent rounded-full animate-spin" />
                      </div>
                    ) : (
                      <ChatAvatar conv={conv} size={28} active={active} />
                    )}

                    {/* Name */}
                    <span
                      className={`truncate text-[12px] flex-1 ${active ? "font-medium" : ""}`}
                      style={{ color: active ? "var(--text)" : "var(--muted)" }}
                    >
                      {isDeleting ? (t.sidebar.deleting) : name}
                    </span>

                    {/* ··· button */}
                    {!isDeleting && (
                      <button
                        onClick={(e) => { e.preventDefault(); e.stopPropagation(); onMenuToggle(conv.id); }}
                        className="opacity-0 group-hover:opacity-100 flex-shrink-0 w-5 h-5 rounded flex items-center justify-center transition-all hover:bg-white/10"
                        style={{ color: "var(--muted)" }}
                        title={t.sidebar.moreOptions}
                      >
                        <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
                          <circle cx="3" cy="8" r="1.5"/><circle cx="8" cy="8" r="1.5"/><circle cx="13" cy="8" r="1.5"/>
                        </svg>
                      </button>
                    )}
                  </Link>

                  {/* Dropdown */}
                  {isMenuOpen && (
                    <div className="absolute right-0 top-full mt-0.5 z-50 rounded-lg border py-1 shadow-xl min-w-[140px]"
                      style={{ background: "var(--card-bg)", borderColor: "var(--card-border)", boxShadow: "0 8px 24px rgba(0,0,0,0.4)" }}
                    >
                      <button onClick={() => onDelete(conv)}
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
      ))}
    </div>
  );
}

// ── Main Sidebar ────────────────────────────────────────────────────────────

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { t, locale, setLocale } = useI18n();
  const { getToken, isSignedIn } = useAuth();
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
    getToken().then((token) => fetchConversations(undefined, token))
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
        <button onClick={() => setCollapsed(!collapsed)} className="hover:opacity-70 transition flex-shrink-0" title={t.sidebar.toggleSidebar}>
          {collapsed ? (
            /* Icon-only: claw mark */
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect width="28" height="28" rx="7" fill="#1a0d12"/>
              <path d="M9 4 Q7.5 12 10 24" stroke="#e8607a" strokeWidth="2.5" strokeLinecap="round"/>
              <path d="M14 3 Q12.5 12 14 25" stroke="#e8607a" strokeWidth="2.5" strokeLinecap="round"/>
              <path d="M19 4 Q18 12 19 24" stroke="#c04060" strokeWidth="2.5" strokeLinecap="round"/>
              <path d="M9 4 Q7.5 12 10 24" stroke="#f4a0b0" strokeWidth="0.8" strokeLinecap="round" opacity="0.5"/>
              <path d="M14 3 Q12.5 12 14 25" stroke="#f4a0b0" strokeWidth="0.8" strokeLinecap="round" opacity="0.5"/>
              <path d="M19 4 Q18 12 19 24" stroke="#f4a0b0" strokeWidth="0.8" strokeLinecap="round" opacity="0.5"/>
            </svg>
          ) : (
            /* Full logo: claw + wordmark */
            <svg width="120" height="28" viewBox="0 0 120 28" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M6 3 Q4.5 11 7 22" stroke="#e8607a" strokeWidth="2.5" strokeLinecap="round"/>
              <path d="M11 2 Q9.5 11 11 23" stroke="#e8607a" strokeWidth="2.5" strokeLinecap="round"/>
              <path d="M16 3 Q15 11 16 22" stroke="#c04060" strokeWidth="2.5" strokeLinecap="round"/>
              <path d="M6 3 Q4.5 11 7 22" stroke="#f4a0b0" strokeWidth="0.8" strokeLinecap="round" opacity="0.5"/>
              <path d="M11 2 Q9.5 11 11 23" stroke="#f4a0b0" strokeWidth="0.8" strokeLinecap="round" opacity="0.5"/>
              <path d="M16 3 Q15 11 16 22" stroke="#f4a0b0" strokeWidth="0.8" strokeLinecap="round" opacity="0.5"/>
              <text x="26" y="20" fontFamily="system-ui, -apple-system, sans-serif" fontWeight="800" fontSize="15" fill="white" letterSpacing="-0.3">Claw<tspan fill="#e8607a">Fans</tspan></text>
            </svg>
          )}
        </button>
      </div>

      {/* Nav */}
      <nav className="px-2 space-y-0.5 flex-shrink-0">
        {[
          { href: "/", label: t.sidebar.home, icon: "🏠" },
          { href: "/create", label: t.sidebar.createCharacter, icon: "✨" },
          { href: "/settings", label: (t.sidebar as Record<string, string>).settings || "Settings", icon: "⚙️" },
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

      {/* Recent Chats — timeline with avatar */}
      {!collapsed && recentChats.length > 0 && (
        <div className="flex-1 overflow-y-auto mt-3 px-2" ref={menuRef}>
          <ChatTimeline
            chats={recentChats}
            pathname={pathname}
            openMenuId={openMenuId}
            deletingCharId={deletingCharId}
            onMenuToggle={(id) => setOpenMenuId(openMenuId === id ? null : id)}
            onDelete={handleDelete}
            t={t}
          />
        </div>
      )}

      {/* Collapsed mode: stacked avatars only */}
      {collapsed && recentChats.length > 0 && (
        <div className="flex-1 overflow-y-auto py-2 flex flex-col items-center gap-1.5">
          {recentChats.map((conv) => {
            const chatPath = `/chat/${conv.character_id}`;
            const active = pathname === chatPath;
            return (
              <Link key={conv.id} href={chatPath} title={conv.character_name || conv.title}>
                <ChatAvatar conv={conv} size={32} active={active} />
              </Link>
            );
          })}
        </div>
      )}

      {recentChats.length === 0 && <div className="flex-1" />}

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

      {/* User account */}
      <div className="px-3 mb-2 flex-shrink-0">
        {!collapsed ? (
          <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--card-border)" }}>
            <UserButton
              appearance={{
                elements: {
                  avatarBox: "w-6 h-6",
                  userButtonPopoverCard: "bg-[var(--card-bg)] border border-[var(--card-border)]",
                },
              }}
            />
            {isSignedIn && (
              <span className="text-[11px] truncate" style={{ color: "var(--muted)" }}>
                {(t.sidebar as Record<string, string>).account || "My Account"}
              </span>
            )}
            {!isSignedIn && (
              <Link href="/sign-in" className="text-[11px] transition-colors hover:text-white" style={{ color: "var(--accent)" }}>
                {(t.sidebar as Record<string, string>).signIn || "Sign In"}
              </Link>
            )}
          </div>
        ) : (
          <div className="flex justify-center">
            <UserButton appearance={{ elements: { avatarBox: "w-6 h-6" } }} />
          </div>
        )}
      </div>

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
