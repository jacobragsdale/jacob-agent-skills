# Wiring work-log into agents

The always-on loop has two halves: read-back at session start, capture during
work. How each agent gets them:

## Cursor (first-class)

`worklog.py init` stamps a rule block into the project's `AGENTS.md`, which
Cursor loads every session. That block carries both halves: read the log at
start, append when a turn contains a struggle / decision / environment fact /
milestone. No hooks required. If Cursor hooks are configured on this machine
later (`~/.cursor/hooks.json`), a `stop` hook can additionally run
`worklog.py check`, but the rule block is the load-bearing mechanism.

## Claude Code (second-class, deluxe)

Claude Code reads the same rule block via `CLAUDE.md` → `@AGENTS.md` (init
ensures the import). Hooks in `~/.claude/settings.json` add the automatic
loop; both scripts exit silently in projects without `.agents/LOG.md`, so
global wiring is safe:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run ~/.claude/skills/work-log/scripts/worklog.py digest"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run ~/.claude/skills/work-log/scripts/worklog.py check"
          }
        ]
      }
    ]
  }
}
```

- **SessionStart** — `digest` stdout (Now + Map + recent Lessons + practices)
  is injected as context.
- **Stop** — `check` reads the hook JSON, and only when enough transcript has
  accumulated since the last checkpoint (default 60 KB, 10 min cooldown, log
  untouched in between) emits a `decision: block` whose reason tells the
  agent to run a capture pass. `stop_hook_active` guards against loops.
  Tune with `WORK_LOG_MIN_GROWTH` / `WORK_LOG_COOLDOWN` env vars.

Nudge state lives in `~/.cache/work-log/<session>.json`; deleting that
directory is always safe.
