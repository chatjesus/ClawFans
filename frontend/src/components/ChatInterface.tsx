"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useAuth, SignInButton } from "@clerk/nextjs";
import {
  sendMessageStream,
  fetchConversation,
  fetchConversations,
  createConversation,
  fetchCharacter,
  resolveImageUrl,
  type ChatMessage,
  type ChatImage,
  type Character,
} from "@/lib/api";
import { useT, useI18n } from "@/contexts/I18nContext";

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

function stripImgTags(text: string): string {
  return text.replace(IMG_TAG_RE, "").replace(SCENE_TAG_RE, "").replace(EMOJI_IMG_RE, "").trim();
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

export default function ChatInterface({ characterId }: Props) {
  const t = useT();
  const { locale } = useI18n();
  const { getToken, isSignedIn } = useAuth();
  const [memoryBannerDismissed, setMemoryBannerDismissed] = useState(false);
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
          // Reuse the most recent conversation
          convId = existing[existing.length - 1].id;
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
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/e6ced9bb-e966-4409-8f50-ec8bd238becf',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'c16f2f'},body:JSON.stringify({sessionId:'c16f2f',location:'ChatInterface.tsx:onDone',message:'on_done_callback',data:{finalTextLen:finalText.length,finalTextEmpty:!finalText.trim(),stripped:stripImgTags(finalText).length,preview:finalText.slice(0,60)},timestamp:Date.now()})}).catch(()=>{});
        // #endregion
        if (finalText.trim()) {
          const aiMsg: ChatMessage = {
            id: uniqueId(),
            role: "assistant",
            content: stripImgTags(finalText),
            images: collectedImages.length > 0 ? [...collectedImages] : undefined,
            created_at: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, aiMsg]);
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
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
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
        className="w-8 h-8 rounded-full object-cover flex-shrink-0 ring-1 ring-white/10"
      />
    ) : (
      <div className={`w-8 h-8 rounded-full bg-gradient-to-br ${getAvatarGradient(character.name)} flex items-center justify-center text-white text-xs font-bold flex-shrink-0`}>
        {character.name.charAt(0)}
      </div>
    );

  return (
    <div className="flex flex-col h-full" style={{ background: "var(--background)" }}>

      {/* ── Character Header (ClawFans style: centered avatar + name) ── */}
      <div
        className="flex flex-col items-center pt-6 pb-4 border-b flex-shrink-0"
        style={{ borderColor: "var(--card-border)" }}
      >
        {character.avatar_url ? (
          <img
            src={character.avatar_url}
            alt={character.name}
            className="w-20 h-20 rounded-full object-cover mb-2 ring-2 ring-rose-500/30"
          />
        ) : (
          <div className={`w-20 h-20 rounded-full bg-gradient-to-br ${getAvatarGradient(character.name)} flex items-center justify-center text-white text-2xl font-bold mb-2`}>
            {character.name.charAt(0)}
          </div>
        )}
        <h2 className="font-bold text-base">{character.name}</h2>
        <p className="text-[11px] mt-0.5 max-w-xs text-center px-4" style={{ color: "var(--muted)" }}>
          {t.chat.disclaimer}
        </p>
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
