---
name: programming
description: "Apply repository-specific language contracts for Go—especially SAPCC/go-bits—and a small set of version-sensitive Kotlin, PHP, Swift, and TypeScript boundaries. General language programming needs no skill."
user-invocable: false
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit, Task, Skill]
routing:
  force_route: true
  not_for: "general language syntax, ordinary testing patterns, Python, or debugging"
  triggers: [.go, go test, "*_test.go", goroutine, sync.Mutex, context.Context, Go code review, Go lint, sapcc, go-bits, make check, Go version migration, kotlin coroutines, kotlin Flow, suspend function, kotlin testing, kotest, Kotlin cancellation, php quality, php code review, PSR standards, phpstan, phpunit, PHP version compatibility, swift concurrency, swift async await, Swift Actor, XCTest, Swift actor reentrancy, TypeScript check, tsc noEmit, tsc errors]
  pairs_with: [golang-general-engineer, kotlin-general-engineer, php-general-engineer, swift-general-engineer, typescript-frontend-engineer]
  category: language
---

# Programming

Repository instructions, toolchain versions, and existing conventions outrank
this skill. Use it only when one of the contracts below changes the action; do
not load it as a general language tutorial.

## Go

Read `go.mod`, repository instructions, and the project’s own check targets
before choosing commands or language features. For a SAPCC repository, load
[references/sapcc-go.md](references/sapcc-go.md) only when `go.mod` contains
`github.com/sapcc/go-bits`. The reference records conventions that intentionally
diverge from generic Go advice.

The SAPCC scanners in `scripts/check-sapcc-*.sh` are narrow heuristics. They all
support `--help`, `--json`, and `--limit`; exit 0 means clean, 1 means findings,
and 2 means scanner/usage error. Run only scanners relevant to changed code and
inspect every hit rather than treating regex output as proof:

- `check-sapcc-identify-endpoint.sh`: handlers lacking early endpoint identity;
- `check-sapcc-auth-ordering.sh`: likely data access before authorization;
- `check-sapcc-json-strict.sh`: decoder flows lacking unknown-field rejection;
- `check-sapcc-httptest.sh`: removed or noncanonical HTTP-test APIs;
- `check-sapcc-time-now.sh`: direct clocks in testable code;
- `check-sapcc-todo-format.sh`: TODOs without local context.

Use repository checks (`make check`, `go test ./...`, race tests, generated-code
checks) when they exist. Do not impose a universal command set or rewrite code
merely to match a style guide.

## Version-sensitive boundaries

Load [references/version-boundaries.md](references/version-boundaries.md) when a
task involves a toolchain upgrade, concurrency/cancellation behavior, or feature
availability across Go, Kotlin, PHP, or Swift. Confirm the target version from
the repository; never infer it from the current machine.

## TypeScript check-only requests

Use the affected package’s checked-in `tsconfig.json` and local TypeScript
binary. Do not let `npx` download a compiler. Run the repository script when one
exists; otherwise use the local equivalent of `tsc --noEmit --project <config>`.
Do not add `--strict`, `--skipLibCheck`, or config changes unless requested.
Capture the exit code and preserve `file:line:column`, `TS####`, and message.
Distinguish compiler absence/configuration failure from type diagnostics. In a
monorepo, name every checked and omitted package; a package pass is not a
repository pass. Avoid incremental output that writes build-info during a
read-only check.

## Completion

Report which repository/version contract changed the work, commands actually
run, and unresolved compatibility assumptions. A failing local check is evidence;
do not reinterpret it as a style disagreement.
