# Contributing

Thanks for wanting to help! This is a small project, so the process is light.

## Setup

```powershell
powershell -ExecutionPolicy Bypass -File setup\setup_windows.ps1   # Windows
pip install -r requirements-dev.txt                                # everyone
```

## Before you open a pull request

1. Run the tests: `python -m pytest`. They never call a real API, so they're quick and free.
2. Check your commit messages: `python roast.py --lint --range main..HEAD`.
   It would be a little embarrassing to get roasted by the project you're contributing to.

## Commit messages

We follow [Conventional Commits](https://www.conventionalcommits.org): `type(scope): description`.

| Type | Use it for |
|---|---|
| `feat` | something new for users |
| `fix` | a bug fix |
| `docs` | documentation only |
| `test` | adding or fixing tests |
| `refactor` | code changes that don't change behavior |
| `ci` | GitHub Actions workflows |
| `chore` | maintenance, dependencies |

Good: `feat(agent): limit diff inspections to 4 per run`
Not so good: `fix stuff`

Common scopes: `agent`, `knowledge`, `cli`, `lint`, `dify`, `ci`.

## Adding a rule to the knowledge base

Rules live in `knowledge/*.md`. Each rule is a section with a heading like `## [BP-15] Short title`.
The ID must be unique, because that's what reviews cite. After adding one, add a search test in
`tests/test_knowledge.py` so we know retrieval actually finds it.

## Every pull request gets roasted

The `Roast PR commits` workflow reviews the commits in your PR and leaves a comment.
Don't take it personally. It roasts the messages, not you.
