# ClawFans x OpenClaw Integration Plan (Detailed)

## 1. Purpose and Scope

This document defines a practical integration roadmap to evolve `synclub-local` from a web-only character chat app into a multi-platform, action-capable, memory-driven character system inspired by OpenClaw architecture.

### 1.1 Product Goal

Build a character platform where the same character can:

- chat consistently across multiple channels (Web + Telegram first),
- remember user context over time,
- perform real actions (search, schedule reminders, generate/send media),
- proactively message users under controlled rules.

### 1.2 Scope Boundaries (Phase 1)

- In scope:
  - Web + Telegram channel sync
  - session continuity across channels
  - tool calling for 3 actions (`web_search`, `schedule_message`, `generate_image`)
  - memory extraction and retrieval
  - proactive messaging (basic cron/event triggers)
- Out of scope (later phases):
  - full voice stack across all channels
  - video generation pipeline
  - broad channel rollout (WhatsApp/Discord/WeChat at once)

---

## 2. Current System Snapshot

Current stack in `synclub-local`:

- Backend: FastAPI + SQLite + Ollama (Qwen)
- Frontend: Next.js
- Character model: `system_prompt`, `description`, `greeting`, `avatar_url`, etc.
- Existing strengths:
  - good local LLM chat loop
  - character CRUD
  - image avatar pipeline

Main gaps to address:

- no cross-platform adapters,
- no standardized gateway/event bus,
- no tool execution framework for actions,
- no durable user memory model,
- no proactive message orchestrator.

---

## 3. Target Architecture

## 3.1 Logical Topology

1. Channel Adapters (Web, Telegram, later others)
2. Gateway (normalizes inbound/outbound events)
3. Session Router (maps user+character+platform sessions)
4. Agent Runtime (prompt assembly + model + tools)
5. Memory Service (extract/store/retrieve)
6. Action Registry (tool execution)
7. Scheduler (proactive events)
8. Persistence (sessions/messages/memories/jobs)

## 3.2 Data Flow

1. Inbound message arrives via channel adapter.
2. Gateway converts to `InboundEvent`.
3. Session router resolves `session_id`.
4. Runtime builds context (`system_prompt + memory + recent history`).
5. Qwen responds, optionally issuing tool calls.
6. Tools execute and results are re-injected.
7. Final `AgentReply` is sent back through adapter.
8. Messages + memory deltas + metrics are persisted.

---

## 4. Milestone Plan

## M1 - Foundation and Contracts (3-4 days)

### Objectives

- Introduce core architecture scaffolding without breaking existing web chat.

### Deliverables

- new modules (backend):
  - `gateway/`
  - `channels/`
  - `agent_runtime/`
  - `memory/`
  - `actions/`
  - `scheduler/`
- internal message contracts:
  - `InboundEvent`
  - `AgentReply`
  - `ToolCallRequest/Result`
- compatibility layer so current `/api/chat` still works.

### Acceptance

- Existing web chat endpoint still responds.
- Internal tests can pass a synthetic `InboundEvent` through runtime and return `AgentReply`.

---

## M2 - Data Model Upgrade (2-3 days)

### Objectives

- Add persistence needed for multi-channel continuity and memory.

### New Tables

- `sessions`
  - `id`, `user_id`, `character_id`, `platform`, `platform_user_id`, `status`, `created_at`, `last_active_at`
- `messages`
  - `id`, `session_id`, `role`, `content`, `tool_calls_json`, `tool_results_json`, `created_at`
- `user_memories`
  - `id`, `user_id`, `character_id`, `key`, `value`, `confidence`, `source_message_id`, `updated_at`
- `scheduled_jobs`
  - `id`, `user_id`, `character_id`, `platform`, `run_at`, `job_type`, `payload_json`, `status`, `attempts`

### Migration Strategy

- keep existing `characters` table unchanged.
- add non-breaking migrations.
- backfill sessions for active web users only when needed (lazy create).

### Acceptance

- CRUD for all new tables works.
- old character APIs remain valid.

---

## M3 - Telegram Channel Adapter (3-4 days)

### Objectives

- Ship first external platform with real users.

### Features

- Telegram private chat ingestion
- outbound text replies
- typing indicator simulation
- `/char <name>` to switch active character
- `/status` to inspect active character and session
- `/bind <code>` for account linking (optional in M3, required by M4)

### Security Rules

- allowlist-only mode by default
- optional pairing code approval flow

### Acceptance

- Telegram message reaches same runtime as web.
- response is delivered with character persona.

---

## M4 - Cross-Channel Session Continuity (2-3 days)

### Objectives

- Ensure one user can continue the same relationship from web to Telegram.

### Implementation

- introduce `identity_links` table:
  - `id`, `user_id`, `platform`, `platform_user_id`, `verified_at`
- bind flow:
  - web generates one-time code
  - user sends code in Telegram
  - gateway links identity

### Acceptance

- user chats on web, then Telegram context reflects ongoing thread.

---

## M5 - Tool/Action System (4-5 days)

### Objectives

- Add true action capability with strict guardrails.

### Tool Registry (MVP)

- `web_search(query)`
  - return summarized results + source links
- `schedule_message(run_at, text, recurrence?)`
  - write `scheduled_jobs`
- `generate_image(prompt, style, character_id)`
  - call local ComfyUI endpoint and return URL

### Runtime Behavior

- model can request tool call through structured schema.
- runtime executes tool, captures output, asks model for final user-facing response.

### Safety

- strict JSON schema validation for tool args.
- tool timeout and retries.
- per-user rate limits.

### Acceptance

- each tool can be manually invoked and also agent-invoked.
- logs include tool call trace and result status.

---

## M6 - Memory Layer (3-4 days)

### Objectives

- Create durable, character-specific, user-specific memory.

### Pipeline

- after each turn, run memory extractor:
  - candidate facts: profile, preferences, relationship signals, recurring goals
- score confidence
- upsert memory keys
- on next turn, retrieve relevant top-k memories and inject as context block

### Memory Rules

- separate memory per `(user_id, character_id)`
- decay low-confidence facts
- conflict resolution: newest high-confidence wins

### Acceptance

- user provides preferences in one session; character recalls correctly in later session/channel.

---

## M7 - Proactive Messaging (3 days)

### Objectives

- Characters initiate interaction under controlled policies.

### Trigger Types (MVP)

- time-based greetings
- inactivity re-engagement (N days silent)
- scheduled reminders from user requests

### Guardrails

- quiet hours
- daily cap per user
- opt-out toggle per user and per character

### Acceptance

- scheduler executes job and sends message to Telegram/web inbox successfully.

---

## M8 - Observability and Control Panel (3-4 days)

### Objectives

- make operations stable and diagnosable.

### Metrics

- inbound/outbound volume by platform
- median response latency
- tool call success/failure
- proactive delivery success rate
- memory write/read counts

### Admin Views (minimal)

- sessions list
- recent messages
- failed jobs queue
- per-character usage summary

### Acceptance

- failures are visible with actionable logs.

---

## M9 - Platform Expansion (Optional Next)

Potential order:

1. Discord
2. WhatsApp
3. WeChat ecosystem channel (depends on compliance/infra constraints)

Each new channel should only require adapter implementation while reusing the same gateway/runtime stack.

---

## 5. Backend Module Design

## 5.1 `gateway/`

- normalize inbound payloads from all adapters.
- route to runtime and return normalized replies.

Core interfaces:

- `handle_inbound(event: InboundEvent) -> AgentReply`
- `send_outbound(reply: AgentReply, target: PlatformTarget)`

## 5.2 `channels/telegram/`

- bot webhook/polling
- convert Telegram update -> `InboundEvent`
- convert `AgentReply` -> Telegram messages/media

## 5.3 `agent_runtime/`

- context builder:
  - character system prompt
  - memory block
  - recent messages
  - tool schemas
- model invocation via Ollama Qwen
- tool-call loop orchestration

## 5.4 `actions/`

- registry + handlers
- unified execution wrapper:
  - validate args
  - enforce auth/rate-limit
  - timeout/retry
  - structured result

## 5.5 `memory/`

- extractor
- store/upsert
- retrieval and ranking
- summarization for prompt budget

## 5.6 `scheduler/`

- periodic runner
- pending job scanner
- execution and dead-letter handling

---

## 6. API and Contract Additions

Recommended new endpoints:

- `POST /api/gateway/inbound` (internal use)
- `POST /api/channels/telegram/webhook`
- `POST /api/identity/bind/start`
- `POST /api/identity/bind/confirm`
- `GET /api/sessions/{id}/messages`
- `POST /api/tools/test/{tool_name}` (admin/test only)
- `POST /api/scheduler/jobs`
- `POST /api/scheduler/jobs/{id}/cancel`

Keep existing:

- `POST /api/chat/...` for frontend compatibility during migration.

---

## 7. Security Model

## 7.1 Inbound Trust

- treat all channel messages as untrusted input.
- allowlist/pairing for DM channels by default.

## 7.2 Tool Safety

- explicit tool allowlist per character.
- no arbitrary shell/system execution in MVP.
- strict argument schema and max cost/time budgets.

## 7.3 Privacy

- memory is scoped per user + character.
- redact sensitive logs where possible.

## 7.4 Abuse Controls

- per-user request rate limits
- per-platform anti-spam controls
- automated lockout for repeated malformed payloads

---

## 8. Testing Strategy

## 8.1 Unit

- session router mapping logic
- memory extraction/upsert conflict logic
- tool registry argument validation

## 8.2 Integration

- web inbound -> runtime -> web outbound
- telegram inbound -> runtime -> telegram outbound
- tool invocation loop end-to-end

## 8.3 E2E Acceptance Scenarios

1. User chats on web, binds Telegram, continues conversation with continuity.
2. Character sets reminder and delivers proactive message at target time.
3. Character executes web search and returns sourced answer in persona style.

---

## 9. Rollout Plan

## Phase A (internal)

- single test user
- Telegram only
- action tools behind feature flag

## Phase B (limited beta)

- 10-50 users
- memory + proactive enabled with conservative caps
- monitor error rates and abuse patterns

## Phase C (general availability)

- broader user rollout
- add second channel adapter

---

## 10. Risks and Mitigations

- Channel API volatility:
  - Mitigation: strict adapter abstraction and contract tests.
- Prompt/tool instability:
  - Mitigation: structured tool schemas + fallback text-only path.
- Context explosion:
  - Mitigation: sliding windows + memory summarization.
- User annoyance from proactive messages:
  - Mitigation: opt-out + quiet hours + caps.
- Operational complexity:
  - Mitigation: observability before scaling channel count.

---

## 11. Suggested Timeline (3 Weeks)

Week 1:

- M1 Foundation
- M2 Data Model
- M3 Telegram Adapter (basic)

Week 2:

- M4 Session Continuity
- M5 Tool/Action System
- M6 Memory Layer

Week 3:

- M7 Proactive Messaging
- M8 Observability/Admin
- hardening and beta rollout prep

---

## 12. Definition of Done (Project Level)

The integration is considered successful when all are true:

- same character session persists across web + Telegram for linked user,
- at least 3 tools can be invoked by agent and return reliable outputs,
- memory recall works across sessions and channels,
- proactive messaging can be configured and safely rate-limited,
- system is observable with actionable metrics/logs.

---

## 13. Immediate Next Step

Start implementation with:

1. M1 scaffolding and contracts
2. M2 schema migration
3. M3 Telegram adapter (minimal inbound/outbound)

This sequence delivers the earliest user-visible value with manageable risk.
