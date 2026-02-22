"""
v0.3.0 Verification Script
===========================
Tests all M1-M3 features end-to-end.
Run: python -u scripts/verify_v030.py

Requires: backend running on :8000, Ollama running on :11434
"""
import sys
import time
import requests

sys.stdout.reconfigure(encoding="utf-8")

API = "http://localhost:8000"
PASS = 0
FAIL = 0


def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} — {detail}")


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ─── 0. Prerequisites ────────────────────────────────────────

section("0. Prerequisites")

r = requests.get(f"{API}/api/health", timeout=5)
test("Backend is running", r.status_code == 200)
data = r.json()
test("Ollama connected", data.get("ollama") == "connected", f"got: {data.get('ollama')}")
test("Model available", len(data.get("models", [])) > 0, f"models: {data.get('models')}")


# ─── 1. Existing API Compatibility ──────────────────────────

section("1. Existing API Compatibility (no regression)")

r = requests.get(f"{API}/api/characters/", timeout=5)
test("GET /api/characters/ returns 200", r.status_code == 200)
chars = r.json()
test("Characters exist in DB", len(chars) > 0, f"count: {len(chars)}")

r = requests.get(f"{API}/api/characters/1", timeout=5)
test("GET /api/characters/1 returns 200", r.status_code == 200)
test("Character has name", bool(r.json().get("name")))


# ─── 2. Gateway API Endpoints ───────────────────────────────

section("2. Gateway API Endpoints (M1)")

r = requests.get(f"{API}/api/gateway/sessions", timeout=5)
test("GET /api/gateway/sessions returns 200", r.status_code == 200)
test("Sessions is a list", isinstance(r.json(), list))

# Non-streaming inbound
event = {
    "platform": "web",
    "platform_user_id": "verify_user_001",
    "character_id": 1,
    "text": "Hi! My name is Alex and I live in Tokyo."
}
print("\n  Sending test message to gateway (non-streaming, may take ~10s)...")
r = requests.post(f"{API}/api/gateway/inbound", json=event, timeout=120)
test("POST /api/gateway/inbound returns 200", r.status_code == 200)
reply = r.json()
test("Reply has text", bool(reply.get("text")), f"got: {repr(reply.get('text', '')[:50])}")
test("Reply has session_id", reply.get("session_id") is not None)
test("Reply has character_id", reply.get("character_id") == 1)

# Verify session was created
r = requests.get(f"{API}/api/gateway/sessions", params={"platform_user_id": "verify_user_001"}, timeout=5)
sessions = r.json()
test("Session created for verify_user_001", len(sessions) > 0, f"sessions: {len(sessions)}")
if sessions:
    sid = sessions[0]["id"]
    test("Session platform is 'web'", sessions[0]["platform"] == "web")
    test("Session character_id is 1", sessions[0]["character_id"] == 1)


# ─── 3. Message Persistence ─────────────────────────────────

section("3. Message Persistence (M2)")

if sessions:
    r = requests.get(f"{API}/api/gateway/sessions/{sid}/messages", timeout=5)
    msgs = r.json()
    test("Messages endpoint returns list", isinstance(msgs, list))
    test("At least 2 messages (user + assistant)", len(msgs) >= 2, f"count: {len(msgs)}")
    if len(msgs) >= 2:
        test("First message is 'user' role", msgs[0]["role"] == "user")
        test("Second message is 'assistant' role", msgs[1]["role"] == "assistant")
        test("User message contains our text", "Alex" in msgs[0]["content"])


# ─── 4. Memory Extraction ───────────────────────────────────

section("4. Memory System (M6 preview)")

# Give memory extraction a moment (it runs async after the reply)
time.sleep(2)

r = requests.get(f"{API}/api/gateway/memories/verify_user_001", timeout=5)
test("GET /api/gateway/memories returns 200", r.status_code == 200)
memories = r.json()
if memories:
    test("Memories were extracted", len(memories) > 0)
    keys = [m["key"] for m in memories]
    print(f"    Extracted keys: {keys}")
    has_name = any("name" in k.lower() for k in keys)
    has_city = any("city" in k.lower() or "tokyo" in m["value"].lower() for m in memories for k in [m["key"]])
    test("Extracted user name fact", has_name, f"keys: {keys}")
else:
    test("Memory extraction (may be async/slow)", False, "No memories yet — Qwen may not have extracted facts this time")


# ─── 5. Slash Commands ──────────────────────────────────────

section("5. Slash Commands (M3)")

# /status
r = requests.post(f"{API}/api/gateway/inbound", json={
    "platform": "web",
    "platform_user_id": "verify_user_001",
    "command": "status",
}, timeout=5)
test("/status command works", r.status_code == 200)
test("/status shows character name", "Luna" in r.json().get("text", ""), f"got: {r.json().get('text', '')[:80]}")

# /char (list)
r = requests.post(f"{API}/api/gateway/inbound", json={
    "platform": "web",
    "platform_user_id": "verify_user_001",
    "command": "char",
}, timeout=5)
test("/char list works", r.status_code == 200)
test("/char shows available characters", "Available characters" in r.json().get("text", ""))

# /char <name> (switch)
r = requests.post(f"{API}/api/gateway/inbound", json={
    "platform": "web",
    "platform_user_id": "verify_user_001",
    "command": "char",
    "command_args": "Mika",
}, timeout=5)
test("/char switch works", r.status_code == 200)
test("/char confirms switch", "Mika" in r.json().get("text", ""), f"got: {r.json().get('text', '')[:80]}")


# ─── 6. Multi-Session ───────────────────────────────────────

section("6. Multi-Session / Multi-Character (M2)")

r = requests.get(f"{API}/api/gateway/sessions", params={"platform_user_id": "verify_user_001"}, timeout=5)
user_sessions = r.json()
test("Multiple sessions for same user", len(user_sessions) >= 2, f"count: {len(user_sessions)}")
char_names = [s.get("character_name") for s in user_sessions]
test("Sessions with different characters", len(set(char_names)) >= 2, f"chars: {char_names}")


# ─── 7. SSE Streaming ───────────────────────────────────────

section("7. SSE Streaming Endpoint")

event = {
    "platform": "web",
    "platform_user_id": "verify_user_001",
    "character_id": 1,
    "text": "Tell me a short joke.",
}
print("  Testing streaming endpoint (may take ~10s)...")
r = requests.post(f"{API}/api/gateway/inbound/stream", json=event, stream=True, timeout=120)
test("Streaming endpoint returns 200", r.status_code == 200)
test("Content-Type is text/event-stream", "text/event-stream" in r.headers.get("content-type", ""))

chunks = []
for line in r.iter_lines(decode_unicode=True):
    if line and line.startswith("data: "):
        data = line[6:]
        if data == "[DONE]":
            break
        chunks.append(data)

test("Received streaming chunks", len(chunks) > 0, f"chunk count: {len(chunks)}")
full_text = "".join(chunks)
test("Streamed text is non-empty", len(full_text) > 10, f"length: {len(full_text)}")


# ─── 8. Tool Registry ───────────────────────────────────────

section("8. Tool Registry (M5 preview)")

r = requests.get(f"{API}/openapi.json", timeout=5)
paths = list(r.json().get("paths", {}).keys())
gateway_paths = [p for p in paths if "gateway" in p]
test("Gateway endpoints in OpenAPI", len(gateway_paths) >= 4, f"found: {gateway_paths}")


# ─── 9. Cross-Platform Simulation ───────────────────────────

section("9. Cross-Platform Simulation (Telegram path)")

# Simulate a Telegram user hitting the same gateway
tg_event = {
    "platform": "telegram",
    "platform_user_id": "tg_12345",
    "character_id": 1,
    "text": "Hello from Telegram!",
}
print("  Simulating Telegram inbound (non-streaming)...")
r = requests.post(f"{API}/api/gateway/inbound", json=tg_event, timeout=120)
test("Telegram inbound returns 200", r.status_code == 200)
tg_reply = r.json()
test("Telegram reply has text", bool(tg_reply.get("text")))

r = requests.get(f"{API}/api/gateway/sessions", params={"platform": "telegram"}, timeout=5)
tg_sessions = r.json()
test("Telegram session created", len(tg_sessions) > 0)
if tg_sessions:
    test("Session platform is 'telegram'", tg_sessions[0]["platform"] == "telegram")


# ─── Summary ────────────────────────────────────────────────

section("SUMMARY")
total = PASS + FAIL
print(f"\n  Passed: {PASS}/{total}")
print(f"  Failed: {FAIL}/{total}")
if FAIL == 0:
    print("\n  All tests passed! v0.3.0 is verified.")
else:
    print(f"\n  {FAIL} test(s) need attention.")
print()
