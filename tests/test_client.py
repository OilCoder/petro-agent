"""Tests for make_chat backend dispatch + the OpenRouter ceiling-control wrapper.

No network: httpx.post and ollama.Client are monkeypatched. Verifies the (system,
user) -> str contract, payload shape, and honest error semantics (infra failures
raise; only a genuine empty completion returns "").
"""

import httpx
import pytest

from src.agents.client import OPENROUTER_API_KEY_ENV, make_chat


class _Resp:
    """Minimal stand-in for an httpx.Response."""

    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self) -> dict:
        return self._payload


def _completion(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def _sequence(*items):
    """Return a fake httpx.post yielding the given responses/exceptions in order."""
    it = iter(items)

    def fake_post(url, **kw):
        item = next(it)
        if isinstance(item, Exception):
            raise item
        return item

    return fake_post


# ----------------------------------------
# Step 1 — backend dispatch
# ----------------------------------------


def test_client_auto_routes_slash_to_openrouter(monkeypatch):
    monkeypatch.setenv(OPENROUTER_API_KEY_ENV, "k")
    captured = {}

    def fake_post(url, **kw):
        captured["url"] = url
        captured["json"] = kw["json"]
        return _Resp(200, _completion("ok"))

    monkeypatch.setattr(httpx, "post", fake_post)
    chat = make_chat(model="deepseek/deepseek-r1:free")
    assert chat("sys", "usr") == "ok"
    assert "openrouter.ai" in captured["url"]
    assert captured["json"]["model"] == "deepseek/deepseek-r1:free"
    assert captured["json"]["temperature"] == 0.0
    assert captured["json"]["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "usr"},
    ]


def test_client_auto_routes_plain_to_ollama(monkeypatch):
    import ollama

    captured = {}

    class FakeClient:
        def __init__(self, host=None):
            captured["host"] = host

        def chat(self, model, messages, options):
            captured["model"] = model
            return {"message": {"content": "local"}}

    monkeypatch.setattr(ollama, "Client", FakeClient)
    chat = make_chat(model="qwen3:30b-a3b")
    assert chat("sys", "usr") == "local"
    assert captured["model"] == "qwen3:30b-a3b"


def test_client_backend_override_forces_ollama(monkeypatch):
    import ollama

    class FakeClient:
        def __init__(self, host=None):
            pass

        def chat(self, model, messages, options):
            return {"message": {"content": "forced"}}

    monkeypatch.setattr(ollama, "Client", FakeClient)
    # a slash id would auto-route to openrouter; the override forces ollama
    chat = make_chat(model="ns/local-model", backend="ollama")
    assert chat("s", "u") == "forced"


def test_client_unknown_backend_raises():
    with pytest.raises(ValueError):
        make_chat(model="x", backend="bogus")


# ----------------------------------------
# Step 2 — OpenRouter error semantics
# ----------------------------------------


def test_client_openrouter_missing_key_raises(monkeypatch):
    monkeypatch.delenv(OPENROUTER_API_KEY_ENV, raising=False)
    with pytest.raises(RuntimeError):
        make_chat(model="deepseek/deepseek-r1:free")


def test_client_openrouter_hardfail_raises_immediately(monkeypatch):
    monkeypatch.setenv(OPENROUTER_API_KEY_ENV, "k")
    calls = {"n": 0}

    def fake_post(url, **kw):
        calls["n"] += 1
        return _Resp(404, text="model not found")

    monkeypatch.setattr(httpx, "post", fake_post)
    chat = make_chat(model="deepseek/deepseek-r1:free")
    with pytest.raises(RuntimeError, match="404"):
        chat("s", "u")
    assert calls["n"] == 1  # 404 is a hard error: no retry


def test_client_openrouter_retries_then_succeeds(monkeypatch):
    monkeypatch.setenv(OPENROUTER_API_KEY_ENV, "k")
    monkeypatch.setattr("time.sleep", lambda _s: None)
    monkeypatch.setattr(
        httpx, "post", _sequence(_Resp(429, text="busy"), _Resp(200, _completion("late ok")))
    )
    chat = make_chat(model="deepseek/deepseek-r1:free")
    assert chat("s", "u") == "late ok"


def test_client_openrouter_exhausts_retries_raises(monkeypatch):
    monkeypatch.setenv(OPENROUTER_API_KEY_ENV, "k")
    monkeypatch.setattr("time.sleep", lambda _s: None)
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _Resp(429, text="rate limited"))
    chat = make_chat(model="deepseek/deepseek-r1:free")
    with pytest.raises(RuntimeError, match="exhausted"):
        chat("s", "u")


def test_client_openrouter_transport_error_retries_then_raises(monkeypatch):
    monkeypatch.setenv(OPENROUTER_API_KEY_ENV, "k")
    monkeypatch.setattr("time.sleep", lambda _s: None)

    def boom(url, **kw):
        raise httpx.ConnectTimeout("t")

    monkeypatch.setattr(httpx, "post", boom)
    chat = make_chat(model="deepseek/deepseek-r1:free")
    with pytest.raises(RuntimeError, match="exhausted"):
        chat("s", "u")


def test_client_openrouter_empty_content_returns_empty(monkeypatch):
    monkeypatch.setenv(OPENROUTER_API_KEY_ENV, "k")
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _Resp(200, _completion("")))
    chat = make_chat(model="deepseek/deepseek-r1:free")
    assert chat("s", "u") == ""  # genuine empty flows into the agent cascade


def test_client_openrouter_200_without_choices_retries(monkeypatch):
    monkeypatch.setenv(OPENROUTER_API_KEY_ENV, "k")
    monkeypatch.setattr("time.sleep", lambda _s: None)
    # 200 carrying an error envelope (no choices), then a real completion
    monkeypatch.setattr(
        httpx,
        "post",
        _sequence(_Resp(200, {"error": {"code": 429}}), _Resp(200, _completion("ok"))),
    )
    chat = make_chat(model="deepseek/deepseek-r1:free")
    assert chat("s", "u") == "ok"  # 200-without-choices is retried, not a crash


def test_client_openrouter_200_without_choices_exhausts(monkeypatch):
    monkeypatch.setenv(OPENROUTER_API_KEY_ENV, "k")
    monkeypatch.setattr("time.sleep", lambda _s: None)
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _Resp(200, {"error": {"code": 429}}))
    chat = make_chat(model="deepseek/deepseek-r1:free")
    with pytest.raises(RuntimeError, match="exhausted"):
        chat("s", "u")
