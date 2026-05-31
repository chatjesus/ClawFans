"use client";

/**
 * AudioPlayer — pill-style TTS button at the TOP of AI message bubbles.
 * State machine: idle → loading (fetch+download) → playing → idle
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type State = "idle" | "loading" | "playing" | "error";

interface Props {
  text: string;
  charId: number;
  autoPlay?: boolean;
}

function estimateDuration(text: string): string {
  const clean = text.replace(/[^\u4e00-\u9fa5\w]/g, "");
  const secs = Math.max(1, Math.round(clean.length * 0.24));
  return secs < 60 ? `${secs}秒` : `${Math.round(secs / 60)}分`;
}

function cleanForTts(text: string): string {
  return text
    .replace(/\*[^*]*\*/g, "")
    .replace(/\[[^\]]*\]/g, "")
    .replace(/[#_~`>]/g, "")
    .trim()
    .slice(0, 500);
}

export function AudioPlayer({ text, charId, autoPlay = false }: Props) {
  const [state, setState] = useState<State>("idle");
  const [errMsg, setErrMsg] = useState("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const objUrlRef = useRef<string>("");

  const cleanText = useMemo(() => cleanForTts(text), [text]);
  const duration = useMemo(() => estimateDuration(cleanText), [cleanText]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    if (audioRef.current) {
      audioRef.current.onended = null;
      audioRef.current.onerror = null;
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (objUrlRef.current) {
      URL.revokeObjectURL(objUrlRef.current);
      objUrlRef.current = "";
    }
    setState("idle");
  }, []);

  const play = useCallback(async () => {
    if (state === "playing") { stop(); return; }
    if (state === "loading") { stop(); return; }
    if (!cleanText) return;

    stop();

    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setState("loading");
    setErrMsg("");

    // Auto-cancel if loading takes > 25s (backend timeout is 20s)
    const timeoutId = setTimeout(() => {
      if (!ctrl.signal.aborted) {
        ctrl.abort();
        setState("error");
        setErrMsg("超时，点击重试");
      }
    }, 25000);

    try {
      const res = await fetch(`${API_BASE}/api/voice/synthesize`, {
        method: "POST",
        signal: ctrl.signal,
        headers: { "Content-Type": "application/json", "Accept": "audio/mpeg, audio/*" },
        body: JSON.stringify({ text: cleanText, character_id: charId }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      if (!res.body) {
        throw new Error("No response body");
      }

      // Collect all audio chunks (MP3 data)
      const chunks: Uint8Array[] = [];
      const reader = res.body.getReader();
      while (true) {
        const { done, value } = await reader.read();
        if (ctrl.signal.aborted) return;
        if (done) break;
        if (value) chunks.push(value);
      }

      if (ctrl.signal.aborted) return;
      if (chunks.length === 0) throw new Error("Empty audio response");

      const totalBytes = chunks.reduce((s, c) => s + c.length, 0);
      if (totalBytes < 100) throw new Error(`Audio too small (${totalBytes}b)`);

      const blob = new Blob(chunks as BlobPart[], { type: "audio/mpeg" });
      const objUrl = URL.createObjectURL(blob);
      objUrlRef.current = objUrl;

      const audio = new Audio(objUrl);
      audioRef.current = audio;

      // Only switch to "playing" when audio actually starts
      audio.oncanplaythrough = () => {
        if (!ctrl.signal.aborted) setState("playing");
      };
      audio.onended = () => {
        URL.revokeObjectURL(objUrl);
        objUrlRef.current = "";
        setState("idle");
      };
      audio.onerror = (e) => {
        console.warn("[TTS] audio error", e);
        URL.revokeObjectURL(objUrl);
        objUrlRef.current = "";
        setState("error");
        setErrMsg("播放失败");
      };

      await audio.play();
      // audio.play() resolves immediately for modern browsers — canplaythrough fires later
      // but we want to show playing state right away once play() succeeds
      if (!ctrl.signal.aborted) setState("playing");

    } catch (err: unknown) {
      clearTimeout(timeoutId);
      if ((err as Error)?.name === "AbortError") return;
      const msg = (err as Error)?.message ?? "未知错误";
      console.warn("[TTS] error:", msg);
      setState("error");
      setErrMsg(msg);
    } finally {
      clearTimeout(timeoutId);
    }
  }, [cleanText, charId, state, stop]);

  useEffect(() => {
    if (autoPlay) {
      const t = setTimeout(() => play(), 400);
      return () => clearTimeout(t);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => () => stop(), [stop]);

  if (!cleanText) return null;

  return (
    <button
      onClick={play}
      title={
        state === "playing" ? "点击停止"
        : state === "loading" ? "正在加载语音…"
        : state === "error" ? `失败: ${errMsg} — 点击重试`
        : "点击朗读"
      }
      className={`
        inline-flex items-center gap-1.5 px-2.5 py-[3px] rounded-full mb-2
        text-[11px] font-medium select-none transition-all duration-150
        ${state === "error"
          ? "bg-red-500/10 text-red-400 ring-1 ring-red-400/30"
          : state === "loading"
          ? "bg-amber-500/10 text-amber-400 ring-1 ring-amber-400/20 cursor-wait"
          : state === "playing"
          ? "bg-rose-500/15 text-rose-400 ring-1 ring-rose-400/30"
          : "text-gray-400 hover:text-rose-400 hover:bg-rose-500/8 cursor-pointer"}
      `}
      style={state === "idle" ? { background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)" } : {}}
    >
      {/* Icon */}
      {state === "loading" && (
        <span className="w-2.5 h-2.5 border-[1.5px] border-amber-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
      )}
      {state === "playing" && (
        <span className="flex items-end gap-[2px] h-3 flex-shrink-0">
          {[0, 1, 2, 3].map((i) => (
            <span
              key={i}
              className="w-[2.5px] rounded-full bg-rose-400"
              style={{
                height: `${[50, 100, 70, 85][i]}%`,
                animation: "tts-bar 0.5s ease-in-out infinite alternate",
                animationDelay: `${i * 100}ms`,
              }}
            />
          ))}
        </span>
      )}
      {state === "error" && <span className="text-[10px]">⚠</span>}
      {state === "idle" && (
        <svg viewBox="0 0 10 12" fill="currentColor" className="w-2 h-2.5 flex-shrink-0">
          <path d="M0 0l10 6-10 6V0z" />
        </svg>
      )}

      {/* Label */}
      <span>
        {state === "loading" ? "加载中…"
        : state === "playing" ? "播放中"
        : state === "error" ? "重试"
        : duration}
      </span>
    </button>
  );
}
