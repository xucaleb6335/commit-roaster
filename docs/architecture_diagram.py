# Regenerates docs/architecture.png:  pip install matplotlib && python docs/architecture_diagram.py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

plt.rcParams["font.family"] = "DejaVu Sans"
fig, ax = plt.subplots(figsize=(11, 6.6), dpi=200)
ax.set_xlim(0, 100); ax.set_ylim(0, 65); ax.axis("off")
INK, MUTED = "#2B3138", "#5B6570"
BLUE, GREEN, ORANGE, PURPLE, TEAL, GRAY = "#2F6FB5", "#3B8A5A", "#C0692B", "#8A4FB0", "#1F8A8A", "#7A848F"

ax.text(0.5, 64.6, "Commit Roaster: how it works", fontsize=15, weight="bold", color=INK, va="top")
ax.text(0.5, 61.2, "An AI agent reads your Git history, digs into suspicious diffs, looks up the rules, and writes a cited review.",
        fontsize=8.6, color=MUTED, va="top")

def box(x, y, w, h, title, body, col, dashed=False, title_size=8.4):
    ls = (0, (4, 2.5)) if dashed else "solid"
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.9", fc="white", ec=col, lw=1.4, ls=ls))
    ax.add_patch(FancyBboxPatch((x, y + h - 3.4), w, 3.4, boxstyle="round,pad=0,rounding_size=0.9", fc=col, ec=col, lw=1.4, ls=ls))
    ax.text(x + w / 2, y + h - 1.7, title, ha="center", va="center", fontsize=title_size, color="white", weight="bold")
    ax.text(x + w / 2, y + (h - 3.4) / 2, body, ha="center", va="center", fontsize=7.1, color=INK, linespacing=1.35)

def arrow(pts, col=INK, both=False, label=None, lxy=None, lcol=None, ha="center"):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=col, lw=1.1, solid_capstyle="round")
    ax.annotate("", xy=pts[-1], xytext=pts[-2], arrowprops=dict(arrowstyle="-|>", color=col, lw=1.1, mutation_scale=9))
    if both:
        ax.annotate("", xy=pts[0], xytext=pts[1], arrowprops=dict(arrowstyle="-|>", color=col, lw=1.1, mutation_scale=9))
    if label:
        ax.text(*lxy, label, ha=ha, va="center", fontsize=6.6, color=lcol or col, style="italic")

# LangGraph container
ax.add_patch(FancyBboxPatch((24, 2), 51, 50.5, boxstyle="round,pad=0,rounding_size=1.4", fc="#F4F7FB", ec="#AEB8C4", lw=0.9, ls=(0, (3, 2))))
ax.text(73.8, 51.4, "LANGGRAPH AGENT  (StateGraph)", fontsize=7.6, color=MUTED, weight="bold", va="top", ha="right")

# Entry points and output
box(1, 40, 18, 9, "Your terminal", "python roast.py --agent", BLUE)
box(1, 28, 18, 9, "GitHub Actions", "runs on every\npull request", BLUE)
box(1, 4, 18, 12, "Cited review", "terminal panel\nor PR comment\n+ Sources list", GREEN)

# Graph nodes
box(28, 39, 18, 9.5, "agent node", "LLM decides which\ntool to call next", ORANGE)
box(53, 39, 18, 9.5, "tools node", "runs the tool calls,\nreturns results", ORANGE)
box(28, 25.5, 18, 8.5, "finalize node", "drop fake citations,\nappend Sources", ORANGE)
ax.text(47.6, 30.5, "guardrails: step budget,\nnudge if history unread,\nmax 4 diff inspections", ha="left", va="center",
        fontsize=6.5, color=MUTED, style="italic", linespacing=1.3)

# Tools
box(25.5, 13.5, 15, 7.5, "read_git_history", "git log", TEAL, title_size=7.4)
box(42, 13.5, 15, 7.5, "inspect_commit", "git show --stat", TEAL, title_size=7.4)
box(58.5, 13.5, 15.5, 7.5, "search_guidelines", "BM25 retrieval", PURPLE, title_size=7.4)

# Data sources
box(25.5, 3.5, 31.5, 7, "Git repository", "commit messages + diffs", GRAY)
box(58.5, 3.5, 15.5, 7, "Knowledge base", "22 rules (RAG)", PURPLE, title_size=7.6)

# Model side
box(80, 39, 19, 9.5, "OpenRouter", "chat + tool schemas,\nretries on 429/timeouts", "#B5476B")
box(80, 25.5, 19, 9.5, "NVIDIA Nemotron", "3.5 Lightning (free)\n$0 per review", "#76B900")
box(80, 4, 19, 13, "Simple mode", "python roast.py\n-> Dify app -> OpenRouter\n(one call, no tools)", GRAY, dashed=True)

# Arrows
arrow([(19, 44.5), (28, 44.5)])
arrow([(19, 32.5), (23, 32.5), (23, 42), (28, 42)])
arrow([(46, 45.5), (53, 45.5)], label="tool calls", lxy=(49.5, 47.2), lcol=MUTED)
arrow([(53, 42), (46, 42)], label="results", lxy=(49.5, 40.4), lcol=MUTED)
arrow([(37, 39), (37, 34)])
arrow([(28, 29.8), (21.5, 29.8), (21.5, 10), (19, 10)])
arrow([(62, 39), (62, 25), (33, 25), (33, 21)])
arrow([(62, 25), (49.5, 25), (49.5, 21)])
arrow([(62, 25), (66.25, 25), (66.25, 21)])
arrow([(33, 13.5), (33, 10.5)]); arrow([(49.5, 13.5), (49.5, 10.5)]); arrow([(66.25, 13.5), (66.25, 10.5)])
arrow([(37, 48.5), (37, 54.5), (89.5, 54.5), (89.5, 48.5)], both=True, label="LLM requests over HTTPS (chat completions with tool schemas)", lxy=(63, 56.2), lcol=MUTED)
arrow([(89.5, 39), (89.5, 35)], both=True)

plt.savefig(str(__import__("pathlib").Path(__file__).with_name("architecture.png")), bbox_inches="tight", pad_inches=0.08, facecolor="white")
