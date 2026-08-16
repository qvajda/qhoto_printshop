"""`qops install` renders .github/workflows from templates + .qops/config.yml;
`qops doctor` detects drift between what is on disk and what the config says.

A workflow nobody may hand-edit is the point: the CLAUDE.md line cap and the
tripwire list live in config, and the workflow is a rendering of them.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

TEMPLATES = Path(__file__).parent / "templates"
WORKFLOWS = ("test.yml", "gate.yml", "guard.yml", "digest.yml", "groom.yml",
             "automerge.yml")

_DOC_LINK = re.compile(r"docs/[A-Za-z0-9_./-]+\.md")


def context(cfg: dict) -> dict:
    ci = cfg.get("ci", {})
    return {
        "project": cfg["project"],
        "repo": cfg.get("repo", ""),
        "default_branch": cfg.get("default_branch", "master"),
        "python_version": ci.get("python_version", "3.12"),
        "test_command": ci.get("test_command", "python -m pytest -q"),
        "gate_command": ci.get("gate_command", "python -m pytest -q"),
        "runs_on": ci.get("runs_on", "ubuntu-latest"),
        "digest_cron": ci.get("digest_cron", "0 6 * * *"),
        "groom_cron": ci.get("groom_cron", "0 5 * * 1"),
        "status_issue_label": ci.get("status_issue_label", "qops:status"),
        "claude_md_max_lines": str(cfg["claude_md_max_lines"]),
    }


def render_one(name: str, cfg: dict) -> str:
    text = (TEMPLATES / (name + ".tmpl")).read_text(encoding="utf-8")
    for key, value in context(cfg).items():
        text = text.replace("{{" + key + "}}", str(value))
    left = re.search(r"\{\{(\w+)\}\}", text)
    if left:
        raise KeyError(f"{name}: no config value for {{{{{left.group(1)}}}}}")
    return text


def render_all(root: Path, cfg: dict) -> list[str]:
    out = Path(root) / ".github" / "workflows"
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name in WORKFLOWS:
        p = out / name
        p.write_text(render_one(name, cfg), encoding="utf-8", newline="\n")
        written.append(str(p))
    return written


def drift(root: Path, cfg: dict) -> list[str]:
    problems = []
    for name in WORKFLOWS:
        p = Path(root) / ".github" / "workflows" / name
        if not p.exists():
            problems.append(f"{name}: missing — run `qops install`")
            continue
        if p.read_text(encoding="utf-8").replace("\r\n", "\n") != render_one(name, cfg):
            problems.append(f"{name}: hand-edited — edit .qops/config.yml or the "
                            f"template, then `qops install`")
    return problems


def broken_doc_links(root: Path) -> list[str]:
    """Every docs/*.md path cited from code must resolve (PRD §7 Phase 4).

    Phase 3 broke 13 of 15 by archiving 89 docs. Only a check caught it.
    """
    root = Path(root)
    cfg_roots = ["pipeline", "scripts", "tests"]
    try:
        from . import config as qconfig
        cfg_roots = qconfig.load(root).get("doc_link_roots", cfg_roots)
    except Exception:
        pass
    missing = []
    for tree in cfg_roots:
        for p in (root / tree).rglob("*.py"):
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for cited in set(_DOC_LINK.findall(text)):
                if not (root / cited).exists():
                    missing.append(f"{p.relative_to(root)} -> {cited}")
    return sorted(missing)


def skill_drift(root: Path, cfg: dict) -> list[str]:
    """The installed skill set equals the declared one (ADR-0018).

    ADR-0013 named the count as its mitigation and asked a human to re-read it.
    Nobody did, and 11 accepted skills became 19 installed. So it is a check.

    A MISSING external is not a problem: they are gitignored, reinstallable
    copies, so a fresh checkout (CI) legitimately has none. An EXTRA is - that
    is the drift that actually happened. The natives are tracked source and
    must be there.
    """
    root, problems = Path(root), []
    declared = cfg.get("skills") or {}
    native = set(declared.get("native", []))
    external = set(declared.get("external", []))
    if not native and not external:
        return ["`.qops/config.yml` declares no `skills:` set — ADR-0018"]

    skills_dir = root / ".claude" / "skills"
    installed = {p.name for p in skills_dir.iterdir() if p.is_dir()} \
        if skills_dir.is_dir() else set()
    for extra in sorted(installed - native - external):
        problems.append(f"skill `{extra}` is installed and not declared in "
                        f".qops/config.yml — uninstall it or declare it")
    for missing in sorted(native - installed):
        problems.append(f"native skill `{missing}` is declared and missing "
                        f"from .claude/skills/")

    lock_path = root / "skills-lock.json"
    if not lock_path.exists():
        return problems + ["skills-lock.json missing"]
    lock = json.loads(lock_path.read_text(encoding="utf-8")).get("skills", {})
    for name in sorted(external - set(lock)):
        problems.append(f"external skill `{name}` is declared and absent from "
                        f"skills-lock.json")
    for name in sorted(set(lock) - external):
        problems.append(f"skills-lock.json pins `{name}`, which is not in the "
                        f"declared external set")
    for name, entry in sorted(lock.items()):
        if not entry.get("ref"):
            problems.append(f"skills-lock.json: `{name}` has no upstream ref — "
                            f"drift against it cannot be detected (ADR-0018)")
    return problems


def doctor(root: Path, cfg: dict) -> list[str]:
    problems = drift(root, cfg)
    problems += skill_drift(root, cfg)
    problems += [f"broken doc citation: {m}" for m in broken_doc_links(root)]
    settings = Path(root) / ".claude" / "settings.json"
    if not settings.exists():
        problems.append(".claude/settings.json missing — hooks are not installed")
    elif "qops" not in settings.read_text(encoding="utf-8"):
        problems.append(".claude/settings.json does not invoke qops")
    n = len((Path(root) / "CLAUDE.md").read_text(encoding="utf-8").splitlines())
    if n > cfg["claude_md_max_lines"]:
        problems.append(f"CLAUDE.md is {n} lines, cap is {cfg['claude_md_max_lines']}")
    return problems


def main(argv: list[str], root: Path, cfg: dict) -> int:
    written = render_all(root, cfg)
    for p in written:
        print(f"rendered {Path(p).relative_to(Path(root))}")
    return 0


def doctor_main(argv: list[str], root: Path, cfg: dict) -> int:
    problems = doctor(root, cfg)
    for p in problems:
        print(p, file=sys.stderr)
    if problems:
        print(f"\n{len(problems)} problem(s).", file=sys.stderr)
        return 1
    print("doctor: clean.")
    return 0
