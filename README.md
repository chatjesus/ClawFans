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

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16 + Tailwind CSS v4 |
| Backend | FastAPI + SQLite (WAL mode) |
| LLM | Ollama + Qwen 2.5 14B (abliterated) |
| Auth | Clerk (optional) |

---

## Quick Start

### Prerequisites

- [Ollama](https://ollama.ai) installed and running
- Python 3.11+
- Node.js 20+

### 1. Pull the LLM model

```bash
ollama pull huihui_ai/qwen2.5-abliterate:14b
```

### 2. Start the backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Start the frontend

```bash
cd frontend
cp .env.local.example .env.local   # fill in Clerk keys (or leave blank for no auth)
npm install
npm run dev
```

Open **http://localhost:3000**

---

## Configuration

### Environment Variables (frontend)

Copy `frontend/.env.local.example` to `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...   # optional
CLERK_SECRET_KEY=sk_test_...                      # optional
```

### Telegram Bot (optional)

1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Paste the token in **Settings → Telegram** in the UI

---

## Translation Scripts

Characters support 15 languages via local Qwen translation:

```bash
# Translate all characters into all languages
cd backend
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
├── backend/                # FastAPI + SQLite
│   ├── api/                # REST endpoints
│   ├── models/             # SQLAlchemy models
│   ├── services/           # LLM, chat logic
│   └── main.py
├── frontend/               # Next.js app
│   ├── src/app/            # Pages
│   ├── src/components/     # UI components
│   ├── src/i18n/           # 15-language translations
│   └── src/lib/api.ts      # API client
└── scripts/                # Utility scripts
```

---

## License

MIT
