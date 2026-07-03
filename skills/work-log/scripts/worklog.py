#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""work-log plumbing: init a project log, emit a session-start digest, filter stop-hook nudges.

Subcommands:
  init [--project DIR]   Create .agents/LOG.md and stamp the always-on rule
                         block into AGENTS.md (idempotent). Ensures CLAUDE.md
                         imports @AGENTS.md.
  digest [--project DIR] Print a compact digest (Now + Map + recent Lessons +
                         global practices) for injection at session start.
                         Prints nothing and exits 0 if the project has no log.
  check                  Claude Code Stop-hook filter. Reads hook JSON on
                         stdin; emits {"decision": "block", ...} only when
                         enough work has accumulated since the last nudge and
                         the log hasn't been touched. Exits 0 silently
                         otherwise. Not for manual use.

Exit codes: 0 ok / nothing to do, 1 usage or filesystem error.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
PRACTICES = SKILL_DIR / "PRACTICES.md"

LOG_TEMPLATE = """\
# Agent work log

Maintained by agents via the work-log skill. `Now` is replaced in place;
`Map` is merged in place; `Lessons` and `Journal` are dated, newest first.

## Now

_(handoff state: what's in flight, where it stands, the next step)_

## Map

_(environment facts agents keep rediscovering: paths, log locations, where
credentials live, how to run things)_

## Lessons

_(`- YYYY-MM-DD: <what happened> -> <what to do instead>`)_

## Journal

_(`### YYYY-MM-DD -- <title>` entries, newest first)_
"""

RULE_START = "<!-- work-log:start -->"
RULE_END = "<!-- work-log:end -->"
RULE_BLOCK = f"""{RULE_START}
## Work log (always on)

- At session start, read `.agents/LOG.md` before doing anything else.
- When a turn contains a struggle or dead end, a settled decision, a
  discovered environment fact, or a milestone, append it to `.agents/LOG.md`
  in the matching section (see the `work-log` skill for entry format).
- Cross-project practices live in `~/.agents/skills/work-log/PRACTICES.md`;
  read it before large or novel changes.
{RULE_END}"""


def log_path(project: Path) -> Path:
    return project / ".agents" / "LOG.md"


def section(text: str, name: str) -> str:
    """Return the body of a `## name` section, without placeholder comments."""
    m = re.search(rf"^## {re.escape(name)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return ""
    body = m.group(1).strip()
    if body.startswith("_(") and body.endswith(")_"):
        return ""  # untouched placeholder
    return body


def cmd_init(project: Path) -> int:
    log = log_path(project)
    log.parent.mkdir(exist_ok=True)
    if log.exists():
        print(f"ok        {log} already exists")
    else:
        log.write_text(LOG_TEMPLATE)
        print(f"created   {log}")

    agents_md = project / "AGENTS.md"
    if agents_md.exists() and RULE_START in agents_md.read_text():
        print(f"ok        {agents_md} already has the work-log block")
    else:
        header = "" if agents_md.exists() else f"# {project.name}\n\n"
        existing = agents_md.read_text() if agents_md.exists() else ""
        agents_md.write_text(existing.rstrip() + ("\n\n" if existing else header) + RULE_BLOCK + "\n")
        print(f"stamped   {agents_md}")

    claude_md = project / "CLAUDE.md"
    if not claude_md.exists():
        claude_md.write_text("@AGENTS.md\n")
        print(f"created   {claude_md} (imports @AGENTS.md)")
    elif "@AGENTS.md" not in claude_md.read_text():
        print(f"WARNING   {claude_md} exists but does not import @AGENTS.md -- add the line yourself")
    return 0


def cmd_digest(project: Path) -> int:
    log = log_path(project)
    parts: list[str] = []
    if log.exists():
        text = log.read_text()
        now = section(text, "Now")
        env_map = section(text, "Map")
        lessons = section(text, "Lessons")
        recent = "\n".join(lessons.splitlines()[:5]) if lessons else ""
        if now:
            parts.append(f"## Now\n{now}")
        if env_map:
            parts.append(f"## Map\n{env_map}")
        if recent:
            parts.append(f"## Lessons (recent)\n{recent}")
    if PRACTICES.exists():
        practices = "\n".join(
            line for line in PRACTICES.read_text().splitlines() if line.startswith("- ")
        )
        if practices:
            parts.append(f"## Cross-project practices\n{practices}")
    if not parts:
        return 0
    print(f"[work-log digest -- {project.name}]")
    print("\n\n".join(parts))
    print(
        "\n(Full log: .agents/LOG.md -- append struggles, decisions, environment"
        " facts, and milestones there as you work; the work-log skill has the format.)"
    )
    return 0


def cmd_check(min_growth: int, cooldown: float) -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    if payload.get("stop_hook_active"):
        return 0  # continuation after a previous nudge -- never loop
    project = Path(payload.get("cwd") or os.getcwd())
    log = log_path(project)
    if not log.exists():
        return 0  # project has not opted in

    transcript = Path(payload.get("transcript_path", ""))
    size = transcript.stat().st_size if transcript.is_file() else 0
    key = payload.get("session_id") or hashlib.sha1(str(transcript).encode()).hexdigest()
    state_file = Path.home() / ".cache" / "work-log" / f"{key}.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        state = json.loads(state_file.read_text())
    except (OSError, json.JSONDecodeError, ValueError):
        state = {"offset": 0, "last_nudge": 0.0}

    now = time.time()
    if log.stat().st_mtime > state.get("last_nudge", 0.0) and state.get("last_nudge"):
        # Log was updated since the last nudge: capture is happening on its own.
        state.update(offset=size, last_nudge=now)
        state_file.write_text(json.dumps(state))
        return 0
    if size - state.get("offset", 0) < min_growth or now - state.get("last_nudge", 0.0) < cooldown:
        return 0

    state.update(offset=size, last_nudge=now)
    state_file.write_text(json.dumps(state))
    print(
        json.dumps(
            {
                "decision": "block",
                "reason": (
                    "Work-log checkpoint: review the work since the last checkpoint. "
                    "If it contained a struggle or dead end, a settled decision, a "
                    "discovered environment fact, or a milestone, append it to "
                    ".agents/LOG.md (Now: replace in place; Map: merge; Lessons/"
                    "Journal: dated, newest first). If nothing qualifies, or you "
                    "already logged it, finish without writing anything."
                ),
            }
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("init", "digest"):
        p = sub.add_parser(name)
        p.add_argument("--project", type=Path, default=Path.cwd(), help="project root (default: cwd)")
    p = sub.add_parser("check")
    p.add_argument("--min-growth", type=int, default=int(os.environ.get("WORK_LOG_MIN_GROWTH", 60_000)),
                   help="transcript bytes that must accumulate before a nudge (default 60000)")
    p.add_argument("--cooldown", type=float, default=float(os.environ.get("WORK_LOG_COOLDOWN", 600)),
                   help="minimum seconds between nudges (default 600)")
    args = parser.parse_args()

    if args.cmd == "init":
        return cmd_init(args.project.resolve())
    if args.cmd == "digest":
        return cmd_digest(args.project.resolve())
    return cmd_check(args.min_growth, args.cooldown)


if __name__ == "__main__":
    sys.exit(main())
