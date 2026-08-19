"""The local guard. PreToolUse exit 2 blocks a call outright (ADR-0001).

Not a security control — an agent can run with hooks disabled. It is the local
half of a pair whose other half is server-side branch protection (PRD §5 B8).
The tripwire list lives in .qops/config.yml and is read here AND by guard.yml,
so there is one definition with two enforcement points.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

# git commands that write to the current branch
_WRITES = re.compile(r"\bgit\s+(commit|push|merge|rebase)\b")
_RESET_HARD = re.compile(r"\bgit\s+reset\b[^|;&]*--hard\b")
_WORKTREE_ADD = re.compile(r"\bgit\s+worktree\s+add\b")
# A command that makes its own branch first is not writing to the protected one.
_BRANCHES_FIRST = re.compile(r"\bgit\s+(checkout|switch)\s+-[bcBC]\b")

_TEXT_FIELDS = ("content", "new_string", "command", "file_text")

# Flags whose value is prose the caller wrote, not something the shell will run.
# A comment quoting a git rule documents it; it does not break it. The tripwire
# scan has had that exemption since it was written and the git checks did not,
# so the substrate could not state its own git rules through any tool that takes
# prose on the command line (#168).
#
# Long forms only, plus `-m`. Every short form is ambiguous, and dropping the
# token after one hides a ref: to gh, `-b` is the body; to git checkout it is
# the new branch. `-c` carries a whole command and `-d` a ref to delete.
_PROSE_FLAGS = {"-m", "--message", "--body", "--title", "--notes",
                "--description", "--reason"}

_FORCE_FLAGS = ("--force", "--force-with-lease", "--force-if-includes")

# Flags whose value is another command. `bash -c "..."` hides its payload from
# a token scan the same way `--body "..."` hid prose from a string scan; the
# difference is that this one runs. Expanded, not dropped.
_COMMAND_FLAGS = {"-c", "-lc", "-ic", "--command", "/c", "/C"}

# `git push` flags that consume the token after them.
_PUSH_VALUE_FLAGS = {"-o", "--push-option", "--receive-pack", "--exec", "--repo"}


def argv_tokens(cmd: str) -> list[str]:
    """Command tokens, with the values of prose-carrying flags dropped (#168).

    Unbalanced quotes fall back to a naive split rather than to allowing the
    call: the guard may read less, it never reads nothing.
    """
    try:
        toks = shlex.split(cmd)
    except ValueError:
        return cmd.split()
    out, skip = [], False
    for t in toks:
        if skip:
            skip = False
        elif t in _PROSE_FLAGS:
            skip = True
        elif "=" in t and t.split("=", 1)[0] in _PROSE_FLAGS:
            continue
        else:
            out.append(t)
    for i, t in enumerate(out[1:], 1):
        if out[i - 1] in _COMMAND_FLAGS:
            out += argv_tokens(t)
    return out


def pushes(toks: list[str]) -> bool:
    """These tokens run a git push - including as `git -c x=y push`, which the
    old adjacency regex did not match, so a `-c` in front smuggled a forced one
    past the check (#168)."""
    return "git" in toks and "push" in toks and toks.index("push") > toks.index("git")


def forces(toks: list[str]) -> bool:
    tail = toks[toks.index("push"):] if pushes(toks) else []
    return any(t == "-f" or t.startswith(_FORCE_FLAGS) for t in tail)


def push_targets(toks: list[str], branch: str) -> list[str]:
    """Every branch a `git push` in these tokens would write, as a bare name.

    The old parse read the *last* whitespace-separated token and, when that
    started with `-`, fell back to the checked-out branch. Four routes past it,
    all of which reach a protected branch (#168): a refspec delete, a flag
    delete, a renamed source, and any flag sitting before the remote.

    `*` means every branch — `--all` / `--mirror`. No refspec at all means the
    checked-out branch, which is what git itself pushes.
    """
    if "push" not in toks:
        return []
    rest = toks[toks.index("push") + 1:]
    positional, skip, everything = [], False, False
    for t in rest:
        if skip:
            skip = False
        elif t in _PUSH_VALUE_FLAGS:
            skip = True
        elif t in ("--all", "--mirror"):
            everything = True
        elif t.startswith("-"):
            continue
        else:
            positional.append(t)
    if everything:
        return ["*"]
    refspecs = positional[1:]          # positional[0] is the remote
    if not refspecs:
        return [branch]
    dests = []
    for spec in refspecs:
        dest = spec.split(":")[-1].lstrip("+")
        dests.append(dest.split("/")[-1] if dest.startswith("refs/") else dest)
    return dests


def _in_scope(path_hint: str, scope) -> bool:
    """A tripwire with `paths:` applies only there. path_hint None = no path
    context (a Bash command), where every tripwire applies."""
    if not scope or path_hint is None:
        return True
    norm = path_hint.replace("\\", "/")
    return any(norm.startswith(s.rstrip("/")) or norm.endswith(s) for s in scope)


def _tripwire(text: str, path_hint, cfg: dict):
    for tw in cfg.get("tripwires", []):
        if not _in_scope(path_hint, tw.get("paths")):
            continue
        if re.search(tw["pattern"], text):
            return f"tripwire {tw['name']}: {tw['why']}"
    return None


def check(tool_name: str, tool_input: dict, ctx: dict, cfg: dict) -> str | None:
    """Return a refusal reason, or None to allow. Pure — ctx carries git state."""
    branch = ctx.get("branch") or ""
    protected = cfg.get("protected_branches", [])

    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        # Every git check below reads argv, never the prose argv carries (#168).
        toks = argv_tokens(cmd)
        bare = " ".join(toks)

        # #122: a denied unattended session retried with the sandbox off. An
        # owner at a keyboard can still make that call; a pickup-loop launch
        # (which sets QOPS_UNATTENDED) cannot, because nobody is reading.
        if tool_input.get("dangerouslyDisableSandbox") and ctx.get("unattended"):
            return ("dangerouslyDisableSandbox is refused in an unattended run. "
                    "Report the blocked command on the issue instead.")

        if forces(toks):
            return "force-push is blocked. Rebase and push normally, or ask the owner."
        if _RESET_HARD.search(bare):
            return "git reset --hard discards uncommitted work. Use git stash or a soft reset."
        if _WORKTREE_ADD.search(bare) and ctx.get("worktrees", 0) >= cfg["max_worktrees"]:
            return (f"worktree sprawl: {ctx['worktrees']} already live, cap is "
                    f"{cfg['max_worktrees']}. Remove one first (git worktree remove).")
        write = _WRITES.search(bare)
        if pushes(toks):
            # a push naming another branch is fine even while master is out.
            # Read off the tokens, not `_WRITES`: `git -c x=y push` is a push
            # and the adjacency regex does not see it.
            for target in push_targets(toks, branch):
                if target == "*" and protected:
                    return (f"push --all/--mirror is blocked while "
                            f"{protected[0]} is protected. Open a PR.")
                if target in protected:
                    return f"push to {target} is blocked. Open a PR."
        elif write and branch in protected and not _BRANCHES_FIRST.search(bare):
            return (f"'{write.group(1)}' on {branch} is blocked — {branch} is "
                    f"protected. Branch first.")

        # A commit message that quotes a tripwire is describing the constraint,
        # not breaking it — same exemption the constraint docs get below.
        if not re.match(r"\s*git\s+(commit|log|show|notes)\b", cmd):
            hit = _tripwire(cmd, None, cfg)
            if hit:
                return hit
        return None

    if tool_name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path_hint = tool_input.get("file_path", "")
        norm = path_hint.replace("\\", "/")
        excluded = tuple(cfg.get("scan_exclude", []))
        # The files that state the constraints have to be able to name them.
        if excluded and any(norm.endswith(e) or f"/{e}" in norm for e in excluded):
            return None
        for field in _TEXT_FIELDS:
            value = tool_input.get(field)
            if isinstance(value, str):
                hit = _tripwire(value, path_hint, cfg)
                if hit:
                    return hit
        for edit in tool_input.get("edits", []) or []:
            hit = _tripwire(str(edit.get("new_string", "")), path_hint, cfg)
            if hit:
                return hit
    return None


def git_context(root: Path) -> dict:
    def run(*args):
        try:
            return subprocess.run(["git", *args], cwd=root, capture_output=True,
                                  text=True, timeout=10).stdout.strip()
        except Exception:
            return ""
    worktrees = len([l for l in run("worktree", "list").splitlines() if l.strip()])
    return {"branch": run("rev-parse", "--abbrev-ref", "HEAD"),
            "worktrees": max(worktrees - 1, 0),
            "unattended": os.environ.get("QOPS_UNATTENDED") == "1"}


# --- the CI half -----------------------------------------------------------

def scan(root: Path, cfg: dict) -> list[dict]:
    """Grep the tracked tree for tripwires. What guard.yml runs."""
    root = Path(root)
    hits = []
    files = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True,
                           text=True).stdout.split()
    if not files:
        files = [str(p.relative_to(root)) for p in root.rglob("*")
                 if p.is_file() and ".git" not in p.parts]
    excluded = tuple(cfg.get("scan_exclude", []))
    for tw in cfg.get("tripwires", []):
        rx = re.compile(tw["pattern"])
        for rel in files:
            norm = rel.replace("\\", "/")
            if excluded and norm.startswith(excluded):
                continue          # files that name the tripwires on purpose
            if not _in_scope(norm, tw.get("paths")):
                continue
            p = root / rel
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    hits.append({"file": norm, "line": n, "pattern": tw["pattern"],
                                 "name": tw["name"], "why": tw["why"]})
    return hits


# --- entry points ----------------------------------------------------------

def hook(root: Path, cfg: dict) -> int:
    """PreToolUse. Reads the payload on stdin; exit 2 blocks the call."""
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    reason = check(payload.get("tool_name", ""), payload.get("tool_input") or {},
                   git_context(root), cfg)
    if reason:
        print(f"qops guard: {reason}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str], root: Path, cfg: dict) -> int:
    if argv and argv[0] == "scan":
        hits = scan(root, cfg)
        for h in hits:
            print(f"{h['file']}:{h['line']}: {h['name']} — {h['why']}")
        if hits:
            print(f"\n{len(hits)} tripwire hit(s).", file=sys.stderr)
            return 1
        print("guard: no tripwires.")
        return 0
    return hook(root, cfg)
