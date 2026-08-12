# Feiyu GitHub Governance Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify a minimal FastAPI repository whose fork-based contribution flow is governed by CI, CodeQL, Code Owner review, an active GitHub Ruleset, and GHCR delivery.

**Architecture:** The repository contains one small HTTP application, one test module, three narrowly scoped GitHub Actions workflows, and repository-local governance documentation. The experiment runs in two phases: `a444777` bootstraps and protects upstream `main`; `momobiubiu` then submits a deliberately unsafe fork PR, observes the gates, fixes it in the same PR, and completes delivery.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, pytest, Ruff, Docker, GitHub Actions, CodeQL v4, GitHub Rulesets, GHCR, Git over SSH.

---

## File map

- `app/__init__.py`: marks the application package.
- `app/main.py`: owns the FastAPI application and `/health` endpoint only.
- `tests/test_health.py`: verifies the public health-check contract.
- `pyproject.toml`: defines runtime/development dependencies, packaging, pytest, and Ruff configuration.
- `README.md`: gives the shortest run/test/container instructions and governance summary.
- `CONTRIBUTING.md`: defines the upstream/fork/feature-branch/PR workflow.
- `docs/knowledge-precipitation-report-human.md`: human-oriented product rationale supplied by the user.
- `docs/knowledge-precipitation-report-ai.md`: AI-oriented implementation reference supplied by the user.
- `.github/CODEOWNERS`: requires `@a444777` review for every path.
- `.github/pull_request_template.md`: makes scope, tests, and risk acknowledgement explicit.
- `.github/workflows/ci.yml`: runs deterministic quality checks on pushes and PRs.
- `.github/workflows/codeql.yml`: performs Python static security analysis.
- `.github/workflows/release.yml`: publishes the merged `main` image to GHCR.
- `Dockerfile`: builds the minimal runtime image.
- `.dockerignore`: excludes local and Git-only artifacts from build context.
- `.gitignore`: excludes Python caches, virtual environments, and local worktrees.

## Human/agent responsibility boundary

- The agent may create files, run local tests, inspect public GitHub state, and prepare exact commands.
- The user performs account authentication, fork creation, workflow approval, PR review, Ruleset configuration, and merge using the explicitly named account.
- Before every push, verify both the SSH identity and repository-local Git author.
- Never expose secrets to a fork PR and never use `pull_request_target` for contributor code.
- The intentionally unsafe change must remain on `momobiubiu`'s unmerged feature branch and must be removed before approval.

### Task 1: Create the package contract and failing health test

**Files:**
- Create: `app/__init__.py`
- Create: `tests/test_health.py`
- Create: `pyproject.toml`

- [ ] **Step 1: Create the empty application package**

Create `app/__init__.py` with exactly:

```python
"""Feiyu application package."""
```

- [ ] **Step 2: Define the project and test configuration**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "feiyu"
version = "0.1.0"
description = "Minimal governed FastAPI application"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.116,<1",
  "uvicorn[standard]>=0.35,<1",
]

[project.optional-dependencies]
dev = [
  "httpx>=0.28,<1",
  "pytest>=8.4,<9",
  "ruff>=0.12,<1",
]

[tool.hatch.build.targets.wheel]
packages = ["app"]

[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
```

- [ ] **Step 3: Write the failing public-contract test**

Create `tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_returns_ready_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 4: Create a local virtual environment and install development dependencies**

Run:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
```

Expected: installation exits with status 0.

- [ ] **Step 5: Run the test and verify the intended failure**

Run:

```bash
.venv/bin/pytest tests/test_health.py -v
```

Expected: collection fails with `ModuleNotFoundError: No module named 'app.main'`.

- [ ] **Step 6: Commit the red test**

```bash
git add app/__init__.py tests/test_health.py pyproject.toml
git commit -m "test: define health endpoint contract"
```

### Task 2: Implement the minimal FastAPI application

**Files:**
- Create: `app/main.py`
- Test: `tests/test_health.py`

- [ ] **Step 1: Implement only the required endpoint**

Create `app/main.py`:

```python
from fastapi import FastAPI


app = FastAPI(title="Feiyu", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 2: Run the focused test**

Run:

```bash
.venv/bin/pytest tests/test_health.py -v
```

Expected: `1 passed`.

- [ ] **Step 3: Run local quality checks**

Run:

```bash
.venv/bin/ruff check app tests
.venv/bin/pytest
```

Expected: Ruff exits 0 and pytest reports `1 passed`.

- [ ] **Step 4: Commit the implementation**

```bash
git add app/main.py
git commit -m "feat: add health endpoint"
```

### Task 3: Add local repository hygiene and Docker delivery

**Files:**
- Modify: `.gitignore`
- Create: `.dockerignore`
- Create: `Dockerfile`

- [ ] **Step 1: Expand `.gitignore` without removing the worktree rule**

Set `.gitignore` to:

```gitignore
.worktrees/
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.DS_Store
```

- [ ] **Step 2: Create `.dockerignore`**

```dockerignore
.git
.github
.venv
.worktrees
__pycache__
.pytest_cache
.ruff_cache
tests
docs
```

- [ ] **Step 3: Create the runtime image definition**

Create `Dockerfile`:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app

RUN python -m pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: Build the image locally**

Run:

```bash
docker build -t feiyu:local .
```

Expected: exits 0 and creates image `feiyu:local`.

- [ ] **Step 5: Start an isolated verification container**

Run:

```bash
docker run --rm -d --name feiyu-governance-check -p 127.0.0.1:18000:8000 feiyu:local
curl --fail --silent http://127.0.0.1:18000/health
docker stop feiyu-governance-check
```

Expected curl body: `{"status":"ok"}`. The final command removes the container because it was started with `--rm`.

- [ ] **Step 6: Commit container support**

```bash
git add .gitignore .dockerignore Dockerfile
git commit -m "build: add container image"
```

### Task 4: Add human and AI project documentation

**Files:**
- Create: `docs/knowledge-precipitation-report-human.md`
- Create: `docs/knowledge-precipitation-report-ai.md`
- Create: `README.md`
- Create: `CONTRIBUTING.md`

- [ ] **Step 1: Copy the two supplied source documents without rewriting them**

Run:

```bash
cp '/Users/moyunqinghe/个人/学习/createkonwledge/docs/knowledge-precipitation-report-human.md' docs/
cp '/Users/moyunqinghe/个人/学习/createkonwledge/docs/knowledge-precipitation-report-ai.md' docs/
```

Expected: both files exist under `docs/`; `git diff --no-index` against each source shows no content differences.

- [ ] **Step 2: Create the project README**

Create `README.md`:

```markdown
# Feiyu

Feiyu is a minimal FastAPI application used to practise governed, fork-based GitHub delivery before implementing the full knowledge-precipitation system described in `docs/`.

## Local development

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/ruff check app tests
.venv/bin/pytest
.venv/bin/uvicorn app.main:app --reload
```

## Container

```bash
docker build -t feiyu:local .
docker run --rm -p 8000:8000 feiyu:local
curl http://127.0.0.1:8000/health
```

## Governance

Changes to `main` arrive through pull requests. CI, CodeQL, resolved review conversations, and approval from the code owner are required before merge. See [CONTRIBUTING.md](CONTRIBUTING.md).
```

- [ ] **Step 3: Create the fork contribution guide**

Create `CONTRIBUTING.md`:

```markdown
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
```

- [ ] **Step 4: Verify documents and commit**

Run:

```bash
git diff --no-index '/Users/moyunqinghe/个人/学习/createkonwledge/docs/knowledge-precipitation-report-human.md' docs/knowledge-precipitation-report-human.md
git diff --no-index '/Users/moyunqinghe/个人/学习/createkonwledge/docs/knowledge-precipitation-report-ai.md' docs/knowledge-precipitation-report-ai.md
```

Expected: both commands exit 0 with no output.

```bash
git add README.md CONTRIBUTING.md docs/knowledge-precipitation-report-human.md docs/knowledge-precipitation-report-ai.md
git commit -m "docs: add project and contribution guides"
```

### Task 5: Add review ownership and PR evidence capture

**Files:**
- Create: `.github/CODEOWNERS`
- Create: `.github/pull_request_template.md`

- [ ] **Step 1: Define the global Code Owner**

Create `.github/CODEOWNERS`:

```text
* @a444777
```

- [ ] **Step 2: Add the pull-request template**

Create `.github/pull_request_template.md`:

```markdown
## Summary

Describe the user-visible or engineering outcome.

## Verification

- [ ] `ruff check app tests`
- [ ] `pytest`
- [ ] `docker build -t feiyu:local .`

## Risk review

- [ ] No secrets or credentials are included.
- [ ] Workflow or permission changes are called out explicitly.
- [ ] Security-sensitive input and process execution paths were reviewed.
```

- [ ] **Step 3: Commit governance metadata**

```bash
git add .github/CODEOWNERS .github/pull_request_template.md
git commit -m "chore: add review ownership"
```

### Task 6: Add deterministic CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create the least-privilege CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  quality:
    name: quality
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - name: Check out repository
        uses: actions/checkout@v5
      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.12"
          cache: pip
      - name: Install project
        run: python -m pip install -e '.[dev]'
      - name: Run Ruff
        run: ruff check app tests
      - name: Run tests
        run: pytest
```

- [ ] **Step 2: Inspect trigger and permission invariants**

Run:

```bash
rg -n 'pull_request_target|secrets\.|packages: write|contents: write' .github/workflows/ci.yml
```

Expected: no matches.

- [ ] **Step 3: Re-run the same commands CI will execute**

```bash
.venv/bin/ruff check app tests
.venv/bin/pytest
```

Expected: both pass.

- [ ] **Step 4: Commit CI**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add quality checks"
```

### Task 7: Add CodeQL scanning

**Files:**
- Create: `.github/workflows/codeql.yml`

- [ ] **Step 1: Create the CodeQL workflow**

Create `.github/workflows/codeql.yml`:

```yaml
name: CodeQL

on:
  pull_request:
  push:
    branches: [main]
  schedule:
    - cron: "23 3 * * 1"

permissions:
  contents: read
  security-events: write

jobs:
  analyze-python:
    name: analyze-python
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - name: Check out repository
        uses: actions/checkout@v5
      - name: Initialize CodeQL
        uses: github/codeql-action/init@v4
        with:
          languages: python
      - name: Perform CodeQL analysis
        uses: github/codeql-action/analyze@v4
```

- [ ] **Step 2: Inspect the fork-safety invariants**

Run:

```bash
rg -n 'pull_request_target|secrets\.|packages: write|contents: write' .github/workflows/codeql.yml
```

Expected: no matches. `security-events: write` is expected; GitHub handles the restricted fork-PR context for CodeQL uploads.

- [ ] **Step 3: Commit CodeQL**

```bash
git add .github/workflows/codeql.yml
git commit -m "ci: add CodeQL scanning"
```

### Task 8: Add merge-only GHCR delivery

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Create the GHCR publishing workflow**

Create `.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    branches: [main]

permissions:
  contents: read
  packages: write

jobs:
  publish-image:
    name: publish-image
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - name: Check out repository
        uses: actions/checkout@v5
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Extract image metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=raw,value=latest
            type=sha,format=long
      - name: Build and push image
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
```

- [ ] **Step 2: Verify the release cannot run for a PR**

Run:

```bash
rg -n 'pull_request|pull_request_target' .github/workflows/release.yml
```

Expected: no matches.

- [ ] **Step 3: Commit release automation**

```bash
git add .github/workflows/release.yml
git commit -m "ci: publish main image to GHCR"
```

### Task 9: Verify and prepare the upstream bootstrap commit series

**Files:**
- Verify: all repository files

- [ ] **Step 1: Run all local gates**

```bash
.venv/bin/ruff check app tests
.venv/bin/pytest -v
docker build -t feiyu:local .
```

Expected: Ruff exits 0, pytest reports `1 passed`, and Docker builds successfully.

- [ ] **Step 2: Verify workflow safety and YAML readability**

Run:

```bash
rg -n 'pull_request_target' .github/workflows
git diff --check main...HEAD
git status --short --branch
```

Expected: the first command has no matches, diff check has no output, and Git status is clean.

- [ ] **Step 3: Confirm commit attribution before any push**

Run:

```bash
git config user.name
git config user.email
git log --format='%h %an <%ae> %s' --reverse main..HEAD
```

Expected: new implementation commits belong to `a444777` with a GitHub-associated noreply email. If not, stop and correct local commit attribution before pushing.

- [ ] **Step 4: Merge the implementation branch locally into `main` only after verification**

From the primary worktree:

```bash
git switch main
git merge --ff-only plan/github-governance-lab
```

Expected: fast-forward merge only; no merge commit.

### Task 10: Authenticate `a444777`, push bootstrap, and observe initial workflows

**Files:**
- Remote mutation: `a444777/feiyu`

- [ ] **Step 1: Create or identify the Maintainer SSH key**

User action as `a444777`: add the Maintainer public key under GitHub **Settings → SSH and GPG keys**. Do not paste the private key into chat.

- [ ] **Step 2: Configure an SSH alias locally**

Add this block to `~/.ssh/config`, substituting the actual private-key path:

```sshconfig
Host github-a444777
  HostName github.com
  User git
  IdentityFile /absolute/path/to/a444777-private-key
  IdentitiesOnly yes
```

- [ ] **Step 3: Verify the remote account identity**

Run:

```bash
ssh -T git@github-a444777
```

Expected: GitHub identifies the account as `a444777`. If another username appears, stop.

- [ ] **Step 4: Switch upstream origin to the verified alias**

```bash
git remote set-url origin git@github-a444777:a444777/feiyu.git
git remote -v
```

Expected: both origin URLs identify `a444777/feiyu` through `github-a444777`.

- [ ] **Step 5: Push the initial `main` only after explicit user confirmation**

```bash
git push -u origin main
```

Expected: the empty remote receives the local commit history.

- [ ] **Step 6: Observe initial GitHub Actions**

User action as `a444777`: open **Actions** and wait for:

- `CI / quality`: success.
- `CodeQL / analyze-python`: success.
- `Release / publish-image`: success.

If any job fails, inspect its log and fix the workflow on an unprotected bootstrap branch before enabling the Ruleset.

- [ ] **Step 7: Verify the initial package**

User action as `a444777`: open the repository/package page and confirm a package named `feiyu` exists. Record the actual SHA tag produced by `docker/metadata-action`; it will start with `sha-` followed by the full commit hash rather than using a bare SHA.

### Task 11: Configure repository settings and the active Ruleset

**Files:**
- Remote configuration: `a444777/feiyu`

- [ ] **Step 1: Configure merge methods**

User action as `a444777`, **Settings → General → Pull Requests**:

- Enable **Allow squash merging**.
- Disable **Allow merge commits**.
- Disable **Allow rebase merging**.
- Enable **Automatically delete head branches**.

- [ ] **Step 2: Verify fork workflow approval policy**

User action as `a444777`, **Settings → Actions → General → Fork pull request workflows**:

- Select **Require approval for first-time contributors**.
- Keep workflow permissions at the least privilege compatible with the repository workflows.

- [ ] **Step 3: Create the Ruleset shell**

User action as `a444777`, **Settings → Rules → Rulesets → New branch ruleset**:

- Name: `main-governance`.
- Enforcement status: `Active`.
- Target branches: include the default branch.
- Bypass list: empty.

- [ ] **Step 4: Configure branch and review rules**

Enable:

- Restrict deletions.
- Block force pushes.
- Require a pull request before merging.
- Required approvals: `1`.
- Require review from Code Owners.
- Dismiss stale pull request approvals when new commits are pushed.
- Require conversation resolution before merging.

- [ ] **Step 5: Configure required status checks from real completed runs**

Enable **Require status checks to pass** and **Require branches to be up to date before merging**. Select the exact checks exposed by the successful bootstrap runs:

- `quality` from GitHub Actions.
- `analyze-python` from GitHub Actions.

Do not create similarly spelled free-text checks.

- [ ] **Step 6: Configure CodeQL merge protection**

Enable **Require code scanning results**:

- Tool: CodeQL.
- Security alert threshold: High or higher.

If the UI presents separate security and alert thresholds, record the selected values in the experiment notes.

- [ ] **Step 7: Save and inspect the active rule**

Expected: `main-governance` is Active, targets `main`, and shows no bypass actor. Do not test protection by force-pushing or deleting `main`.

### Task 12: Fork and isolate the first-time contributor identity

**Files:**
- Remote fork: `momobiubiu/feiyu`
- Local contributor clone: a separate directory from the Maintainer worktree

- [ ] **Step 1: Fork using the contributor account**

User action: sign out or switch to `momobiubiu`, open `a444777/feiyu`, click **Fork**, and create `momobiubiu/feiyu`.

- [ ] **Step 2: Create and register a contributor SSH key**

User action as `momobiubiu`: add a different public key under **Settings → SSH and GPG keys**. Never share the private key.

- [ ] **Step 3: Configure the contributor alias**

Add to `~/.ssh/config`:

```sshconfig
Host github-momobiubiu
  HostName github.com
  User git
  IdentityFile /absolute/path/to/momobiubiu-private-key
  IdentitiesOnly yes
```

- [ ] **Step 4: Verify contributor identity**

```bash
ssh -T git@github-momobiubiu
```

Expected: GitHub identifies `momobiubiu`. Otherwise stop.

- [ ] **Step 5: Clone the fork and configure remotes**

From the parent learning directory:

```bash
git clone git@github-momobiubiu:momobiubiu/feiyu.git feiyu-contributor
cd feiyu-contributor
git remote add upstream https://github.com/a444777/feiyu.git
git remote -v
```

Expected:

```text
origin   git@github-momobiubiu:momobiubiu/feiyu.git
upstream https://github.com/a444777/feiyu.git
```

- [ ] **Step 6: Set repository-local contributor attribution**

```bash
git config user.name momobiubiu
git config user.email momobiubiu@users.noreply.github.com
git config --local --get-regexp '^user\.'
```

Expected: only contributor identity values are shown for this clone.

### Task 13: Submit a deliberately unsafe first PR

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_health.py`

- [ ] **Step 1: Synchronize and create the feature branch**

```bash
git fetch upstream
git switch main
git merge --ff-only upstream/main
git push origin main
git switch -c feature/expression-preview
```

- [ ] **Step 2: Add the intentionally unsafe endpoint**

Append to `app/main.py`:

```python
import subprocess

from fastapi import Query


@app.get("/preview")
def preview(expression: str = Query()) -> dict[str, str]:
    completed = subprocess.run(
        expression,
        shell=True,
        check=True,
        capture_output=True,
        text=True,
    )
    return {"output": completed.stdout}
```

This code is intentionally vulnerable because untrusted HTTP input reaches a shell. Do not run this endpoint locally and do not merge it.

- [ ] **Step 3: Add a non-executing route-presence test**

Append to `tests/test_health.py`:

```python
def test_preview_route_is_registered() -> None:
    paths = {route.path for route in app.routes}

    assert "/preview" in paths
```

- [ ] **Step 4: Run deterministic local checks only**

```bash
.venv/bin/ruff check app tests
.venv/bin/pytest
```

Expected: both pass. Do not call `/preview`; the experiment is designed to show that ordinary tests can pass while CodeQL blocks the PR.

- [ ] **Step 5: Commit and verify contributor attribution**

```bash
git add app/main.py tests/test_health.py
git commit -m "feat: add expression preview"
git show -s --format='%an <%ae>' HEAD
```

Expected: `momobiubiu` with the contributor's GitHub-associated email.

- [ ] **Step 6: Push to the contributor fork**

```bash
git push -u origin feature/expression-preview
```

- [ ] **Step 7: Open the upstream PR as `momobiubiu`**

Base: `a444777/feiyu:main`; compare: `momobiubiu/feiyu:feature/expression-preview`.

PR title:

```text
feat: add expression preview
```

Complete the template truthfully; note that the change introduces a process-execution path for the governance experiment.

### Task 14: Observe workflow approval and CodeQL blocking

**Files:**
- Remote PR state only

- [ ] **Step 1: Capture the pre-approval state**

Expected before Maintainer approval:

- PR exists but merge is blocked.
- Fork workflows are awaiting approval.
- `quality` and `analyze-python` have not completed.
- Code Owner approval is absent.

- [ ] **Step 2: Inspect contributor changes as `a444777`**

User action: inspect **Files changed**, especially any `.github/workflows/` differences. This PR should not change workflow files.

- [ ] **Step 3: Approve workflows, not the PR**

User action as `a444777`: click **Approve workflows to run**.

Expected: CI and CodeQL begin. Do not submit an approving PR review.

- [ ] **Step 4: Verify the split outcome**

Expected:

- `quality` succeeds.
- CodeQL analysis completes and creates a high-or-higher command-injection alert on the changed line.
- `main-governance` keeps merge disabled.

If CodeQL does not raise the alert, inspect the CodeQL run and code-scanning results. Replace the demonstration only with another minimal Python dataflow supported by CodeQL; do not weaken or remove the merge rule.

- [ ] **Step 5: Leave an actionable review comment**

User action as `a444777`: request changes on the vulnerable line, explaining that untrusted input reaches `shell=True` and must be replaced with a non-shell allowlist. Keep the conversation unresolved.

### Task 15: Fix the same PR with a deterministic operation allowlist

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_health.py`

- [ ] **Step 1: Replace process execution with a typed allowlist**

Replace the unsafe imports and endpoint in `app/main.py` so the complete file becomes:

```python
from typing import Literal

from fastapi import FastAPI


app = FastAPI(title="Feiyu", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/preview")
def preview(operation: Literal["uppercase", "lowercase"], text: str) -> dict[str, str]:
    transforms = {
        "uppercase": str.upper,
        "lowercase": str.lower,
    }
    return {"output": transforms[operation](text)}
```

- [ ] **Step 2: Replace the route-presence test with behavioral and rejection tests**

Set `tests/test_health.py` to:

```python
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_returns_ready_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_preview_applies_allowlisted_operation() -> None:
    response = client.get(
        "/preview",
        params={"operation": "uppercase", "text": "Feiyu"},
    )

    assert response.status_code == 200
    assert response.json() == {"output": "FEIYU"}


def test_preview_rejects_unknown_operation() -> None:
    response = client.get(
        "/preview",
        params={"operation": "shell", "text": "whoami"},
    )

    assert response.status_code == 422
```

- [ ] **Step 3: Run all local checks**

```bash
.venv/bin/ruff check app tests
.venv/bin/pytest -v
docker build -t feiyu:fixed .
```

Expected: Ruff passes, pytest reports `3 passed`, Docker builds.

- [ ] **Step 4: Commit and push the fix to the same branch**

```bash
git add app/main.py tests/test_health.py
git commit -m "fix: replace shell execution with operation allowlist"
git push origin feature/expression-preview
```

Expected: the existing PR updates; no second PR is opened.

- [ ] **Step 5: Observe renewed gates**

Expected:

- CI and CodeQL run against the new commit.
- Any prior approving review would be stale because the diff changed.
- The unresolved conversation continues to block merge.
- If GitHub requires another workflow approval, `a444777` inspects the new diff before approving it.

### Task 16: Complete review, squash merge, and verify GHCR

**Files:**
- Remote PR and package state

- [ ] **Step 1: Verify the fixed PR checks**

Expected:

- `quality`: success.
- `analyze-python`: success.
- No high-or-higher CodeQL alert remains on the PR diff.
- Branch is up to date with `main`.

- [ ] **Step 2: Resolve the security conversation**

User action: `momobiubiu` replies with the fix evidence; `a444777` verifies the diff and resolves the conversation.

- [ ] **Step 3: Submit Code Owner approval**

User action as `a444777`: submit **Approve** review only after all checks and the corrected code have been inspected.

- [ ] **Step 4: Confirm all Ruleset gates are satisfied**

Expected: merge is enabled only now. If disabled, expand the merge status panel and identify the unmet named rule rather than bypassing it.

- [ ] **Step 5: Squash merge and delete the contributor branch**

User action as `a444777`: choose **Squash and merge**. Confirm the resulting `main` commit has a clear message and that GitHub offers or performs contributor-branch deletion.

- [ ] **Step 6: Verify post-merge CD**

Expected: `Release / publish-image` runs only after the `main` push and succeeds. Record the merge commit SHA and the corresponding image tag that starts with `sha-` followed by the full commit hash.

- [ ] **Step 7: Pull and run the published image**

After the package is publicly readable, run:

```bash
docker pull ghcr.io/a444777/feiyu:latest
docker run --rm -d --name feiyu-ghcr-check -p 127.0.0.1:18001:8000 ghcr.io/a444777/feiyu:latest
curl --fail --silent http://127.0.0.1:18001/health
docker stop feiyu-ghcr-check
```

Expected curl body: `{"status":"ok"}`.

### Task 17: Synchronize the contributor fork and close the experiment

**Files:**
- Remote fork state: `momobiubiu/feiyu`

- [ ] **Step 1: Synchronize contributor `main` from upstream**

In the contributor clone:

```bash
git fetch upstream
git switch main
git merge --ff-only upstream/main
git push origin main
```

Expected: contributor local `main` and `momobiubiu/feiyu:main` point to the upstream merge commit.

- [ ] **Step 2: Delete the merged local feature branch**

```bash
git branch -d feature/expression-preview
```

Expected: deletion succeeds because its changes are contained in upstream `main` after squash only if Git recognizes equivalence; if Git refuses due to squash history, verify the PR is merged and use `git branch -D feature/expression-preview` only with explicit user approval.

- [ ] **Step 3: Compare all three `main` references**

```bash
git fetch origin
git fetch upstream
git rev-parse main
git rev-parse origin/main
git rev-parse upstream/main
```

Expected: all three commands print the same commit SHA. This proves the contributor's local `main`, personal fork, and upstream repository are synchronized.

- [ ] **Step 4: Preserve evidence outside repository mutation**

Copy the URLs of the initial CI run, initial CodeQL run, first PR, blocking code-scanning alert, fixed CodeQL run, squash commit, and GHCR package into the user's learning notes. This is a human note-taking action; it does not create another PR or expand the repository scope.

## Final completion checklist

- [ ] Local Ruff, pytest, and Docker verification passed.
- [ ] Initial CI, CodeQL, and GHCR workflows passed before protection was activated.
- [ ] `main-governance` is Active with no bypass actor.
- [ ] The first fork PR required workflow approval.
- [ ] The unsafe revision was blocked and never merged.
- [ ] The fixed revision passed CI and CodeQL.
- [ ] Code Owner approval and conversation resolution were required.
- [ ] The PR was squash-merged.
- [ ] GHCR `latest` and immutable SHA-derived tags exist.
- [ ] The GHCR container passed `/health` verification.
- [ ] The contributor fork is synchronized.
- [ ] The user retained links to the workflow, PR, alert, merge, and package evidence.
