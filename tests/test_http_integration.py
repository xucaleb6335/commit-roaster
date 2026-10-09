"""End-to-end over HTTP: the real ChatOpenAI client and requests against local fake servers
that speak the OpenRouter (OpenAI-compatible) and Dify wire formats."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from commit_roaster import RoastError
from commit_roaster.agent import make_llm, run_agent
from commit_roaster.dify import ask_dify


class FakeServer:
    """Replays queued (status, body, headers) responses and records each request body."""

    def __init__(self):
        self.queue, self.requests = [], []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                outer.requests.append({"path": self.path, "auth": self.headers.get("Authorization"),
                                       "body": json.loads(self.rfile.read(int(self.headers["Content-Length"])))})
                status, body, headers = outer.queue.pop(0)
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()


@pytest.fixture
def server(monkeypatch):
    s = FakeServer()
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    yield s
    s.httpd.shutdown()


def completion(message, finish="stop"):
    return {"id": "x", "object": "chat.completion", "created": 0, "model": "nvidia/nemotron-3.5-lightning:free",
            "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}


def tool_call_message(name, args, id):
    return {"role": "assistant", "content": None,
            "tool_calls": [{"id": id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}


@pytest.fixture
def openrouter_env(server, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("OPENROUTER_BASE_URL", server.url + "/api/v1")
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)


def test_agent_over_http_with_tool_calls_and_a_429_retry(server, openrouter_env, repo):
    server.queue = [
        (429, {"error": {"message": "Rate limit exceeded: free-models-per-min", "code": 429}}, {"Retry-After": "0"}),
        (200, completion(tool_call_message("read_git_history", {}, "c1"), "tool_calls"), {}),
        (200, completion(tool_call_message("search_commit_guidelines", {"query": "wip"}, "c2"), "tool_calls"), {}),
        (200, completion({"role": "assistant", "content": "<think>hmm</think>WIP is not a message [BP-08]"}), {}),
    ]
    result = run_agent(make_llm(), str(repo), 20, "main..feature")

    assert result.review.startswith("WIP is not a message [BP-08]")
    assert result.citations == ["BP-08"]
    first = server.requests[0]
    assert first["path"] == "/api/v1/chat/completions" and first["auth"] == "Bearer sk-or-test"
    assert first["body"]["model"] == "nvidia/nemotron-3.5-lightning:free"
    assert {t["function"]["name"] for t in first["body"]["tools"]} == {
        "read_git_history", "inspect_commit", "search_commit_guidelines"}
    tool_reply = [m for m in server.requests[2]["body"]["messages"] if m["role"] == "tool"]
    assert tool_reply and "asdf please work" in tool_reply[0]["content"]


def test_agent_reports_bad_key_and_persistent_rate_limit(server, openrouter_env, repo):
    server.queue = [(401, {"error": {"message": "No auth credentials found"}}, {})]
    with pytest.raises(RoastError, match="rejected the API key"):
        run_agent(make_llm(), str(repo), 20)

    server.queue = [(429, {"error": {"message": "slow down"}}, {"Retry-After": "0"})] * 3
    with pytest.raises(RoastError, match="Rate limited"):
        run_agent(make_llm(), str(repo), 20)


def test_missing_openrouter_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    with pytest.raises(RoastError, match="OPENROUTER_API_KEY is missing"):
        make_llm()


@pytest.fixture
def dify_env(server, monkeypatch):
    monkeypatch.setenv("DIFY_API_KEY", "app-test")
    monkeypatch.setenv("DIFY_BASE_URL", server.url + "/v1")


def test_dify_retries_429_then_succeeds(server, dify_env):
    server.queue = [(429, {"message": "rate limited"}, {"Retry-After": "0"}),
                    (200, {"answer": "<think>x</think>Roasted."}, {})]
    sleeps = []
    assert ask_dify("prompt", sleep=sleeps.append) == "Roasted."
    assert sleeps == [0.0]
    assert server.requests[0]["path"] == "/v1/chat-messages" and server.requests[0]["auth"] == "Bearer app-test"


def test_dify_gives_up_after_retries_and_reports_errors(server, dify_env):
    server.queue = [(429, {"message": "rate limited"}, {})] * 3
    with pytest.raises(RoastError, match="Rate limited"):
        ask_dify("prompt", sleep=lambda s: None)

    server.queue = [(400, {"code": "app_unavailable", "message": "App unavailable"}, {})]
    with pytest.raises(RoastError, match="400: App unavailable"):
        ask_dify("prompt", sleep=lambda s: None)
