"""Offline commit-message linter: fast, free checks against the knowledge-base rules, no LLM."""

import re

TYPES = "feat|fix|build|chore|ci|docs|style|refactor|perf|test|revert"
HEADER = re.compile(rf"^(?:{TYPES})(?:\([a-z0-9._/-]+\))?!?: \S")
VAGUE = re.compile(r"^(?:fix(?:es|ed)?|updates?|changes?|stuff|wip|misc|temp|test(?:ing)?|asdf+|\.+)$", re.I)
SKIPPED = re.compile(r"^(?:Merge |Revert \")")
MAX_SUBJECT = 72


def lint_message(subject):
    """Return a list of (rule_id, problem) for one commit subject line. Empty means it passes."""
    subject = subject.strip()
    if SKIPPED.match(subject):
        return []
    problems = []
    description = subject.split(": ", 1)[1] if ": " in subject else subject
    if not HEADER.match(subject):
        problems.append(("CC-01", "not in Conventional Commits form 'type(scope): description'"))
    if VAGUE.match(description.strip()):
        problems.append(("BP-05", f"vague description '{description.strip()}'"))
    if len(subject) > MAX_SUBJECT:
        problems.append(("BP-02", f"subject is {len(subject)} characters (max {MAX_SUBJECT})"))
    if description.rstrip().endswith("."):
        problems.append(("CC-05", "description ends with a period"))
    if re.match(r"^(?:added|fixed|updated|removed|changed)\b", description, re.I):
        problems.append(("BP-03", "use the imperative mood ('add', not 'added')"))
    return problems


def lint_commits(commits):
    """Lint (hash, author, age, subject) tuples; return [(hash, subject, problems)]."""
    return [(h, subject, lint_message(subject)) for h, _author, _age, subject in commits]
