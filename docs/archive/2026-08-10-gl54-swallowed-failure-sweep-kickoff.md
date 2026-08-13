# GL-54 kickoff — the swallowed-failure sweep (+ alt-text rider)

**Type:** C · **Tool:** Claude Code, in-repo · **Live API calls:** none
· **Size:** short — the sweep is mechanical, the judgement is in two places
· **PRD:** not required (CLAUDE.md §2 — no external system, one sitting)
· **Blocks:** E9, the verification run
(`docs/2026-08-10-e9-verification-run-runbook.md`)

Read `docs/2026-07-22-go-live-plan-of-attack.md` row **GL-54** and
`docs/2026-08-10-gl53-findings.md` §4 first.

---

## 0. Why this is a blocker and not housekeeping

E9 costs a Replicate generation, a live Gelato create and an Etsy listing, and
it passes through every loop in §2. **A per-item failure in any of them
currently leaves the row reading "hasn't run yet" and the stage returning
success — so nothing is sent to Telegram and nothing on the row says so.** A
live run through stages that cannot report their own failures is a run whose
negative results mean nothing. That is not a hypothetical: it is what the 08-08
soak did for two nights, and what GL-46 found afterwards (8 of 8 candidates at
`pending` overnight, nothing anywhere saying so).

**Ten minutes of sweep buys the observability of a run that costs money.**

## 1. The rule being applied

From CLAUDE.md, written 2026-08-10 out of GL-46:

> A swallowed per-item exception must always leave a state change behind. Any
> per-item catch inside a stage loop must (a) write the failure onto the row —
> a status plus a reason — and (b) let the stage still fail once at the end,
> after the loop has given the other items their turn.

GL-46 applied it to `generate`. GL-53 applied it to `compliance_draft` and found
that stage had **half** of it — (a) present, (b) missing. **Expect that split
here too: (a) is often already done and (b) almost never is.** Check both
separately per stage; do not assume a stage with a `*_failed` status is
compliant.

## 2. The actual inventory — and it is not the four the findings named

GL-53's findings said "four other stage loops". **Reading the code, it is six,
and one of the two it named is already compliant.** Correct list:

| Module | Loop | (a) row marked? | Notes |
|---|---|---|---|
| `primary_mockup.py:99` | `run_primary_mockup_cycle` | **check** — sets `pending_review` on success; no failure write visible | has the Cloudflare inter-candidate delay; keep it |
| `critic_pass.py:596` | `run_critic_pass_cycle` | likely yes — `critic_pass.py:468/472` write `failed` / `failed_abandoned` with `failed_reason` | inner retry cap is 3, do not touch it |
| `digest.py:163` | `run_digest_cycle` | **probably not, and this is the interesting one** — see §3 | |
| `group_mockup.py:124` | `run_group_mockup_cycle` | **check** | **not named in the findings** |
| `group_critic_pass.py:136` | `run_group_critic_pass_cycle` | likely yes (`group_critic_pass.py:52`) | **not named in the findings** |
| `group_digest.py:126` | `run_group_digest_cycle` | see §3 | **not named in the findings** |

**And the one to leave alone: `publish_primary_group.py:445`.** Its
`process_update` catch is **already compliant and was made so deliberately by
GL-45** — it writes `log_telegram_event(..., accepted=True, f"error: {exc}")`
so a dropped tap leaves a durable trace, and it advances the offset per update
on purpose. **Read the comment block before touching it.** Sweeping it blindly
would be a regression dressed as a fix, and it is exactly the kind of thing a
mechanical sweep gets wrong.

`publish_primary_group.py:422` and `publish_group.py` still need a look — they
were not inspected for this kickoff. **Inspect, then decide; do not assume they
match either pattern.**

## 3. The judgement call — `digest` has nowhere obvious to write the failure

`generate` and `compliance_draft` were easy: the candidate has a status column
with `failed` / `compliance_failed` in its CHECK constraint, so (a) had a home.

**Digest does not.** A digest send failure is not a property of the artwork or
the copy — the group is still legitimately `pending_review`, it just never got
shown to anyone. `groups.status`'s CHECK allows
`pending_generation, pending_review, approved_published, rejected,
failed_abandoned, publish_failed, stalled_skipped` — **none of which means "I
could not tell you about this".** Marking it `failed_abandoned` would be a lie
that costs a real design.

Options, in the order I'd rank them:

1. **(b) only, no (a).** Raise a `DigestCycleError` after the loop naming the
   groups that failed to send, and write nothing to the row. The failure is
   *transient by nature* (Telegram was down, a media upload 502'd) and the next
   cycle will re-send, because the group is still `pending_review` — which is
   the correct state. The Telegram notification from `_run_stage` is the
   durable trace. **This is probably right, and it is the cheapest.**
2. A nullable `last_digest_error` / `digest_attempts` column. More faithful to
   the rule, needs a migration (`schema_version` is 8), and buys little if
   option 1's re-send actually works.
3. Do nothing for digest. **Rejected** — a stage that cannot send and cannot
   say so is precisely the GL-46 failure mode.

**Whichever is chosen, write the reasoning next to the code.** If option 1: say
explicitly *why* the rule's clause (a) is waived here, referencing the CHECK
constraint, so the next reader does not "fix" the omission. **An exception to a
rule that does not say why it is an exception is indistinguishable from the bug
the rule exists to prevent.**

Note there is a second catch at `digest.py:170` around
`surface_publish_failed_groups` — same question, and it is arguably worse,
because that function's whole job is to surface failures.

## 4. The rider — alt texts through `check_forbidden_terms`

One line, and it needs a decision stated rather than assumed. **Alt texts are
model output and they go live on the listing**, so they are listing copy and
they belong inside the guardrail. GL-53 scoped them out only because its
kickoff said "title, tags, description".

Extend `check_forbidden_terms`'s call site in `compliance_draft` to cover
`draft["alt_texts"]`, and add one test. Note the alt texts describe *mockup
photographs* — "flat print mockup shot" vs "lifestyle/room-context shot" — so
they are the field most likely to legitimately want words like `print`. **Check
the shipped term list does not contain anything an honest alt text needs**
before wiring it, and if it does, that is a finding, not a blocker.

## 5. Definition of done

1. Every loop in §2 either fixed or **explicitly recorded as deliberately
   unchanged, with the reason** — `publish_primary_group:445` is the known
   example and must appear in the findings as "left alone on purpose".
2. Per-stage error types following `GenerateCycleError` /
   `ComplianceDraftCycleError`; collect-then-raise-once, never
   raise-on-first-failure — the other items must still get their turn.
3. A test per fixed stage asserting the raise happens **after** the loop
   completes (i.e. a later item still processed), mirroring GL-46/GL-53's.
   **Watch for existing tests that assert the swallow** — GL-53 found two and
   rewriting them was part of the fix, not a side effect.
4. The alt-text rider plus its test.
5. Full suite green (742 after PR #10).
6. Findings note: the corrected inventory (six, not four), the digest decision
   and its reasoning, anything at `publish_group` / `publish_primary_group:422`.
7. PR opened, not merged.

## 6. Out of scope

- **Any recovery or age-out pass for `failed` rows.** GL-46 flagged that
  nothing reads `failed` except `cleanup.prune_stale_candidates`'s 30-day
  purge, and deliberately did not build one. That is GL-36-shaped and stays a
  separate decision. **Do not let this sweep grow into it.**
- Backfilling or repairing existing rows.
- Anything in `run_batch.py`'s `_run_stage` — it already works; the stages were
  the problem.

## 7. The meta-point, worth one line in the findings

Neither prior instance of this bug was found by looking for the shape. GL-46 was
found by a soak losing eight candidates overnight; GL-53's was found only
because its kickoff contained the sentence *"check whether this loop has the
same shape"*. **Two instances found by accident is the argument for sweeping the
rest on purpose** — and for asking, once the sweep is done, what *else* was
written down as a rule and never applied backwards.
