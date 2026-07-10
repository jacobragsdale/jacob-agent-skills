# Learnings

Dated corrections from real use of this skill. Read before executing;
fold recurring/confirmed entries into SKILL.md and delete them here.

Format: `- YYYY-MM-DD: <what happened> → <what to do instead>`

(All entries through 2026-07-06 folded into SKILL.md.)

- 2026-07-09: `scripts/vm.sh status` failed because Compose interpolates the required Windows credentials even for `ps` → run status through `sops exec-env` or use `docker ps` for a read-only check.
- 2026-07-10: Pre-creating `C:\Users\<name>` before a temporary Windows user's first OpenSSH login made User Profile Service create `<name>.<COMPUTERNAME>`, and the SSH-created profile hive stayed loaded after account deletion → let the first password login create the profile before adding `authorized_keys`; if the deleted user's hive remains loaded, reboot the disposable VM before `Remove-CimInstance` cleanup.
