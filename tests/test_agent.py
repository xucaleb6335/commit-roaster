import pytest
from langchain_core.messages import AIMessage, ToolMessage

from commit_roaster import RoastError
from commit_roaster.agent import BUDGET_EXHAUSTED, MUST_READ_HISTORY, apply_citations, run_agent
from commit_roaster.git_tools import read_commits
from commit_roaster.knowledge import KnowledgeBase
from conftest import ScriptedChatModel


def call(name, args, id):
    return {"name": name, "args": args, "id": id, "type": "tool_call"}


def tool_outputs(model):
    return [m for m in model.received[-1] if isinstance(m, ToolMessage)]


def test_agent_reads_history_inspects_diff_searches_and_cites(repo):
    tweak_sha = read_commits(str(repo), 2)[1][0]
    model = ScriptedChatModel(responses=[
        AIMessage("", tool_calls=[call("read_git_history", {}, "1")]),
        AIMessage("", tool_calls=[call("inspect_commit", {"commit_hash": tweak_sha}, "2"),
                                  call("search_commit_guidelines", {"query": "small tweak many files"}, "3")]),
        AIMessage(f'**[{tweak_sha}]** "small tweak" touched 10 files [BP-06] [ZZ-99]\n\n**Score:** 2/10'),
    ])
    calls = []
    result = run_agent(model, str(repo), 20, "main..feature", on_tool_call=calls.append)

    assert model.bound_tools == ["read_git_history", "inspect_commit", "search_commit_guidelines"]
    assert [c.split("(")[0] for c in calls] == ["read_git_history", "inspect_commit", "search_commit_guidelines"]
    outputs = {m.name: m.content for m in tool_outputs(model)}
    assert "asdf please work" in outputs["read_git_history"]
    assert "hello world" not in outputs["read_git_history"]          # range respected
    assert "10 files changed" in outputs["inspect_commit"]
    assert "[BP-06]" in outputs["search_commit_guidelines"]
    assert result.citations == ["BP-06"]
    assert "[ZZ-99]" not in result.review                              # made-up citation dropped
    assert "**Sources**" in result.review and "Match the message to the size" in result.review


def test_agent_is_nudged_when_it_skips_the_history(repo):
    model = ScriptedChatModel(responses=[
        AIMessage("Your commits are bad."),
        AIMessage("", tool_calls=[call("read_git_history", {"max_commits": 3}, "1")]),
        AIMessage("Three commits, zero information."),
    ])
    result = run_agent(model, str(repo), 20)
    assert any(MUST_READ_HISTORY in str(m.content) for m in model.received[1])
    assert result.review == "Three commits, zero information."


def test_agent_fails_clearly_if_it_never_uses_tools(repo):
    model = ScriptedChatModel(responses=[AIMessage("No tools for me."), AIMessage("Still no tools.")])
    with pytest.raises(RoastError, match="tool-calling support"):
        run_agent(model, str(repo), 20)


def test_step_budget_forces_a_final_answer(repo):
    looping = [AIMessage("", tool_calls=[call("read_git_history", {}, str(i))]) for i in range(3)]
    model = ScriptedChatModel(responses=looping + [AIMessage("Final answer after budget.")])
    result = run_agent(model, str(repo), 20, max_steps=3)
    assert BUDGET_EXHAUSTED in str(model.received[-1][-1].content)
    assert result.review == "Final answer after budget."


def test_tool_errors_are_returned_to_the_model_not_raised(repo):
    model = ScriptedChatModel(responses=[
        AIMessage("", tool_calls=[call("read_git_history", {}, "1"),
                                  call("inspect_commit", {"commit_hash": "not-a-hash"}, "2"),
                                  call("delete_repo", {}, "3")]),
        AIMessage("Done."),
    ])
    run_agent(model, str(repo), 20)
    outputs = {m.name: m.content for m in tool_outputs(model)}
    assert outputs["inspect_commit"].startswith("Error:")
    assert outputs["delete_repo"].startswith("Error: unknown tool")


def test_bad_repo_fails_before_calling_the_model(tmp_path):
    model = ScriptedChatModel(responses=[])
    with pytest.raises(RoastError, match="not a Git repository"):
        run_agent(model, str(tmp_path), 20)
    assert model.received == []


def test_apply_citations_without_any_citation_leaves_review_alone():
    kb = KnowledgeBase.load()
    assert apply_citations("plain roast", kb) == ("plain roast", [])
