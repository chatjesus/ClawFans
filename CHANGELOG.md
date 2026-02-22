# Changelog

All notable changes to the ClawFans project are documented here.

---

## [0.3.0] - 2026-02-22 — Gateway Architecture & Multi-Platform Foundation

### Added

#### M1 — Gateway Foundation
- `gateway/contracts.py`: Core message contracts (`InboundEvent`, `AgentReply`, `ToolCallRequest`, `ToolCallResult`, `Platform`, `MediaAttachment`)
- `gateway/handler.py`: Main gateway entry point with slash-command routing (`/status`, `/char`)
- `gateway/router.py`: Session resolver — maps `(platform, user_id, character_id)` to a `ChatSession`

#### M2 — Data Model Upgrade
- `chat_sessions` table: cross-platform sessions with platform, user, character, and status tracking
- `gateway_messages` table: messages routed through the gateway (all platforms)
- `user_memories` table: durable per-user, per-character memory facts with confidence scoring
- `scheduled_jobs` table: proactive messaging and scheduled task persistence
- `identity_links` table: cross-platform identity binding (web <-> Telegram, etc.)

#### M3 — Telegram Channel Adapter
- `channels/telegram/adapter.py`: Full Telegram bot with polling mode
- Commands: `/start`, `/char`, `/status`, `/reset`, `/bind`
- Auto message chunking for Telegram's 4096 char limit
- Typing indicator simulation
- Allowlist security mode (optional)
- `channels/telegram/config.py`: Configuration with env var support (`TELEGRAM_BOT_TOKEN`)
- `channels/base.py`: Abstract channel adapter interface

#### Agent Runtime
- `agent_runtime/runtime.py`: Full processing pipeline with tool-call loop
  - Non-streaming mode for Telegram/API
  - Streaming mode for web frontend SSE compatibility
  - Automatic tool detection via `\`\`\`tool` code blocks
  - Two-pass generation: tool execution → result incorporation
- `agent_runtime/context.py`: Prompt assembler with 4 layers:
  - System rules + character card + memory injection + post-history reinforcement

#### Action/Tool System
- `actions/registry.py`: Central tool registry with schema generation and execution wrapper
- `actions/web_search.py`: DuckDuckGo web search (no API key required)
- `actions/schedule_message.py`: Scheduled message stub (connects to scheduler in M7)
- `actions/generate_image.py`: Image generation stub (connects to ComfyUI when available)

#### Memory System
- `memory/extractor.py`: LLM-powered fact extraction from conversations (uses Qwen)
- `memory/retriever.py`: Confidence-ranked memory retrieval for prompt injection
- `memory/store.py`: CRUD operations for user memories with upsert logic

#### Scheduler
- `scheduler/runner.py`: Background job runner with periodic polling, retry logic, and dead-letter handling

#### API Endpoints
- `POST /api/gateway/inbound` — Non-streaming gateway entry point
- `POST /api/gateway/inbound/stream` — SSE streaming gateway entry point
- `GET /api/gateway/sessions` — List sessions with filters
- `GET /api/gateway/sessions/{id}/messages` — Session message history
- `GET /api/gateway/memories/{platform_user_id}` — User memory inspection

### Changed
- `main.py`: Added gateway router, scheduler startup, tool registry init, Telegram bot lifecycle
- `models/database.py`: Added 5 new ORM models alongside existing ones (non-breaking)

### Compatibility
- All existing web frontend endpoints (`/api/chat/*`, `/api/characters/*`) remain unchanged
- Existing SQLite database is extended, not replaced (auto-migration via `create_all`)

---

## [0.2.0] - 2026-02-22 — Character Enrichment & Image Generation

### Added
- 14 new characters (IDs 31-44) including NSFW/suggestive themes
- Gemini-generated character avatars (Mistress V, Naughty Nurse, Succubus Maid, Ms. Sato, Rina, Mai)
- Qwen 2.5 14B-generated backstories and NSFW system prompts for 28 characters
- Body stats (height, BWH, cup size, blood type, birthday, hobby, secret) for 28 characters
- `POST /api/upload/avatar` — File upload endpoint for user-created character avatars
- Avatar upload UI component: click, drag-and-drop, clipboard paste, URL fallback
- Character creation page (`/create`) with template presets (Romance, Fantasy, Anime, Modern)
- Multiple generation scripts in `scripts/`

### Changed
- `models/schemas.py`: Added `message_count` and `star_count` to `CharacterUpdate`
- `frontend/src/app/create/page.tsx`: Complete rewrite with `AvatarUploader` component

---

## [0.1.0] - 2026-02-22 — Initial MVP

### Added
- FastAPI backend with SQLite (WAL mode)
- Ollama integration (Qwen 2.5 14B abliterated)
- SSE streaming chat with 3-layer prompt architecture
- Next.js frontend with dark theme
- Character gallery with category filtering
- 8 seed characters (Luna, Jake, Dr. Elena Voss, Aria, Mika, Marcus, Coach Kim, Sage)
- User auth (JWT), conversation CRUD, favorites
- Chat interface with real-time streaming

### Technical
- SQLAlchemy ORM with User, Character, Conversation, Message, Favorite models
- CORS configured for localhost development
- WAL mode + busy timeout for concurrent SSE + write safety
