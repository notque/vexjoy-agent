# CI/CD Security Patterns

Load when reviewing GitHub Actions workflows, CI pipeline configs, action definitions, or CI build scripts.

CI/CD pipelines run with elevated privileges: write access, secrets, OIDC tokens, and publishing credentials. Separate privileged and unprivileged execution, pin dependencies to immutable refs, treat all PR-controlled content as untrusted.

---

## Run Untrusted Code in Unprivileged Workflows

Use `pull_request` trigger for fork contributions (read-only, no secrets). Use `pull_request_target` only when the workflow needs write access and does not execute PR-controlled code.

### Correct Pattern

```yaml
on: pull_request
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - run: npm ci
      - run: npm test
```

For reporting results, use a separate `workflow_run` job treating artifacts as data, not code:

```yaml
on:
  workflow_run:
    workflows: ["Test"]
    types: [completed]
permissions:
  pull-requests: write
jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
        with:
          run-id: ${{ github.event.workflow_run.id }}
      - run: cat results.json | jq '.summary' > comment.md
```

### Why This Matters

`pull_request_target` runs with full secrets and write permissions. Checking out and executing fork code gives the fork code execution with trusted credentials ("pwn request").

### Detection

```bash
rg -n 'pull_request_target' .github/workflows/
rg -n 'github\.event\.pull_request\.head\.sha|github\.head_ref' .github/workflows/
rg -B5 -A5 'npm install|npm test|pip install|make |pytest|cargo test|go test' .github/workflows/
```

---

## Pass Untrusted Values Through Environment Variables

GitHub Actions expressions (`${{ }}`) in `run:` blocks are string-interpolated before shell execution. Attacker-controlled content (PR title, issue body, comment, branch name) enables shell injection. Pass through env vars instead.

### Correct Pattern

```yaml
- env:
    PR_TITLE: ${{ github.event.pull_request.title }}
  run: printf '%s\n' "$PR_TITLE"
```

For `actions/github-script`, pass via `env:` and read with `process.env`:

```yaml
- uses: actions/github-script@v7
  env:
    ISSUE_TITLE: ${{ github.event.issue.title }}
  with:
    script: |
      const title = process.env.ISSUE_TITLE;
      await github.rest.issues.createComment({
        owner: context.repo.owner, repo: context.repo.repo,
        issue_number: context.issue.number, body: `Triaged: ${title}`,
      });
```

Safe delimiter-based output for `$GITHUB_OUTPUT`:

```yaml
- run: |
    delimiter="$(openssl rand -hex 16)"
    echo "title<<${delimiter}" >> "$GITHUB_OUTPUT"
    echo "$PR_TITLE" >> "$GITHUB_OUTPUT"
    echo "${delimiter}" >> "$GITHUB_OUTPUT"
  env:
    PR_TITLE: ${{ github.event.pull_request.title }}
```

### Why This Matters

Expression injection is shell injection via CI. Applies to issue titles, comment bodies, review bodies, branch names, filenames, commit messages, and labels.

**CVEs:** CVE-2026-27701 (LiveCode), Sentry getsentry `0898b3d8`, Sentry `e93ee1ce`.

### Detection

```bash
rg -n '\$\{\{.*github\.event\.(pull_request\.(title|body)|issue\.(title|body)|comment\.body|review\.body|discussion\.(title|body))' .github/workflows/
rg -n '\$\{\{' .github/workflows/ | rg 'script:'
rg -n '\$\{\{.*github\.(head_ref|event\.commits)' .github/workflows/
rg -n 'GITHUB_ENV|GITHUB_OUTPUT|GITHUB_PATH' .github/workflows/ | rg '\$\{\{'
```

---

## Gate Comment-Triggered Commands with Author Association

`issue_comment` workflows must verify commenter's `author_association` against `MEMBER`, `OWNER`, or `COLLABORATOR` before executing commands.

### Correct Pattern

```yaml
on: issue_comment
jobs:
  deploy-preview:
    if: >
      contains(github.event.comment.body, '/deploy') &&
      contains(fromJSON('["MEMBER","OWNER","COLLABORATOR"]'),
               github.event.comment.author_association)
    permissions:
      contents: read
      pull-requests: write
    runs-on: ubuntu-latest
    steps:
      - env:
          COMMENT_BODY: ${{ github.event.comment.body }}
        run: ./ci/deploy-preview.sh "$COMMENT_BODY"
```

For `/ok-to-test` approval, pin checkout to the approved SHA, not current head (TOCTOU risk).

### Why This Matters

Without authorization, any GitHub user who can comment on an issue triggers privileged CI actions.

**CVEs:** CVE-2025-53104 (gluestack-ui).

### Detection

```bash
rg -n 'issue_comment|discussion' .github/workflows/
rg -l 'issue_comment' .github/workflows/ | xargs rg -L 'author_association'
rg -n "contains.*'/deploy\|contains.*'/test\|contains.*'/ok-to" .github/workflows/
```

---

## Pin Third-Party Actions to Full Commit SHAs

Reference third-party actions by 40-character SHA. Tags are mutable — maintainers or attackers can rewrite them.

### Correct Pattern

```yaml
steps:
  - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
  - uses: actions/setup-node@39370e3970a6d050c480ffad4ff0ed4d3fdee5af  # v4.1.0
  - uses: tj-actions/changed-files@a4ca7c0a052d49bbf8e69ddca9a3f53dac15c95e  # v45.0.10
```

Use Dependabot for SHA pin updates:

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

### Why This Matters

March 2025: `tj-actions/changed-files` tags v1-v45 were rewritten to exfiltrate secrets from 23,000+ repos via compromised upstream `reviewdog/action-setup`.

**CVEs:** CVE-2025-30066, CVE-2025-30154.

First-party actions (`actions/*`, `github/*`) on tags are acceptable.

### Detection

```bash
rg -n 'uses:' .github/workflows/ | rg -v 'actions/|github/' | rg -v '@[0-9a-f]{40}'
rg -n 'uses:' .github/workflows/ | rg -v 'actions/|github/' | rg '@v[0-9]|@main|@master|@latest'
```

---

## Restrict Artifact Upload Paths and Disable Credential Persistence

Upload only specific build output, never workspace root. Disable credential persistence on checkout.

### Correct Pattern

```yaml
steps:
  - uses: actions/checkout@v4
    with:
      persist-credentials: false
  - run: ./build.sh
  - uses: actions/upload-artifact@v4
    with:
      name: build-output
      path: dist/
```

### Why This Matters

`actions/checkout` persists GITHUB_TOKEN in `.git/config` by default. Uploading workspace root includes it. Public repo artifacts are downloadable by anyone (ArtiPACKED attack, Palo Alto Unit 42 Aug 2024).

### Detection

```bash
rg -n 'upload-artifact' .github/workflows/ -A5 | rg "path: '\.'|path: \./?$|path: \./?"
rg -n 'actions/checkout' .github/workflows/ -A3 | rg -v 'persist-credentials: false'
```

---

## Declare Secrets Explicitly in Reusable Workflows

Reusable workflows (`on: workflow_call`) must declare every consumed secret under `secrets:`. Undeclared secrets mask the security surface.

### Correct Pattern

```yaml
on:
  workflow_call:
    inputs:
      target:
        type: string
        required: true
    secrets:
      DEPLOY_KEY:
        required: true

permissions:
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - run: ./bin/deploy "$TARGET"
        env:
          TARGET: ${{ inputs.target }}
          DEPLOY_KEY: ${{ secrets.DEPLOY_KEY }}
```

### Why This Matters

Without declarations, reviewers cannot see which secrets a callee consumes. Without `permissions:`, the callee inherits caller's broad scope.

### Detection

```bash
rg -l 'workflow_call' .github/workflows/
rg -l 'workflow_call' .github/workflows/ | xargs rg 'secrets\.' | rg -v 'secrets:\|GITHUB_TOKEN'
rg -l 'workflow_call' .github/workflows/ | xargs rg -L 'permissions:'
```
