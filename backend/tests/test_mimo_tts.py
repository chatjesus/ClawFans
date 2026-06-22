"""
Xiaomi MiMo TTS adapter.

MiMo's TTS is an OpenAI-chat-shaped endpoint:
  POST https://api.xiaomimimo.com/v1/chat/completions
  header: api-key: <key>
  body: {model: "mimo-v2.5-tts", messages: [{role:"assistant", content:<text>}],
         audio: {format:"wav", voice:"Chloe"}}
  resp: choices[0].message.audio.data = base64 audio

We test the request SHAPE and base64 decode with a stubbed HTTP client — no
real network, no real key (key comes from env / arg, never from the test).
"""
import asyncio
import base64

import httpx


class _FakeResp:
    status_code = 200

    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


class _FakeClient:
    captured: dict = {}

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None, **k):
        _FakeClient.captured = {"url": url, "headers": headers, "json": json}
        b64 = base64.b64encode(b"RIFF....fakewav").decode()
        return _FakeResp({"choices": [{"message": {"audio": {"data": b64}}}]})


def test_mimo_request_shape_and_decodes_audio(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    from services.mimo_tts import synthesize_mimo

    out = asyncio.run(synthesize_mimo("你好呀", voice="Chloe", api_key="k"))

    cap = _FakeClient.captured
    assert cap["url"].endswith("/v1/chat/completions")
    assert cap["headers"]["api-key"] == "k"
    assert cap["json"]["model"].startswith("mimo-v2.5-tts")
    assert cap["json"]["audio"]["voice"] == "Chloe"
    assert cap["json"]["audio"]["format"] == "wav"
    assert any("你好呀" in (m.get("content") or "") for m in cap["json"]["messages"])
    assert out == b"RIFF....fakewav"


def test_mimo_returns_none_without_key(monkeypatch):
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    from services.mimo_tts import synthesize_mimo
    assert asyncio.run(synthesize_mimo("hi", api_key=None)) is None


def test_mimo_returns_none_on_empty_text(monkeypatch):
    from services.mimo_tts import synthesize_mimo
    assert asyncio.run(synthesize_mimo("   ", api_key="k")) is None
