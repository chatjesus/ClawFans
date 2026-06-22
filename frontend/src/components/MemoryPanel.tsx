"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";
import { fetchMemories, deleteMemory, type Memory } from "@/lib/api";

interface Props {
  characterId: number;
}

/**
 * "她记得你什么" — shows the memories the character has formed about the user,
 * each removable. Auth required (uses the Clerk token).
 */
export default function MemoryPanel({ characterId }: Props) {
  const { getToken } = useAuth();
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const token = await getToken();
        const data = await fetchMemories(characterId, token);
        if (!cancelled) setMemories(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [characterId]);

  const handleDelete = useCallback(async (id: number) => {
    setDeletingId(id);
    try {
      const token = await getToken();
      await deleteMemory(id, token);
      setMemories((prev) => prev.filter((m) => m.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
    } finally {
      setDeletingId(null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <span className="w-4 h-4 border-2 border-rose-400 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl px-4 py-3 text-sm" style={{ background: "rgba(239,68,68,0.1)", color: "#f87171" }}>
        {error}
      </div>
    );
  }

  if (memories.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 px-4 text-center gap-2">
        <span className="text-2xl">🧠</span>
        <p className="text-sm" style={{ color: "var(--muted)" }}>她还在慢慢了解你…</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {memories.map((m) => (
        <div
          key={m.id}
          className="flex items-start gap-2 rounded-xl px-3 py-2.5 text-sm"
          style={{ background: "var(--card-bg)", border: "1px solid var(--card-border)" }}
        >
          <div className="flex-1 min-w-0 leading-relaxed">
            <span className="font-medium" style={{ color: "var(--accent)" }}>{m.key}</span>
            <span style={{ color: "var(--muted)" }}>: </span>
            <span style={{ color: "var(--text)" }}>{m.value}</span>
          </div>
          <button
            onClick={() => handleDelete(m.id)}
            disabled={deletingId === m.id}
            title="删除这条记忆"
            className="flex-shrink-0 w-5 h-5 rounded flex items-center justify-center transition-all hover:bg-red-500/10 disabled:opacity-40"
            style={{ color: "var(--muted)" }}
          >
            {deletingId === m.id ? (
              <span className="w-3 h-3 border border-rose-400 border-t-transparent rounded-full animate-spin" />
            ) : (
              <span className="text-base leading-none">✕</span>
            )}
          </button>
        </div>
      ))}
    </div>
  );
}
