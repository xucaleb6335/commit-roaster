"""Simple mode: send the commit list to a Dify chat app and return its answer."""

import os
import re
import time
from pathlib import Path

import requests

from . import RoastError

MAX_SUBJECT_CHARS = 200
MAX_PROMPT_CHARS = 6000
RETRIES = 2  # extra attempts after a rate limit or timeout


def build_prompt(repo, commits, rev_range=None):
    repo_name = Path(repo).resolve().name
    lines = []
    for i, (short_hash, author, age, subject) in enumerate(commits, 1):
        if len(subject) > MAX_SUBJECT_CHARS:
            subject = subject[:MAX_SUBJECT_CHARS] + "..."
        lines.append(f"{i}. [{short_hash}] {subject} ({author}, {age})")

    if rev_range:
        short_range = re.sub(r"\b([0-9a-f]{7})[0-9a-f]{33}\b", r"\1", rev_range)
        source = f"the branch range {short_range}"
    else:
        source = "the latest history"
    header = f"Roast these {len(commits)} commit messages from {source} of the repo '{repo_name}':\n\n"
    body = "\n".join(lines)
    if len(header) + len(body) > MAX_PROMPT_CHARS:
        body = body[:MAX_PROMPT_CHARS - len(header)].rsplit("\n", 1)[0] + "\n(...list trimmed)"
    return header + body


def _retry_delay(response, attempt):
    try:
        return min(float(response.headers.get("Retry-After", "")), 30)
    except (TypeError, ValueError):
        return 2 * 2 ** attempt


def ask_dify(prompt, sleep=time.sleep):
    api_key = os.getenv("DIFY_API_KEY", "").strip()
    base_url = os.getenv("DIFY_BASE_URL", "https://api.dify.ai/v1").strip().rstrip("/")
    if not api_key or "xxxx" in api_key:
        raise RoastError("DIFY_API_KEY is missing. Paste your Dify app key (app-...) into .env.")

    for attempt in range(RETRIES + 1):
        last_try = attempt == RETRIES
        try:
            response = requests.post(
                f"{base_url}/chat-messages",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"inputs": {}, "query": prompt, "response_mode": "blocking", "user": "commit-roaster-cli"},
                timeout=120,
            )
        except requests.exceptions.Timeout:
            if last_try:
                raise RoastError("Dify timed out even after retries. Try again, or use fewer commits (-n 10).")
            sleep(2 * 2 ** attempt)
            continue
        except requests.exceptions.ConnectionError:
            raise RoastError(f"Could not reach Dify at {base_url}. Check your internet connection and DIFY_BASE_URL.")

        if response.status_code == 429 and not last_try:
            sleep(_retry_delay(response, attempt))
            continue
        break

    if response.status_code == 401:
        raise RoastError("Dify rejected the API key (401). Check DIFY_API_KEY in .env.")
    if response.status_code == 429:
        raise RoastError("Rate limited (429) even after retries. Free models allow only a few requests "
                         "per minute; wait a minute and try again.")
    if not response.ok:
        try:
            message = response.json().get("message", response.text)
        except ValueError:
            message = response.text
        raise RoastError(f"Dify returned {response.status_code}: {message}")

    answer = response.json().get("answer", "")
    # Reasoning models sometimes include their hidden thinking; keep only the final answer.
    answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()
    if not answer:
        raise RoastError("Dify answered with an empty message. Check the model is set up in your Dify app.")
    return answer
