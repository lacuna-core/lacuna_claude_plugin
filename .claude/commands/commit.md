Execute the most recently proposed commit plan (from /commit-plan or a
revised plan agreed upon in this session).

For each group in order:
1. Stage only the listed files with `git add <file>` (or `git add -p` if flagged)
2. Run `git status` to confirm staged files before committing
3. Commit with the agreed message
4. Output a confirmation line after each commit

If no plan has been proposed or approved in this session, run /commit-plan first
and wait for approval before proceeding.

Never use `git add .`
Never commit if staging produced unexpected files — stop and ask instead.
Don't use "Co-Authored-By"
