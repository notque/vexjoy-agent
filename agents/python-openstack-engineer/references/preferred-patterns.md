# OpenStack Preferred Patterns

Common OpenStack development mistakes and their corrections.

## ❌ Reinventing Oslo Libraries
**What it looks like**: Implementing custom config/logging/RPC instead of using Oslo
**Why wrong**: Violates OpenStack standards, incompatible with community tools
**✅ Do instead**: Use oslo.config, oslo.log, oslo.messaging

## ❌ Bare Except Clauses
**What it looks like**: `except:` without exception type
**Why wrong**: H201 hacking rule violation, catches SystemExit/KeyboardInterrupt
**✅ Do instead**: `except SpecificException:`

## ❌ Missing RPC Versioning
**What it looks like**: Changing RPC method signatures without version bump
**Why wrong**: Breaks rolling upgrades
**✅ Do instead**: Increment RPC_API_VERSION and handle both old and new signatures

## Anti-Rationalization

See `shared-patterns/anti-rationalization-core.md` for universal patterns.

### Domain-Specific Rationalizations

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "Bare except is simpler" | H201 hacking rule violation | Catch specific exceptions |
| "Custom config is more flexible" | Violates OpenStack standards | Use oslo.config |
| "i18n adds complexity" | Required for OpenStack projects | Wrap user strings with _() |
| "RPC versioning is overkill" | Required for rolling upgrades | Version all RPC APIs |
| "Local imports avoid circular deps" | H302-H307 hacking violations | Fix architecture, not import order |

## Blocker Criteria

STOP and ask the user (get explicit confirmation) when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| New Oslo library needed | May require oslo-incubator graduation | "Use existing Oslo library or propose new one?" |
| API breaking change | Requires microversion strategy | "Implement microversion or deprecation cycle?" |
| Database schema change | Needs migration strategy | "Online migration (contract/expand) or offline?" |
| RPC signature change | Affects rolling upgrades | "Bump RPC version or add new method?" |

### Always Confirm Before Acting On
- Oslo library selection (when multiple options available)
- API versioning strategy (microversion vs deprecation)
- Database migration approach (online vs offline)
- RPC version increment timing
