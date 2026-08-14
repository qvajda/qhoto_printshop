"""pickup-loop — pick the next sortie an unattended agent may start.

Default OFF. Registered as a disabled Windows scheduled task (`qops-pickup-loop`)
so that turning it on is one `schtasks /change /enable` and not a build.

Eligibility is deliberately narrow, and every condition is the owner's to grant:

    state:planned  AND  ready:auto  AND  NOT no-auto  AND  gate: is not none

`ready:auto` is never applied by the triager (see .claude/agents/triager.md) —
only the owner grants it. `gate:none` blocks pickup because a sortie with no
named gate has no definition of done.

`--launch` is what actually starts an agent. Without it this prints what it
would have picked and exits 0, which is also how the scheduled task is proved
to run without starting anything.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qops import config as qconfig, ledger  # noqa: E402

BLOCKING_FLAGS = {"no-auto", "blocked"}


def eligible(issue: dict) -> bool:
    labels = {l["name"] for l in issue.get("labels", [])}
    if "state:planned" not in labels or "ready:auto" not in labels:
        return False
    if labels & BLOCKING_FLAGS:
        return False
    return "gate:none" not in labels and any(l.startswith("gate:") for l in labels)


def candidates(root: Path) -> list[dict]:
    out = subprocess.run(
        ["gh", "issue", "list", "--state", "open", "--limit", "100",
         "--json", "number,title,labels,updatedAt"],
        cwd=root, capture_output=True, text=True)
    if out.returncode:
        print(out.stderr.strip(), file=sys.stderr)
        return []
    return [i for i in json.loads(out.stdout or "[]") if eligible(i)]


def main(argv: list[str]) -> int:
    root = ROOT
    cfg = qconfig.load(root)
    picks = candidates(root)
    if not picks:
        print("pickup-loop: nothing eligible (state:planned + ready:auto + a real gate).")
        return 0
    issue = sorted(picks, key=lambda i: i["updatedAt"])[0]
    print(f"pickup-loop: #{issue['number']} {issue['title']}")
    if "--launch" not in argv:
        print("pickup-loop: dry run, not launching. Pass --launch to start an agent.")
        return 0
    # Claim it BEFORE launching. Without this the next hourly fire picks the
    # same issue again - the run does not change the issue, so it stays the
    # least-recently-updated eligible one forever, one session per hour.
    num = str(issue["number"])
    claim = subprocess.run(["gh", "issue", "edit", num,
                            "--remove-label", "state:planned",
                            "--add-label", "state:building"],
                           cwd=root, capture_output=True, text=True)
    if claim.returncode:
        print(f"pickup-loop: could not claim #{num}, not launching: "
              f"{claim.stderr.strip()}", file=sys.stderr)
        return 1
    ledger.append(root, "pickup", {"issue": num})
    prompt = (f"Work sortie #{issue['number']} to its stated acceptance criteria. "
              f"Branch first, commit, open a PR, request review. Do not merge.")
    return subprocess.run(["claude", "-p", prompt], cwd=root).returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
