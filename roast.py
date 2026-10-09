"""Commit Roaster: send a repo's recent commit messages to a Dify app and print the roast.

Usage:
    python roast.py                      # roast the repo in the current folder
    python roast.py --repo C:\\code\\app -n 10
    python roast.py --dry-run            # show the prompt without calling Dify
    python roast.py --range main..HEAD   # only the commits on this branch (used by CI)
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

FIELD_SEP = "\x1f"  # ASCII unit separator: never appears in normal commit text
MAX_SUBJECT_CHARS = 200
MAX_PROMPT_CHARS = 6000

console = Console()


class RoastError(Exception):
    """An error with a message that is safe and useful to show the user."""


def parse_args():
    parser = argparse.ArgumentParser(description="Roast a Git repo's recent commit messages.")
    parser.add_argument("--repo", default=".", help="path to a Git repository (default: current folder)")
    parser.add_argument("-n", "--count", type=int, default=int(os.getenv("COMMIT_COUNT", "20")),
                        help="number of commits to roast (default: 20)")
    parser.add_argument("--range", dest="rev_range",
                        help="git revision range to roast, e.g. main..HEAD (default: latest commits)")
    parser.add_argument("--output", type=Path, help="also write the roast (Markdown) to this file")
    parser.add_argument("--dry-run", action="store_true", help="print the prompt and exit without calling Dify")
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be at least 1")
    if args.rev_range and args.rev_range.startswith("-"):
        parser.error("--range must be a revision range like main..HEAD")
    return args


def read_commits(repo, count, rev_range=None):
    """Return a list of (short_hash, author, age, subject) for the latest commits."""
    cmd = ["git", "-C", repo, "log", f"-n{count}",
           f"--pretty=format:%h{FIELD_SEP}%an{FIELD_SEP}%ar{FIELD_SEP}%s"]
    if rev_range:
        cmd += [rev_range, "--"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise RoastError("Git is not installed or not on PATH. Run setup\\setup_windows.ps1 first.")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "does not have any commits" in stderr:
            raise RoastError(f"'{repo}' has no commits yet. Nothing to roast.")
        if "not a git repository" in stderr.lower():
            raise RoastError(f"'{repo}' is not a Git repository. Use --repo to point at one.")
        raise RoastError(f"git log failed: {stderr}")

    commits = [line.split(FIELD_SEP, 3) for line in result.stdout.splitlines() if line.strip()]
    if not commits and rev_range:
        raise RoastError(f"No commits in range {rev_range}. Nothing to roast.")
    if not commits:
        raise RoastError(f"'{repo}' has no commits yet. Nothing to roast.")
    return commits


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


def ask_dify(prompt):
    api_key = os.getenv("DIFY_API_KEY", "").strip()
    base_url = os.getenv("DIFY_BASE_URL", "https://api.dify.ai/v1").strip().rstrip("/")
    if not api_key or "xxxx" in api_key:
        raise RoastError("DIFY_API_KEY is missing. Paste your Dify app key (app-...) into .env.")

    try:
        response = requests.post(
            f"{base_url}/chat-messages",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"inputs": {}, "query": prompt, "response_mode": "blocking", "user": "commit-roaster-cli"},
            timeout=120,
        )
    except requests.exceptions.Timeout:
        raise RoastError("Dify took longer than 2 minutes to answer. Try again, or use fewer commits (-n 10).")
    except requests.exceptions.ConnectionError:
        raise RoastError(f"Could not reach Dify at {base_url}. Check your internet connection and DIFY_BASE_URL.")

    if response.status_code == 401:
        raise RoastError("Dify rejected the API key (401). Check DIFY_API_KEY in .env.")
    if response.status_code == 429:
        raise RoastError("Rate limited (429). Free models allow only a few requests per minute; wait and retry.")
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


def main():
    load_dotenv(Path(__file__).resolve().parent / ".env")
    args = parse_args()
    try:
        commits = read_commits(args.repo, args.count, args.rev_range)
        prompt = build_prompt(args.repo, commits, args.rev_range)
        if args.dry_run:
            console.print(Panel(Text(prompt), title="Prompt (dry run)", border_style="cyan"))
            return 0
        with console.status(f"Roasting {len(commits)} commits..."):
            roast = ask_dify(prompt)
    except RoastError as err:
        console.print(f"[bold red]Error:[/] {escape(str(err))}")
        return 1

    console.print(Panel(Markdown(roast), title="Commit Roast", border_style="red"))
    if args.output:
        args.output.write_text(roast + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
