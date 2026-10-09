# Conventional Commits

Summary of the Conventional Commits 1.0.0 specification (https://www.conventionalcommits.org),
written in our own words for retrieval. Each section is one retrievable chunk; the ID in brackets is
what reviews cite.

## [CC-01] Message structure
A conventional commit message has a header, an optional body and optional footers:
`<type>[optional scope][!]: <description>`, then a blank line, the body, a blank line, and footers.
The header is the only required part. Tools such as changelog generators and semantic-release parse it,
so a header that does not follow the structure cannot be classified automatically.

## [CC-02] The feat and fix types
`feat` means the commit adds a new feature for users and maps to a MINOR version bump in semantic
versioning. `fix` means the commit patches a bug and maps to a PATCH bump. Labelling a refactor or a
chore as `fix` misleads release tooling and reviewers about what changed.

## [CC-03] Other common types
Besides feat and fix, widely used types are `build`, `chore`, `ci`, `docs`, `style`, `refactor`,
`perf` and `test`. Pick the type that matches the main purpose of the change: `docs` for documentation
only, `refactor` for code changes that neither fix a bug nor add a feature, `test` for adding or
correcting tests, `ci` for pipeline configuration, `chore` for maintenance that touches neither source nor tests.

## [CC-04] Scope
A scope is an optional noun in parentheses after the type naming the part of the codebase affected,
for example `feat(parser): support arrays`. Scopes make history searchable by area. Keep scopes short
and consistent across the project; do not invent a new spelling for the same module each time.

## [CC-05] Description
The description comes right after the colon and a space. It is a short summary of the change, written
in the imperative mood ("add", not "added" or "adds"), starting lowercase by convention and with no
trailing period. It must describe the change itself, not the developer's mood or the ticket status.

## [CC-06] Body
The body is free-form text after a blank line that explains the motivation for the change and how it
contrasts with previous behaviour. Use it whenever the header alone cannot explain why the change was
made. A large or risky change with no body leaves future maintainers guessing.

## [CC-07] Breaking changes
A breaking change to a public API must be signalled, either with `!` before the colon
(`feat(api)!: drop v1 endpoints`) or with a `BREAKING CHANGE:` footer describing the break. Breaking
changes map to a MAJOR version bump. Hiding a breaking change behind an innocent header is one of the
most expensive commit mistakes.

## [CC-08] Footers
Footers follow the body after a blank line and use the `Token: value` or `Token #value` format, for
example `Refs: #123` or `Reviewed-by: Name`. Use footers to link issues and record metadata instead of
cramming ticket numbers into the description.

## [CC-09] Why use the convention
Structured commits let tools generate changelogs, decide the next semantic version, and trigger builds
automatically. They also make it easier for contributors to explore a structured history and for
reviewers to understand the intent of each change at a glance.

## [CC-10] One commit, one type
If a change fits more than one type, that is usually a sign it should be split into several commits.
A commit that is half feature and half unrelated refactor is hard to review, hard to revert and hard
to describe honestly in one header.
