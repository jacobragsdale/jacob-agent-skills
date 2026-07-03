---
name: work-log
description: "Capture work state, struggles, lessons, and environment facts into .agents/LOG.md for future agent sessions. Use when asked to log this, record a lesson or struggle, write a handoff, consolidate the work log, or set up work-log in a repo."
disable-model-invocation: true
---

# Work log

Maintain `.agents/LOG.md` — the per-project memory that future agent sessions
(Cursor and Claude Code) read at startup. It has four sections with different
update rules: `## Now` (handoff state — **replace in place**), `## Map`
(environment facts — **merge in place**), `## Lessons` (corrections —
**append, dated**), `## Journal` (narrative — **append, dated, newest
first**). Cross-project rules live in `PRACTICES.md` in this skill's folder.

## Modes

- `/work-log` — capture pass over the current conversation (default).
- `/work-log init` — set a repo up for work-log.
- `/work-log consolidate` — prune and promote; run when the log feels noisy.

## Capture pass

Review the conversation since the last log update and write entries for what
qualifies. Most turns produce nothing — when nothing qualifies, say so and
write nothing. The bar:

| Section | Write when | Format |
|---|---|---|
| Now | The handoff state changed: work finished, direction changed, something left in flight | Replace the whole section: what's in flight, where it stands, next step. ≤6 lines. |
| Map | An environment fact was discovered or rediscovered: a path, log location, where credentials live, how to run something | One bullet per fact; update the existing bullet if it's already there. |
| Lessons | Something cost real time and would recur: a dead end, a wrong assumption, a correction from the user | `- YYYY-MM-DD: <what happened> -> <what to do instead>` |
| Journal | A milestone: feature landed, bug root-caused, decision settled (include the why) | `### YYYY-MM-DD -- <title>` + ≤5 lines, inserted at the top of the section. |

Hard rules:

- Never log routine work (edits that went fine, questions answered, passing
  tests). An entry must change what a future session does.
- Write for agents, not humans: paths, commands, and corrections — no
  narrative padding, no "we then proceeded to".
- One fact, one place. A discovered path goes in Map, not also in Journal.
- Do not invent content to have something to write. An empty capture pass is
  a correct outcome.

## Init

1. RUN `uv run <this-skill-dir>/scripts/worklog.py init --project <repo>` —
   creates `.agents/LOG.md`, stamps the always-on rule block into `AGENTS.md`,
   and ensures `CLAUDE.md` imports `@AGENTS.md`.
2. Seed `## Now` and `## Map` from what you already know (git log, existing
   docs, the current conversation). Ask the user only for what you can't
   discover.
3. If the user hasn't wired Claude Code hooks yet, READ `references/wiring.md`
   and offer to add them to `~/.claude/settings.json`.

## Consolidate

1. **Lessons**: merge duplicates. A lesson confirmed across 2+ projects or
   repeatedly re-earned is a practice — move it to `PRACTICES.md` in this
   skill's folder (resolve via this SKILL.md's location) and delete the
   originals.
2. **Journal**: delete entries older than ~30 days unless `## Now` or an open
   task still references them; fold anything durable they contain into Map or
   Lessons first.
3. **Map**: verify facts still hold (paths exist, commands run) before
   keeping; delete stale ones.
4. Keep LOG.md under ~150 lines. If it's over after pruning, the entries are
   too long — tighten them.

## Example

A session where a deploy failed twice because the SOPS age key was in an
unexpected location, then shipped. The capture pass writes:

```markdown
## Now
Frontend polish shipped and deployed. Next: DHCP reservations for the bulbs.

## Map
- SOPS age key: ~/.config/sops/age/keys.txt (deploy fails cryptic without it)

## Lessons
- 2026-07-02: deploy failed with bare exit 1 when SOPS key missing ->
  check ~/.config/sops/age/keys.txt exists before debugging the deploy script

## Journal
### 2026-07-02 -- Frontend polish deployed
Unified card headers, opaque nav. Deploy is Mac -> server rsync, no CI.
```

## Bundled resources

- `scripts/worklog.py` — RUN for `init` and `digest`; `check` is invoked by
  the Claude Code Stop hook, never manually.
- `references/wiring.md` — READ when wiring or debugging the always-on hooks
  (Claude Code settings.json, Cursor rule block).
- `PRACTICES.md` — the cross-project practices file; edited only by
  consolidate and the user.

## Improving this skill

Before executing, read `LEARNINGS.md` in this skill's folder — entries there
override the instructions above. After use, if the user corrected you or the
outcome surprised you, append one dated line to `LEARNINGS.md`:
`- YYYY-MM-DD: <what happened> → <what to do instead>`. Do not edit SKILL.md
directly; lessons are folded in deliberately, not on the fly.
