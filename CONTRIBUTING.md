# Contributing

## Fork workflow

1. Fork `a444777/feiyu` to your GitHub account.
2. Clone your fork and add the upstream remote:

   ```bash
   git clone git@github-momobiubiu:momobiubiu/feiyu.git feiyu-contributor
   cd feiyu-contributor
   git remote add upstream https://github.com/a444777/feiyu.git
   ```

3. Synchronize and create a feature branch:

   ```bash
   git fetch upstream
   git switch main
   git merge --ff-only upstream/main
   git switch -c feature/expression-preview
   ```

4. Run the local gates before pushing:

   ```bash
   .venv/bin/ruff check app tests
   .venv/bin/pytest
   docker build -t feiyu:local .
   ```

5. Push the feature branch to `origin` and open a pull request against `a444777/feiyu:main`.

## Review and security

- Do not put credentials in code, tests, Actions, issues, or pull requests.
- Fork pull requests do not receive repository secrets.
- A maintainer may need to approve a first-time contributor's workflow run.
- Workflow approval and code-review approval are separate decisions.
- Do not merge while CI, CodeQL, review, or conversation-resolution gates are incomplete.
