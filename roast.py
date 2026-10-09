"""Commit Roaster: get an LLM to review (and roast) a Git repo's commit messages.

Usage:
    python roast.py --agent              # LangGraph agent: inspects diffs, cites guidelines (OpenRouter)
    python roast.py --agent --model nvidia/nemotron-3-super-120b-a12b:free
    python roast.py                      # simple mode: one call to your Dify app
    python roast.py --repo C:\\code\\app -n 10
    python roast.py --range main..HEAD   # only the commits on this branch (used by CI)
    python roast.py --dry-run            # show the prompt without calling a model
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

from commit_roaster import RoastError
from commit_roaster.dify import ask_dify, build_prompt
from commit_roaster.git_tools import read_commits

console = Console()


def parse_args():
    parser = argparse.ArgumentParser(description="Roast a Git repo's recent commit messages.")
    parser.add_argument("--agent", action="store_true",
                        help="use the LangGraph agent (tool calling + RAG) via OpenRouter instead of Dify")
    parser.add_argument("--model", help="OpenRouter model for --agent (overrides OPENROUTER_MODEL in .env)")
    parser.add_argument("--repo", default=".", help="path to a Git repository (default: current folder)")
    parser.add_argument("-n", "--count", type=int, default=int(os.getenv("COMMIT_COUNT", "20")),
                        help="number of commits to roast (default: 20)")
    parser.add_argument("--range", dest="rev_range",
                        help="git revision range to roast, e.g. main..HEAD (default: latest commits)")
    parser.add_argument("--output", type=Path, help="also write the roast (Markdown) to this file")
    parser.add_argument("--dry-run", action="store_true", help="print the prompt and exit without calling a model")
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be at least 1")
    if args.rev_range and args.rev_range.startswith("-"):
        parser.error("--range must be a revision range like main..HEAD")
    if args.model and not args.agent:
        parser.error("--model only applies to --agent (in simple mode the model is chosen in Dify)")
    return args


def roast_with_agent(args):
    from commit_roaster.agent import SYSTEM_PROMPT, make_llm, run_agent

    if args.dry_run:
        console.print(Panel(Text(SYSTEM_PROMPT), title="Agent system prompt (dry run)", border_style="cyan"))
        return None
    if args.model:
        os.environ["OPENROUTER_MODEL"] = args.model
    llm = make_llm()
    with console.status("Agent is investigating the commits...") as status:
        def show(call):
            console.print(f"[dim]  tool call: {escape(call)}[/]")
            status.update(f"Agent is working... ({call.split('(')[0]})")
        result = run_agent(llm, args.repo, args.count, args.rev_range, on_tool_call=show)
    return result.review


def roast_with_dify(args):
    commits = read_commits(args.repo, args.count, args.rev_range)
    prompt = build_prompt(args.repo, commits, args.rev_range)
    if args.dry_run:
        console.print(Panel(Text(prompt), title="Prompt (dry run)", border_style="cyan"))
        return None
    with console.status(f"Roasting {len(commits)} commits..."):
        return ask_dify(prompt)


def main():
    load_dotenv(Path(__file__).resolve().parent / ".env")
    args = parse_args()
    try:
        roast = roast_with_agent(args) if args.agent else roast_with_dify(args)
    except RoastError as err:
        console.print(f"[bold red]Error:[/] {escape(str(err))}")
        return 1
    if roast is None:
        return 0

    console.print(Panel(Markdown(roast), title="Commit Roast", border_style="red", width=min(console.width, 110)))
    if args.output:
        args.output.write_text(roast + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
