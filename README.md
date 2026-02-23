# ClawFans

**Uncensored AI Character Chat Platform** — run fully local with Ollama.

> Chat with 100+ AI characters across 15 languages. Create custom characters. Full NSFW support via local LLMs.

---

## Features

- 🤖 **100+ AI Characters** — Romance, Fantasy, Roleplay, Anime, and more
- 🌍 **15 Languages** — EN / 中文简体 / 繁體中文 / 日本語 / 한국어 / Español / Français / Português / Deutsch / Русский / Italiano / ภาษาไทย / Tiếng Việt / Indonesia / العربية
- 💬 **Streaming Chat** — real-time SSE responses from local Qwen 2.5 14B
- 🎨 **Custom Characters** — upload avatar, define personality, start chatting instantly
- 🔒 **100% Local** — no cloud API needed, all data stays on your machine
- 📱 **Telegram Bot** — connect characters to Telegram (optional)
- ❤️ **Intimacy System** — 5-stage relationship depth with dynamic content
- 🗓️ **Daily Rhythm** — characters change mood by time of day; streak tracking

---

## Hardware Requirements

> **TL;DR — you need a machine that can run Qwen 2.5 14B locally.**

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 16 GB | 32 GB |
| VRAM (GPU) | 10 GB (runs quantized) | 16 GB+ (full quality) |
| Storage | 20 GB free | 50 GB free |
| GPU | NVIDIA RTX 3080 / AMD RX 7900 | RTX 4090 / RTX 5090 |
| CPU-only | ⚠️ Very slow (~5 min/msg) | Not recommended |

The **LLM (Qwen 2.5 14B)** is ~9 GB. The **image generation model (NoobAI XL)** is ~7 GB (optional, for character image generation).

---

## Models You Need to Prepare

### 1. LLM — Qwen 2.5 14B (required)

This project uses the **abliterated** (uncensored) variant of Qwen 2.5 14B:

```bash
# Install Ollama first: https://ollama.ai
ollama pull huihui_ai/qwen2.5-abliterate:14b
```

> **Why abliterated?** The standard Qwen 2.5 refuses NSFW roleplay. The abliterated version removes those restrictions for adult content. This is what makes the characters work as intended.

**Alternative models** (if you have less VRAM):

```bash
ollama pull huihui_ai/qwen2.5-abliterate:7b    # ~5 GB, lower quality
ollama pull huihui_ai/qwen2.5-abliterate:3b    # ~2 GB, basic quality
```

If you use a different model, set it in `backend/.env`:
```env
OLLAMA_MODEL=your-model-name
```

### 2. Image Generation — NoobAI XL (optional)

For generating character images locally (anime-style, NSFW capable):

1. Download **NoobAI XL** (~7 GB) from [CivitAI](https://civitai.com/models/833294)
2. Place the `.safetensors` file in `ComfyUI/models/checkpoints/`
3. Install [ComfyUI](https://github.com/comfyanonymous/ComfyUI) and start it (`http://127.0.0.1:8188`)

Without ComfyUI, the image generation API falls back to placeholders. Characters still work fully for chat.

---

## Quick Start

### Option A — Docker (recommended for most users)

```bash
git clone https://github.com/claude-office-skills/ClawFans.git
cd ClawFans

# 1. Configure environment
cp backend/.env.example backend/.env        # edit as needed
cp frontend/.env.local.example frontend/.env.local

# 2. Pull the LLM model (required before starting)
ollama pull huihui_ai/qwen2.5-abliterate:14b

# 3. Start everything
docker compose up
```

Open **http://localhost:3000**

> Docker compose starts: Ollama (LLM), FastAPI backend, Next.js frontend.

---

### Option B — Manual Setup

#### Prerequisites

- [Ollama](https://ollama.ai) installed and running
- Python 3.11+
- Node.js 20+

#### 1. Pull the LLM model

```bash
ollama pull huihui_ai/qwen2.5-abliterate:14b
```

#### 2. Configure backend

```bash
cd backend
cp .env.example .env    # fill in any optional settings
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

#### 3. Start backend

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### 4. Configure & start frontend

```bash
cd frontend
cp .env.local.example .env.local   # fill in Clerk keys (or leave blank for no auth)
npm install
npm run dev
```

Open **http://localhost:3000**

---

## Configuration

### Backend Environment Variables

Copy `backend/.env.example` → `backend/.env`. Key variables:

```env
# LLM
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=huihui_ai/qwen2.5-abliterate:14b

# Image Storage (optional — defaults to local disk)
R2_ACCOUNT_ID=...
R2_ACCESS_KEY=...
R2_SECRET_KEY=...
R2_BUCKET=clawfans
R2_PUBLIC_URL=https://your-domain.dev

# Auth (optional — Clerk)
CLERK_SECRET_KEY=sk_test_...

# Telegram Bot (optional)
TELEGRAM_BOT_TOKEN=...
```

### Frontend Environment Variables

Copy `frontend/.env.local.example` → `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...   # optional
CLERK_SECRET_KEY=sk_test_...                      # optional
```

---

## Image Generation

ClawFans supports two image backends:

| Backend | Setup | Quality | Cost |
|---------|-------|---------|------|
| **ComfyUI + NoobAI XL** | Local (~7 GB model) | ⭐⭐⭐⭐⭐ Anime NSFW | Free |
| **Google Gemini** | API key required | ⭐⭐⭐ Censored | ~$0.03/img |
| **None** | No setup | Placeholder images | Free |

The backend auto-detects ComfyUI at `http://127.0.0.1:8188`. If it's running, it's used automatically.

---

## Translation Scripts

Characters support 15 languages via local Qwen translation:

```bash
cd backend

# Translate all characters into all languages (requires Ollama running)
python ..\scripts\translate_chars_direct.py

# Specific locales only
python ..\scripts\translate_chars_direct.py --locale en ja ko

# Single character
python ..\scripts\translate_chars_direct.py --locale en --char-id 1
```

---

## Project Structure

```
ClawFans/
├── backend/                    # FastAPI + SQLite
│   ├── api/                    # REST endpoints (characters, chat, upload…)
│   ├── models/                 # SQLAlchemy ORM models + Pydantic schemas
│   ├── services/               # LLM, chat, intimacy, streak, image gen…
│   ├── actions/                # Agent tools (web search, weather…)
│   ├── channels/telegram/      # Telegram bot adapter
│   ├── gateway/                # Multi-platform message router
│   ├── memory/                 # Per-user persistent memory
│   ├── scheduler/              # Background jobs (proactive messages)
│   ├── tools/                  # Dev/maintenance scripts (not part of app)
│   ├── .env.example            # Environment variable template
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                   # Next.js 16 app
│   ├── src/app/                # Pages (home, chat)
│   ├── src/components/         # UI components
│   ├── src/i18n/               # 15-language JSON translations
│   ├── src/lib/api.ts          # Typed API client
│   ├── .env.local.example
│   └── Dockerfile
├── scripts/                    # Utility scripts (translation, migration…)
├── deploy/                     # Production deployment templates
├── docker-compose.yml          # One-command local stack
└── README.md
```

---

## FAQ

**Q: Do I need a GPU?**
A: Technically no, but CPU-only is ~5 minutes per message. A GPU with ≥10 GB VRAM is strongly recommended.

**Q: Can I use a different LLM?**
A: Yes. Set `OLLAMA_MODEL` in `backend/.env` to any Ollama-compatible model. For NSFW roleplay, you need an uncensored model.

**Q: The characters speak Chinese — why?**
A: The original character data is in Chinese. Set your language to English in the UI and characters will respond in English (translations are pre-generated). Run the translation script to add/refresh translations.

**Q: How do I add my own characters?**
A: Use the **Create Character** button in the UI. Upload a reference image, fill in the personality, and start chatting.

**Q: Image generation isn't working.**
A: Make sure ComfyUI is running at `http://127.0.0.1:8188` with NoobAI XL loaded. The backend will fall back gracefully if ComfyUI is unavailable.

---

## License

MIT
