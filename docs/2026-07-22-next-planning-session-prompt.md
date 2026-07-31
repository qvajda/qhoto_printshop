# Next planning-session kickoff prompt (Etsy POD go-live)

Paste the block below into a fresh Cowork session **after the mockup-track and
GL-16 coding sessions finish**, filling the two feedback slots. It resumes the
same planning/orchestration loop this doc set was built in — integrate
coding-session results into the plan, close/open actions, write the next
kickoff prompts, update Notion. **This session plans; it does not write pipeline
code.**

---

## PROMPT — paste from here down

You are continuing the **Etsy POD go-live planning/orchestration** loop for the
`qhoto_printshop` project (my personal print-on-demand pipeline — the one-way
valve in CLAUDE.md applies; this is my own project, fine to work on). Your job
is to fold the latest coding-session results into the living plan, then tee up
what's next. **Do not write pipeline code** — you produce plan updates, kickoff/
research prompts, and the Notion checkpoint.

**Read first, in order:**
1. `docs/2026-07-22-go-live-plan-of-attack.md` — the canonical plan (open points
   classified by work-type IR/R/C/M/T/D, sequencing, go-live gate, Part 4
   session-feedback log). This is the source of truth; keep it current.
2. `CLAUDE.md` — hard constraints (v4.11) + my operating prefs (PRD threshold,
   pushback, reversibility, note-taking, tool-fit).
3. The most recent dated docs in `docs/` (kickoffs, briefings, findings, any new
   `*-findings.md` / `.remember/` incident notes the coding sessions produced) —
   ground yourself in what actually happened, not what was planned.

**Where things stood at the end of the last planning session (verify against the
plan doc, things may have moved):**
- ✅ GL-1 merge, GL-9 Round-1 live test (PASS/GO w/ residuals), GL-6 mockup
  prototype + GL-2 decision (go pre-launch, near-frontal), GL-14 (Gelato crop)
  and GL-15 (Etsy token auto-refresh) — all done/merged to master.
- 🔜 Launched next: the **mockup track** (GL-4 compositor research →
  GL-5 build → GL-6 library) and **GL-16** (unattended-resilience hardening).
  GL-16 stub: `docs/2026-07-22-gl16-resilience-hardening-stub.md`; GL-4 briefing:
  `docs/2026-07-22-gl4-compositor-research-briefing.md`.
- ⏳ Still ahead: GL-7 cron (gated on GL-16), GL-8 host confirm, GL-10 storefront,
  GL-11 Dev-Mode revert, GL-12 Google Trends, GL-13/GL-17 Round-2 + residuals.

**Feedback from the coding sessions to integrate (I'm pasting raw results):**

> **Slot A — mockup track (GL-4 research / GL-5 build / GL-6 library):**
> [PASTE: what was decided/built — the compositor-approach recommendation
> (library vs Dynamic Mockups vs homography), whether GL-5 shipped and to what
> scope (near-frontal v1.0?), scene-library progress, anything that changed the
> 3-flat/7-lifestyle split or v1.1 angled deferral, and any new bugs/risks.]

> **Slot B — GL-16 resilience hardening:**
> [PASTE: the fault taxonomy found, what shipped (backoff/retry classes,
> transient-vs-reject separation, self-healing state model), what's deferred,
> and whether GL-7 cron is now unblocked to go unattended.]

**What to produce:**
1. **Integrate into `docs/2026-07-22-go-live-plan-of-attack.md`:** mark closed
   items ✅ with a one-line result; spin out any new actions with fresh GL-IDs
   and the right work-type (IR/R/C/M/T/D); update the sequencing + go-live gate;
   append a Part 4 session-feedback log entry per session. Push back if a result
   contradicts the plan's assumptions or if something's being declared done that
   isn't gate-ready (no reflexive agreement).
2. **Tee up the next step(s):** write the house-style kickoff/briefing prompt(s)
   for whatever is now on the critical path (likely GL-7 cron orchestrator once
   GL-16 lands, and/or GL-13 Round-2 test once mockups ship). Match the existing
   kickoff docs' structure (Method=SDD, Hard rules, Tasks/Phases, Deferred, DoD;
   ground every reference in real code paths; STOP-gate any live calls). For
   live tests, extend the Round-1 launch guide's format.
3. **Update the Notion checkpoint** on the "Etsy POD storefront" project page
   (id `3974e724-309e-811a-9a31-d5abcaa0d07c`, via the connected Notion tools):
   append a dated checkpoint with the new milestone state + open actions, and
   bump the `Last Checkpoint` date property.
4. **Flag tool-fit** (CLAUDE.md §7) where relevant — esp. anything that should
   move off Cowork to Claude Code, a scheduled task, or a real host.

Start by reading the three items above and reconciling them with the two
feedback slots, then tell me the reconciled state (what's done, what moved, what
the critical path is now) before writing any new kickoff prompts.
