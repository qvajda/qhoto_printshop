#!/usr/bin/env python3
"""qops Phase 0 — freeze and inventory. NON-DESTRUCTIVE BY DESIGN.

What it does (and all it does):
  1. Tags every local branch tip as pre-qops-<date>-<branch>  (a safety net, so
     that Phase 4's branch deletion is reversible).
  2. Pushes the branches that carry unmerged work absent from origin, plus all
     tags created above.
  3. Scans every text blob that has *ever* existed in git history for credential
     patterns. The repo is public, so this is the point of Phase 0.
  4. Emits branch metadata for the inventory doc.

What it deliberately does NOT do: delete a branch, delete a worktree, rewrite
history, or touch the working tree. Deletion is Phase 4 and needs its own
explicit go-ahead.

Written in Python rather than bash so it runs the same under Windows Claude Code
as anywhere else — no git-bash dependency.

Usage
-----
    python scripts/qops_phase0.py              # dry run: report only, no writes
    python scripts/qops_phase0.py --execute    # create tags + push
    python scripts/qops_phase0.py --scan-only  # just the secret scan
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date

TAG_PREFIX = f"pre-qops-{date.today().isoformat()}"

# Branches carrying unmerged work that is absent from origin (verified 2026-07-26).
# Recomputed at runtime; this list is only the expected answer, for drift detection.
EXPECTED_AT_RISK = {
    "feat/gl6-scene-library",
    "proto/mockup-scene-prototype",
    "feat/gl5-mockup-compositor",
}

# Credential shapes relevant to this project. Deliberately narrow: a scan that
# cries wolf gets ignored, which is worse than no scan.
SECRET_PATTERNS: list[tuple[str, str]] = [
    ("Anthropic API key", r"sk-ant-[A-Za-z0-9\-_]{20,}"),
    ("Replicate token", r"\br8_[A-Za-z0-9]{30,}\b"),
    ("Telegram bot token", r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
    ("OpenAI-style key", r"\bsk-[A-Za-z0-9]{32,}\b"),
    ("AWS/R2 access key id", r"\bAKIA[0-9A-Z]{16}\b"),
    ("Etsy keystring assignment", r"(?i)etsy[_a-z]*(key|secret|token)\s*[=:]\s*['\"][A-Za-z0-9]{16,}"),
    ("Gelato key assignment", r"(?i)gelato[_a-z]*(key|secret|token)\s*[=:]\s*['\"][A-Za-z0-9\-]{16,}"),
    ("Cloudflare R2 secret", r"(?i)r2[_a-z]*secret[_a-z]*\s*[=:]\s*['\"][A-Za-z0-9/+]{32,}"),
    ("Generic bearer token", r"(?i)authorization['\"]?\s*[=:]\s*['\"]bearer\s+[A-Za-z0-9\-._~+/]{24,}"),
    ("Private key block", r"-----BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
]

# Known-benign matches. A scan that cries wolf gets ignored, which is worse than
# no scan at all — so every false positive found in practice gets pinned here
# with the reason, rather than the pattern being loosened.
ALLOWLIST_LITERALS = {
    # The canonical AWS documentation example key. Appears in test fixtures.
    "AKIAIOSFODNN7EXAMPLE",
}

# If the match is preceded (within 40 chars) by one of these, it is not our
# secret. Presigned S3 URLs embed the *vendor's* access key id, which is an
# identifier rather than a credential — the signature is what grants access, and
# it carries its own expiry.
ALLOWLIST_CONTEXT = [
    re.compile(r"X-Amz-Credential="),
    re.compile(r"(?i)example|dummy|fixture|placeholder|redacted"),
]

# Paths that should never appear as a blob in history at all.
FORBIDDEN_PATHS = re.compile(r"(^|/)\.env($|\.)(?!example)|(^|/)\.env$|\.pem$|\.p12$|id_rsa$")

TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".cfg", ".ini",
    ".sh", ".ps1", ".bat", ".env", ".example", ".csv", ".tsv", ".sql", ".html",
    ".js", ".ts", ".gitattributes", ".gitignore", "",
}


def git(*args: str, check: bool = True) -> str:
    r = subprocess.run(
        ["git", *args], capture_output=True, text=True, errors="replace"
    )
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{r.stderr.strip()}")
    return r.stdout


def local_branches() -> list[str]:
    return [b for b in git("branch", "--format=%(refname:short)").split() if b]


def merged_into_master() -> set[str]:
    out = git("branch", "--merged", "master", "--format=%(refname:short)")
    return {b for b in out.split() if b and b != "master"}


def on_origin(branch: str) -> bool:
    r = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--heads", "origin", branch],
        capture_output=True, text=True,
    )
    return r.returncode == 0


def ahead_of_master(branch: str) -> int:
    return int(git("rev-list", "--count", f"master..{branch}").strip() or 0)


def unpushed_commits(branch: str) -> int:
    """Commits on the local branch not present on origin/<branch>."""
    remote = f"origin/{branch}"
    if subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", remote],
        capture_output=True,
    ).returncode != 0:
        return ahead_of_master(branch)
    return int(git("rev-list", "--count", f"{remote}..{branch}").strip() or 0)


def tag_name(branch: str) -> str:
    return f"{TAG_PREFIX}-{branch.replace('/', '-')}"


def check_max_tokens_on_master() -> tuple[bool, str]:
    """proto/mockup-scene-prototype's only possibly-unique change is the
    Anthropic max_tokens 1024->2048 bump. The plan doc says it already landed on
    master; the inventory's 'retire this branch' call depends on that being true,
    so verify rather than trust.
    """
    hits = []
    for path in ("pipeline/compliance_draft.py", "pipeline/critic_pass.py"):
        try:
            body = git("show", f"master:{path}")
        except RuntimeError:
            return False, f"{path} not found on master"
        for m in re.finditer(r"max_tokens\s*[=:]\s*(\d+)", body):
            hits.append((path, int(m.group(1))))
    if not hits:
        return False, "no max_tokens setting found in either module on master"
    low = [f"{p}={v}" for p, v in hits if v <= 1024]
    summary = ", ".join(f"{p.split('/')[-1]}={v}" for p, v in hits)
    if low:
        return False, f"still at or below 1024: {', '.join(low)}  (all: {summary})"
    return True, summary


# --------------------------------------------------------------------------- #
# Secret scan
# --------------------------------------------------------------------------- #

def iter_history_blobs() -> dict[str, set[str]]:
    """Every blob that ever existed -> the set of paths it appeared under.

    Deduplicated by blob SHA, so a file touched 50 times is scanned once.
    """
    out = git("rev-list", "--objects", "--all")
    blobs: dict[str, set[str]] = defaultdict(set)
    for line in out.splitlines():
        parts = line.split(" ", 1)
        if len(parts) != 2:
            continue  # commit/tree entries have no path
        sha, path = parts
        blobs[sha].add(path)
    return blobs


def looks_textual(paths: set[str]) -> bool:
    for p in paths:
        name = p.rsplit("/", 1)[-1]
        suffix = ("." + name.rsplit(".", 1)[-1]) if "." in name else ""
        if suffix.lower() in TEXT_SUFFIXES or name.startswith("."):
            return True
    return False


def scan_history() -> tuple[list[str], list[str]]:
    findings: list[str] = []
    path_hits: list[str] = []

    blobs = iter_history_blobs()
    candidates = {sha: paths for sha, paths in blobs.items() if looks_textual(paths)}

    for paths in blobs.values():
        for p in paths:
            if FORBIDDEN_PATHS.search(p):
                path_hits.append(p)

    print(f"  scanning {len(candidates)} unique text blobs "
          f"(of {len(blobs)} total objects in history)...")

    compiled = [(label, re.compile(pat)) for label, pat in SECRET_PATTERNS]
    batch = "\n".join(candidates) + "\n"
    proc = subprocess.run(
        ["git", "cat-file", "--batch"],
        input=batch, capture_output=True, text=True, errors="replace",
    )

    # Parse the --batch stream: "<sha> blob <size>\n<contents>\n"
    stream = proc.stdout
    pos = 0
    while pos < len(stream):
        nl = stream.find("\n", pos)
        if nl == -1:
            break
        header = stream[pos:nl]
        bits = header.split()
        if len(bits) != 3 or bits[1] != "blob":
            pos = nl + 1
            continue
        sha, size = bits[0], int(bits[2])
        body = stream[nl + 1: nl + 1 + size]
        pos = nl + 1 + size + 1
        for label, rx in compiled:
            for m in rx.finditer(body):
                if _allowlisted(m, body):
                    continue
                where = ", ".join(sorted(candidates.get(sha, {"?"})))
                snippet = m.group(0)[:12] + "..."
                findings.append(f"{label}: blob {sha[:10]} at {where} ({snippet})")
                break  # one report per pattern per blob is enough

    return findings, sorted(set(path_hits))


def _allowlisted(m: re.Match[str], body: str) -> bool:
    if m.group(0) in ALLOWLIST_LITERALS:
        return True
    lead = body[max(0, m.start() - 40): m.start()]
    return any(rx.search(lead) for rx in ALLOWLIST_CONTEXT)


# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true",
                    help="actually create tags and push (default is dry run)")
    ap.add_argument("--scan-only", action="store_true",
                    help="run the credential scan and nothing else")
    args = ap.parse_args()

    if git("rev-parse", "--abbrev-ref", "HEAD").strip() == "HEAD":
        print("! detached HEAD — check out a branch first", file=sys.stderr)
        return 2

    print("=" * 72)
    print(f"qops Phase 0 — {'EXECUTE' if args.execute else 'DRY RUN'}  ({TAG_PREFIX})")
    print("=" * 72)

    if not args.scan_only:
        print("\n[1/4] Branch classification")
        merged = merged_into_master()
        branches = local_branches()
        unmerged = [b for b in branches if b not in merged and b != "master"]

        print(f"  merged into master (Phase 4 delete candidates): {len(merged)}")
        for b in sorted(merged):
            print(f"    - {b}")
        print(f"  unmerged (keep for now): {len(unmerged)}")
        at_risk = []
        for b in sorted(unmerged):
            n = unpushed_commits(b)
            flag = ""
            if n:
                at_risk.append(b)
                flag = f"  <-- {n} commit(s) not on origin"
            print(f"    - {b} | +{ahead_of_master(b)} vs master | "
                  f"origin:{'yes' if on_origin(b) else 'NO'}{flag}")

        drift = set(at_risk) ^ (EXPECTED_AT_RISK & set(unmerged))
        if drift:
            print(f"  ! drift vs the PRD's expectation: {sorted(drift)}")
            print("    (not an error — the repo moved. Update the inventory doc.)")

        if "proto/mockup-scene-prototype" in unmerged:
            ok, detail = check_max_tokens_on_master()
            verdict = "PRESENT on master" if ok else "NOT confirmed"
            print(f"\n  proto/mockup-scene-prototype retirement precondition:")
            print(f"    max_tokens fix: {verdict} — {detail}")
            if not ok:
                print("    -> cherry-pick that one commit onto a GL-issue branch")
                print("       BEFORE retiring the branch in Phase 4.")

        print(f"\n[2/4] Safety tags at every branch tip ({len(branches)} branches)")
        for b in branches:
            t = tag_name(b)
            exists = subprocess.run(
                ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{t}"],
                capture_output=True,
            ).returncode == 0
            if exists:
                print(f"    = {t} (already exists)")
            elif args.execute:
                git("tag", t, b)
                print(f"    + {t}")
            else:
                print(f"    ~ would tag {t} -> {b}")

        print(f"\n[3/4] Push at-risk branches + all safety tags")
        if not at_risk:
            print("    nothing at risk — every branch is on origin")
        for b in at_risk:
            if args.execute:
                git("push", "-u", "origin", b)
                print(f"    + pushed {b}")
            else:
                print(f"    ~ would push {b}")
        if args.execute:
            git("push", "origin", "--tags")
            print("    + pushed tags")
        else:
            print("    ~ would push tags")

    print("\n[4/4] Credential scan over ALL git history (repo is PUBLIC)")
    findings, path_hits = scan_history()
    if path_hits:
        print("  ! files that should never have been committed:")
        for p in path_hits:
            print(f"      {p}")
    if findings:
        print(f"  ! {len(findings)} possible credential(s) in history:")
        for f in findings:
            print(f"      {f}")
        print("\n  ACTION: rotate the credential FIRST. History rewriting is a")
        print("  separate decision — do not run filter-repo on impulse.")
    if not findings and not path_hits:
        print("  clean — no credential patterns and no forbidden paths in history")

    print("\n" + "=" * 72)
    print("Phase 0 complete. Nothing was deleted; deletion is Phase 4.")
    if not args.execute and not args.scan_only:
        print("Re-run with --execute to create tags and push.")
    print("=" * 72)
    return 1 if (findings or path_hits) else 0


if __name__ == "__main__":
    sys.exit(main())
