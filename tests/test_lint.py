import pytest

from commit_roaster.knowledge import KnowledgeBase
from commit_roaster.lint import lint_commits, lint_message


def rules(subject):
    return [rule for rule, _ in lint_message(subject)]


@pytest.mark.parametrize("subject", [
    "feat: add hello world app",
    "fix(parser): handle empty arrays",
    "feat(api)!: drop v1 endpoints",
    "docs: explain the --range flag",
    'Revert "feat: add hello world app"',
    "Merge branch 'main' into feature",
])
def test_good_messages_pass(subject):
    assert rules(subject) == []


@pytest.mark.parametrize("subject, expected", [
    ("wip", ["CC-01", "BP-05"]),
    ("fix: fix", ["BP-05"]),
    ("Added login page", ["CC-01", "BP-03"]),
    ("feat: add login page.", ["CC-05"]),
    ("feat: " + "x" * 80, ["BP-02"]),
    ("Feature: add login", ["CC-01"]),
])
def test_bad_messages_are_flagged_with_rule_ids(subject, expected):
    assert rules(subject) == expected


def test_every_rule_id_exists_in_the_knowledge_base():
    kb = KnowledgeBase.load()
    for subject in ["wip", "Added x.", "feat: " + "x" * 80]:
        assert all(rule in kb.by_id for rule in rules(subject))


def test_lint_commits_against_a_repo(repo):
    from commit_roaster.git_tools import read_commits
    results = lint_commits(read_commits(str(repo), 20, "main..feature"))
    assert [subject for _, subject, problems in results if problems] == ["asdf please work", "small tweak", "fix", "wip"]
