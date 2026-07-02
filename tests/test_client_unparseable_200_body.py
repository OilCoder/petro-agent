"""Regression: an OpenRouter HTTP 200 whose body is not valid JSON must be retried.

Observed in the v7 paid batch (deepseek-r1): a 200 with an unparseable body raised
json.JSONDecodeError from resp.json() and killed the whole model run. It is the same
transient flaky-pool condition as "200 without choices" — retry with backoff, and only
raise the loud "exhausted retries" RuntimeError if it persists.
"""

import json

import httpx
import pytest

from src.agents.client import OPENROUTER_API_KEY_ENV, make_chat


class _Resp:
    """Minimal stand-in for an httpx.Response."""

    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> dict:
        # httpx raises json.JSONDecodeError when the body is not valid JSON
        if self._payload is None:
            raise json.JSONDecodeError("Expecting value", self.text or "<html>", 0)
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


def test_client_openrouter_unparseable_200_retries_then_succeeds(monkeypatch):
    monkeypatch.setenv(OPENROUTER_API_KEY_ENV, "k")
    monkeypatch.setattr("time.sleep", lambda _s: None)
    # 200 with a non-JSON body (truncated/HTML), then a real completion
    monkeypatch.setattr(
        httpx,
        "post",
        _sequence(_Resp(200, None, text="<html>bad gateway</html>"), _Resp(200, _completion("ok"))),
    )
    chat = make_chat(model="deepseek/deepseek-r1")
    assert chat("s", "u") == "ok"  # unparseable 200 is retried, not a crash


def test_client_openrouter_unparseable_200_exhausts_raises(monkeypatch):
    monkeypatch.setenv(OPENROUTER_API_KEY_ENV, "k")
    monkeypatch.setattr("time.sleep", lambda _s: None)
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _Resp(200, None, text="not json"))
    chat = make_chat(model="deepseek/deepseek-r1")
    with pytest.raises(RuntimeError, match="exhausted"):
        chat("s", "u")
