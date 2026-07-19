# Git rules

All repos here are solo, single-developer projects — no review gate, no team.
These rules replace any default agent guidance to branch first or to wait for
an explicit request before committing and pushing.

- Work directly on `main`; no branches or PRs unless explicitly requested.
- Commit at every working checkpoint; push after every commit.
- Never `--no-verify`; never force-push `main`; never rewrite pushed history.
- End every task on `main`, working tree clean, everything pushed.
- For the full procedure — commit-message rules, secrets handling, a dirty or
  diverged repo — use the `git-ops` skill.
