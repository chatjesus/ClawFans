"use client";

import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { createCharacter, importCharacterCard } from "@/lib/api";
import { useT } from "@/contexts/I18nContext";

const CATEGORIES = [
  "Featured","Fantasy","Romance","Modern","Roleplay",
  "Sci-Fi","Anime","School","Drama","Horror","Wellness","NSFW",
];

const TEMPLATES = [
  { label: "Romance", prompt: "Personality: Seductive, confident, attentive, playful.\nAppearance: [Vivid detail]\nScenario: [Scene setup]\n{{char}}'s speech style: Intimate, uses *actions*.\n\nStory Arc:\nAct 1 -- [Initial meeting]\nAct 2 -- [Escalation]\nAct 3 -- [Climax]\n\nExample dialogue:\n{{char}}: *leans closer* ..." },
  { label: "Fantasy", prompt: "Personality: [Fierce / mysterious / noble]\nAppearance: [Race, build, armor]\nScenario: {{user}} encounters {{char}} in [setting].\n{{char}}'s speech style: [Terse warrior / poetic mage]\n\nStory Arc:\nAct 1 -- [Encounter]\nAct 2 -- [Trust / conflict]\nAct 3 -- [Resolution]\n\nExample dialogue:\n{{char}}: *draws blade* ..." },
  { label: "Anime", prompt: "Personality: [Tsundere / yandere / kuudere]\nAppearance: [Hair, eyes, outfit]\nScenario: {{user}} and {{char}} are [relationship] at [location].\n{{char}}'s speech style: Kaomoji, stutters.\n\nStory Arc:\nAct 1 -- [Denial]\nAct 2 -- [Wall cracks]\nAct 3 -- [Payoff]\n\nExample dialogue:\n{{char}}: K-kyaa! ..." },
  { label: "Modern", prompt: "Personality: [Coworker / trainer / doctor]\nAppearance: [Age, build, style]\nScenario: [Office / gym / apartment]\n{{char}}'s speech style: [Casual / flirty]\n\nStory Arc:\nAct 1 -- [Facade]\nAct 2 -- [Pretense drops]\nAct 3 -- [Giving in]\n\nExample dialogue:\n{{char}}: *smirking* ..." },
];

function AvatarUploader({ value, onChange }: { value: string; onChange: (url: string) => void }) {
  const t = useT();
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const upload = useCallback(async (file: File) => {
    setUploadError(null);
    if (!file.type.startsWith("image/")) { setUploadError(t.create.uploaderInvalidType); return; }
    if (file.size > 10 * 1024 * 1024) { setUploadError(t.create.uploaderTooLarge); return; }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const apiBase = (process.env.NEXT_PUBLIC_API_URL !== undefined && process.env.NEXT_PUBLIC_API_URL !== "undefined") ? process.env.NEXT_PUBLIC_API_URL : "";
      const res = await fetch(`${apiBase}/api/upload/avatar`, { method: "POST", body: formData });
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail || t.create.uploaderFailed); }
      const data = await res.json();
      onChange(apiBase + data.url);
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : t.create.uploaderFailed);
    } finally {
      setUploading(false);
    }
  }, [onChange]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => { const f = e.target.files?.[0]; if (f) upload(f); };
  const handleDrop = (e: React.DragEvent) => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files?.[0]; if (f) upload(f); };
  const handlePaste = (e: React.ClipboardEvent) => {
    const f = Array.from(e.clipboardData.items).find(i => i.type.startsWith("image/"))?.getAsFile();
    if (f) upload(f);
  };

  const previewSrc = value.startsWith("http") ? value : value.startsWith("/") ? value : value;

  return (
    <div className="space-y-3">
      <div
        onClick={() => !uploading && fileInputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onPaste={handlePaste}
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && fileInputRef.current?.click()}
        style={{
          background: dragOver ? "rgba(244,63,94,0.08)" : "var(--card-bg)",
          borderColor: dragOver || value ? "var(--accent)" : "var(--card-border)",
          borderWidth: "2px", borderStyle: value ? "solid" : "dashed",
          cursor: uploading ? "wait" : "pointer", transition: "all 0.2s",
        }}
        className="relative w-full rounded-2xl overflow-hidden flex items-center justify-center"
      >
        {value ? (
          <div className="relative w-full" style={{ maxHeight: "288px" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={previewSrc} alt="avatar" style={{ width: "100%", maxHeight: "288px", objectFit: "cover", display: "block" }} />
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 opacity-0 hover:opacity-100 transition-opacity" style={{ background: "rgba(0,0,0,0.55)" }}>
              <span className="text-white text-xs font-medium">{t.create.uploaderChange}</span>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 py-10 px-6 text-center">
            {uploading ? (
              <><div className="w-8 h-8 border-2 border-rose-400 border-t-transparent rounded-full animate-spin" /><span className="text-sm" style={{ color: "var(--muted)" }}>{t.create.uploaderUploading}</span></>
            ) : (
              <>
                <div className="w-16 h-16 rounded-full flex items-center justify-center text-3xl" style={{ background: "rgba(244,63,94,0.1)" }}>馃摲</div>
                <div>
                  <p className="text-sm font-medium" style={{ color: "var(--text)" }}>{t.create.uploaderClick}</p>
                  <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>JPG 路 PNG 路 GIF 路 WEBP 路 Max 10 MB</p>
                  <p className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>{t.create.uploaderPaste}</p>
                </div>
              </>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2">
        <div className="h-px flex-1" style={{ background: "var(--card-border)" }} />
        <span className="text-[10px] uppercase tracking-wider" style={{ color: "var(--muted)" }}>{t.create.uploaderOrUrl}</span>
        <div className="h-px flex-1" style={{ background: "var(--card-border)" }} />
      </div>

      <input
        type="url"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={t.create.uploaderUrlPlaceholder}
        className="w-full rounded-xl border px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500/40 focus:border-rose-500/40"
        style={{ background: "var(--card-bg)", borderColor: "var(--card-border)" }}
      />

      {uploadError && <p className="text-xs" style={{ color: "#f87171" }}>{uploadError}</p>}

      {value && (
        <button type="button" onClick={() => onChange("")}
          className="text-xs px-3 py-1.5 rounded-lg transition-all hover:bg-white/5"
          style={{ color: "var(--muted)", border: "1px solid var(--card-border)" }}>
          Remove image
        </button>
      )}
      <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleFileChange} />
    </div>
  );
}

export default function CreatePage() {
  const router = useRouter();
  const t = useT();
  const { getToken } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "", description: "", system_prompt: "", greeting: "",
    avatar_url: "", tags: "", category: "Featured", is_public: true,
  });

  // ── Character card import ──
  const [cardText, setCardText] = useState("");
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const cardFileRef = useRef<HTMLInputElement>(null);

  const handleCardFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    try {
      const text = await f.text();
      setCardText(text);
      setImportError(null);
    } catch {
      setImportError("无法读取文件 / Could not read file");
    }
  };

  const handleImport = async () => {
    if (!cardText.trim()) { setImportError("请粘贴角色卡 JSON / Paste card JSON"); return; }
    let parsed: object;
    try {
      parsed = JSON.parse(cardText);
    } catch {
      setImportError("无效的 JSON / Invalid JSON");
      return;
    }
    setImporting(true); setImportError(null);
    try {
      const token = await getToken();
      const char = await importCharacterCard(parsed, token);
      router.push("/chat/" + char.id);
    } catch (err) {
      setImportError(err instanceof Error ? err.message : "导入失败 / Import failed");
      setImporting(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.system_prompt.trim()) { setError(t.create.errorRequired); return; }
    setLoading(true); setError(null);
    try {
      const token = await getToken();
      const char = await createCharacter(form, token);
      router.push("/chat/" + char.id);
    }
    catch (err) { setError(err instanceof Error ? err.message : t.create.errorFailed); setLoading(false); }
  };

  const inputStyle = { background: "var(--card-bg)", borderColor: "var(--card-border)" };
  const inputClass = "w-full rounded-xl border px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500/40 focus:border-rose-500/40";

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-2xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold mb-1"><span className="gradient-text">{t.create.title}</span></h1>
        <p className="text-sm mb-8" style={{ color: "var(--muted)" }}>Design your fantasy. Use {"{{char}}"} and {"{{user}}"} as placeholders.</p>

        {error && <div className="rounded-lg px-4 py-3 text-sm mb-6" style={{ background: "rgba(239,68,68,0.1)", color: "#f87171" }}>{error}</div>}

        {/* ── Import character card ── */}
        <div className="rounded-2xl border p-4 mb-8" style={{ background: "var(--card-bg)", borderColor: "var(--card-border)" }}>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-base">📥</span>
            <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>导入角色卡 / Import card</h2>
          </div>
          <p className="text-[11px] mb-3" style={{ color: "var(--muted)" }}>
            粘贴角色卡 JSON，或上传 .json 文件 / Paste a character card JSON, or upload a .json file.
          </p>

          {importError && (
            <div className="rounded-lg px-3 py-2 text-xs mb-3" style={{ background: "rgba(239,68,68,0.1)", color: "#f87171" }}>{importError}</div>
          )}

          <textarea
            value={cardText}
            onChange={(e) => setCardText(e.target.value)}
            placeholder={'{ "name": "...", "description": "...", "personality": "...", "scenario": "...", "first_mes": "...", "mes_example": "..." }'}
            rows={5}
            className={inputClass + " resize-none font-mono text-xs leading-relaxed"}
            style={inputStyle}
          />

          <div className="flex items-center gap-3 mt-3">
            <button
              type="button"
              onClick={() => cardFileRef.current?.click()}
              className="text-xs px-3 py-2 rounded-xl transition-all hover:bg-white/5"
              style={{ color: "var(--muted)", border: "1px solid var(--card-border)" }}
            >
              选择文件 / Choose .json
            </button>
            <input ref={cardFileRef} type="file" accept=".json,application/json" className="hidden" onChange={handleCardFile} />
            <button
              type="button"
              onClick={handleImport}
              disabled={importing}
              className="accent-btn ml-auto px-5 py-2 rounded-xl font-medium text-white text-xs disabled:opacity-50"
            >
              {importing ? "导入中… / Importing…" : "导入 / Import"}
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-medium mb-1.5 uppercase tracking-wider" style={{ color: "var(--muted)" }}>{t.create.avatar}</label>
            <AvatarUploader value={form.avatar_url} onChange={(url) => setForm((prev) => ({ ...prev, avatar_url: url }))} />
          </div>

          <div>
            <label className="block text-xs font-medium mb-1.5 uppercase tracking-wider" style={{ color: "var(--muted)" }}>{t.create.name} <span style={{ color: "var(--accent)" }}>*</span></label>
            <input name="name" value={form.name} onChange={handleChange} placeholder={t.create.namePlaceholder} className={inputClass} style={inputStyle} maxLength={100} />
          </div>

          <div>
            <label className="block text-xs font-medium mb-1.5 uppercase tracking-wider" style={{ color: "var(--muted)" }}>{t.create.tagline}</label>
            <input name="description" value={form.description} onChange={handleChange} placeholder={t.create.taglinePlaceholder} className={inputClass} style={inputStyle} />
          </div>

          <div>
            <label className="block text-xs font-medium mb-1.5 uppercase tracking-wider" style={{ color: "var(--muted)" }}>{t.create.definition} <span style={{ color: "var(--accent)" }}>*</span></label>
            <div className="flex gap-2 mb-3 flex-wrap">
              {TEMPLATES.map((t) => (
                <button key={t.label} type="button" onClick={() => setForm((prev) => ({ ...prev, system_prompt: t.prompt }))}
                  className="text-[11px] px-3 py-1.5 rounded-full border transition-all hover:bg-white/5"
                  style={{ borderColor: "var(--card-border)", color: "var(--tag-text)" }}>{t.label}</button>
              ))}
            </div>
            <textarea name="system_prompt" value={form.system_prompt} onChange={handleChange}
              placeholder={"Personality: ...\nAppearance: ...\nScenario: ...\nSpeech style: ...\nStory Arc:\nAct 1 -- ...\nAct 2 -- ...\nAct 3 -- ...\nExample dialogue:\n{{char}}: *action* Dialogue"}
              rows={12} className={inputClass + " resize-none font-mono text-xs leading-relaxed"} style={inputStyle} />
            <p className="text-[10px] mt-1.5" style={{ color: "var(--muted)" }}>Include: Personality, Appearance, Scenario, Speech Style, Story Arc (3 acts), Example Dialogue.</p>
          </div>

          <div>
            <label className="block text-xs font-medium mb-1.5 uppercase tracking-wider" style={{ color: "var(--muted)" }}>{t.create.openingMessage}</label>
            <textarea name="greeting" value={form.greeting} onChange={handleChange} placeholder="*The scene opens...* Character's first words." rows={4} className={inputClass + " resize-none"} style={inputStyle} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium mb-1.5 uppercase tracking-wider" style={{ color: "var(--muted)" }}>{t.create.category}</label>
              <select name="category" value={form.category} onChange={handleChange} className={inputClass} style={inputStyle}>
                {CATEGORIES.map((cat) => (<option key={cat} value={cat}>{cat}</option>))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5 uppercase tracking-wider" style={{ color: "var(--muted)" }}>{t.create.tags}</label>
              <input name="tags" value={form.tags} onChange={handleChange} placeholder={t.create.tagsPlaceholder} className={inputClass} style={inputStyle} />
            </div>
          </div>

          <button type="submit" disabled={loading} className="accent-btn w-full py-3 rounded-xl font-medium text-white text-sm">
            {loading ? t.create.submitting : t.create.submit}
          </button>
        </form>
      </div>
    </div>
  );
}
