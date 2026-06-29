"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import dynamic from "next/dynamic";
import { useAuth, SignInButton } from "@clerk/nextjs";
import {
  sendMessageStream,
  fetchConversation,
  fetchConversations,
  createConversation,
  fetchCharacter,
  checkinConversation,
  drawSurprise,
  resolveImageUrl,
  type ChatMessage,
  type ChatImage,
  type Character,
  type IntimacyUpdate,
  type StreakUpdate,
  type ToolExecuting,
  type ToolResult,
} from "@/lib/api";
import { useT, useI18n } from "@/contexts/I18nContext";
import { AudioPlayer } from "@/components/AudioPlayer";

// Lazy-load the story event modal; it's only rendered when an event triggers.
const EventModal = dynamic(() => import("@/components/EventModal"), { ssr: false });

// Lazy-load the memory panel; only rendered when the drawer is open.
const MemoryPanel = dynamic(() => import("@/components/MemoryPanel"), { ssr: false });

interface Props {
  characterId: number;
}

function getAvatarGradient(name: string): string {
  const gradients = [
    "from-rose-700 to-red-900",
    "from-pink-700 to-rose-900",
    "from-rose-600 to-pink-900",
    "from-red-700 to-rose-900",
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return gradients[Math.abs(hash) % gradients.length];
}

let _msgIdCounter = 0;
function uniqueId() { return Date.now() * 1000 + (++_msgIdCounter); }

// Include optional surrounding roleplay asterisks e.g. *[SCENE:0]* → strip whole thing
const IMG_TAG_RE = /\*?\s*\[IMG:\s*[^\]]+\]\s*\*?/g;
const SCENE_TAG_RE = /\*?\s*\[SCENE:\s*\d+\]\s*\*?/g;
// u flag required for supplementary Unicode (emoji are > U+FFFF, surrogate pairs without u flag)
const EMOJI_IMG_RE = /[🖼📸🌄🎨]\s*[^\n\[]{15,200}/gu;
// Weaker models leak the prompt's internal Hook labels ("SECRET TEASE:", etc.)
// into the reply — strip them so the user never sees scaffolding. Optional
// surrounding */_ markdown and half/full-width colon are consumed.
const HOOK_LABEL_RE = /[*_]{0,2}\s*(SECRET TEASE|MEMORY CALLBACK|EMOTIONAL CRACK|PROGRESS HINT|INTERRUPTED CONFESSION|CLIFFHANGER|QUESTION|HOOK|钩子)\s*[:：]\s*[*_]{0,2}\s*/gi;
// Tool calls are executed server-side and shown via the tool-result UI — the
// raw ```tool {...}``` block must never appear as message text.
const TOOL_BLOCK_RE = /```tool[\s\S]*?```/g;

function stripImgTags(text: string): string {
  return text.replace(IMG_TAG_RE, "").replace(SCENE_TAG_RE, "").replace(EMOJI_IMG_RE, "").replace(TOOL_BLOCK_RE, "").replace(HOOK_LABEL_RE, "").trim();
}

const MD_IMG_RE = /!\[([^\]]*)\]\(([^)]+)\)/g;

/** Extract images from markdown ![alt](url) in stored messages. */
function extractMarkdownImages(content: string): { cleanContent: string; images: ChatImage[] } {
  const images: ChatImage[] = [];
  const cleanContent = content.replace(MD_IMG_RE, (_, alt, url) => {
    images.push({ url, alt });
    return "";
  }).trim();
  return { cleanContent, images };
}

/**
 * Renders roleplay-style text:
 *   **text**  → bold
 *   *text*    → italic + muted color (for action/narration)
 *   newlines  → <br/>
 */
function renderRoleplayText(text: string): React.ReactNode {
  // Split on bold first (**text**), then italic (*text*), then newlines
  const parts: React.ReactNode[] = [];
  // Regex: matches **bold**, *italic*, or plain text segments
  const regex = /(\*\*[^*]+\*\*|\*[^*\n]+\*|\n)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = regex.exec(text)) !== null) {
    // Plain text before this match
    if (match.index > last) {
      parts.push(<span key={key++}>{text.slice(last, match.index)}</span>);
    }
    const token = match[0];
    if (token === "\n") {
      parts.push(<br key={key++} />);
    } else if (token.startsWith("**")) {
      parts.push(<strong key={key++}>{token.slice(2, -2)}</strong>);
    } else {
      // *action* — italic with muted accent color (roleplay narration style)
      parts.push(
        <em key={key++} style={{ color: "var(--accent-2)", fontStyle: "italic", opacity: 0.9 }}>
          {token.slice(1, -1)}
        </em>
      );
    }
    last = match.index + token.length;
  }
  // Remaining text
  if (last < text.length) {
    parts.push(<span key={key++}>{text.slice(last)}</span>);
  }
  return <>{parts}</>;
}

// Intimacy tier definitions (mirror of backend)
const INTIMACY_TIERS = [
  { threshold: 0,  name: "陌生",    color: "#888", emoji: "🤝" },
  { threshold: 20, name: "普通朋友", color: "#60a5fa", emoji: "😊" },
  { threshold: 40, name: "亲近",    color: "#f472b6", emoji: "💞" },
  { threshold: 60, name: "暧昧",    color: "#e879f9", emoji: "💕" },
  { threshold: 80, name: "亲密无间", color: "#f43f5e", emoji: "❤️" },
];

function getIntimacyTier(level: number) {
  let tier = INTIMACY_TIERS[0];
  for (const t of INTIMACY_TIERS) {
    if (level >= t.threshold) tier = t;
  }
  return tier;
}

// Surprise (gacha) rarity → reveal styling. Mirrors backend rarity strings.
const SURPRISE_RARITY: Record<string, { label: string; color: string; shine: boolean }> = {
  common:    { label: "普通", color: "#9ca3af", shine: false },
  rare:      { label: "稀有", color: "#60a5fa", shine: false },
  epic:      { label: "史诗", color: "#a855f7", shine: false },
  legendary: { label: "传说", color: "#f5c518", shine: true },
};

function getSurpriseRarity(rarity?: string) {
  return (rarity && SURPRISE_RARITY[rarity]) || SURPRISE_RARITY.common;
}

interface SurpriseReveal {
  rarity: string;
  intimacy_bonus: number;
}

export default function ChatInterface({ characterId }: Props) {
  const t = useT();
  const { locale } = useI18n();
  const { getToken, isSignedIn } = useAuth();
  const [memoryBannerDismissed, setMemoryBannerDismissed] = useState(false);
  const [showMemory, setShowMemory] = useState(false);
  const [character, setCharacter] = useState<Character | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [generatingImage, setGeneratingImage] = useState(false);
  const [streamingImages, setStreamingImages] = useState<ChatImage[]>([]);
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);
  const [intimacyLevel, setIntimacyLevel] = useState(0);
  const [intimacyToast, setIntimacyToast] = useState<IntimacyUpdate | null>(null);
  const [checkinToast, setCheckinToast] = useState<number | null>(null);
  const [surpriseReveal, setSurpriseReveal] = useState<SurpriseReveal | null>(null);
  const [surpriseUnavailable, setSurpriseUnavailable] = useState(false);
  const [drawingSurprise, setDrawingSurprise] = useState(false);
  const [streakDays, setStreakDays] = useState(0);
  const [streakToast, setStreakToast] = useState<StreakUpdate | null>(null);
  const [toolExecuting, setToolExecuting] = useState<ToolExecuting | null>(null);
  const [toolResult, setToolResult] = useState<ToolResult | null>(null);
  const [storyEvent, setStoryEvent] = useState<import("@/components/EventModal").StoryEventData | null>(null);
  const [ttsEnabled, setTtsEnabled] = useState(false);
  const lastAiMsgIdRef = useRef<number | undefined>(undefined);
  const checkedInRef = useRef<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const streamingTextRef = useRef("");

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingText, scrollToBottom]);

  useEffect(() => {
    // Clear all state immediately when character changes
    setCharacter(null);
    setMessages([]);
    setConversationId(null);
    setStreamingText("");
    setError(null);
    setGeneratingImage(false);
    setStreamingImages([]);
    setIntimacyLevel(0);
    setIntimacyToast(null);
    setSurpriseReveal(null);
    setSurpriseUnavailable(false);
    setDrawingSurprise(false);
    setStreakDays(0);
    setStreakToast(null);
    setToolExecuting(null);
    setToolResult(null);
    streamingTextRef.current = "";

    async function init() {
      try {
        const char = await fetchCharacter(characterId, locale);
        setCharacter(char);

        // Get-or-create: reuse existing conversation for this character
        const token = await getToken();
        const existing = await fetchConversations(characterId, token);

        let convId: number;
        if (existing.length > 0) {
          // Reuse the most recent conversation. The API returns them ordered
          // by updated_at DESC, so the most recent is existing[0] (NOT [-1],
          // which is the oldest and may be a stale/other-user conversation).
          convId = existing[0].id;
        } else {
          const conv = await createConversation(characterId, token);
          convId = conv.id;
        }
        setConversationId(convId);
        // Notify Sidebar to refresh its chat list now that the conversation exists
        window.dispatchEvent(new CustomEvent("conversation-ready", { detail: { characterId } }));

        const detail = await fetchConversation(convId, token);
        if (detail.messages.length > 0) {
          setMessages(detail.messages);
        }
        setIntimacyLevel(detail.intimacy_level ?? 0);
        setStreakDays(detail.streak_days ?? 0);

        // Proactive return greeting: if the user has been away a while, the
        // character opens the conversation ("missed you"). Guarded so it fires
        // at most once per conversation load (React strict-mode double-invoke).
        if (detail.messages.length > 0 && checkedInRef.current !== convId) {
          checkedInRef.current = convId;
          const ci = await checkinConversation(convId, token);
          if (ci?.greeting) {
            setMessages((prev) => [
              ...prev,
              {
                id: uniqueId(),
                role: "assistant",
                content: ci.greeting as string,
                created_at: new Date().toISOString(),
              },
            ]);
          }
          // Daily check-in reward — reciprocity payoff: she's glad you came back.
          if (ci?.checkin_reward && ci.checkin_reward > 0) {
            if (typeof ci.intimacy_level === "number") setIntimacyLevel(ci.intimacy_level);
            setCheckinToast(ci.checkin_reward);
            setTimeout(() => setCheckinToast(null), 4000);
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : t.chat.initFailed);
      }
    }
    init();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [characterId, locale]);

  const handleSend = async () => {
    if (!input.trim() || isStreaming || !conversationId) return;

    const userMessage = input.trim();
    setInput("");
    setError(null);

    const userMsg: ChatMessage = {
      id: uniqueId(),
      role: "user",
      content: userMessage,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsStreaming(true);
    setStreamingText("");
    setGeneratingImage(false);
    setStreamingImages([]);
    streamingTextRef.current = "";

    const collectedImages: ChatImage[] = [];
    const token = await getToken();
    await sendMessageStream(
      conversationId,
      userMessage,
      (chunk) => {
        streamingTextRef.current += chunk;
        setStreamingText(streamingTextRef.current);
      },
      () => {
        const finalText = streamingTextRef.current;
        const hasImages = collectedImages.length > 0;
        if (finalText.trim() || hasImages) {
          const aiMsg: ChatMessage = {
            id: uniqueId(),
            role: "assistant",
            content: stripImgTags(finalText),
            images: hasImages ? [...collectedImages] : undefined,
            created_at: new Date().toISOString(),
          };
          lastAiMsgIdRef.current = aiMsg.id;
          setMessages((prev) => [...prev, aiMsg]);
        } else {
          // Model produced nothing (e.g. reasoning consumed the token budget,
          // or a transient model error). Never fail silently — tell the user.
          setError("角色这次没有回复，请重试。(No reply — please try again.)");
        }
        streamingTextRef.current = "";
        setStreamingText("");
        setStreamingImages([]);
        setGeneratingImage(false);
        setIsStreaming(false);
        inputRef.current?.focus();
      },
      (errMsg) => {
        setError(errMsg);
        setIsStreaming(false);
        setGeneratingImage(false);
        setStreamingImages([]);
        streamingTextRef.current = "";
        setStreamingText("");
      },
      locale,
      token,
      (image) => {
        collectedImages.push(image);
        setStreamingImages((prev) => [...prev, image]);
        setGeneratingImage(false);
      },
      () => {
        setGeneratingImage(true);
      },
      (intimacy) => {
        setIntimacyLevel(intimacy.level);
        if (intimacy.tier_unlocked) {
          setIntimacyToast(intimacy);
          setTimeout(() => setIntimacyToast(null), 4000);
        }
      },
      (streak) => {
        setStreakDays(streak.streak_days);
        if (streak.milestone_toast) {
          setStreakToast(streak);
          setTimeout(() => setStreakToast(null), 5000);
        }
      },
      (tool) => {
        setToolExecuting(tool);
        setToolResult(null);
      },
      (result) => {
        setToolResult(result);
        setToolExecuting(null);
        setTimeout(() => setToolResult(null), 8000);
      },
      (followupText) => {
        // Append tool follow-up to the last assistant message
        setMessages((prev) => {
          const last = [...prev];
          for (let i = last.length - 1; i >= 0; i--) {
            if (last[i].role === "assistant") {
              last[i] = { ...last[i], content: last[i].content + "\n\n" + followupText };
              break;
            }
          }
          return last;
        });
      },
      (eventData) => {
        // Story event triggered — show modal
        setStoryEvent(eventData as import("@/components/EventModal").StoryEventData);
      },
      (voiceUrl) => {
        // Auto-play voice from SSE if TTS is enabled
        if (ttsEnabled && voiceUrl) {
          const fullUrl = voiceUrl.startsWith("http") ? voiceUrl : `${process.env.NEXT_PUBLIC_API_URL || ""}${voiceUrl}`;
          const audio = new Audio(fullUrl);
          audio.play().catch(() => {});
        }
      },
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleDrawSurprise = async () => {
    if (!conversationId || drawingSurprise) return;
    setDrawingSurprise(true);
    try {
      const token = await getToken();
      const res = await drawSurprise(conversationId, token);
      if (!res.available) {
        setSurpriseUnavailable(true);
        setTimeout(() => setSurpriseUnavailable(false), 4000);
        return;
      }
      // Celebratory reveal, colored by rarity.
      setSurpriseReveal({
        rarity: res.rarity ?? "common",
        intimacy_bonus: res.intimacy_bonus ?? 0,
      });
      setTimeout(() => setSurpriseReveal(null), 4000);
      // Update intimacy meter.
      if (typeof res.intimacy_level === "number") setIntimacyLevel(res.intimacy_level);
      // Append the in-character line as a new assistant message.
      if (res.message) {
        const surpriseMsg: ChatMessage = {
          id: uniqueId(),
          role: "assistant",
          content: res.message,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, surpriseMsg]);
      }
    } finally {
      setDrawingSurprise(false);
    }
  };

  // ── Loading states ──
  if (error && !character) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center p-8">
          <p className="text-red-400 text-lg mb-2">{t.chat.connectionError}</p>
          <p className="text-sm" style={{ color: "var(--muted)" }}>
            {error}. Make sure the backend is running.
          </p>
        </div>
      </div>
    );
  }

  if (!character) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-rose-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm" style={{ color: "var(--muted)" }}>{t.chat.loading}</span>
        </div>
      </div>
    );
  }

  const hasMessages = messages.length > 0 || streamingText;

  // Reusable small avatar for AI messages
  const SmallAvatar = () =>
    character.avatar_url ? (
      <img
        src={character.avatar_url}
        alt={character.name}
        className="w-8 h-8 rounded-full object-cover object-top flex-shrink-0 ring-1 ring-white/10"
      />
    ) : (
      <div className={`w-8 h-8 rounded-full bg-gradient-to-br ${getAvatarGradient(character.name)} flex items-center justify-center text-white text-xs font-bold flex-shrink-0`}>
        {character.name.charAt(0)}
      </div>
    );

  // Time-based online status indicator
  const OnlineIndicator = () => {
    const hour = new Date().getHours();
    let label: string;
    let color: string;
    let dot: string;
    if (hour >= 0 && hour < 6) {
      label = "深夜"; color = "#6366f1"; dot = "bg-indigo-400";
    } else if (hour < 9) {
      label = "清晨"; color = "#f59e0b"; dot = "bg-amber-400";
    } else if (hour < 18) {
      label = "在线"; color = "#22c55e"; dot = "bg-green-400";
    } else if (hour < 22) {
      label = "傍晚"; color = "#f97316"; dot = "bg-orange-400";
    } else {
      label = "深夜"; color = "#6366f1"; dot = "bg-indigo-400";
    }
    return (
      <div className="flex items-center gap-1 text-[11px]" style={{ color }}>
        <span className={`w-1.5 h-1.5 rounded-full ${dot} animate-pulse`} />
        {label}
      </div>
    );
  };

  const intimacyTier = getIntimacyTier(intimacyLevel);
  const nextTier = INTIMACY_TIERS.find(t => t.threshold > intimacyLevel);
  const tierRange = nextTier ? nextTier.threshold - intimacyTier.threshold : 20;
  const progressInTier = intimacyLevel - intimacyTier.threshold;
  const tierProgress = Math.min(100, Math.round((progressInTier / tierRange) * 100));

  return (
    <div className="flex flex-col h-full" style={{ background: "var(--background)" }}>

      {/* ── Story Event Modal ── */}
      {storyEvent && EventModal && (
        <EventModal
          event={storyEvent}
          conversationId={conversationId!}
          characterName={character.name}
          characterAvatar={character.avatar_url ? resolveImageUrl(character.avatar_url) : undefined}
          onResolved={(reaction: string, delta: number, newLevel: number) => {
            setIntimacyLevel(newLevel);
            // Inject character's reaction as a new message
            if (reaction) {
              const reactionMsg: ChatMessage = {
                id: uniqueId(),
                role: "assistant",
                content: reaction,
                created_at: new Date().toISOString(),
              };
              setMessages((prev) => [...prev, reactionMsg]);
            }
          }}
          onDismiss={() => setStoryEvent(null)}
        />
      )}

      {/* ── Daily Check-in Reward Toast ── */}
      {checkinToast && (
        <div
          className="fixed top-4 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-2xl text-white text-sm font-medium shadow-xl animate-bounce"
          style={{ background: "linear-gradient(135deg, #f472b6, #e8607a)" }}
        >
          💞 {character?.name} 很开心你回来了 · 亲密度 +{checkinToast}
        </div>
      )}

      {/* ── Daily Surprise (gacha) Reveal Overlay ── */}
      {surpriseReveal && (() => {
        const r = getSurpriseRarity(surpriseReveal.rarity);
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
            <div
              className="px-8 py-6 rounded-3xl text-center text-white shadow-2xl animate-bounce"
              style={{
                background: `linear-gradient(135deg, ${r.color}, ${r.color}cc)`,
                boxShadow: r.shine
                  ? `0 0 36px 6px ${r.color}99, 0 0 80px 12px ${r.color}55`
                  : `0 0 28px 4px ${r.color}66`,
                border: r.shine ? `2px solid ${r.color}` : "none",
              }}
            >
              <div className="text-4xl mb-2">{r.shine ? "🌟🎁🌟" : "✨🎁✨"}</div>
              <div className="text-lg font-bold">
                {r.label}惊喜！
              </div>
              <div className="text-sm font-medium mt-1 opacity-95">
                亲密度 +{surpriseReveal.intimacy_bonus}
              </div>
            </div>
          </div>
        );
      })()}

      {/* ── Surprise already claimed today Toast ── */}
      {surpriseUnavailable && (
        <div
          className="fixed top-4 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-2xl text-white text-sm font-medium shadow-xl animate-bounce"
          style={{ background: "linear-gradient(135deg, #f59e0b, #d97706)" }}
        >
          🎁 今天的惊喜已经领取啦，明天再来~
        </div>
      )}

      {/* ── Intimacy Unlock Toast ── */}
      {intimacyToast && (
        <div
          className="fixed top-4 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-2xl text-white text-sm font-medium shadow-xl animate-bounce"
          style={{ background: "linear-gradient(135deg, #e879f9, #f43f5e)" }}
        >
          💕 解锁新阶段：{intimacyToast.unlocked_tier_name}！
        </div>
      )}

      {/* ── Streak Milestone Toast ── */}
      {streakToast && (
        <div
          className="fixed top-16 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-2xl text-white text-sm font-medium shadow-xl"
          style={{ background: "linear-gradient(135deg, #f97316, #ef4444)", animation: "fadeInDown 0.4s ease" }}
        >
          {streakToast.milestone_toast}
        </div>
      )}

      {/* ── Character Header (ClawFans style: centered avatar + name) ── */}
      <div
        className="flex flex-col items-center pt-6 pb-4 border-b flex-shrink-0"
        style={{ borderColor: "var(--card-border)" }}
      >
        {character.avatar_url ? (
          <img
            src={character.avatar_url}
            alt={character.name}
            className="w-20 h-20 rounded-full object-cover object-top mb-2 ring-2 ring-rose-500/30"
          />
        ) : (
          <div className={`w-20 h-20 rounded-full bg-gradient-to-br ${getAvatarGradient(character.name)} flex items-center justify-center text-white text-2xl font-bold mb-2`}>
            {character.name.charAt(0)}
          </div>
        )}
        <h2 className="font-bold text-base">{character.name}</h2>

        {/* ── Streak + Online Status + TTS Toggle Row ── */}
        <div className="flex items-center gap-3 mt-1">
          {/* Online/time state indicator */}
          <OnlineIndicator />
          {/* Streak counter */}
          {streakDays >= 1 && (
            <div className="flex items-center gap-1 text-[11px]" style={{ color: "var(--muted)" }}>
              <span>{streakDays >= 30 ? "🔥🔥🔥" : streakDays >= 7 ? "🔥🔥" : "🔥"}</span>
              <span className="font-medium" style={{ color: "#f97316" }}>
                {streakDays}天连续
              </span>
            </div>
          )}
          {/* TTS auto-play toggle */}
          <button
            onClick={() => setTtsEnabled((v) => !v)}
            title={ttsEnabled ? "关闭自动朗读" : "开启自动朗读（新消息自动播放）"}
            className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] transition-all border ${
              ttsEnabled
                ? "border-rose-400/40 bg-rose-500/15 text-rose-400"
                : "border-transparent text-gray-400 hover:text-rose-400 hover:border-rose-400/30"
            }`}
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-3 h-3">
              <path d="M10 3.75a.75.75 0 0 0-1.264-.546L4.703 7H3.167a.75.75 0 0 0-.75.75v4.5c0 .414.336.75.75.75h1.536l4.033 3.796A.75.75 0 0 0 10 16.25V3.75ZM15.95 5.05a.75.75 0 1 0-1.06 1.061 5.5 5.5 0 0 1 0 7.778.75.75 0 1 0 1.06 1.06 7 7 0 0 0 0-9.899ZM13.829 7.172a.75.75 0 1 0-1.061 1.06 2.5 2.5 0 0 1 0 3.536.75.75 0 1 0 1.06 1.06 4 4 0 0 0 0-5.656Z" />
            </svg>
            {ttsEnabled ? "自动朗读 ●" : "自动朗读"}
          </button>
          {/* Memory drawer toggle */}
          <button
            onClick={() => setShowMemory((v) => !v)}
            title="她记得你什么"
            className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] transition-all border ${
              showMemory
                ? "border-rose-400/40 bg-rose-500/15 text-rose-400"
                : "border-transparent text-gray-400 hover:text-rose-400 hover:border-rose-400/30"
            }`}
          >
            <span>🧠</span>
            记忆
          </button>
          {/* Daily surprise (gacha) draw */}
          <button
            onClick={handleDrawSurprise}
            disabled={drawingSurprise}
            title="每日惊喜 · 开盒"
            className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] transition-all border border-transparent text-gray-400 hover:text-amber-300 hover:border-amber-300/30 disabled:opacity-40"
          >
            {drawingSurprise ? (
              <span className="w-3 h-3 border border-amber-300/70 border-t-transparent rounded-full animate-spin" />
            ) : (
              <span>🎁</span>
            )}
            惊喜
          </button>
        </div>

        <p className="text-[11px] mt-1 max-w-xs text-center px-4" style={{ color: "var(--muted)" }}>
          {t.chat.disclaimer}
        </p>

        {/* ── Intimacy Meter ── */}
        <div className="mt-3 w-48 flex flex-col items-center gap-1">
          <div className="flex items-center justify-between w-full text-[10px]" style={{ color: "var(--muted)" }}>
            <span style={{ color: intimacyTier.color }}>{intimacyTier.emoji} {intimacyTier.name}</span>
            <span>{intimacyLevel}/100</span>
          </div>
          <div className="w-full h-1.5 rounded-full overflow-hidden" style={{ background: "var(--card-border)" }}>
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${tierProgress}%`,
                background: `linear-gradient(90deg, ${intimacyTier.color}99, ${intimacyTier.color})`,
              }}
            />
          </div>
          {nextTier && (
            <div className="text-[9px]" style={{ color: "var(--muted)" }}>
              还差 {nextTier.threshold - intimacyLevel} 点解锁「{nextTier.name}」
            </div>
          )}
        </div>
      </div>

      {/* ── Memory upsell banner (anonymous users only) ── */}
      {!isSignedIn && !memoryBannerDismissed && (
        <div className="mx-4 mt-3 px-4 py-2.5 rounded-xl flex items-center gap-3 text-xs"
          style={{ background: "rgba(244,114,182,0.08)", border: "1px solid rgba(244,114,182,0.25)" }}>
          <span className="text-lg">🧠</span>
          <span style={{ color: "var(--muted)" }}>
            登录后自动保存记忆，跨设备同步对话记录。
          </span>
          <SignInButton mode="modal">
            <button className="ml-auto shrink-0 px-3 py-1 rounded-lg text-xs font-semibold transition-colors"
              style={{ background: "var(--accent)", color: "#fff" }}>
              登录
            </button>
          </SignInButton>
          <button onClick={() => setMemoryBannerDismissed(true)}
            className="shrink-0 opacity-40 hover:opacity-80 transition-opacity text-base leading-none"
            style={{ color: "var(--muted)" }}>
            ✕
          </button>
        </div>
      )}

      {/* ── Messages ── */}
      <div className="flex-1 overflow-y-auto px-4 py-5">
        <div className="max-w-2xl mx-auto space-y-4">

          {/* Greeting block */}
          {!hasMessages && character.greeting && (
            <div className="flex gap-3 items-start">
              <SmallAvatar />
              <div
                className="flex-1 rounded-2xl rounded-tl-sm px-4 py-3 text-sm leading-relaxed"
                style={{ background: "var(--card-bg)", border: "1px solid var(--card-border)" }}
              >
                <AudioPlayer text={character.greeting} charId={character.id} />
                {renderRoleplayText(character.greeting)}
              </div>
            </div>
          )}

          {/* Chat history */}
          {messages.map((msg) => {
            const parsed = msg.role === "assistant" ? extractMarkdownImages(msg.content) : null;
            const displayContent = parsed ? parsed.cleanContent : msg.content;
            const msgImages = msg.images ?? parsed?.images ?? [];

            return (
              <div
                key={msg.id}
                className={`flex gap-3 items-start ${msg.role === "user" ? "flex-row-reverse" : ""}`}
              >
                {msg.role === "assistant" && <SmallAvatar />}

                <div
                  className={`text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "rounded-2xl rounded-tr-sm max-w-[75%] text-white px-4 py-3"
                      : "flex-1 rounded-2xl rounded-tl-sm px-4 py-3"
                  }`}
                  style={
                    msg.role === "user"
                      ? { background: "linear-gradient(135deg, #e8607a, #c0405a)" }
                      : { background: "var(--card-bg)", border: "1px solid var(--card-border)" }
                  }
                >
                  {/* TTS pill — above message text, like competitor */}
                  {msg.role === "assistant" && (
                    <AudioPlayer
                      text={stripImgTags(displayContent)}
                      charId={character.id}
                      autoPlay={ttsEnabled && msg.id === lastAiMsgIdRef.current}
                    />
                  )}

                  {msg.role === "user"
                    ? msg.content
                    : renderRoleplayText(stripImgTags(displayContent))}

                  {/* Inline images */}
                  {msgImages.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {msgImages.map((img, idx) => (
                        <button
                          key={idx}
                          onClick={() => setLightboxUrl(resolveImageUrl(img.url))}
                          className="block rounded-xl overflow-hidden hover:opacity-90 transition-opacity cursor-zoom-in"
                        >
                          <img
                            src={resolveImageUrl(img.url)}
                            alt={img.alt}
                            className="max-w-[280px] max-h-[400px] rounded-xl object-cover"
                            loading="lazy"
                          />
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {/* Streaming message */}
          {isStreaming && (
            <div className="flex gap-3 items-start">
              <SmallAvatar />
              <div
                className="flex-1 rounded-2xl rounded-tl-sm px-4 py-3 text-sm leading-relaxed"
                style={{ background: "var(--card-bg)", border: "1px solid var(--card-border)" }}
              >
                {streamingText ? renderRoleplayText(stripImgTags(streamingText)) : (
                  <span className="flex items-center gap-1.5 py-0.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-bounce" style={{ animationDelay: "160ms" }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-bounce" style={{ animationDelay: "320ms" }} />
                  </span>
                )}

                {/* Image generation in progress */}
                {generatingImage && (
                  <div className="mt-3 flex items-center gap-2 text-xs px-3 py-2 rounded-lg"
                    style={{ background: "rgba(244,114,182,0.08)", border: "1px solid rgba(244,114,182,0.2)" }}>
                    <span className="w-4 h-4 border-2 border-rose-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
                    <span style={{ color: "var(--muted)" }}>正在生成图片，稍候约 30 秒…</span>
                  </div>
                )}

                {/* Tool executing indicator */}
                {toolExecuting && (
                  <div className="mt-3 flex items-center gap-2 text-xs px-3 py-2 rounded-lg"
                    style={{ background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.25)" }}>
                    <span className="w-4 h-4 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
                    <span style={{ color: "#818cf8" }}>
                      {toolExecuting.name === "food_search" && `🍜 正在搜索「${toolExecuting.args?.keyword || ""}」外卖…`}
                      {toolExecuting.name === "weather" && `🌤 正在查询「${toolExecuting.args?.city || ""}」天气…`}
                      {toolExecuting.name === "web_search" && `🔍 正在搜索「${toolExecuting.args?.query || ""}」…`}
                      {!["food_search","weather","web_search"].includes(toolExecuting.name) && `⚙️ 正在执行 ${toolExecuting.name}…`}
                    </span>
                  </div>
                )}

                {/* Tool result card (brief, auto-dismiss) */}
                {toolResult && !toolExecuting && (
                  <div className="mt-2 text-[10px] px-2 py-1 rounded flex items-center gap-1"
                    style={{ background: toolResult.success ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)", color: toolResult.success ? "#4ade80" : "#f87171" }}>
                    {toolResult.success ? "✓" : "✗"} {toolResult.name} 完成
                  </div>
                )}

                {/* Streamed images (arrived during this turn) */}
                {streamingImages.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {streamingImages.map((img, idx) => (
                      <button
                        key={idx}
                        onClick={() => setLightboxUrl(resolveImageUrl(img.url))}
                        className="block rounded-xl overflow-hidden hover:opacity-90 transition-opacity cursor-zoom-in"
                      >
                        <img
                          src={resolveImageUrl(img.url)}
                          alt={img.alt}
                          className="max-w-[280px] max-h-[400px] rounded-xl object-cover"
                          loading="lazy"
                        />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="rounded-xl px-4 py-3 text-sm" style={{ background: "rgba(239,68,68,0.1)", color: "#f87171" }}>
              {error}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* ── Memory drawer ── */}
      {showMemory && (
        <div className="fixed inset-0 z-50 flex justify-end" onClick={() => setShowMemory(false)}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
          <div
            className="relative w-80 max-w-[85vw] h-full overflow-y-auto border-l flex flex-col"
            style={{ background: "var(--background)", borderColor: "var(--card-border)", animation: "fadeInDown 0.25s ease" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              className="flex items-center justify-between px-4 py-3 border-b flex-shrink-0"
              style={{ borderColor: "var(--card-border)" }}
            >
              <div className="flex items-center gap-2">
                <span className="text-base">🧠</span>
                <h3 className="text-sm font-semibold">她记得你什么</h3>
              </div>
              <button
                onClick={() => setShowMemory(false)}
                className="w-7 h-7 rounded-full flex items-center justify-center transition-all hover:bg-white/10"
                style={{ color: "var(--muted)" }}
                title="关闭"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-4 py-4">
              <MemoryPanel characterId={character.id} />
            </div>
          </div>
        </div>
      )}

      {/* ── Lightbox overlay ── */}
      {lightboxUrl && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={() => setLightboxUrl(null)}
        >
          <button
            className="absolute top-4 right-4 w-10 h-10 flex items-center justify-center rounded-full text-white/70 hover:text-white hover:bg-white/10 transition-colors text-2xl"
            onClick={() => setLightboxUrl(null)}
          >
            &times;
          </button>
          <img
            src={lightboxUrl}
            alt="Full size"
            className="max-w-[90vw] max-h-[90vh] rounded-2xl object-contain shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}

      {/* ── Input (ClawFans style: pill shape, up-arrow send) ── */}
      <div
        className="px-4 py-4 border-t flex-shrink-0"
        style={{ borderColor: "var(--card-border)" }}
      >
        <div className="max-w-2xl mx-auto">
          <div
            className="flex items-end gap-2 rounded-2xl border px-4 py-2"
            style={{ background: "var(--card-bg)", borderColor: "var(--card-border)" }}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t.chat.messagePlaceholder}
              rows={1}
              disabled={isStreaming}
              className="flex-1 resize-none bg-transparent text-sm focus:outline-none disabled:opacity-50 py-1"
              style={{ color: "var(--foreground)" }}
              onInput={(e) => {
                const t = e.target as HTMLTextAreaElement;
                t.style.height = "auto";
                t.style.height = Math.min(t.scrollHeight, 120) + "px";
              }}
            />
            {/* Send button — up arrow (ClawFans style) */}
            <button
              onClick={handleSend}
              disabled={!input.trim() || isStreaming}
              className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 transition-all disabled:opacity-30"
              style={{
                background: input.trim() && !isStreaming
                  ? "linear-gradient(135deg, #e8607a, #c0405a)"
                  : "var(--card-border)",
              }}
            >
              {isStreaming ? (
                <span className="w-3 h-3 border border-white/60 border-t-transparent rounded-full animate-spin" />
              ) : (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="12" y1="19" x2="12" y2="5" />
                  <polyline points="5 12 12 5 19 12" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
