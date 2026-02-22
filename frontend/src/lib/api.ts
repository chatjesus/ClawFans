/**
 * API client for the ClawFans backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
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
  search?: string
): Promise<CharacterCard[]> {
  const params = new URLSearchParams();
  if (category && category !== "Featured") params.set("category", category);
  if (search) params.set("search", search);
  const res = await fetch(`${API_BASE}/api/characters?${params}`);
  if (!res.ok) throw new Error("Failed to fetch characters");
  return res.json();
}

export async function fetchCharacter(id: number): Promise<Character> {
  const res = await fetch(`${API_BASE}/api/characters/${id}`);
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
  characterId: number
): Promise<Conversation> {
  const res = await fetch(`${API_BASE}/api/chat/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ character_id: characterId }),
  });
  if (!res.ok) throw new Error("Failed to create conversation");
  return res.json();
}

export async function fetchConversation(
  id: number
): Promise<ConversationDetail> {
  const res = await fetch(`${API_BASE}/api/chat/conversations/${id}`);
  if (!res.ok) throw new Error("Conversation not found");
  return res.json();
}

export async function fetchConversations(
  characterId?: number
): Promise<Conversation[]> {
  const params = new URLSearchParams();
  if (characterId) params.set("character_id", String(characterId));
  const res = await fetch(`${API_BASE}/api/chat/conversations?${params}`);
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
 */
export async function sendMessageStream(
  conversationId: number,
  content: string,
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (error: string) => void
): Promise<void> {
  try {
    const res = await fetch(
      `${API_BASE}/api/chat/conversations/${conversationId}/messages`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      }
    );

    if (!res.ok) {
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
          if (data.done) {
            onDone();
            return;
          }
          if (data.error) {
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

