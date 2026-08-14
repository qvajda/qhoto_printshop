"""`qops metrics` — S1/S2/S4/S9/S10, plus `--state` for PRD §1.2.

S1 adopts the Phase −1 findings §1 method **verbatim**, because a baseline
measured one way and re-measured another is not a baseline and Phase 6 compares
against it:

  session          one *.jsonl transcript
  main thread      records with `isSidechain` falsy — subagent traffic excluded
  read             a tool_use block named Read or NotebookRead
  productive       Write/Edit/MultiEdit/NotebookEdit, or a Bash/PowerShell
                   command matching git commit | pytest | -m pytest |
                   -m unittest | npm test
  S1               reads strictly before the first productive call
  >200-line read   a read whose result carries more than 200 newlines, before
                   the first productive call

Bash reads (cat, sed, head) are deliberately NOT counted, so S1 is a floor.
"""

import json
import os
import re
import statistics
import subprocess
import sys
from pathlib import Path

READ_TOOLS = {"Read", "NotebookRead"}
EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}
PRODUCTIVE_CMD = re.compile(r"git commit|pytest|-m pytest|-m unittest|npm test")
BIG_READ_LINES = 200
KICKOFF_DOCS = re.compile(r"docs/.*(kickoff|session-prompt|launch|brief|runbook)")


# --- S1 --------------------------------------------------------------------

def _blocks(rec: dict):
    msg = rec.get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):
        return content
    return []


def _result_lines(block: dict) -> int:
    content = block.get("content")
    if isinstance(content, str):
        return content.count("\n")
    if isinstance(content, dict):
        text = content.get("file", {}).get("content", "") if isinstance(
            content.get("file"), dict) else content.get("text", "")
        return str(text).count("\n")
    if isinstance(content, list):
        return sum(str(b.get("text", "")).count("\n") for b in content
                   if isinstance(b, dict))
    return 0


def s1_for_transcript(path: Path) -> dict:
    reads = 0
    productive = False
    big_read = False
    pending_read = False
    for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("isSidechain"):
            continue                       # subagent traffic is not the owner's cost
        for block in _blocks(rec):
            btype = block.get("type")
            if btype == "tool_result" and pending_read and not productive:
                if _result_lines(block) > BIG_READ_LINES:
                    big_read = True
                pending_read = False
            if btype != "tool_use":
                continue
            name = block.get("name")
            if name in EDIT_TOOLS:
                productive = True
            elif name in SHELL_TOOLS:
                if PRODUCTIVE_CMD.search((block.get("input") or {}).get("command", "")):
                    productive = True
            elif name in READ_TOOLS and not productive:
                reads += 1
                pending_read = True
        if productive:
            break
    return {"reads": reads, "productive": productive, "big_read": big_read,
            "transcript": str(path)}


def _transcript_dirs(root: Path) -> list[Path]:
    home = Path(os.path.expanduser("~")) / ".claude" / "projects"
    if not home.exists():
        return []
    slug = str(Path(root).resolve()).replace(":", "").replace("\\", "-").replace("/", "-")
    slug = slug.replace("--", "-").lstrip("-")
    return [d for d in home.iterdir()
            if d.is_dir() and Path(root).name.replace("_", "-") in d.name.lower()]


def s1(root: Path) -> dict:
    rows = []
    for d in _transcript_dirs(root):
        for t in d.glob("*.jsonl"):
            try:
                rows.append(s1_for_transcript(t))
            except OSError:
                continue
    scored = [r for r in rows if r["productive"]]
    counts = [r["reads"] for r in scored]
    return {
        "sessions": len(rows),
        "scored": len(scored),
        "no_productive_call": len(rows) - len(scored),
        "median_reads": statistics.median(counts) if counts else None,
        "mean_reads": round(statistics.mean(counts), 2) if counts else None,
        "pct_with_big_read": round(100 * sum(r["big_read"] for r in scored)
                                   / len(scored)) if scored else None,
    }


# --- S2 / S4 / S9 / S10 ----------------------------------------------------

def s2(root: Path, since: str = "2026-07-14") -> int:
    out = subprocess.run(
        ["git", "log", f"--since={since}", "--diff-filter=A", "--name-only",
         "--pretty=format:"], cwd=root, capture_output=True, text=True).stdout
    return len({p for p in out.split() if KICKOFF_DOCS.search(p)})


def _gh(root: Path, *args: str):
    try:
        out = subprocess.run(["gh", *args], cwd=root, capture_output=True,
                             text=True, timeout=60)
        return json.loads(out.stdout) if out.returncode == 0 and out.stdout else None
    except Exception:
        return None


def s4(root: Path) -> dict:
    """PRs where review was requested before the gate check went green."""
    prs = _gh(root, "pr", "list", "--state", "all", "--limit", "50",
              "--json", "number,reviewRequests,statusCheckRollup,createdAt")
    if prs is None:
        return {"available": False}
    bad = []
    for pr in prs:
        rollup = pr.get("statusCheckRollup") or []
        # Every applicable gate, not two named ones: naming `gate` and `test`
        # let a red guard.yml (tripwires, doc links) score as clean.
        conclusions = [c.get("conclusion") for c in rollup]
        gate_green = (bool(rollup)
                      and not any(c in ("FAILURE", "TIMED_OUT", "CANCELLED",
                                        "ACTION_REQUIRED", "STARTUP_FAILURE")
                                  for c in conclusions)
                      and "SUCCESS" in conclusions)
        if pr.get("reviewRequests") and not gate_green:
            bad.append(pr["number"])
    return {"available": True, "requests_without_green_gate": bad,
            "total": len(prs)}


def s9(root: Path) -> dict:
    """state:planned -> first commit on the matching branch."""
    issues = _gh(root, "issue", "list", "--label", "state:building", "--limit", "20",
                 "--json", "number,title,updatedAt")
    if issues is None:
        return {"available": False}
    return {"available": True, "in_flight": [i["number"] for i in issues]}


def s10(root: Path, cfg: dict) -> dict:
    """Hot path: what enters context without being asked for."""
    claude_md = Path(root) / "CLAUDE.md"
    lines = len(claude_md.read_text(encoding="utf-8").splitlines()) if claude_md.exists() else 0
    from . import brief as briefmod
    brief_tokens = briefmod.tokens(briefmod.render(root, cfg))
    return {"claude_md_lines": lines, "claude_md_cap": cfg["claude_md_max_lines"],
            "claude_md_tokens": -(-claude_md.stat().st_size // 4) if claude_md.exists() else 0,
            "brief_tokens": brief_tokens,
            "within_cap": lines <= cfg["claude_md_max_lines"]}


# --- --state: PRD §1.2, the table becomes generated ------------------------

_STATE_ROWS = [
    ("Plan/doc sprawl", "ls docs/*.md | wc -l"),
    ("Plan/doc lines", "cat docs/*.md | wc -l"),
    ("Per-session fixed cost", "wc -l CLAUDE.md"),
    ("Branches", "git branch | wc -l"),
    ("Worktrees", "git worktree list | wc -l"),
    ("Dirty paths", "git status --porcelain | wc -l"),
    ("Unmerged branches", "git branch --no-merged master | wc -l"),
    ("Test files", "ls tests/test_*.py | wc -l"),
    ("Workflows", "ls .github/workflows/*.yml | wc -l"),
]


def state_report(root: Path, cfg: dict) -> str:
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root,
                          capture_output=True, text=True).stdout.strip()
    lines = ["# qops state report", "",
             "Generated by `qops metrics --state`. PRD v3 §1 is a pointer to this "
             "file, not a cache of it — a number without a `measured-at` is the "
             "defect.", "",
             f"measured-at: `{head}`", "", "| Symptom | Value | Command |",
             "|---|---|---|"]
    for label, cmd in _STATE_ROWS:
        out = subprocess.run(["bash", "-lc", cmd], cwd=root, capture_output=True,
                             text=True).stdout.strip().splitlines()
        value = out[0].strip() if out else "—"
        lines.append(f"| {label} | {value} | `{cmd}` |")
    text = "\n".join(lines) + "\n"
    (Path(root) / ".qops" / "state-report.md").write_text(text, encoding="utf-8")
    return text


def main(argv: list[str], root: Path, cfg: dict) -> int:
    if "--state" in argv:
        sys.stdout.write(state_report(root, cfg))
        return 0
    report = {"S1_resume_cost": s1(root), "S2_kickoff_docs": s2(root),
              "S4_review_before_gate": s4(root), "S9_planned_to_working": s9(root),
              "S10_hot_path": s10(root, cfg)}
    if "--json" in argv:
        print(json.dumps(report, indent=2))
        return 0
    for key, value in report.items():
        print(f"{key}: {json.dumps(value)}")
    return 0
