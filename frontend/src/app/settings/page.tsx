"use client";

import { useState, useEffect, useCallback } from "react";
import { useI18n } from "@/contexts/I18nContext";

const API = (process.env.NEXT_PUBLIC_API_URL !== undefined && process.env.NEXT_PUBLIC_API_URL !== "undefined") ? process.env.NEXT_PUBLIC_API_URL : "";

interface TelegramStatus {
  platform: string;
  enabled: boolean;
  connected: boolean;
  bot_username?: string;
  error?: string;
}

interface TelegramConfig {
  bot_token_set: boolean;
  bot_token_masked: string;
  enabled: boolean;
  default_character_id: number;
  allowlist_mode: boolean;
  allowed_user_ids: number[];
}

interface TokenTest {
  valid: boolean;
  bot_username?: string;
  bot_name?: string;
  error?: string;
}

export default function SettingsPage() {
  const { t } = useI18n();
  const st = t.settings ?? ({} as Record<string, string>);

  const [config, setConfig] = useState<TelegramConfig | null>(null);
  const [status, setStatus] = useState<TelegramStatus | null>(null);
  const [token, setToken] = useState("");
  const [defaultCharId, setDefaultCharId] = useState(1);
  const [enabled, setEnabled] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TokenTest | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const loadConfig = useCallback(async () => {
    try {
      const [cfgRes, statusRes] = await Promise.all([
        fetch(`${API}/api/settings/telegram`),
        fetch(`${API}/api/settings/telegram/status`),
      ]);
      const cfg: TelegramConfig = await cfgRes.json();
      const st: TelegramStatus = await statusRes.json();
      setConfig(cfg);
      setStatus(st);
      setEnabled(cfg.enabled);
      setDefaultCharId(cfg.default_character_id);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => { loadConfig(); }, [loadConfig]);

  const handleTest = async () => {
    if (!token) return;
    setTesting(true);
    setTestResult(null);
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 15000);
      const res = await fetch(`${API}/api/settings/telegram/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bot_token: token }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      setTestResult(await res.json());
    } catch (e) {
      setTestResult({ valid: false, error: String(e) });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveMsg(null);
    try {
      const body: Record<string, unknown> = {
        enabled,
        default_character_id: defaultCharId,
        allowlist_mode: false,
        allowed_user_ids: [],
      };
      if (token) body.bot_token = token;
      else body.bot_token = "";

      const res = await fetch(`${API}/api/settings/telegram`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const result = await res.json();
      if (result.connected) {
        setSaveMsg({ ok: true, text: `${st.connected || "Connected"}: ${result.bot_username}` });
      } else if (result.status === "disabled") {
        setSaveMsg({ ok: true, text: st.botDisabled || "Bot disabled" });
      } else {
        setSaveMsg({ ok: false, text: result.error || st.saveFailed || "Failed" });
      }
      setToken("");
      await loadConfig();
    } catch (e) {
      setSaveMsg({ ok: false, text: String(e) });
    } finally {
      setSaving(false);
    }
  };

  const handleDisconnect = async () => {
    setSaving(true);
    try {
      await fetch(`${API}/api/settings/telegram`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bot_token: "",
          enabled: false,
          default_character_id: defaultCharId,
        }),
      });
      setSaveMsg({ ok: true, text: st.disconnected || "Disconnected" });
      await loadConfig();
    } catch (e) {
      setSaveMsg({ ok: false, text: String(e) });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-2xl mx-auto p-6 space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--text)" }}>
            {st.title || "Settings"}
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
            {st.subtitle || "Configure platform integrations and preferences"}
          </p>
        </div>

        {/* Telegram Card */}
        <section
          className="rounded-xl border p-5 space-y-5"
          style={{ background: "var(--card-bg)", borderColor: "var(--card-border)" }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-2xl">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="12" fill="#2AABEE"/>
                  <path d="M17.2 7.6l-2.1 9.9c-.2.7-.6.9-1.2.6l-3.3-2.4-1.6 1.5c-.2.2-.3.3-.6.3l.2-3.3 5.8-5.2c.3-.2 0-.4-.4-.2L7.2 14l-3.2-1c-.7-.2-.7-.7.1-1l12.5-4.8c.6-.2 1.1.1.9 1l-.3-.6z" fill="#fff"/>
                </svg>
              </span>
              <div>
                <h2 className="font-semibold" style={{ color: "var(--text)" }}>Telegram</h2>
                <p className="text-xs" style={{ color: "var(--muted)" }}>
                  {st.telegramDesc || "Connect a Telegram bot to chat with AI characters"}
                </p>
              </div>
            </div>
            {/* Status badge */}
            <span
              className="text-xs px-2.5 py-1 rounded-full font-medium"
              style={{
                background: status?.connected
                  ? "rgba(34,197,94,0.12)"
                  : "rgba(239,68,68,0.12)",
                color: status?.connected ? "#22c55e" : "#ef4444",
              }}
            >
              {status?.connected
                ? `${st.connected || "Connected"} ${status.bot_username || ""}`
                : st.notConnected || "Not connected"}
            </span>
          </div>

          {/* Token input */}
          <div className="space-y-2">
            <label className="block text-sm font-medium" style={{ color: "var(--text)" }}>
              Bot Token
            </label>
            {config?.bot_token_set && !token && (
              <div
                className="flex items-center gap-2 text-xs px-3 py-2 rounded-lg"
                style={{ background: "rgba(255,255,255,0.04)", color: "var(--muted)" }}
              >
                <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor"><path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 2a1.5 1.5 0 110 3 1.5 1.5 0 010-3zM6.5 7.5h3v5h-3z"/></svg>
                {st.tokenSaved || "Token saved"}: {config.bot_token_masked}
              </div>
            )}
            <div className="flex gap-2">
              <input
                type="password"
                value={token}
                onChange={(e) => { setToken(e.target.value); setTestResult(null); }}
                placeholder={config?.bot_token_set ? (st.tokenReplace || "Paste new token to replace...") : (st.tokenPlaceholder || "Paste bot token from @BotFather")}
                className="flex-1 px-3 py-2.5 rounded-lg border text-sm outline-none transition-all focus:ring-2 focus:ring-rose-500/30"
                style={{
                  background: "rgba(255,255,255,0.04)",
                  borderColor: "var(--card-border)",
                  color: "var(--text)",
                }}
              />
              <button
                onClick={handleTest}
                disabled={!token || testing}
                className="px-4 py-2.5 rounded-lg text-sm font-medium transition-all disabled:opacity-40"
                style={{
                  background: "rgba(255,255,255,0.06)",
                  color: "var(--text)",
                  border: "1px solid var(--card-border)",
                }}
              >
                {testing ? (st.testing || "Testing...") : (st.testToken || "Test")}
              </button>
            </div>
            {testResult && (
              <div
                className="text-xs px-3 py-2 rounded-lg"
                style={{
                  background: testResult.valid ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)",
                  color: testResult.valid ? "#22c55e" : "#ef4444",
                }}
              >
                {testResult.valid
                  ? `${st.tokenValid || "Valid"}: @${testResult.bot_username} (${testResult.bot_name})`
                  : `${st.tokenInvalid || "Invalid"}: ${testResult.error}`}
              </div>
            )}
            <p className="text-[11px]" style={{ color: "var(--muted)" }}>
              {st.tokenHelp || 'Get a token from @BotFather on Telegram: send /newbot and follow the prompts.'}
            </p>
          </div>

          {/* Default character */}
          <div className="space-y-2">
            <label className="block text-sm font-medium" style={{ color: "var(--text)" }}>
              {st.defaultChar || "Default Character ID"}
            </label>
            <input
              type="number"
              min={1}
              value={defaultCharId}
              onChange={(e) => setDefaultCharId(parseInt(e.target.value) || 1)}
              className="w-32 px-3 py-2.5 rounded-lg border text-sm outline-none transition-all focus:ring-2 focus:ring-rose-500/30"
              style={{
                background: "rgba(255,255,255,0.04)",
                borderColor: "var(--card-border)",
                color: "var(--text)",
              }}
            />
            <p className="text-[11px]" style={{ color: "var(--muted)" }}>
              {st.defaultCharHelp || "The character AI will use when a Telegram user starts chatting. Users can switch with /char <id>."}
            </p>
          </div>

          {/* Enable toggle */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium" style={{ color: "var(--text)" }}>
                {st.enableBot || "Enable Bot"}
              </p>
              <p className="text-[11px]" style={{ color: "var(--muted)" }}>
                {st.enableBotHelp || "Start receiving messages from Telegram when enabled"}
              </p>
            </div>
            <button
              onClick={() => setEnabled(!enabled)}
              className="relative w-11 h-6 rounded-full transition-colors duration-200"
              style={{
                background: enabled ? "var(--accent)" : "rgba(255,255,255,0.1)",
              }}
            >
              <span
                className="absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform duration-200 shadow"
                style={{ transform: enabled ? "translateX(20px)" : "translateX(0)" }}
              />
            </button>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 pt-2 border-t" style={{ borderColor: "var(--card-border)" }}>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-5 py-2.5 rounded-lg text-sm font-medium text-white transition-all disabled:opacity-50"
              style={{ background: "var(--accent)" }}
            >
              {saving ? (st.saving || "Saving...") : (st.saveConnect || "Save & Connect")}
            </button>
            {status?.connected && (
              <button
                onClick={handleDisconnect}
                disabled={saving}
                className="px-4 py-2.5 rounded-lg text-sm transition-all hover:bg-red-500/10"
                style={{ color: "#f87171", border: "1px solid rgba(248,113,113,0.3)" }}
              >
                {st.disconnect || "Disconnect"}
              </button>
            )}
          </div>

          {saveMsg && (
            <div
              className="text-xs px-3 py-2 rounded-lg"
              style={{
                background: saveMsg.ok ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)",
                color: saveMsg.ok ? "#22c55e" : "#ef4444",
              }}
            >
              {saveMsg.text}
            </div>
          )}
        </section>

        {/* How-to Guide */}
        <section
          className="rounded-xl border p-5 space-y-3"
          style={{ background: "var(--card-bg)", borderColor: "var(--card-border)" }}
        >
          <h3 className="font-semibold" style={{ color: "var(--text)" }}>
            {st.howTo || "How to set up Telegram"}
          </h3>
          <ol className="text-sm space-y-2 list-decimal list-inside" style={{ color: "var(--muted)" }}>
            <li>{st.step1 || 'Open Telegram, search for @BotFather'}</li>
            <li>{st.step2 || 'Send /newbot and choose a name & username'}</li>
            <li>{st.step3 || 'Copy the bot token (a long string like 123456:ABC-DEF1234ghIkl)'}</li>
            <li>{st.step4 || 'Paste it above, click "Test" to verify, then "Save & Connect"'}</li>
            <li>{st.step5 || 'Open your bot in Telegram and send /start'}</li>
          </ol>
        </section>

        {/* Future: Discord, Slack, etc. */}
        <section
          className="rounded-xl border p-5 opacity-50"
          style={{ background: "var(--card-bg)", borderColor: "var(--card-border)" }}
        >
          <div className="flex items-center gap-3">
            <span className="text-2xl">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="12" fill="#5865F2"/>
                <path d="M16.2 8.5c-.9-.4-1.8-.7-2.8-.8l-.1.3c1 .2 1.8.6 2.6 1.1-1.1-.6-2.2-.9-3.9-.9s-2.8.3-3.9.9c.8-.5 1.7-.9 2.6-1.1l-.1-.3c-1 .1-2 .4-2.8.8-1.5 2.2-1.9 4.3-1.7 6.4 1.1.8 2.2 1.3 3.2 1.6.3-.3.5-.7.7-1.1-.4-.1-.7-.3-1.1-.5l.3-.2c1 .5 2.1.7 3.2.7s2.2-.2 3.2-.7l.3.2c-.3.2-.7.4-1.1.5.2.4.4.8.7 1.1 1-.3 2.1-.8 3.2-1.6.2-2.4-.4-4.4-1.6-6.4zM9.7 13.8c-.6 0-1-.5-1-1.2s.4-1.2 1-1.2 1.1.5 1 1.2c0 .7-.5 1.2-1 1.2zm4.6 0c-.6 0-1-.5-1-1.2s.4-1.2 1-1.2 1.1.5 1 1.2c0 .7-.4 1.2-1 1.2z" fill="#fff"/>
              </svg>
            </span>
            <div>
              <h2 className="font-semibold" style={{ color: "var(--text)" }}>Discord</h2>
              <p className="text-xs" style={{ color: "var(--muted)" }}>
                {st.comingSoon || "Coming soon"}
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
