/**
 * API client for the ClawFans backend.
 */

// Use env var if set; fallback to "" (relative URL) so nginx can proxy correctly in production
const API_BASE = (process.env.NEXT_PUBLIC_API_URL !== undefined && process.env.NEXT_PUBLIC_API_URL !== "undefined")
  ? process.env.NEXT_PUBLIC_API_URL
  : "";

/** Build auth headers. Pass the Clerk token when available. */
export function authHeaders(token?: string | null): HeadersInit {
  const h: HeadersInit = { "Content-Type": "application/json" };
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

// ── Types ──

export interface CharacterCard {
  id: number;
  name: string;
  description: string;
  avatar_url: string;
  tags: string;
  category: string;
  message_count: number;
  star_count: number;
}

export interface Character {
  id: number;
  name: string;
  description: string;
  system_prompt: string;
  greeting: string;
  avatar_url: string;
  tags: string;
  category: string;
  is_public: boolean;
  message_count: number;
  star_count: number;
  creator_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface CharacterCreate {
  name: string;
  description: string;
  system_prompt: string;
  greeting: string;
  avatar_url: string;
  tags: string;
  category: string;
  is_public: boolean;
}

export interface Conversation {
  id: number;
  character_id: number;
  title: string;
  character_name: string;
  character_avatar: string;
  created_at: string;
  updated_at: string;
}

export interface ChatImage {
  url: string;
  alt: string;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  images?: ChatImage[];
  created_at: string;
}

export interface ConversationDetail {
  id: number;
  character_id: number;
  character_name: string;
  character_avatar: string;
  title: string;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
}

export interface HealthStatus {
  status: string;
  ollama: string;
  models: string[];
}

// ── API Functions ──

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) throw new Error("Backend unreachable");
  return res.json();
}

export async function fetchCharacters(
  category?: string,
  search?: string,
  locale?: string,
): Promise<CharacterCard[]> {
  const params = new URLSearchParams();
  if (category && category !== "Featured") params.set("category", category);
  if (search) params.set("search", search);
  if (locale && locale !== "zh") params.set("locale", locale);
  params.set("limit", "300");
  const res = await fetch(`${API_BASE}/api/characters?${params}`);
  if (!res.ok) throw new Error("Failed to fetch characters");
  return res.json();
}

export async function fetchCharacter(id: number, locale?: string): Promise<Character> {
  const params = new URLSearchParams();
  if (locale && locale !== "zh") params.set("locale", locale);
  const res = await fetch(`${API_BASE}/api/characters/${id}?${params}`);
  if (!res.ok) throw new Error("Character not found");
  return res.json();
}

export async function createCharacter(
  data: CharacterCreate
): Promise<Character> {
  const res = await fetch(`${API_BASE}/api/characters`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to create character");
  return res.json();
}

export async function fetchCategories(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/api/characters/categories`);
  if (!res.ok) return ["Featured"];
  return res.json();
}

export async function createConversation(
  characterId: number,
  token?: string | null,
): Promise<Conversation> {
  const res = await fetch(`${API_BASE}/api/chat/conversations`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ character_id: characterId }),
  });
  if (!res.ok) throw new Error("Failed to create conversation");
  return res.json();
}

export async function fetchConversation(
  id: number,
  token?: string | null,
): Promise<ConversationDetail> {
  const res = await fetch(`${API_BASE}/api/chat/conversations/${id}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("Conversation not found");
  return res.json();
}

export async function fetchConversations(
  characterId?: number,
  token?: string | null,
): Promise<Conversation[]> {
  const params = new URLSearchParams();
  if (characterId) params.set("character_id", String(characterId));
  const res = await fetch(`${API_BASE}/api/chat/conversations?${params}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) return [];
  return res.json();
}

export async function deleteConversation(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chat/conversations/${id}`, {
    method: "DELETE",
    signal: AbortSignal.timeout(8000),
  });
  if (!res.ok && res.status !== 404) {
    throw new Error(`Delete failed: ${res.status}`);
  }
}

/** Delete ALL conversations for a character (handles sidebar duplicates). */
export async function deleteAllConversationsForCharacter(
  characterId: number
): Promise<void> {
  const convs = await fetchConversations(characterId);
  // Sequential deletes to avoid SQLite lock contention
  for (const c of convs) {
    await deleteConversation(c.id);
  }
}

/**
 * Send a message and stream the AI response via SSE.
 * Calls onChunk for each text chunk, onDone when complete.
 * Optional: onImage for inline image generation, onGeneratingImage when image gen starts.
 */
export async function sendMessageStream(
  conversationId: number,
  content: string,
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (error: string) => void,
  locale?: string,
  token?: string | null,
  onImage?: (image: ChatImage) => void,
  onGeneratingImage?: () => void,
): Promise<void> {
  try {
    const params = new URLSearchParams();
    if (locale && locale !== "zh") params.set("locale", locale);
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/e6ced9bb-e966-4409-8f50-ec8bd238becf',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'c16f2f'},body:JSON.stringify({sessionId:'c16f2f',location:'api.ts:sendMessageStream',message:'send_start',data:{conversationId,content_preview:content.slice(0,30)},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
    const res = await fetch(
      `${API_BASE}/api/chat/conversations/${conversationId}/messages?${params}`,
      {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ content }),
      }
    );

    if (!res.ok) {
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/e6ced9bb-e966-4409-8f50-ec8bd238becf',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'c16f2f'},body:JSON.stringify({sessionId:'c16f2f',location:'api.ts:res_not_ok',message:'http_error',data:{status:res.status,conversationId},timestamp:Date.now()})}).catch(()=>{});
      // #endregion
      onError("Failed to send message");
      return;
    }

    const reader = res.body?.getReader();
    if (!reader) {
      onError("No response stream");
      return;
    }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data: ")) continue;
        const jsonStr = trimmed.slice(6);
        try {
          const data = JSON.parse(jsonStr);
          if (data.content) {
            onChunk(data.content);
          }
          if (data.generating_image) {
            onGeneratingImage?.();
          }
          if (data.image) {
            onImage?.(data.image as ChatImage);
          }
          if (data.done) {
            // #region agent log
            fetch('http://127.0.0.1:7242/ingest/e6ced9bb-e966-4409-8f50-ec8bd238becf',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'c16f2f'},body:JSON.stringify({sessionId:'c16f2f',location:'api.ts:done_event',message:'sse_done',data:{conversationId,chunksReceived:buffer.length},timestamp:Date.now()})}).catch(()=>{});
            // #endregion
            onDone();
            return;
          }
          if (data.error) {
            // #region agent log
            fetch('http://127.0.0.1:7242/ingest/e6ced9bb-e966-4409-8f50-ec8bd238becf',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'c16f2f'},body:JSON.stringify({sessionId:'c16f2f',location:'api.ts:error_event',message:'sse_error',data:{conversationId,error:data.error},timestamp:Date.now()})}).catch(()=>{});
            // #endregion
            onError(data.error);
            return;
          }
        } catch {
          // skip malformed JSON
        }
      }
    }
    onDone();
  } catch (err) {
    onError(err instanceof Error ? err.message : "Unknown error");
  }
}

/** Resolve image URLs — prefix with API_BASE if relative */
export function resolveImageUrl(url: string): string {
  if (url.startsWith("http")) return url;
  return `${API_BASE}${url}`;
}

