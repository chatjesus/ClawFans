"use client";

import { useState, useEffect, useCallback } from "react";
import {
  fetchOpsConfig,
  updateOpsConfig,
  type OpsConfig,
} from "@/lib/api";

const TOKEN_KEY = "clawfans_admin_token";

/** Number levers: key → { label (Chinese), and input constraints }. */
const NUMBER_FIELDS: {
  key: keyof OpsConfig;
  label: string;
  hint: string;
  min?: number;
  max?: number;
  step?: number;
}[] = [
  {
    key: "nsfw_unlock_intimacy",
    label: "露骨内容解锁所需亲密度",
    hint: "用户亲密度达到此值后才会解锁露骨内容（0-100）",
    min: 0,
    max: 100,
    step: 1,
  },
  {
    key: "intimacy_gain_multiplier",
    label: "亲密度成长倍率",
    hint: "每次互动获得亲密度的倍率，越高升级越快",
    min: 0,
    step: 0.1,
  },
  {
    key: "proactive_greeting_min_hours",
    label: "多久没来角色主动找你（小时）",
    hint: "用户离开多少小时后，角色会主动发起问候",
    min: 0,
    step: 1,
  },
  {
    key: "daily_checkin_intimacy_bonus",
    label: "每日签到亲密度奖励",
    hint: "用户每日首次回来签到时额外获得的亲密度",
    min: 0,
    step: 1,
  },
];

/** Boolean levers: key → label (Chinese). */
const BOOLEAN_FIELDS: { key: keyof OpsConfig; label: string; hint: string }[] = [
  {
    key: "nsfw_images_enabled",
    label: "开启露骨图片生成",
    hint: "允许角色生成露骨图片",
  },
  {
    key: "vip_only_explicit",
    label: "露骨内容仅 VIP",
    hint: "仅 VIP 用户可访问露骨内容",
  },
];

export default function AdminPage() {
  const [adminToken, setAdminToken] = useState("");
  const [config, setConfig] = useState<OpsConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // Prefill the token from localStorage on first mount.
  useEffect(() => {
    const stored = typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
    if (stored) setAdminToken(stored);
  }, []);

  const load = useCallback(async (token: string) => {
    setLoading(true);
    setLoadError(null);
    setSaveMsg(null);
    try {
      const cfg = await fetchOpsConfig(token || null);
      setConfig(cfg);
    } catch (e) {
      setConfig(null);
      setLoadError(e instanceof Error ? e.message : "加载失败 / Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  // Load on mount and whenever the stored token changes.
  useEffect(() => {
    const stored = typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : "";
    load(stored || "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleApplyToken = () => {
    if (typeof window !== "undefined") {
      if (adminToken) localStorage.setItem(TOKEN_KEY, adminToken);
      else localStorage.removeItem(TOKEN_KEY);
    }
    load(adminToken);
  };

  const setField = <K extends keyof OpsConfig>(key: K, value: OpsConfig[K]) => {
    setConfig((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    setSaveMsg(null);
    try {
      const updated = await updateOpsConfig(config, adminToken || null);
      setConfig(updated);
      setSaveMsg({ ok: true, text: "已保存 / Saved" });
    } catch (e) {
      setSaveMsg({ ok: false, text: e instanceof Error ? e.message : "保存失败 / Save failed" });
    } finally {
      setSaving(false);
    }
  };

  const inputStyle = {
    background: "rgba(255,255,255,0.04)",
    borderColor: "var(--card-border)",
    color: "var(--text)",
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-2xl mx-auto p-6 space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--text)" }}>
            运营配置 / Ops Config
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
            调节成人陪伴产品的运营杠杆 / Tune the levers for running the product
          </p>
        </div>

        {/* Admin token card */}
        <section
          className="rounded-xl border p-5 space-y-3"
          style={{ background: "var(--card-bg)", borderColor: "var(--card-border)" }}
        >
          <label className="block text-sm font-medium" style={{ color: "var(--text)" }}>
            管理员令牌 / Admin Token
          </label>
          <div className="flex gap-2">
            <input
              type="password"
              value={adminToken}
              onChange={(e) => setAdminToken(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleApplyToken(); }}
              placeholder="X-Admin-Token（本地开发可留空）"
              className="flex-1 px-3 py-2.5 rounded-lg border text-sm outline-none transition-all focus:ring-2 focus:ring-rose-500/30"
              style={inputStyle}
            />
            <button
              onClick={handleApplyToken}
              disabled={loading}
              className="px-4 py-2.5 rounded-lg text-sm font-medium transition-all disabled:opacity-40"
              style={{
                background: "rgba(255,255,255,0.06)",
                color: "var(--text)",
                border: "1px solid var(--card-border)",
              }}
            >
              {loading ? "加载中..." : "应用 / Apply"}
            </button>
          </div>
          <p className="text-[11px]" style={{ color: "var(--muted)" }}>
            令牌会保存在本地浏览器。若服务器设置了 OPS_ADMIN_TOKEN，则必须填写。
          </p>
        </section>

        {/* Load error */}
        {loadError && (
          <div
            className="text-sm px-4 py-3 rounded-lg"
            style={{ background: "rgba(239,68,68,0.08)", color: "#ef4444" }}
          >
            {loadError}
          </div>
        )}

        {/* Config form */}
        {config && (
          <section
            className="rounded-xl border p-5 space-y-6"
            style={{ background: "var(--card-bg)", borderColor: "var(--card-border)" }}
          >
            {/* Number levers */}
            {NUMBER_FIELDS.map((f) => (
              <div key={f.key} className="space-y-2">
                <label className="block text-sm font-medium" style={{ color: "var(--text)" }}>
                  {f.label}
                </label>
                <input
                  type="number"
                  min={f.min}
                  max={f.max}
                  step={f.step}
                  value={config[f.key] as number}
                  onChange={(e) => {
                    const v = e.target.value === "" ? 0 : Number(e.target.value);
                    setField(f.key, (Number.isNaN(v) ? 0 : v) as OpsConfig[typeof f.key]);
                  }}
                  className="w-40 px-3 py-2.5 rounded-lg border text-sm outline-none transition-all focus:ring-2 focus:ring-rose-500/30"
                  style={inputStyle}
                />
                <p className="text-[11px]" style={{ color: "var(--muted)" }}>{f.hint}</p>
              </div>
            ))}

            {/* Boolean levers */}
            <div className="space-y-4 pt-2 border-t" style={{ borderColor: "var(--card-border)" }}>
              {BOOLEAN_FIELDS.map((f) => {
                const on = config[f.key] as boolean;
                return (
                  <div key={f.key} className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium" style={{ color: "var(--text)" }}>{f.label}</p>
                      <p className="text-[11px]" style={{ color: "var(--muted)" }}>{f.hint}</p>
                    </div>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={on}
                      aria-label={f.label}
                      onClick={() => setField(f.key, !on as OpsConfig[typeof f.key])}
                      className="relative w-11 h-6 rounded-full transition-colors duration-200 shrink-0"
                      style={{ background: on ? "var(--accent)" : "rgba(255,255,255,0.1)" }}
                    >
                      <span
                        className="absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform duration-200 shadow"
                        style={{ transform: on ? "translateX(20px)" : "translateX(0)" }}
                      />
                    </button>
                  </div>
                );
              })}
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3 pt-2 border-t" style={{ borderColor: "var(--card-border)" }}>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-5 py-2.5 rounded-lg text-sm font-medium text-white transition-all disabled:opacity-50"
                style={{ background: "var(--accent)" }}
              >
                {saving ? "保存中..." : "保存 / Save"}
              </button>
              {saveMsg && (
                <span
                  className="text-xs px-3 py-2 rounded-lg"
                  style={{
                    background: saveMsg.ok ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)",
                    color: saveMsg.ok ? "#22c55e" : "#ef4444",
                  }}
                >
                  {saveMsg.text}
                </span>
              )}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
