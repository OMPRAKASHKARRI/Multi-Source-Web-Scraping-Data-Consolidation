"""HttpClient retry/backoff behaviour using a scripted fake session (no network)."""
import pytest
import requests

from scrapers.base_scraper import FetchError, HttpClient


class FakeResponse:
    def __init__(self, status=200, content=b"ok", headers=None, url="http://x/"):
        self.status_code = status
        self.content = content
        self.headers = headers or {}
        self.url = url
        self.ok = status < 400


class ScriptedSession:
    """Returns/raises the scripted items in order."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def get(self, url, timeout):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self):
        pass


def make_client(script, **kwargs):
    sleeps = []
    session = ScriptedSession(script)
    client = HttpClient(session=session, sleep=sleeps.append, clock=lambda: 0.0, delay=0, **kwargs)
    return client, session, sleeps


def test_success_first_try():
    client, session, sleeps = make_client([FakeResponse()])
    assert client.get("http://x/").status_code == 200
    assert session.calls == 1 and sleeps == []


def test_retries_temporary_errors_with_exponential_backoff():
    client, session, sleeps = make_client([FakeResponse(503), FakeResponse(429), FakeResponse(200)])
    assert client.get("http://x/").status_code == 200
    assert session.calls == 3
    assert sleeps == [1.0, 2.0]


def test_retries_timeouts_and_connection_errors():
    client, session, _ = make_client([requests.Timeout("slow"), requests.ConnectionError("down"), FakeResponse()])
    assert client.get("http://x/").ok
    assert session.calls == 3


def test_gives_up_after_max_retries():
    client, session, _ = make_client([FakeResponse(500)] * 4, max_retries=3)
    with pytest.raises(FetchError, match="after 4 attempts"):
        client.get("http://x/")
    assert session.calls == 4


def test_non_retryable_status_fails_immediately():
    client, session, _ = make_client([FakeResponse(404)])
    with pytest.raises(FetchError, match="404"):
        client.get("http://x/")
    assert session.calls == 1


def test_non_retryable_request_exception_fails_immediately():
    client, session, _ = make_client([requests.exceptions.InvalidURL("bad")])
    with pytest.raises(FetchError):
        client.get("http://x/")
    assert session.calls == 1


def test_retry_after_header_is_honoured_but_capped():
    client, _, sleeps = make_client([FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(429, headers={"Retry-After": "999"}), FakeResponse()])
    client.get("http://x/")
    assert sleeps == [7.0, 30.0]


def test_delay_between_requests():
    sleeps = []
    ticks = iter([0.0, 0.1, 0.1, 0.1, 5.0, 5.0])
    session = ScriptedSession([FakeResponse(), FakeResponse()])
    client = HttpClient(session=session, sleep=sleeps.append, clock=lambda: next(ticks), delay=0.5)
    client.get("http://x/")
    client.get("http://x/")
    assert sleeps == [pytest.approx(0.4)]
