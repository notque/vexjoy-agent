---
description: "OpenStack Python development: Nova, Neutron, Cinder services, Oslo libraries, WSGI, RPC versioning, hacking rules, Tempest, tox gates."
type: reference
---

# OpenStack Python Development

Rules for building OpenStack-compliant services, plugins, and components with
strict adherence to community standards.

Not for: general Python features, debugging, or web frameworks outside
OpenStack (load `python-general.md`); running Python lint, format, and test gates
alone (use the `code-quality` skill); SQLite and Peewee ORM work (use the `data`
skill).

## Expertise areas

- **Architecture:** core services (Nova, Neutron, Cinder, Keystone, Glance,
  Swift), service interactions, API patterns, policy enforcement, quotas.
- **Oslo libraries:** oslo.config, oslo.messaging (RPC/notifications), oslo.db
  (sessions/migrations), oslo.log (structured logging), oslo.policy (RBAC).
- **Service development:** WSGI with Paste Deploy, RPC versioning for rolling
  upgrades, Alembic migrations, eventlet concurrency.
- **Testing:** Tempest integration tests, tempest-lib service clients, oslotest
  fixtures, functional tests, stevedore plugin tests.
- **Workflow:** Gerrit review, Zuul CI, DevStack, OpenStack release cycles,
  upgrade paths.

## Coding standards

- PEP 8 with OpenStack hacking rules (H* series).
- No bare `except:`; always catch specific exceptions.
- OpenStack import ordering.
- Oslo libraries for config, logging, messaging, and db.
- i18n with `_()`.
- API microversioning for backward compatibility.

## Priorities

1. **Oslo library usage:** oslo.config, oslo.messaging, oslo.db instead of
   reinventing.
2. **Hacking compliance:** all code passes `tox -e pep8`.
3. **RPC versioning:** version negotiation for rolling upgrades.
4. **i18n:** every user-facing string uses `_()`.
5. **Tempest:** integration tests for all API operations.

## Hard rules

- **Specific exceptions** in every `except` clause (H201).
- **Oslo libraries** for config, logging, messaging, and db; rely on existing
  implementations.
- **Eventlet monkey-patching:** `eventlet.monkey_patch()` before other imports in
  service entry points.
- **i18n:** all user-facing strings use `_()`.
- **Hacking compliance:** `tox -e pep8` passes.

## Defaults (on unless disabled)

- Microversions for API changes.
- oslo.policy authorization checks on all API operations.
- Alembic migrations with upgrade/downgrade paths for schema changes.
- More than 80% unit coverage with oslotest fixtures and proper mocking.
- Versioned RPC APIs with version negotiation for rolling upgrades.

## Off unless requested

- DevStack plugin (only when local dev environment config is needed).
- Heat templates (only when orchestration integration is requested).
- Horizon dashboard (only when UI integration is requested).
- Rally benchmarks (only when performance scenarios are needed).

## Verification STOP blocks

Mandatory. Do not skip them even when confident.

- **After writing code:** STOP. Run `tox -e py3` and show the output.
- **After claiming a fix:** STOP. Confirm the fix addresses the root cause, not
  the symptom. Re-read the original error and confirm it cannot recur.
- **After completing the task:** STOP. Run `tox -e pep8` and `tox -e py3` before
  reporting. Show the actual output. Hacking compliance is non-negotiable.
- **Before editing a file:** read it first.
- **Before committing:** do not commit to main. Create a feature branch.

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| oslo.config option registration, oslo.log setup, oslo.messaging transport, oslo.db sessions, oslo.policy enforcement, `CONF.register_opts`, `enginefacade`, `get_rpc_transport` | [oslo-patterns.md](python-openstack/oslo-patterns.md) | Full Oslo library reference |
| quick Oslo code examples: oslo.config integration, RPC server, Alembic migration | [openstack-patterns.md](python-openstack/openstack-patterns.md) | Short code examples; points to the full Oslo reference |
| H201, H301, H303, H304, H501, `tox -e pep8`, import ordering, bare except, wildcard imports, i18n hacking rules, flake8 H-series | [hacking-rules.md](python-openstack/hacking-rules.md) | Hacking rule reference |
| RPC version negotiation, rolling upgrades, `RPC_API_VERSION`, `prepare(version=X)`, `version_cap`, `RPCVersionCapError`, oslo.messaging Target | [rpc-versioning.md](python-openstack/rpc-versioning.md) | RPC versioning reference |
| quick error lookup: bare except (H201), missing i18n, import order (H301-H307) | [error-handling.md](python-openstack/error-handling.md) | Error-to-fix examples for the three most common hacking violations |
| failure mode list, rationalization table, blocker criteria (new Oslo library, API breaking change, database schema, RPC signature) | [preferred-patterns.md](python-openstack/preferred-patterns.md) | OpenStack failure modes and stop conditions |
| scope, Implementation Schema, final output template | [output-format.md](python-openstack/output-format.md) | Four-phase schema (analyze, design, implement, validate) and in/out-of-scope lists |
| general Python rules (typing, ruff, pytest) | [python-general.md](python-general.md) | Base Python guidance |
| cleanup, linting, formatting, quality gates | the `code-quality` skill | Shared quality-gate workflow |
