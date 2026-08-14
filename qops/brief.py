"""`qops brief` — what a session is given at SessionStart instead of reading
its way in (CONTEXT.md: *Brief*).

Two contracts, both asserted in tests/test_qops.py:
  1. never more than 400 tokens — it is hot path, and hot path is what S10
     measures;
  2. it leads with a dirty-tree violation rather than papering over it.
"""

import subprocess
import sys
from pathlib import Path

from . import ledger

TOKEN_CAP = 400
BYTES_PER_TOKEN = 4          # PRD §2.1's own divisor, so the numbers compare


def tokens(text: str) -> int:
    return -(-len(text) // BYTES_PER_TOKEN)


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True,
                              text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def _porcelain(root: Path) -> list[str]:
    """Paths from `git status --porcelain`. NOT via _git: its .strip() eats the
    leading space of an unstaged first line and takes the path's first char
    with it (`.qops/config.yml` -> `qops/config.yml`)."""
    try:
        out = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                             capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return []
    return [line[3:] for line in out.splitlines() if len(line) > 3]


def collect(root: Path, cfg: dict) -> dict:
    dirty = _porcelain(root)
    worktrees = max(len(_git(root, "worktree", "list").splitlines()) - 1, 0)
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    ahead = _git(root, "rev-list", "--count", "@{u}..HEAD") or "0"
    events = ledger.read(root, 6)
    issue = next((r.get("issue") for r in reversed(events) if r.get("issue")), None)
    resume = ""
    p = Path(root) / ".qops" / "resume.md"
    if p.exists():
        body = [l for l in p.read_text(encoding="utf-8").splitlines()
                if l.startswith("- ")]
        resume = "\n".join(body[-3:])
    return {"branch": branch, "dirty": dirty, "worktrees": worktrees,
            "ahead": int(ahead or 0), "issue": issue, "resume": resume}


def render_from(state: dict, cfg: dict) -> str:
    lines: list[str] = []
    dirty = state.get("dirty") or []
    if dirty:
        shown = ", ".join(dirty[:6]) + (" ..." if len(dirty) > 6 else "")
        lines.append(f"**Dirty tree - {len(dirty)} path(s): {shown}.** "
                     f"Commit, stash or ignore before starting new work.")
    if state.get("branch") in cfg.get("protected_branches", []):
        lines.append(f"On `{state['branch']}` (protected). Branch before committing.")
    if state.get("worktrees", 0) >= cfg.get("max_worktrees", 99):
        lines.append(f"{state['worktrees']} worktrees live — at the cap.")

    head = f"qops | `{state.get('branch','?')}`"
    if state.get("ahead"):
        head += f" | {state['ahead']} unpushed"
    if state.get("issue"):
        head += f" | sortie #{state['issue']}"
    lines.append(head)
    lines.append("Issues are the source of truth: `gh issue list`. "
                 "Vocabulary: CONTEXT.md | decisions: docs/adr/ | constraints: CLAUDE.md.")
    if state.get("resume"):
        lines.append("Last session:\n" + state["resume"])

    text = "\n\n".join(lines) + "\n"
    cap = TOKEN_CAP * BYTES_PER_TOKEN
    if len(text) > cap:
        text = text[: cap - 4].rstrip() + " ...\n"
    return text


def render(root: Path, cfg: dict) -> str:
    return render_from(collect(root, cfg), cfg)


def main(argv: list[str], root: Path, cfg: dict) -> int:
    sys.stdout.write(render(root, cfg))
    return 0
