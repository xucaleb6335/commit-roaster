"""LangGraph agent that investigates a repo's commits with tools and writes a cited roast.

Graph:
    START -> agent --(tool calls)--> tools -> agent ... --(no tool calls)--> finalize -> END
                  +--(answered without reading history, once)--> nudge -> agent

The agent decides which tools to call: read the history, inspect suspicious diffs, and search
the commit-guidelines knowledge base (RAG). A step budget stops runaway loops, and the finalize
node keeps only citations that exist in the knowledge base and appends a Sources list.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Annotated, Callable, Optional, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from . import RoastError
from .git_tools import read_commits, show_commit
from .knowledge import CITATION, KnowledgeBase

DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning:free"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
MAX_STEPS = 8          # LLM calls that may still request tools
MAX_INSPECTIONS = 4    # diffs the agent may open per run

SYSTEM_PROMPT = """You are Commit Roaster, a savage but witty senior engineer who reviews Git commit
messages. You have tools; use them before writing anything.

WORKFLOW
1. Call read_git_history to get the commits. Never invent commits.
2. Pick up to 3 of the most suspicious commits (vague, tiny message, WIP, misleading) and call
   inspect_commit on them to see what actually changed.
3. Call search_commit_guidelines for the problems you found (e.g. "vague message",
   "wip commit", "imperative mood") to get the rules to cite.
4. Write the review.

REVIEW FORMAT (Markdown)
- One line per commit worth roasting: **[hash]** "message" - burn, citing the broken rule like
  [BP-05]. Use evidence from the diff when you have it ("'small tweak' touched 14 files").
- **Verdict:** two sentences on the overall commit hygiene.
- **Score:** X/10 with a one-line justification.
- **Fixes:** for the 2-3 worst commits, a rewritten commit message that follows the guidelines.

RULES
- Roast the messages, never the people. No slurs, no insults about identity or intelligence.
- Only cite IDs that search_commit_guidelines returned. Do not make up IDs.
- No encouragement fluff. Max one emoji."""

BUDGET_EXHAUSTED = ("Tool budget used up. Do not call any more tools; write the final review now "
                    "using the information you already have.")
MUST_READ_HISTORY = ("You have not read the commit history yet. Call read_git_history first; "
                     "never review commits you have not seen.")


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    steps: int
    nudged: bool
    history_read: bool
    review: str
    citations: list[str]


@dataclass
class AgentResult:
    review: str
    citations: list[str]
    tool_calls: list[str] = field(default_factory=list)


def make_tools(repo, count, rev_range, kb):
    """Build the agent's tools. The repo and range are fixed here, never chosen by the model."""
    inspected = set()

    @tool
    def read_git_history(max_commits: int = count) -> str:
        """Read the commit history to review: one line per commit with hash, message, author and age."""
        n = max(1, min(int(max_commits), count))
        commits = read_commits(repo, n, rev_range)
        return "\n".join(f"[{h}] {subject} ({author}, {age})" for h, author, age, subject in commits)

    @tool
    def inspect_commit(commit_hash: str) -> str:
        """Show one commit's full message, changed files with line counts, and a truncated diff."""
        if commit_hash not in inspected and len(inspected) >= MAX_INSPECTIONS:
            return f"Inspection limit reached ({MAX_INSPECTIONS} commits). Work with what you have."
        inspected.add(commit_hash)
        return show_commit(repo, commit_hash)

    @tool
    def search_commit_guidelines(query: str) -> str:
        """Search the commit-message guidelines (Conventional Commits and best practices).
        Returns the most relevant rules with IDs like [BP-05] to cite in the review."""
        return kb.format_results(kb.search(query, k=3))

    return [read_git_history, inspect_commit, search_commit_guidelines]


def strip_thinking(text):
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()


def apply_citations(review, kb):
    """Drop citations that are not in the knowledge base and append a Sources section."""
    cited = []
    for cid in CITATION.findall(review):
        if cid in kb.by_id and cid not in cited:
            cited.append(cid)
    review = CITATION.sub(lambda m: m.group(0) if m.group(1) in kb.by_id else "", review)
    if cited:
        sources = "\n".join(f"- **[{c}]** {kb.by_id[c].title} ({kb.by_id[c].source})" for c in cited)
        review = f"{review.rstrip()}\n\n**Sources**\n{sources}"
    return review, cited


def build_graph(llm, tools, kb, max_steps=MAX_STEPS):
    tools_by_name = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    def agent(state: AgentState):
        if state["steps"] >= max_steps:
            response = llm.invoke(state["messages"] + [HumanMessage(BUDGET_EXHAUSTED)])
        else:
            response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response], "steps": state["steps"] + 1}

    def run_tools(state: AgentState):
        results, history_read = [], state["history_read"]
        for call in state["messages"][-1].tool_calls:
            selected = tools_by_name.get(call["name"])
            if selected is None:
                content = f"Error: unknown tool '{call['name']}'. Available: {', '.join(tools_by_name)}."
            else:
                try:
                    content = str(selected.invoke(call["args"]))
                    history_read = history_read or call["name"] == "read_git_history"
                except RoastError as err:
                    content = f"Error: {err}"
                except Exception as err:  # bad arguments from the model; let it retry
                    content = f"Error: invalid arguments for {call['name']}: {err}"
            results.append(ToolMessage(content=content, tool_call_id=call["id"], name=call["name"]))
        return {"messages": results, "history_read": history_read}

    def nudge(state: AgentState):
        return {"messages": [HumanMessage(MUST_READ_HISTORY)], "nudged": True}

    def finalize(state: AgentState):
        if not state["history_read"]:
            raise RoastError("The model answered without reading the Git history. Pick a model with "
                             "tool-calling support (OPENROUTER_MODEL).")
        review = strip_thinking(state["messages"][-1].content)
        if not review:
            raise RoastError("The model returned an empty review. Try again or pick another model.")
        review, cited = apply_citations(review, kb)
        return {"review": review, "citations": cited}

    def route(state: AgentState):
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls and state["steps"] <= max_steps:
            return "tools"
        if not state["history_read"] and not state["nudged"]:
            return "nudge"
        return "finalize"

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent)
    graph.add_node("tools", run_tools)
    graph.add_node("nudge", nudge)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route, ["tools", "nudge", "finalize"])
    graph.add_edge("tools", "agent")
    graph.add_edge("nudge", "agent")
    graph.add_edge("finalize", END)
    return graph.compile()


def make_llm():
    """Chat model on OpenRouter. Retries with backoff cover rate limits (429) and timeouts."""
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key or "xxxx" in api_key:
        raise RoastError("OPENROUTER_API_KEY is missing. Paste your OpenRouter key (sk-or-...) into .env.")
    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        api_key=api_key,
        base_url=os.getenv("OPENROUTER_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
        temperature=0.8,
        timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "90")),
        max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
        default_headers={"X-Title": "Commit Roaster"},
    )


def describe_call(call):
    args = ", ".join(f"{k}={v!r}" for k, v in call["args"].items())
    return f"{call['name']}({args})"


def run_agent(llm, repo, count, rev_range=None, kb=None,
              on_tool_call: Optional[Callable[[str], None]] = None, max_steps=MAX_STEPS):
    """Run the agent and return the cited review. Raises RoastError with a readable message."""
    import openai

    read_commits(repo, 1, rev_range)  # fail fast on a bad repo or range before spending LLM calls
    kb = kb or KnowledgeBase.load()
    graph = build_graph(llm, make_tools(repo, count, rev_range, kb), kb, max_steps)
    scope = f"the commits in {rev_range}" if rev_range else f"the latest {count} commits"
    state = {"messages": [SystemMessage(SYSTEM_PROMPT), HumanMessage(f"Roast {scope} of this repository.")],
             "steps": 0, "nudged": False, "history_read": False, "review": "", "citations": []}

    calls, final = [], {}
    try:
        for update in graph.stream(state, {"recursion_limit": 4 * max_steps + 10}, stream_mode="updates"):
            for node, delta in update.items():
                if node == "agent":
                    for call in getattr(delta["messages"][-1], "tool_calls", None) or []:
                        calls.append(describe_call(call))
                        if on_tool_call:
                            on_tool_call(calls[-1])
                elif node == "finalize":
                    final = delta
    except openai.AuthenticationError:
        raise RoastError("OpenRouter rejected the API key (401). Check OPENROUTER_API_KEY in .env.")
    except openai.RateLimitError:
        raise RoastError("Rate limited (429) even after retries. Free models allow only a few requests "
                         "per minute; wait a minute and try again.")
    except openai.APITimeoutError:
        raise RoastError("The model timed out even after retries. Try again, or use fewer commits (-n 10).")
    except openai.APIConnectionError:
        raise RoastError("Could not reach OpenRouter. Check your internet connection and OPENROUTER_BASE_URL.")
    except openai.NotFoundError as err:
        raise RoastError(f"Model or endpoint not found: {err.message}. Check OPENROUTER_MODEL.")
    except openai.APIStatusError as err:
        raise RoastError(f"OpenRouter returned {err.status_code}: {err.message}")

    return AgentResult(final["review"], final["citations"], calls)
