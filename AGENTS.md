# Working in this repo

This is a library of Agent Skills (agentskills.io format) and the single
source of truth for skills on this machine. The canonical source is
`skills/<name>/`; agent-specific directories (`~/.agents/skills`,
`~/.claude/skills`) receive per-skill symlinks via `install.py` — never edit
skills there, edit them here.

Rules:

- **Added, renamed, or removed a skill?** Run `uv run install.py` before
  finishing so the symlinks in `~/.agents/skills` and `~/.claude/skills`
  stay current. Editing an existing skill needs nothing — symlinks pick it
  up immediately.
- Keep the skill count low. Fold new material into an existing skill
  (`python-standards` for anything Python tooling/testing related) before
  creating a new one.
- Every skill folder has `SKILL.md` (frontmatter: `name`, `description`)
  and `LEARNINGS.md`.
- All bundled Python is a single file with a PEP 723 `# /// script` header,
  runnable via `uv run` with no environment setup.
- **Git workflow:** This is a personal repository; when authorized changes are
  complete and checks pass, commit directly to the main branch and push it —
  do not create a feature branch or PR unless the user explicitly requests one.
- Never edit a skill's SKILL.md to record a one-off correction — append a
  dated line to that skill's `LEARNINGS.md` instead. Folding learnings into
  SKILL.md is a deliberate, reviewed step.
