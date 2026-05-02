# OpenStack Preferred Patterns

## Use Oslo Libraries
**Signal**: Custom config/logging/RPC instead of Oslo
**Preferred action**: Use oslo.config, oslo.log, oslo.messaging

## Catch Specific Exceptions
**Signal**: `except:` without type
**Preferred action**: `except SpecificException:`

## Version All RPC Changes
**Signal**: RPC method signature changes without version bump
**Preferred action**: Increment RPC_API_VERSION, handle both old and new signatures

## Anti-Rationalization

See `shared-patterns/anti-rationalization-core.md` for universal patterns.

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "Bare except is simpler" | H201 violation | Catch specific exceptions |
| "Custom config is more flexible" | Violates OpenStack standards | Use oslo.config |
| "i18n adds complexity" | Required for OpenStack | Wrap user strings with _() |
| "RPC versioning is overkill" | Required for rolling upgrades | Version all RPC APIs |
| "Local imports avoid circular deps" | H302-H307 violations | Fix architecture, not import order |

## Blocker Criteria

STOP and ask the user when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| New Oslo library needed | May require graduation | "Use existing Oslo library or propose new?" |
| API breaking change | Requires microversion | "Microversion or deprecation cycle?" |
| Database schema change | Needs migration strategy | "Online (contract/expand) or offline?" |
| RPC signature change | Affects rolling upgrades | "Bump version or add new method?" |

### Always Confirm Before Acting On
- Oslo library selection
- API versioning strategy
- Database migration approach
- RPC version increment timing
