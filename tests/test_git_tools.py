import pytest

from commit_roaster import RoastError
from commit_roaster.git_tools import read_commits, show_commit


def test_read_commits_latest_first(repo):
    commits = read_commits(str(repo), 2)
    assert [c[3] for c in commits] == ["asdf please work", "small tweak"]


def test_read_commits_range_only_returns_branch_commits(repo):
    commits = read_commits(str(repo), 20, "main..feature")
    assert [c[3] for c in commits] == ["asdf please work", "small tweak", "fix", "wip"]


def test_read_commits_errors(repo, tmp_path):
    with pytest.raises(RoastError, match="not a Git repository"):
        read_commits(str(tmp_path), 5)
    with pytest.raises(RoastError, match="No commits in range"):
        read_commits(str(repo), 5, "feature..feature")


def test_show_commit_includes_stats_and_message(repo):
    sha = read_commits(str(repo), 2)[1][0]  # "small tweak"
    text = show_commit(str(repo), sha)
    assert "small tweak" in text and "10 files changed" in text


def test_show_commit_truncates_long_diffs(repo):
    sha = read_commits(str(repo), 2)[1][0]
    assert "[diff truncated:" in show_commit(str(repo), sha, max_chars=300)


@pytest.mark.parametrize("bad", ["--output=x", "HEAD; rm -rf /", "main", ""])
def test_show_commit_rejects_anything_but_a_hash(repo, bad):
    with pytest.raises(RoastError, match="not a commit hash"):
        show_commit(str(repo), bad)
