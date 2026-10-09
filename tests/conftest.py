import os
import subprocess
import sys
from pathlib import Path

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def git(repo, *args):
    env = {"GIT_AUTHOR_NAME": "Dev", "GIT_AUTHOR_EMAIL": "dev@example.com",
           "GIT_COMMITTER_NAME": "Dev", "GIT_COMMITTER_EMAIL": "dev@example.com"}
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                          env={**os.environ, **env}).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """A repo with a clean commit on main and four bad commits on a feature branch."""
    path = tmp_path / "demo"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    (path / "app.py").write_text("print('hi')\n")
    git(path, "add", ".")
    git(path, "commit", "-q", "-m", "feat: add hello world app")
    git(path, "checkout", "-q", "-b", "feature")
    for i, message in enumerate(["wip", "fix", "small tweak", "asdf please work"]):
        for j in range(10 if message == "small tweak" else 1):
            (path / f"file_{i}_{j}.py").write_text(f"x = {i}\n" * 20)
        git(path, "add", ".")
        git(path, "commit", "-q", "-m", message)
    return path


class ScriptedChatModel(BaseChatModel):
    """A fake chat model that replays scripted AIMessages and records what it was sent."""

    responses: list = Field(default_factory=list)
    received: list = Field(default_factory=list)
    bound_tools: list = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "scripted"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.received.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=self.responses.pop(0))])

    def bind_tools(self, tools, **kwargs):
        self.bound_tools = [t.name for t in tools]
        return self
