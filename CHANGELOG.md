# Changelog

All notable changes to the ClawFans project are documented here.

---

## [0.7.0] - 2026-02-22 — Character Consistency & Scene Pre-generation

### Added
- **Character reference images**: Gemini 3 Pro Image now receives the character's avatar as a visual reference when generating in-chat images, producing characters that look consistent with their established appearance
- **`services/scene_service.py`**: Scene pre-generation service
  - Generates 5 tailored scene images per character using LLM-planned descriptions
  - Uses character avatar as reference for visual consistency across all scenes
  - Triggered automatically in background when a new conversation is created
  - Retry logic (3 attempts per scene) for Gemini server resilience
  - Per-character async lock prevents duplicate generation
- **`[SCENE:N]` tag system**: Pre-generated scenes served instantly (zero wait)
  - LLM is instructed to prefer `[SCENE:N]` tags in early messages for instant images
  - `[SCENE:N]` tags are parsed, resolved, and replaced with markdown in DB
  - Falls back to `[IMG:]` custom generation for scenes beyond the pre-generated set
- **Scene availability prompt injection**: System prompt dynamically lists available pre-generated scenes so the LLM knows what's available
- **`uploads/scenes/{character_id}/`**: Organized scene storage per character

### Changed
- `image_service.py`:
  - `generate_image_gemini()` accepts optional `reference_image` bytes and `output_dir` for flexible storage
  - `generate_image()` accepts `avatar_url` and resolves avatar to bytes for Gemini reference
  - `_resolve_avatar_bytes()` loads avatars from `frontend/public/avatars/` or `backend/uploads/`
  - Added `SCENE_TAG_PATTERN`, `extract_scene_tags()`, `replace_scene_tags()`, `get_pregenerated_scenes()`, `scenes_ready()`, `get_scene_dir()`
  - `strip_image_tags()` now also strips `[SCENE:N]` tags
- `chat_service.py`:
  - `build_messages()` injects scene availability prompt into system message
  - `process_reply_images()` handles both `[SCENE:N]` (instant) and `[IMG:]` (generated) tags
  - Post-history instruction nudges LLM to use pre-generated scenes in early messages
- `api/chat.py`:
  - `create_conversation()` triggers background scene pre-generation via `asyncio.create_task`
  - `event_stream()` sends instant scene images before generated images
- `ChatInterface.tsx`: `stripImgTags()` also strips `[SCENE:N]` tags from display text
- `main.py`: Creates `uploads/scenes/` directory on startup

### Technical
- Scene pre-generation runs fully in background (non-blocking conversation creation)
- First 5 chat image moments are instant (~0ms vs ~30s for real-time generation)
- Gemini multimodal input: avatar PNG sent as `Part.from_bytes()` alongside text prompt
- Scene images stored as `scene_{N}.png` in `uploads/scenes/{char_id}/` for predictable lookup

---

## [0.6.0] - 2026-02-22 — In-Chat Image Generation (Gemini 3 Pro Image + ComfyUI)

### Added
- **`services/image_service.py`**: Dual-engine image generation service
  - **Gemini 3 Pro Image** (cloud): High-quality reasoning-based generation via Vertex AI (`gemini-3-pro-image-preview`)
  - **ComfyUI + NoobAI XL** (local): Uncensored anime-style generation, zero cloud cost
  - Auto-detect available provider (prefers local ComfyUI, falls back to Gemini)
  - `[IMG: description]` tag parsing, stripping, and markdown replacement utilities
- **System prompt image instruction**: LLM now knows when and how to request image generation
  - Uses `[IMG: detailed visual description]` tags in character responses
  - Guidelines for sparing usage (~1 in 5-8 messages), consistent character visuals, and natural placement
- **Extended SSE protocol**: Three new event types in chat streaming
  - `{"generating_image": true}` — signals image generation has started
  - `{"image": {"url": "...", "alt": "..."}}` — delivers generated image
  - Images generated after text streaming completes (text is never delayed)
- **`process_reply_images()`** in `chat_service.py`: Post-stream image tag detection, generation, and DB update
- **`StreamResult`** class: Allows API layer to access accumulated reply text for image post-processing
- **Frontend image rendering** in `ChatInterface.tsx`:
  - Inline images in chat bubbles (both streaming and history)
  - "Generating image..." loading spinner with pink accent animation
  - Full-screen lightbox overlay (click image to zoom, click outside or × to close)
  - `[IMG:]` tags stripped from displayed text during streaming
  - `![alt](url)` markdown parsed from stored messages on reload
- **`resolveImageUrl()`** helper: Resolves relative image URLs to absolute backend URLs
- **`ChatImage`** TypeScript interface for type-safe image handling
- **`uploads/generated/`** directory: Auto-created on startup for storing generated chat images

### Changed
- `api/chat.py`: `event_stream()` now performs image post-processing after text streaming
- `chat_service.py`: `generate_reply_stream()` accepts `result_holder` for image tag extraction
- `lib/api.ts`: `sendMessageStream()` extended with `onImage` and `onGeneratingImage` callbacks
- `main.py`: Creates `uploads/generated/` directory on startup

### Technical
- Image generation is fully async and non-blocking
- Text streaming latency is unaffected (images are a post-processing step)
- Generated images served via existing `/uploads` static mount
- DB messages store final content with `![alt](url)` markdown (survives page reload)
- Dual-provider architecture: swap between cloud and local without code changes

---

## [0.5.0] - 2026-02-22 — Local Image Generation Pipeline (NoobAI XL)

### Added
- **NoobAI XL v1.1** (6.6GB) downloaded to `D:\AI_Models\checkpoints\`
- **SDXL VAE fp16-fix** (319MB) downloaded to `D:\AI_Models\vae\`
- **ComfyUI `extra_model_paths.yaml`**: Added `d_drive_models` path config scanning `D:\AI_Models\`
- **`scripts/gen_char_images_local.py`**: Batch character image generator via ComfyUI API
  - All 44 characters with tailored anime prompts
  - External VAE support for NoobAI XL
  - Auto-detect checkpoint and VAE from ComfyUI
  - Skip-if-exists for resumable generation
- **`scripts/update_avatars.py`**: Batch DB avatar URL updater for new characters
- 44/44 character avatar images generated locally via NoobAI XL + ComfyUI

### Technical
- NoobAI XL downloaded from public `arcacolab/models` mirror (no HF token required)
- curl.exe with resume support (`-C -`) for reliable large file downloads
- ComfyUI SDXL txt2img workflow: 28 steps, euler_ancestral, karras scheduler, CFG 7.0

---

## [0.4.0] - 2026-02-22 — Clerk Auth + Per-User Memory Isolation

### Added
- `backend/auth/clerk.py`: Clerk JWT verification dependency
  - Verifies Bearer tokens via Clerk JWKS endpoint (auto-discovered from `iss` claim)
  - In-process JWKS cache to avoid per-request network calls
  - Falls back to `"anonymous"` when no token present (backward compatible)
- `Conversation.clerk_user_id`: New string column linking conversations to Clerk users
- `memory/extractor.py`: New `extract_memories_for_user()` function (no ChatSession needed)
- `memory/extractor.py`: Refactored to shared `_run_extraction()` core
- `chat_service.py`: Memory injection into system prompt for identified users
- `chat_service.py`: Background memory extraction after each web chat turn
- `frontend/src/middleware.ts`: Route protection for `/chat/*` and `/create`
- `frontend/src/app/sign-in/[[...sign-in]]/page.tsx`: Dark-themed Clerk sign-in page
- `frontend/src/app/sign-up/[[...sign-up]]/page.tsx`: Dark-themed Clerk sign-up page
- `frontend/.env.local`: Clerk key placeholders
- `UserButton` in sidebar with sign-in link for unauthenticated users
- Auth token passed to all conversation API calls

### Changed
- `api/chat.py`: Conversations scoped to `clerk_user_id` when authenticated
- `api/chat.py`: `sendMessageStream` now carries Bearer token for user attribution
- `lib/api.ts`: All conversation functions accept optional `token` parameter
- `layout.tsx`: Wrapped with `ClerkProvider`

---

## [0.3.1] - 2026-02-22 — Settings UI & Telegram Bot Fix

### Added
- `backend/api/settings.py`: Platform settings API with dynamic Telegram bot start/stop
  - `GET /api/settings/telegram` — read config (token masked)
  - `PUT /api/settings/telegram` — save & dynamically connect/disconnect bot
  - `POST /api/settings/telegram/test` — validate token without saving
  - `GET /api/settings/telegram/status` — real-time bot connection status
  - Config persisted to `backend/platform_config.json` (gitignored)
- `frontend/src/app/settings/page.tsx`: Settings page with Telegram config UI
  - Token input with test + masked display of saved token
  - Enable/disable toggle
  - Default character ID picker
  - Step-by-step setup guide
  - Discord placeholder card
- Sidebar "Settings" nav link (⚙️)
- i18n translations for settings in all 8 languages (en/zh/ja/ko/es/fr/pt/de)

### Fixed
- **Telegram startup blocking server**: `auto_start_telegram()` was `await`-ed inside lifespan, blocking the entire server for 2-5s on startup. Changed to `asyncio.create_task()` so server accepts requests immediately.
- **`bot.get_me()` timeout hang**: Added `asyncio.wait_for(..., timeout=8.0)` around the bot username lookup so slow/blocked Telegram API doesn't freeze the connect flow.
- **Test button stuck at "Testing..."**: Frontend fetch had no timeout; added `AbortController` with 15s timeout so UI always recovers.
- **Multiple uvicorn instances on port 8000**: Documented restart procedure to kill all stale processes before starting fresh.

### Security
- `platform_config.json` (contains bot token) added to `.gitignore`

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
