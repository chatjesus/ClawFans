"use client";
/**
 * Story Event Modal — shown when a milestone event triggers.
 * Displays the scene description and 3 choices; sends the user's pick to backend.
 */
import { useState } from "react";

export interface EventChoice {
  text: string;
  hint?: string;
  intimacy_delta?: number;
}

export interface StoryEventData {
  instance_id: number;
  event_id: number;
  title: string;
  description: string;
  choices: EventChoice[];
  event_type?: string;
}

interface EventModalProps {
  event: StoryEventData;
  conversationId: number;
  characterName: string;
  characterAvatar?: string;
  onResolved: (reaction: string, intimacyDelta: number, intimacyLevel: number) => void;
  onDismiss: () => void;
}

const EVENT_TYPE_ICON: Record<string, string> = {
  milestone: "✨",
  daily: "🌅",
  crisis: "⚡",
  anniversary: "🌸",
  special: "💫",
};

// Relative same-origin (proxied) so event images load through the tunnel.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function EventModal({
  event,
  conversationId,
  characterName,
  characterAvatar,
  onResolved,
  onDismiss,
}: EventModalProps) {
  const [selected, setSelected] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [reaction, setReaction] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(false);

  const icon = EVENT_TYPE_ICON[event.event_type || "milestone"] ?? "✨";

  async function handleChoice(index: number) {
    if (loading || revealed) return;
    setSelected(index);
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/events/choose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          instance_id: event.instance_id,
          choice_index: index,
          conversation_id: conversationId,
        }),
      });
      const data = await res.json();
      setReaction(data.reaction || "");
      setRevealed(true);
      onResolved(data.reaction || "", data.intimacy_delta ?? 0, data.intimacy_level ?? 0);
    } catch (err) {
      console.error("Event choice error:", err);
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
      <div className="relative w-full max-w-md bg-gray-900 border border-pink-500/30 rounded-2xl shadow-2xl overflow-hidden">

        {/* Glowing top bar */}
        <div className="h-1 w-full bg-gradient-to-r from-pink-500 via-purple-500 to-indigo-500" />

        {/* Header */}
        <div className="flex items-center gap-3 px-5 pt-5 pb-3">
          {characterAvatar && (
            <img
              src={characterAvatar}
              alt={characterName}
              className="w-10 h-10 rounded-full object-cover object-top ring-2 ring-pink-500/50"
            />
          )}
          <div className="flex-1 min-w-0">
            <p className="text-xs text-pink-400 font-semibold uppercase tracking-wider">
              {icon} 剧情事件
            </p>
            <h2 className="text-white font-bold text-base leading-tight truncate">
              {event.title}
            </h2>
          </div>
        </div>

        {/* Scene description */}
        <div className="px-5 pb-4">
          <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-line">
            {event.description}
          </p>
        </div>

        {/* Choices or Reaction */}
        {!revealed ? (
          <div className="px-5 pb-5 space-y-2">
            <p className="text-xs text-gray-500 mb-3">你会怎么做？</p>
            {event.choices.map((choice, i) => (
              <button
                key={i}
                disabled={loading}
                onClick={() => handleChoice(i)}
                className={`
                  w-full text-left px-4 py-3 rounded-xl text-sm font-medium transition-all
                  border ${selected === i && loading
                    ? "border-pink-400 bg-pink-500/20 text-pink-200 opacity-70"
                    : "border-gray-700 bg-gray-800 text-gray-200 hover:border-pink-500/50 hover:bg-gray-700 active:scale-[0.98]"
                  }
                `}
              >
                <span className="text-pink-400 mr-2">{["A", "B", "C"][i]}.</span>
                {choice.text}
                {choice.hint && (
                  <span className="block text-xs text-gray-500 mt-1">{choice.hint}</span>
                )}
              </button>
            ))}
          </div>
        ) : (
          <div className="px-5 pb-5 space-y-4">
            {/* Character reaction */}
            <div className="bg-gray-800/80 border border-pink-500/20 rounded-xl px-4 py-3">
              <p className="text-xs text-pink-400 mb-2 font-semibold">{characterName} 的反应</p>
              <p className="text-gray-200 text-sm leading-relaxed whitespace-pre-line">
                {reaction}
              </p>
            </div>

            {/* Intimacy change indicator */}
            {event.choices[selected ?? 0]?.intimacy_delta !== undefined && (
              <div className="flex items-center gap-2 text-sm">
                <span className="text-gray-400">亲密度</span>
                <span className={
                  (event.choices[selected ?? 0]?.intimacy_delta ?? 0) > 0
                    ? "text-pink-400 font-bold"
                    : (event.choices[selected ?? 0]?.intimacy_delta ?? 0) < 0
                    ? "text-red-400 font-bold"
                    : "text-gray-400"
                }>
                  {(event.choices[selected ?? 0]?.intimacy_delta ?? 0) > 0 ? "+" : ""}
                  {event.choices[selected ?? 0]?.intimacy_delta}
                </span>
              </div>
            )}

            <button
              onClick={onDismiss}
              className="w-full py-2.5 rounded-xl bg-gradient-to-r from-pink-600 to-purple-600 hover:from-pink-500 hover:to-purple-500 text-white text-sm font-semibold transition-all active:scale-[0.98]"
            >
              继续聊天
            </button>
          </div>
        )}

        {/* Loading overlay */}
        {loading && !revealed && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/30 rounded-2xl">
            <div className="w-8 h-8 border-2 border-pink-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}
      </div>
    </div>
  );
}
