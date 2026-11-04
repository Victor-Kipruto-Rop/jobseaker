# Sensitive Git history purge checklist

**Do not run this against the only copy of the repository. Do not force-push until the owner has reviewed the scan results and coordinated with every collaborator.**

The current branch removes private files from its latest tree, but earlier commits may still contain them. A normal delete commit does not erase historical blobs.

## Before rewriting

- [ ] Preserve private source files outside the repository in an encrypted, access-controlled location if they are still required.
- [ ] Create a full backup clone, including all branches and tags: `git clone --mirror <repository-url> jobseaker-backup.git`.
- [ ] Create a separate fresh working clone for the rewrite.
- [ ] Install a current `git-filter-repo` release.
- [ ] Record the remote branches and tags that must be retained.
- [ ] Coordinate a temporary push freeze with collaborators.
- [ ] Run Gitleaks against every branch and tag and save only redacted findings.
- [ ] Identify exposed credential types without copying values into tickets, chat, or logs.
- [ ] Rotate/revoke exposed credentials before rewriting history.

## Review and execute

1. In the fresh clone, check out the intended canonical branch and confirm the worktree is clean.
2. Copy this repository's `scripts/security/purge_sensitive_history.py` into the clone if needed.
3. Run a dry run: `python scripts/security/purge_sensitive_history.py`.
4. Review the printed paths. The script targets the secrets directory, private-data directory, and the five named private data/report files.
5. Execute locally only after confirming the backup: `python scripts/security/purge_sensitive_history.py --execute`.
6. Inspect rewritten refs, tags, branches, and repository contents. `git-filter-repo` may remove the `origin` remote; restore it only after review.
7. Run Gitleaks across all refs again. Review GitHub cached references, forks, releases, pull-request refs, CI artifacts, and clones separately.
8. Do not assume history rewrite removes copies already downloaded by collaborators or retained by Git hosting.

## Push coordination

- [ ] Confirm all collaborators have stopped pushing.
- [ ] Share the rewritten history and migration instructions.
- [ ] Confirm the repository owner approves the exact refs to replace.
- [ ] Reconcile protected branches and tags.
- [ ] Only the owner should perform the coordinated remote ref replacement.
- [ ] No force-push is performed by the supplied script or by this implementation.
- [ ] Ask collaborators to re-clone rather than merge old history back into rewritten refs.
- [ ] Re-run secret scans after the coordinated push.

## Scope limitations

This checklist does not purge forks, cached GitHub objects, pull-request refs, release assets, Actions artifacts, package registries, external backups, or collaborator clones. Those require separate review and, where necessary, a GitHub Support request.
