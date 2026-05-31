# ClawFans Architecture

A map of how ClawFans is built — for anyone reading the code or forking it.
For setup/run instructions see [README.md](README.md); this doc is about the
*shape* of the system and where to plug in.

---

## 1. The one-paragraph mental model

ClawFans is a **local-first AI character chat app**. A **Next.js** frontend
talks to a **FastAPI** backend over a simple REST + Server-Sent-Events (SSE)
API. The backend turns each character into a layered prompt and streams a reply
from a **local Ollama LLM**. On top of plain chat it layers *relationship
mechanics* (intimacy, streaks, story events), *media* (on-the-fly image
generation via ComfyUI, voice via local TTS), *durable memory*, *agent tools*
(web search, weather…), and a *multi-channel gateway* (Telegram). State lives in
a single **SQLite** file.

```
                 ┌────────────────────────┐
  Browser  ◄────►│  Next.js 16 (frontend) │  Clerk auth, i18n (15 langs)
                 └───────────┬────────────┘
                             │  REST + SSE  (/api/*, proxied)
                 ┌───────────▼────────────┐
                 │   FastAPI (backend)    │
                 │  api/ → services/      │
                 └───┬───────┬───────┬────┘
                     │       │       │
        ┌────────────▼┐ ┌────▼─────┐ ┌▼─────────────┐
        │ Ollama LLM  │ │ ComfyUI  │ │ TTS engines  │
        │ (chat)      │ │ (images) │ │ SoVITS/edge  │
        └─────────────┘ └──────────┘ └──────────────┘
                     │
                 ┌───▼────────┐        ┌──────────────┐
                 │  SQLite    │        │ Telegram bot │ (optional channel)
                 │ clawfans.db│◄───────┤  gateway/    │
                 └────────────┘        └──────────────┘
```

---

## 2. Repository layout

```
clawfans/                      (git root; folder may be named synclub-local)
├── backend/                   FastAPI + SQLite + SQLAlchemy
│   ├── main.py                App factory, lifespan, CORS, character seeding
│   ├── api/                   HTTP routers (thin — delegate to services/)
│   │   ├── chat.py            Conversations + SSE streaming chat (core path)
│   │   ├── characters.py      Character CRUD + translation overlay
│   │   ├── auth.py            Legacy local JWT (mostly superseded by Clerk)
│   │   ├── upload.py          Avatar upload (R2 or local disk)
│   │   ├── voice.py / tts.py  Two overlapping TTS endpoints (see §8)
│   │   ├── events.py          Story-event trigger/choice API
│   │   ├── gateway_api.py     Inbound webhook for multi-channel
│   │   └── settings.py        Platform config + Telegram start/stop
│   ├── services/              Business logic (the deep modules)
│   │   ├── chat_service.py    Prompt assembly + stream + persistence
│   │   ├── llm_service.py     Ollama client (env-configured)
│   │   ├── intimacy_service.py 0–100 relationship tiers + image tagging
│   │   ├── streak_service.py  Consecutive-day tracking + milestones
│   │   ├── event_service.py   Story event triggering
│   │   ├── image_service.py   [SCENE:N] / [IMG:] tag handling
│   │   ├── scene_service.py   Pre-generate per-character scene images
│   │   ├── schedule_service.py Time-of-day mood injection
│   │   ├── proactive_service.py Decide when a character messages first
│   │   ├── tts_service.py     GPT-SoVITS + edge-tts engines
│   │   └── voice_service.py   Voice-profile selection + Google Cloud TTS
│   ├── models/                SQLAlchemy ORM + Pydantic schemas
│   │   └── database.py        Tables, engine, init_db(), ensure_columns()
│   ├── actions/               Agent tools (registry + web_search/weather/…)
│   ├── gateway/               Multi-platform message router (contracts/router/handler)
│   ├── agent_runtime/         Agent loop used by the gateway path
│   ├── channels/telegram/     Telegram bot adapter
│   ├── memory/                Per-user durable memory (extractor/retriever/store)
│   ├── scheduler/             Background loop for due/proactive jobs
│   └── tests/                 pytest suite (hermetic, in-memory SQLite)
├── frontend/                  Next.js 16 (App Router) + Tailwind 4
│   └── src/
│       ├── app/               Pages: home, chat/[id], create, settings, sign-in/up
│       ├── components/        ChatInterface, Sidebar, CharacterCard, AudioPlayer…
│       ├── contexts/          I18nContext (locale state)
│       ├── i18n/              15 language JSON files
│       └── lib/api.ts         Typed API client (the single fetch layer)
├── scripts/                   Dev/maintenance scripts (translation, image gen…)
├── deploy/                    Production service templates
└── docker-compose.yml         Ollama + backend + frontend stack
```

**Layering rule:** `api/` routers stay thin (parse request, check auth, shape
response). All real logic lives in `services/`. Models are dumb data.

---

## 3. Two chat paths (important!)

There are **two independent implementations** of "turn a user message into a
character reply". Know which one you're touching:

| | Web path | Gateway path |
|---|---|---|
| Entry | `api/chat.py::send_message` | `gateway/handler.py::handle_inbound` |
| Engine | `services/chat_service.generate_reply_stream` | `agent_runtime/runtime.AgentRuntime` |
| Transport | SSE stream to the browser | Telegram (and other channels) |
| Session | `Conversation` + `Message` tables | `ChatSession` + `GatewayMessage` tables |

They share the LLM client, character data, and most subsystems, but the
orchestration is duplicated. **Converging these is the single biggest
refactor opportunity** (see §11).

---

## 4. The core flow: web streaming chat

`POST /api/chat/conversations/{id}/messages?locale=xx` returns `text/event-stream`.

1. **Auth + ownership** — resolve Clerk user; `_ensure_conv_visible` (owner-only,
   anonymous convs shared).
2. **Locale overlay** — build a *request-scoped* `system_prompt_override`
   (translated prompt + "reply in X" directive). The ORM `Character` is **never
   mutated** (that used to leak into the DB).
3. **`generate_reply_stream`** (`chat_service.py`):
   - Re-fetch `character`/`conversation` onto the live DB session (FastAPI tears
     down the `Depends(get_db)` session when the handler returns the
     `StreamingResponse`, leaving the originals detached).
   - Persist the user message; bump the streak.
   - **Assemble the 3-layer prompt** (see §5) via `build_messages`.
   - Stream chunks from Ollama, yielding each to the client.
   - In a `finally` (so it survives mid-stream disconnect): strip any
     ```` ```tool ```` block, persist the assistant message, update intimacy,
     fire background memory extraction.
4. **Post-stream events** (back in `api/chat.py`), each emitted as an SSE `data:`:
   - Images: resolve `[SCENE:N]` (instant) and `[IMG:…]` (ComfyUI) tags.
   - Tool call: execute the requested tool, then a **second LLM pass** to narrate
     the result in character.
   - `intimacy`, `streak`, `story_event` updates.
   - `voice`: synthesize TTS audio for the reply.
   - `done`.

SSE event shapes are the contract with `frontend/src/lib/api.ts::sendMessageStream`.

---

## 5. The 3-layer prompt

`chat_service.build_messages` assembles one big system message + history +
a trailing system reinforcement:

- **Layer 1 — SYSTEM_PROMPT:** global roleplay rules, narrative design, the
  "hook system", image-tag formatting rules.
- **Layer 2 — Character Card:** the character's `system_prompt`, then dynamically
  injected context: intimacy stage (`build_intimacy_prompt`), time-of-day mood
  (`build_schedule_prompt`), available tools, pre-generated scene list, and
  retrieved user memories.
- **Layer 3 — POST_HISTORY_INSTRUCTION:** placed *after* the conversation history
  to re-assert behavior right before generation.

`{{char}}` / `{{user}}` macros are substituted throughout.

---

## 6. Data model (SQLite, `models/database.py`)

Core: **User**, **Character** (+ **CharacterTranslation** for i18n),
**Conversation**, **Message**, **Favorite**.

Relationship mechanics live on **Conversation** (`intimacy_level`, `streak_days`,
`last_chat_date`) and in **CharacterEvent** / **ConversationEvent** (story
events). Durable facts go in **UserMemory**.

Multi-channel: **ChatSession**, **GatewayMessage**, **IdentityLink**,
**ScheduledJob**.

Notes for forkers:
- **WAL mode** is on (concurrent reads during long SSE streams).
- **No Alembic.** `init_db()` runs `create_all()` then **`ensure_columns()`**, a
  lightweight forward-migration that `ALTER TABLE ADD COLUMN`s any model columns
  missing from existing tables. Add a column to a model and it self-heals on boot.
- Two ownership fields exist for historical reasons: `Character.creator_id` (int,
  legacy local users) and `Character.clerk_creator_id` (str, current). Auth uses
  the Clerk one.

---

## 7. Relationship & content subsystems

- **Intimacy** (`intimacy_service.py`): 0–100, five tiers (Stranger → Intimate).
  `calc_intimacy_gain` scores each message; the tier drives both the system-prompt
  tone and the SDXL tags appended to image prompts (how revealing photos may be).
- **Streak** (`streak_service.py`): consecutive-day counter with milestone
  rewards injected into the prompt.
- **Story events** (`event_service.py` + `*_event` tables): templated scenes
  triggered at intimacy milestones; the user picks one of three choices, which
  feeds back into intimacy and the next reply.
- **Images** (`image_service.py` + `scene_service.py`): characters embed
  `[SCENE:N]` (instant, pre-generated per character) or `[IMG: description]`
  (generated live via ComfyUI at `127.0.0.1:8188`, prompt augmented by intimacy
  tier). Graceful fallback to placeholders when ComfyUI is absent.
- **Memory** (`memory/`): after each exchange, an LLM extractor pulls durable
  facts into `UserMemory`; `retriever` injects the top-N back into the prompt.

---

## 8. Voice / TTS

Engines, in priority order:
1. **GPT-SoVITS** (local, `127.0.0.1:9880`) — best character-voice quality.
2. **edge-tts** (Microsoft neural, free) — fallback, **gated behind
   `ALLOW_ONLINE_MODELS=1`** so the default stays fully local.
3. **Google Cloud Chirp3 HD** — via a subprocess worker; needs credentials.

Voice is auto-selected from character tags/description (gender + personality).
⚠️ **Three delivery paths currently coexist** — the inline SSE `voice` event,
`POST /api/voice/synthesize` (used by the `AudioPlayer` button), and
`GET /api/tts/synthesize` (**unused by the frontend**). Consolidating these is a
good cleanup (see §11).

---

## 9. Auth, gateway, scheduler

- **Auth:** Clerk JWT verified against JWKS (`auth/clerk.py`). Intentionally
  *permissive* — no token ⇒ `"anonymous"`. Endpoints opt in with `require_auth`,
  and conversations/characters enforce ownership. A legacy local-JWT system
  (`api/auth.py`) still exists but is largely superseded.
- **Gateway:** `gateway/` normalizes inbound events from any channel into an
  `InboundEvent`, resolves a `ChatSession`, and runs `AgentRuntime`.
  `channels/telegram/adapter.py` is the one implemented channel.
- **Scheduler:** `scheduler/runner.scheduler_loop` ticks every 30s, runs due
  `ScheduledJob`s (e.g. proactive Telegram messages), and every ~5 min asks
  `proactive_service` to schedule new "character messages you first" jobs.

---

## 10. Configuration (env)

Backend (`backend/.env`, see `.env.example`):

| Var | Purpose | Default |
|---|---|---|
| `OLLAMA_BASE_URL` | Ollama endpoint | `http://localhost:11434` |
| `OLLAMA_MODEL` | Chat model | `qwen2.5:14b` |
| `OLLAMA_NUM_CTX` | Context window | `8192` |
| `DATABASE_URL` | SQLite path | `sqlite:///./clawfans.db` |
| `ALLOWED_ORIGINS` | CORS (comma-sep) | localhost:3000 |
| `ALLOW_ONLINE_MODELS` | Allow edge-tts / cloud | unset (local-only) |
| `CLERK_SECRET_KEY` | Auth (optional) | — |
| `R2_*` | Image storage (optional) | local disk |
| `TELEGRAM_BOT_TOKEN` | Telegram channel (optional) | — |
| `COMFYUI_URL` | Local image gen (optional) | `127.0.0.1:8188` |

Frontend (`frontend/.env.local`): `NEXT_PUBLIC_API_URL` (blank ⇒ proxy `/api/*`
to `BACKEND_URL` via `next.config.ts`), Clerk publishable/secret keys.

---

## 11. Extending ClawFans

- **Add a character:** UI "Create", `POST /api/characters` (auth required), or
  seed in `main.py::seed_characters`. Add translations via the
  `/api/characters/{id}/translations` endpoint or `scripts/translate_chars_direct.py`.
- **Add an agent tool:** implement a `ToolSpec` (name, params, async handler
  returning `ToolCallResult`) and register it in
  `actions/registry._register_builtin_tools`. The schema is auto-injected into the
  prompt; the model calls it via a ```` ```tool {json} ``` ```` block.
- **Add a TTS engine:** add a streaming generator in `tts_service.py` and route to
  it from `synthesize_stream` (mirror `_stream_sovits` / `_stream_edge_tts`).
- **Add a channel:** implement an adapter under `channels/`, convert its events to
  `InboundEvent`, and deliver `AgentReply`. The gateway + `AgentRuntime` handle the rest.
- **Add a language:** drop a JSON file in `frontend/src/i18n/`, register it in
  `i18n/index.ts` + `LOCALE_LANGUAGE` (backend), and generate character
  translations.

---

## 12. Testing

`cd backend && ./venv/Scripts/python.exe -m pytest tests/`

Tests are **hermetic**: each runs against a fresh in-memory SQLite, with Ollama
and TTS stubbed (`tests/conftest.py`), so no model or network is needed. They
assert *behavior through the public API* (auth, persistence, locale, streaming
resilience, config, schema migration) rather than internals.

---

## 13. Known gaps / good first issues

- **Converge the two chat paths** (§3) — web SSE vs gateway/`AgentRuntime`.
- **Consolidate the three TTS delivery paths** (§8); remove the unused `/api/tts`.
- **Context trimming is by message count** (`MAX_CONTEXT_MESSAGES`), not tokens —
  can overflow `num_ctx`.
- **No real migrations** — `ensure_columns` only adds columns; it won't rename/drop.
  A move to Alembic would be welcome.
- **`next build` fails on pre-existing ESLint errors** (`set-state-in-effect` in
  `I18nContext`/pages) — fix or relax before shipping a production build.
- **Hardcoded Google credentials path** in `voice_service.py` — should be env-only.
- **Two auth systems** (`api/auth.py` local JWT vs Clerk) and two character
  ownership columns — pick one and delete the other.
