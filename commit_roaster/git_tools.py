"""Read commit history and individual commits with the git CLI."""

import re
import subprocess

from . import RoastError

FIELD_SEP = "\x1f"  # ASCII unit separator: never appears in normal commit text
COMMIT_HASH = re.compile(r"^[0-9a-fA-F]{4,40}$")


def _git(repo, *args):
    try:
        return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise RoastError("Git is not installed or not on PATH. Run setup\\setup_windows.ps1 first.")


def read_commits(repo, count, rev_range=None):
    """Return a list of (short_hash, author, age, subject) for the latest commits."""
    args = ["log", f"-n{count}", f"--pretty=format:%h{FIELD_SEP}%an{FIELD_SEP}%ar{FIELD_SEP}%s"]
    if rev_range:
        args += [rev_range, "--"]
    result = _git(repo, *args)

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


def show_commit(repo, commit_hash, max_chars=4000):
    """Return the full message, file stats and a truncated patch for one commit."""
    commit_hash = commit_hash.strip()
    if not COMMIT_HASH.match(commit_hash):
        raise RoastError(f"'{commit_hash}' is not a commit hash.")
    result = _git(repo, "show", "--stat", "--patch", "-U2",
                  "--format=commit %h%nAuthor: %an%nDate: %ar%n%n%B", commit_hash, "--")
    if result.returncode != 0:
        raise RoastError(f"Commit {commit_hash} not found.")

    text = result.stdout
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n[diff truncated: {len(text) - max_chars} more characters]"
    return text
