# Commit message best practices

General guidance for writing useful Git commit messages, collected from common industry practice
(the "seven rules" popularised by Chris Beams, the Git project's own SubmittingPatches guide, and
common code-review norms), written in our own words for retrieval.

## [BP-01] Separate subject from body
Write a short subject line, then a blank line, then the body. Git tools such as `git log --oneline`,
`git shortlog` and many review UIs show only the subject, so everything important must fit there.

## [BP-02] Keep the subject short
Aim for a subject of about 50 characters and treat 72 as a hard limit. Long subjects get truncated in
tools and usually mean the commit is doing too much or the author has not decided what it is about.

## [BP-03] Use the imperative mood
Write the subject as a command: "Fix login timeout", not "Fixed login timeout" or "Fixes login timeout".
A good test: the subject should complete the sentence "If applied, this commit will ...".

## [BP-04] Say what and why, not how
The diff already shows how the code changed. The message should explain what problem is being solved
and why this approach was chosen. "Change line 42" is useless; "Retry uploads on 503 to survive
deploys" is useful.

## [BP-05] Avoid vague messages
Messages like "fix", "update", "changes", "stuff", "wip", "misc" or "asdf" carry no information. Six
months later nobody, including the author, can tell what the commit did without reading the whole diff.
Every message should let a reader decide whether the commit is relevant without opening it.

## [BP-06] Match the message to the size of the change
A message that understates the change ("small tweak", "minor fix") on a commit touching dozens of
files or hundreds of lines is misleading. Large changes deserve a body explaining the scope, or should
be split into smaller commits that are each easy to describe.

## [BP-07] Make atomic commits
Each commit should contain one logical change that builds and passes tests on its own. Atomic commits
are easier to review, bisect and revert. Mixing formatting changes with behaviour changes hides the
real change in noise.

## [BP-08] Do not commit work in progress to shared history
"WIP", "temp", "testing" and "please work" commits belong on a private branch. Squash or reword them
with an interactive rebase before merging so the shared history tells a clean story.

## [BP-09] Reference issues without relying on them
Link the related issue or ticket in a footer, but make sure the message still makes sense on its own.
Trackers move and links rot; "Fix #812" alone tells a reader nothing once the tracker is gone.

## [BP-10] Be consistent across the team
Whatever conventions a project chooses (Conventional Commits, capitalisation, ticket prefixes), apply
them consistently. A history that mixes five styles is harder to scan and to automate than one that
follows any single style well.

## [BP-11] No secrets, no noise
Never put credentials, tokens or personal data in commit messages; they live forever in history.
Skip emoji spam, all-caps shouting and jokes that hide the meaning of the change.

## [BP-12] Merge and revert messages
Keep Git's default "Merge branch ..." and "Revert ..." messages, but add a line explaining why a
revert was needed. A revert without a reason invites someone to re-apply the broken change later.
