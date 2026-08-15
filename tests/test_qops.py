"""qops substrate — the assertions that make the rules real.

CLAUDE.md's own convention: an instruction in a prompt is a preference, not a
control (GL-53). Every rule qops states in a workflow, a hook or a prompt has an
assertion here.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from qops import config as qconfig  # noqa: E402
from qops import guard, install, ledger, metrics, brief as briefmod  # noqa: E402


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------

def test_config_carries_every_project_specific():
    cfg = qconfig.load(REPO)
    for key in (
        "project", "python", "protected_branches", "max_worktrees",
        "tripwires", "claude_md_max_lines", "ci", "agents", "labels",
    ):
        assert key in cfg, f"{key} missing from .qops/config.yml"
    assert cfg["claude_md_max_lines"] == 150
    assert "master" in cfg["protected_branches"]


# --------------------------------------------------------------------------
# guard — the hard blocks. ADR-0001: PreToolUse exit 2 blocks for real.
# --------------------------------------------------------------------------

CTX = {"branch": "master", "worktrees": 1}
FEATURE = {"branch": "gl-63-thing", "worktrees": 1}


@pytest.mark.parametrize("command", [
    "git commit -m 'x'",
    "git commit --amend --no-edit",
    "git push origin master",
    "git push",
])
def test_guard_blocks_writes_to_master(command):
    assert guard.check("Bash", {"command": command}, CTX, qconfig.load(REPO))


@pytest.mark.parametrize("command", [
    "git push --force origin gl-63",
    "git push -f origin gl-63",
    "git push --force-with-lease origin gl-63",
    "git reset --hard HEAD~1",
])
def test_guard_blocks_destructive_git(command):
    assert guard.check("Bash", {"command": command}, FEATURE, qconfig.load(REPO))


def test_guard_blocks_worktree_sprawl():
    cfg = qconfig.load(REPO)
    over = dict(FEATURE, worktrees=cfg["max_worktrees"])
    assert guard.check("Bash", {"command": "git worktree add ../wt"}, over, cfg)
    under = dict(FEATURE, worktrees=0)
    assert guard.check("Bash", {"command": "git worktree add ../wt"}, under, cfg) is None


@pytest.mark.parametrize("payload", [
    ("Bash", {"command": "python -c \"etsy_client.create_draft_listing()\""}),
    ("Write", {"file_path": "pipeline/x.py", "content": "resp = create_draft_listing(x)"}),
    ("Edit", {"file_path": "pipeline/generate.py", "new_string": 'MODEL = "FLUX.1 [dev]"'}),
    ("Write", {"file_path": "config/static_config.json",
               "content": '{"template_id": "PLACEHOLDER_PORTRAIT"}'}),
])
def test_guard_blocks_project_tripwires(payload):
    tool, inp = payload
    reason = guard.check(tool, inp, FEATURE, qconfig.load(REPO))
    assert reason, f"{tool} {inp} should have tripped a tripwire"


def test_guard_lets_a_commit_message_quote_a_tripwire():
    cmd = "git commit -m 'never substitute FLUX.1 [dev]'"
    assert guard.check("Bash", {"command": cmd}, FEATURE, qconfig.load(REPO)) is None
    # ...but a write of the same string is still blocked
    assert guard.check("Bash", {"command": "echo 'FLUX.1 [dev]' >> pipeline/x.py"},
                       FEATURE, qconfig.load(REPO))


def test_guard_lets_the_constraint_docs_name_the_tripwires():
    """CLAUDE.md states the FLUX.1 [dev] prohibition; writing it must not be
    blocked by the tripwire that enforces it."""
    inp = {"file_path": "CLAUDE.md", "content": "Never substitute FLUX.1 [dev]."}
    assert guard.check("Write", inp, FEATURE, qconfig.load(REPO)) is None


@pytest.mark.parametrize("command", [
    "git commit -m 'x'",          # on a feature branch, fine
    "git push origin gl-63-thing",
    "python -m pytest -q",
    "git status --short",
    "git reset HEAD~1",           # soft reset is not the blocked one
])
def test_guard_allows_ordinary_work(command):
    assert guard.check("Bash", {"command": command}, FEATURE, qconfig.load(REPO)) is None


def test_guard_reasons_are_ascii():
    """Blocked-call reasons go to a Windows console via the hook."""
    for tw in qconfig.load(REPO)["tripwires"]:
        tw["why"].encode("ascii")


def test_guard_scan_is_clean_on_this_repo():
    """The tripwire scan guard.yml runs. Green today; it is a regression alarm."""
    hits = guard.scan(REPO, qconfig.load(REPO))
    assert hits == [], f"tripwires present: {hits}"


def test_guard_scan_catches_a_planted_string(tmp_path):
    (tmp_path / "pipeline").mkdir()
    (tmp_path / "pipeline" / "generate.py").write_text('m = "FLUX.1 [dev]"\n')
    hits = guard.scan(tmp_path, qconfig.load(REPO))
    assert any("FLUX" in h["pattern"] for h in hits)


# --------------------------------------------------------------------------
# ledger + resume
# --------------------------------------------------------------------------

def test_ledger_appends_one_json_object_per_line(tmp_path):
    ledger.append(tmp_path, "session_start", {"branch": "master"})
    ledger.append(tmp_path, "stop", {"reads": 3})
    lines = (tmp_path / ".qops" / "ledger.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2
    rec = json.loads(lines[0])
    assert rec["event"] == "session_start" and rec["branch"] == "master" and rec["ts"]


def test_resume_is_written_from_the_ledger(tmp_path):
    ledger.append(tmp_path, "session_start", {"branch": "gl-63", "cwd": str(tmp_path)})
    ledger.append(tmp_path, "note", {"text": "picked up GL-63"})
    text = ledger.write_resume(tmp_path)
    assert "GL-63" in text or "gl-63" in text
    assert (tmp_path / ".qops" / "resume.md").exists()


# --------------------------------------------------------------------------
# brief — the two contracts
# --------------------------------------------------------------------------

def test_brief_never_exceeds_400_tokens():
    text = briefmod.render(REPO, qconfig.load(REPO))
    assert briefmod.tokens(text) <= 400, f"brief is {briefmod.tokens(text)} tokens"


def test_brief_is_ascii():
    """It is written to a Windows console by a hook; a dash became U+FFFD."""
    text = briefmod.render(REPO, qconfig.load(REPO))
    text.encode("ascii")


def test_brief_reports_dotted_paths_intact():
    """`git status --porcelain`'s first line starts with a space; stripping it
    took the first character of the path with it."""
    state = briefmod.collect(REPO, qconfig.load(REPO))
    assert not any(p.startswith("qops/config.yml") for p in state["dirty"])


def test_brief_leads_with_a_dirty_tree_violation():
    state = {"branch": "master", "dirty": ["pipeline/x.py", "notes/y.txt"],
             "worktrees": 1, "issue": None, "resume": "", "ahead": 0}
    text = briefmod.render_from(state, qconfig.load(REPO))
    first = [ln for ln in text.splitlines() if ln.strip()][0]
    assert "dirty" in first.lower(), f"first line was: {first}"


def test_brief_is_quiet_when_the_tree_is_clean():
    state = {"branch": "gl-63", "dirty": [], "worktrees": 1, "issue": None,
             "resume": "", "ahead": 0}
    text = briefmod.render_from(state, qconfig.load(REPO))
    assert "dirty" not in text.lower().splitlines()[0]


# --------------------------------------------------------------------------
# brief — the routing verdict (ADR-0017)
#
# The rule decides how much of the owner's time an issue may spend. In a skill
# body it is a preference; here it is read unasked, every session.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("labels,expected", [
    (["type:epic", "gate:taste"], "mission"),
    (["type:code", "gate:machine"], "no owner contact"),
    (["type:code", "gate:taste"], "artefact"),
    (["type:code", "gate:none"], "unrouted"),
    (["type:code"], "unrouted"),
])
def test_routing_verdict_per_gate(labels, expected):
    assert expected in briefmod.routing(labels).lower()


def test_routing_says_proceed_only_with_ready_auto():
    """`gate:machine` alone means no contact before review. `ready:auto` is the
    stronger claim — an unattended pickup — and needs both labels."""
    assert "unattended" not in briefmod.routing(["gate:machine"]).lower()
    assert "unattended" in briefmod.routing(["gate:machine", "ready:auto"]).lower()


def test_routing_never_promises_autonomy_without_a_gate():
    """gate:none blocks ready:auto (finding B7). A mislabelled issue must not
    read as a licence to run unattended."""
    for labels in (["ready:auto"], ["ready:auto", "gate:none"]):
        assert "unattended" not in briefmod.routing(labels).lower()


@pytest.mark.parametrize("branch,expected", [
    ("feat/117-brief-routing-verdict", 117),
    ("fix/110-ci-duplicate-runs", 110),
    ("docs/112-phase7-proposal", 112),
    ("no-issue/quick-look", None),
    ("master", None),
    ("gl45-telegram-drops", None),
])
def test_active_issue_comes_from_the_branch(branch, expected):
    """The ledger only ever carried an `issue` on `qops close`, so the brief's
    active sortie was the last CLOSED one — and a routing verdict for a closed
    sortie is worse than none. The branch is the live fact (ADR-0019)."""
    assert briefmod.issue_from_branch(branch) == expected


def test_brief_prints_the_verdict_for_the_active_issue():
    state = {"branch": "feat/117-x", "dirty": [], "worktrees": 1, "issue": 117,
             "labels": ["type:code", "gate:machine"], "resume": "", "ahead": 0}
    text = briefmod.render_from(state, qconfig.load(REPO))
    assert "no owner contact" in text.lower()


def test_brief_degrades_silently_when_labels_are_unavailable():
    """`gh` may be absent, offline or slow. A brief that fails is worse than a
    brief with no verdict — it is hot path and it runs before anything else."""
    state = {"branch": "feat/117-x", "dirty": [], "worktrees": 1, "issue": 117,
             "labels": [], "resume": "", "ahead": 0}
    text = briefmod.render_from(state, qconfig.load(REPO))
    assert "unrouted" not in text.lower()
    assert "sortie #117" in text


# --------------------------------------------------------------------------
# metrics — S1 must reproduce the Phase -1 method exactly
# --------------------------------------------------------------------------

def _transcript(tmp_path, records):
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records))
    return p


def _msg(role, blocks, sidechain=False):
    return {"type": role, "isSidechain": sidechain,
            "message": {"role": role, "content": blocks}}


def _read(lines=10):
    return {"type": "tool_use", "name": "Read", "input": {"file_path": "x.py"}}


def _bash(cmd):
    return {"type": "tool_use", "name": "Bash", "input": {"command": cmd}}


def test_s1_counts_reads_before_the_first_productive_call(tmp_path):
    t = _transcript(tmp_path, [
        _msg("assistant", [_read(), _read()]),
        _msg("assistant", [{"type": "tool_use", "name": "Edit", "input": {}}]),
        _msg("assistant", [_read()]),          # after productive: not counted
    ])
    assert metrics.s1_for_transcript(t)["reads"] == 2


def test_s1_excludes_subagent_traffic(tmp_path):
    t = _transcript(tmp_path, [
        _msg("assistant", [_read()], sidechain=True),
        _msg("assistant", [_read()]),
        _msg("assistant", [{"type": "tool_use", "name": "Write", "input": {}}]),
    ])
    assert metrics.s1_for_transcript(t)["reads"] == 1


def test_s1_does_not_count_bash_reads(tmp_path):
    t = _transcript(tmp_path, [
        _msg("assistant", [_bash("cat CLAUDE.md"), _bash("sed -n '1,50p' x")]),
        _msg("assistant", [{"type": "tool_use", "name": "Edit", "input": {}}]),
    ])
    assert metrics.s1_for_transcript(t)["reads"] == 0


@pytest.mark.parametrize("cmd,productive", [
    ("git commit -m x", True),
    ("python -m pytest -q", True),
    ("npm test", True),
    ("git status", False),
])
def test_s1_productive_call_definition(tmp_path, cmd, productive):
    t = _transcript(tmp_path, [
        _msg("assistant", [_bash(cmd)]),
        _msg("assistant", [_read()]),
    ])
    # a read after the first productive call is not counted; if the bash call is
    # not productive, the read is the only thing before nothing -> no productive
    got = metrics.s1_for_transcript(t)
    assert got["productive"] is productive


def test_s1_flags_reads_over_200_lines(tmp_path):
    big = {"type": "tool_result", "content": "\n".join(str(i) for i in range(250))}
    t = _transcript(tmp_path, [
        _msg("assistant", [_read()]),
        _msg("user", [big]),
        _msg("assistant", [{"type": "tool_use", "name": "Edit", "input": {}}]),
    ])
    assert metrics.s1_for_transcript(t)["big_read"] is True


def _timed_transcript(dir_path, name, ts, records):
    p = dir_path / name
    lines = [json.dumps({"type": "user", "timestamp": ts,
                          "isSidechain": False, "message": {"role": "user", "content": []}})]
    lines += [json.dumps(r) for r in records]
    p.write_text("\n".join(lines))
    return p


def test_s1_floors_transcript_on_first_user_assistant_record_and_windows_by_date(tmp_path, monkeypatch):
    home = tmp_path / "home"
    proj_dir = home / ".claude" / "projects" / "C--fake-project"
    proj_dir.mkdir(parents=True)
    monkeypatch.setattr(metrics.os.path, "expanduser", lambda p: str(home))
    root = tmp_path / "project"
    root.mkdir()

    in_window = [_msg("assistant", [_read(), _read()]),
                 _msg("assistant", [{"type": "tool_use", "name": "Edit", "input": {}}])]
    before = [_msg("assistant", [_read()]),
              _msg("assistant", [{"type": "tool_use", "name": "Edit", "input": {}}])]
    after = [_msg("assistant", [_read()]),
             _msg("assistant", [{"type": "tool_use", "name": "Edit", "input": {}}])]

    _timed_transcript(proj_dir, "in.jsonl", "2026-07-20T10:00:00.000Z", in_window)
    _timed_transcript(proj_dir, "before.jsonl", "2026-06-01T10:00:00.000Z", before)
    _timed_transcript(proj_dir, "after.jsonl", "2026-09-01T10:00:00.000Z", after)

    result = metrics.s1(root, since="2026-07-01", until="2026-08-01")
    assert result["sessions"] == 1
    assert result["median_reads"] == 2
    assert "C--fake-project" in result["by_dir"]
    assert result["by_dir"]["C--fake-project"]["sessions"] == 1


def test_s2_counts_kickoff_class_docs():
    n = metrics.s2(REPO, since="2026-07-14")
    assert isinstance(n, int) and n >= 0


# --------------------------------------------------------------------------
# install / doctor — rendered workflows, and drift is detectable
# --------------------------------------------------------------------------

def test_install_renders_the_five_workflows(tmp_path):
    written = install.render_all(tmp_path, qconfig.load(REPO))
    names = {Path(p).name for p in written}
    assert names == {"test.yml", "gate.yml", "guard.yml", "digest.yml", "groom.yml"}
    import re
    for p in written:
        # `${{ secrets.X }}` is GitHub's own syntax and stays; qops placeholders
        # are `{{word}}` and must all be gone.
        left = re.search(r"\{\{\w+\}\}", Path(p).read_text())
        assert left is None, f"unrendered placeholder {left.group(0)} in {p}"


def test_doctor_is_green_on_a_fresh_install(tmp_path):
    install.render_all(tmp_path, qconfig.load(REPO))
    assert install.drift(tmp_path, qconfig.load(REPO)) == []


def test_doctor_detects_drift(tmp_path):
    install.render_all(tmp_path, qconfig.load(REPO))
    wf = tmp_path / ".github" / "workflows" / "groom.yml"
    wf.write_text(wf.read_text() + "\n# hand-edited\n")
    assert "groom.yml" in " ".join(install.drift(tmp_path, qconfig.load(REPO)))


def test_the_repo_itself_is_installed_and_undrifted():
    assert install.drift(REPO, qconfig.load(REPO)) == []


# --------------------------------------------------------------------------
# the two rules that are otherwise only stated in a workflow
# --------------------------------------------------------------------------

def test_claude_md_is_within_the_hot_path_cap():
    cfg = qconfig.load(REPO)
    n = len((REPO / "CLAUDE.md").read_text(encoding="utf-8").splitlines())
    assert n <= cfg["claude_md_max_lines"], f"CLAUDE.md is {n} lines"


def test_every_doc_path_cited_from_code_resolves():
    missing = install.broken_doc_links(REPO)
    assert missing == [], f"broken doc citations: {missing}"


# --------------------------------------------------------------------------
# the CLI is actually wired
# --------------------------------------------------------------------------

@pytest.mark.parametrize("verb", ["brief", "ledger", "resume", "guard", "close",
                                  "install", "doctor", "metrics"])
def test_every_verb_is_dispatchable(verb):
    out = subprocess.run([sys.executable, "-m", "qops", verb, "--help"],
                         cwd=REPO, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr


# --------------------------------------------------------------------------
# subagent definitions — the roster, and the two §3.4 levers, asserted
# --------------------------------------------------------------------------

AGENT_DIR = REPO / ".claude" / "agents"


def _frontmatter(path: Path) -> dict:
    import yaml
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name} has no frontmatter"
    return yaml.safe_load(text.split("---", 2)[1])


def test_the_roster_is_exactly_the_config_s():
    names = {p.stem for p in AGENT_DIR.glob("*.md")}
    assert names == set(qconfig.load(REPO)["agents"])


@pytest.mark.parametrize("role", ["planner", "coder", "reviewer", "scribe",
                                  "triager", "interactor"])
def test_each_agent_matches_its_config_entry(role):
    spec = qconfig.load(REPO)["agents"][role]
    fm = _frontmatter(AGENT_DIR / f"{role}.md")
    assert fm["model"] == spec["model"]
    assert fm["effort"] == spec["effort"]
    assert [t.strip() for t in fm["tools"].split(",")] == spec["tools"]


@pytest.mark.parametrize("role", ["planner", "coder", "reviewer", "scribe",
                                  "triager", "interactor"])
def test_no_agent_nags_about_verification(role):
    """§3.4: scope-fencing language replaces verification-nagging. The named
    exception is the reviewer, which exists because of a 2026-08-01 incident."""
    body = (AGENT_DIR / f"{role}.md").read_text(encoding="utf-8").lower()
    for phrase in ("double-check", "double check", "verify your own work",
                   "make sure you did"):
        assert phrase not in body, f"{role} contains {phrase!r}"
    assert "scope fence" in body


def test_read_only_agents_cannot_write():
    for role in ("planner", "reviewer", "triager", "interactor"):
        tools = qconfig.load(REPO)["agents"][role]["tools"]
        assert not ({"Write", "Edit", "MultiEdit", "NotebookEdit"} & set(tools)), role
