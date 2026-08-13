# ADR-0002 — Approvals come from Remote Control; Telegram is a channel, not an authority

**Status:** accepted · **Date:** 2026-08-13 · **Session:** E14, Phase 1 item 4
**Implements:** PRD v3 decisions 25, 31, 38 · review finding B13.

## Context

Two different things both happen on a phone and were repeatedly conflated:

- **Tool-permission decisions** inside an agent session ("may I run this Bash
  command / write this file").
- **Product decisions** about an artwork — the pipeline's own digest buttons
  (Approve / Edit / Reject / Redo copy).

PRD v2 proposed a dedicated dev Telegram bot whose token went into Actions
secrets, and a permission **relay** so approvals could come from chat.

## Decision

1. **Tool-permission approvals come from Remote Control** (`claude
   --remote-control` + *Push when actions required*). It forwards the real
   permission prompt and the real `AskUserQuestion`; authority is the signed-in
   claude.ai account rather than whoever is on a chat allowlist; it has no
   platform restriction, so it works on this Windows machine today. **This
   session ran under it.**
2. **The Telegram permission relay stays OFF.** No relay setting is configured
   anywhere under `~/.claude/channels/`, so it is off by default rather than by
   an explicit switch — recorded here because "off by default" is a weaker
   guarantee than "off by configuration", and if a future release adds an
   opt-out key it should be set explicitly.
3. **Telegram keeps digests, questions and external events**, and nothing else.
4. **The pipeline's own Telegram approvals are untouched.** They are product
   decisions against a domain model and stay exactly where they are.

## B13 verified by measurement, not by assumption

The requirement is that the production bot — the one that approves real Etsy
publishes — is never reused as the agent channel. **Checked by comparing token
hashes, not by reading either token:**

| | bot id prefix | token SHA-256 (first 12) |
|---|---|---|
| Channel bot (`~/.claude/channels/telegram/.env`) | `8865923015` | `16fd0b3745a4` |
| Pipeline bot (repo `.env`) | `8743490219` | `3e0e823a1885` |

**Different bots.** The channel token lives outside the repository entirely and
never enters CI, which is the property v2's Actions-secret design lacked.
`dmPolicy` is already `allowlist` with two ids, one of which is
`TELEGRAM_ADMIN_CHAT_ID`. The allowlist stays credential-grade for the same
reason that variable already is.

**Open, and it needs the owner's hands:** the channel bot predates qops
(2026-07-11). It satisfies B13's actual requirement — separate from production —
but it is not a bot created *for* qops. Whether to mint a dedicated one is an
owner call and a BotFather action; nothing here depends on the answer.

## Consequence found while verifying this, and it is not cosmetic

`~/.claude/settings.json` denies `Read(.env)`. That rule binds the **Read tool
only** — the comparison above was done from a Bash-invoked Python one-liner,
which read `.env` without tripping anything. The deny rule is a Read-tool
convention, not a boundary.

ADR-0001 established that `PreToolUse` can **hard-block** a Bash call on exit 2
and receives `tool_input.command`. **That is the instrument that closes this
gap**, and it is a Phase 4 guard requirement, not a nice-to-have: a rule that
only covers one of two paths to the same file is the "instruction is a
preference, not a control" failure (GL-53) in permissions form.
