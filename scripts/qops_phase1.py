#!/usr/bin/env python3
"""qops Phase 1 — import .qops/issues.md into GitHub Issues. IDEMPOTENT.

Creates (or reconciles) labels, milestones, epics and issues via `gh`. Safe to
re-run: every object is matched by a stable marker, so a second run updates
rather than duplicates. Nothing is ever deleted.

Order of operations:
  1. labels        — created if missing, left alone if present
  2. milestones    — Go-live, Post-launch
  3. epics         — so child issues can reference their number
  4. issues        — body gets an epic backlink; closed ones are closed after creation
  5. mapping       — .qops/issue-map.json  (GL-21 -> 47, ...)

Matching is by the hidden marker `<!-- qops:id=GL-21 -->` appended to each body,
searched via `gh issue list --search`. Titles can therefore be edited freely on
GitHub without breaking re-runs.

Usage
-----
    python scripts/qops_phase1.py                # dry run: show the plan
    python scripts/qops_phase1.py --execute      # create/reconcile
    python scripts/qops_phase1.py --only GL-21   # single issue, for testing
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / ".qops" / "issues.md"
MAP_FILE = REPO_ROOT / ".qops" / "issue-map.json"

OPEN_RE = re.compile(
    r"<!--qops\s+(?P<attrs>[^>]*?)-->\n(?P<body>.*?)\n<!--/qops-->",
    re.DOTALL,
)

LABELS: dict[str, tuple[str, str]] = {
    # name: (colour, description)
    "type:code":           ("1d76db", "Coding and implementation"),
    "type:research":       ("0e8a16", "Research producing findings"),
    "type:impl-research":  ("5319e7", "Implementation research: plan + code-session prompt"),
    "type:manual":         ("fbca04", "Manual action by the owner"),
    "type:test":           ("d93f0b", "Test run producing pass/fail"),
    "type:decision":       ("b60205", "Decision or sign-off only the owner can make"),
    "type:epic":           ("000000", "Mission: holds a fork tree and child issues"),
    "epic":                ("000000", "Mission-level issue"),
    "state:triage":        ("ededed", "Not yet planned"),
    "state:planned":       ("c2e0c6", "Planned, has acceptance criteria and a named gate"),
    "state:building":      ("bfd4f2", "Branch open, work in progress"),
    "state:gate":          ("fef2c0", "Awaiting machine gate"),
    "state:review":        ("f9d0c4", "Gate green, awaiting owner review"),
    "state:blocked":       ("e11d21", "Blocked on another issue or a decision"),
    "ready:auto":          ("0052cc", "Eligible for unattended pickup (branch+PR only)"),
    "fork":                ("d4c5f9", "Contains a decision point"),
    "budget:approved":     ("006b75", "Paid API spend authorised for this issue"),
    "go-live-blocker":     ("b60205", "Blocks the public launch"),
    "mission:mockups":     ("c5def5", "Custom mockup track"),
    "mission:automation":  ("c5def5", "Unattended operation track"),
    "mission:launch-prep": ("c5def5", "Manual launch-prep track"),
}

MILESTONES = {
    "Go-live": "Everything gating the public launch",
    "Post-launch": "Deliberately deferred until after launch",
}


def gh(*args: str, check: bool = True, stdin: str | None = None) -> str:
    r = subprocess.run(
        ["gh", *args], capture_output=True, text=True, input=stdin, errors="replace"
    )
    if check and r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])}... failed:\n{r.stderr.strip()}")
    return r.stdout.strip()


def parse_source() -> list[dict]:
    if not SOURCE.exists():
        sys.exit(f"! {SOURCE} not found")
    text = SOURCE.read_text(encoding="utf-8")
    items: list[dict] = []
    for m in OPEN_RE.finditer(text):
        attrs = dict(
            kv.split("=", 1) for kv in m.group("attrs").split() if "=" in kv
        )
        body = m.group("body").strip()
        first = body.splitlines()[0]
        title = first.lstrip("# ").strip()
        labels = [l for l in attrs.get("labels", "").split(",") if l]
        if attrs.get("type"):
            labels.append(f"type:{attrs['type']}")
        items.append({
            "id": attrs["id"],
            "state": attrs.get("state", "open"),
            "milestone": attrs.get("milestone"),
            "labels": sorted(set(labels)),
            "title": title,
            "body": body,
            "is_epic": attrs.get("type") == "epic",
        })
    return items


def marker(qid: str) -> str:
    return f"<!-- qops:id={qid} -->"


def find_existing(qid: str) -> int | None:
    out = gh("issue", "list", "--state", "all", "--limit", "200",
             "--search", f'"qops:id={qid}"', "--json", "number,body", check=False)
    try:
        for row in json.loads(out or "[]"):
            if marker(qid) in (row.get("body") or ""):
                return row["number"]
    except json.JSONDecodeError:
        pass
    return None


def ensure_labels(execute: bool) -> None:
    existing = set()
    out = gh("label", "list", "--limit", "200", "--json", "name", check=False)
    try:
        existing = {r["name"] for r in json.loads(out or "[]")}
    except json.JSONDecodeError:
        pass
    for name, (colour, desc) in LABELS.items():
        if name in existing:
            continue
        if execute:
            gh("label", "create", name, "--color", colour, "--description", desc,
               check=False)
            print(f"    + label {name}")
        else:
            print(f"    ~ would create label {name}")


def ensure_milestones(execute: bool) -> None:
    out = gh("api", "repos/{owner}/{repo}/milestones?state=all", check=False)
    try:
        existing = {m["title"] for m in json.loads(out or "[]")}
    except json.JSONDecodeError:
        existing = set()
    for title, desc in MILESTONES.items():
        if title in existing:
            continue
        if execute:
            gh("api", "repos/{owner}/{repo}/milestones", "-f", f"title={title}",
               "-f", f"description={desc}", check=False)
            print(f"    + milestone {title}")
        else:
            print(f"    ~ would create milestone {title}")


def upsert(item: dict, epic_numbers: dict[str, int], execute: bool) -> int | None:
    qid = item["id"]
    body = item["body"]
    epic = EPIC_OF.get(qid)
    if epic and epic in epic_numbers:
        body += f"\n\n---\nMission: #{epic_numbers[epic]}"
    body += f"\n\n{marker(qid)}"

    number = find_existing(qid)
    if number:
        if execute:
            gh("issue", "edit", str(number), "--body-file", "-", stdin=body)
            print(f"    = #{number} {qid} (body reconciled)")
        else:
            print(f"    ~ would reconcile existing #{number} {qid}")
        return number

    if not execute:
        print(f"    ~ would create {qid}: {item['title'][:58]}")
        return None

    args = ["issue", "create", "--title", item["title"], "--body-file", "-"]
    for l in item["labels"]:
        args += ["--label", l]
    if item["milestone"]:
        args += ["--milestone", item["milestone"]]
    url = gh(*args, stdin=body)
    number = int(url.rstrip("/").split("/")[-1])
    print(f"    + #{number} {qid}: {item['title'][:52]}")

    if item["state"] == "closed":
        gh("issue", "close", str(number),
           "--comment", "Imported as already-resolved by qops Phase 1.", check=False)
        print(f"      closed (was resolved before the migration)")
    return number


# Which epic each issue hangs off. Kept here rather than in the source file so
# the source stays readable; both are hand-maintained exactly once.
EPIC_OF = {
    "GL-1": "EPIC-mockups", "GL-2": "EPIC-mockups", "GL-4": "EPIC-mockups",
    "GL-5": "EPIC-mockups", "GL-6": "EPIC-mockups", "GL-13": "EPIC-mockups",
    "GL-14": "EPIC-mockups", "GL-17": "EPIC-mockups", "GL-18": "EPIC-mockups",
    "GL-19": "EPIC-mockups", "GL-20": "EPIC-mockups", "GL-21": "EPIC-mockups",
    "BL-3": "EPIC-mockups",
    "GL-3": "EPIC-automation", "GL-7": "EPIC-automation", "GL-8": "EPIC-automation",
    "GL-9": "EPIC-automation", "GL-15": "EPIC-automation", "GL-16": "EPIC-automation",
    "GL-10": "EPIC-launch", "GL-11": "EPIC-launch", "GL-12": "EPIC-launch",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--only", help="import a single id, e.g. GL-21")
    args = ap.parse_args()

    if subprocess.run(["gh", "auth", "status"], capture_output=True).returncode != 0:
        sys.exit("! gh is not authenticated — run `gh auth login`")

    items = parse_source()
    if args.only:
        items = [i for i in items if i["id"] == args.only]
        if not items:
            sys.exit(f"! no issue with id {args.only}")

    print("=" * 72)
    print(f"qops Phase 1 — {'EXECUTE' if args.execute else 'DRY RUN'} "
          f"({len(items)} issues from .qops/issues.md)")
    print("=" * 72)

    print("\n[1/4] Labels")
    ensure_labels(args.execute)
    print("\n[2/4] Milestones")
    ensure_milestones(args.execute)

    epic_numbers: dict[str, int] = {}
    print("\n[3/4] Epics")
    for item in [i for i in items if i["is_epic"]]:
        n = upsert(item, epic_numbers, args.execute)
        if n:
            epic_numbers[item["id"]] = n

    print("\n[4/4] Issues")
    mapping: dict[str, int] = dict(epic_numbers)
    for item in [i for i in items if not i["is_epic"]]:
        n = upsert(item, epic_numbers, args.execute)
        if n:
            mapping[item["id"]] = n

    if args.execute and mapping:
        MAP_FILE.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
        print(f"\n  wrote {MAP_FILE.relative_to(REPO_ROOT)} ({len(mapping)} entries)")

    print("\n" + "=" * 72)
    n_open = sum(1 for i in items if i["state"] == "open")
    print(f"{n_open} open / {len(items) - n_open} closed-on-import.")
    if not args.execute:
        print("Re-run with --execute. Safe to run repeatedly — matching is by")
        print("the hidden qops:id marker, so nothing duplicates.")
    else:
        print("Next: spot-check 5 issues against the plan doc, then mark it superseded.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
