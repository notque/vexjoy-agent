# OpenStack RPC Versioning Reference

> **Scope**: oslo.messaging RPC API version negotiation for zero-downtime rolling upgrades in OpenStack services. Does not cover REST API microversioning (see Nova/Cinder API versioning docs).
> **Version range**: oslo.messaging 14.x+, used with OpenStack 2023.x+ (Antelope/Bobcat)
> **Generated**: 2026-04-09 — verify against https://docs.openstack.org/oslo.messaging/latest/

---

## Overview

OpenStack services update RPC API versions to allow older nodes to coexist with newer ones during rolling upgrades. The server pins its minimum version; the client negotiates down. Failing to version RPC changes causes `RPCVersionCapError` on mixed-version deployments — a production blocker during upgrades.

---

## Version Negotiation Model

```
Client (new node)        Transport        Server (old node)
     |                      |                    |
     | prepare(version='1.5')|                    |
     |--------------------> |                    |
     |                      | version_cap=1.3    |
     |                      | (server cap known) |
     |  RPCVersionCapError   |                    |
     | <------------------  |                    |
```

`RPC_API_VERSION` on the manager class is the **server's maximum** — what it can handle.
`version_cap` on the client side is the **client's declared maximum** — what it will send.
`prepare(version=X)` on a call sets what **this specific call** requires.

---

## Pattern Table

| Scenario | Version Bump | Server Change | Client Change |
|----------|-------------|---------------|---------------|
| New optional argument (with default) | Minor (`1.2` → `1.3`) | Accept new arg, keep backward default | `prepare(version='1.3')` before calls using new arg |
| New required method | Minor (`1.2` → `1.3`) | Add new method | `prepare(version='1.3')` for new method calls |
| Remove argument | Major (`1.x` → `2.0`) | New major series | Both sides must be updated simultaneously |
| Change argument type | Major (`1.x` → `2.0`) | New major series | Treat as incompatible change |

---

## Correct Patterns

### Server Side — Versioned RPC Manager

```python
import oslo_messaging as messaging

class MyServiceManager(manager.Manager):
    """RPC server — receives calls from clients."""

    # Increment minor when adding new methods or optional args.
    # Increment major only when removing old methods/args.
    RPC_API_VERSION = '1.4'

    target = messaging.Target(version=RPC_API_VERSION)

    def create_resource(self, context, name, properties=None):
        """Available since 1.0. `properties` added in 1.2."""
        # Handle callers from before 1.2 (properties=None)
        if properties is None:
            properties = {}
        return db.resource_create(context, name, properties)

    def resize_resource(self, context, resource_id, new_size,
                        preserve_data=False):
        """Added in 1.4. `preserve_data` added in 1.4."""
        return db.resource_resize(context, resource_id,
                                  new_size, preserve_data)
```

**Why**: `RPC_API_VERSION` on `target` tells oslo.messaging what this server supports. Old clients sending `version='1.1'` still match because `1.1 <= 1.4`.

---

### Client Side — Version-Pinned Calls

```python
import oslo_messaging as messaging
from oslo_config import cfg

CONF = cfg.CONF

class MyServiceAPI:
    """Client stub — used by other services to call MyService."""

    RPC_API_VERSION = '1.4'

    def __init__(self):
        transport = messaging.get_rpc_transport(CONF)
        target = messaging.Target(
            topic='myservice',
            version=self.RPC_API_VERSION,
        )
        self._client = messaging.get_rpc_client(transport, target)

    def create_resource(self, context, name):
        """Basic create — works against servers >= 1.0."""
        cctxt = self._client.prepare(version='1.0')
        return cctxt.call(context, 'create_resource', name=name)

    def create_resource_with_props(self, context, name, properties):
        """Requires server >= 1.2 (properties argument)."""
        cctxt = self._client.prepare(version='1.2')
        return cctxt.call(context, 'create_resource',
                          name=name, properties=properties)

    def resize_resource(self, context, resource_id, new_size,
                        preserve_data=False):
        """Requires server >= 1.4."""
        cctxt = self._client.prepare(version='1.4')
        return cctxt.call(context, 'resize_resource',
                          resource_id=resource_id,
                          new_size=new_size,
                          preserve_data=preserve_data)
```

---

### Version Cap During Upgrades

Pin the version cap during upgrades so new clients don't send calls old servers can't handle.

```python
# oslo.config option (registered in opts)
cfg.StrOpt(
    'rpc_current_version',
    default=None,
    help='RPC API version cap. When set, limits client to this version '
         'for rolling upgrade safety. Set to old version during upgrade, '
         'unset when all nodes are upgraded.',
),

# In client constructor
def __init__(self):
    transport = messaging.get_rpc_transport(CONF)
    # Use configured cap, falling back to latest
    version_cap = CONF.myservice.rpc_current_version or self.RPC_API_VERSION
    target = messaging.Target(
        topic='myservice',
        version=self.RPC_API_VERSION,
        version_cap=version_cap,
    )
    self._client = messaging.get_rpc_client(transport, target)
```

---

## Anti-Pattern Catalog

### ❌ Changing Method Signature Without Version Bump

**Detection**:
```bash
# Check git log for RPC method signature changes without version bump
git diff HEAD~1 HEAD -- '*.py' | grep -E '^\+.*def (create|update|delete|get|list)_.*context' | head -20
# Then verify RPC_API_VERSION changed in same diff
git diff HEAD~1 HEAD -- '*.py' | grep 'RPC_API_VERSION'
```

**What it looks like**:
```python
# Before (version still '1.2'):
def create_resource(self, context, name):
    ...

# After (version still '1.2' — NOT bumped!):
def create_resource(self, context, name, resource_type):  # Added required arg
    ...
```

**Why wrong**: Old nodes calling `create_resource(ctx, name)` will crash with `TypeError` on the new server. Rolling upgrade fails.

**Fix**: Bump `RPC_API_VERSION` to `'1.3'`, make `resource_type` optional with a default, and pin new client calls to `prepare(version='1.3')`.

---

### ❌ Calling New Method Without Version Pin

**Detection**:
```bash
grep -rn 'cctxt\.call\|cctxt\.cast' --include="*.py" -B 2 | grep -v "prepare"
```

**What it looks like**:
```python
# Client calling method added in 1.4 without prepare()
def resize_resource(self, context, resource_id, new_size):
    return self._client.call(context, 'resize_resource',
                             resource_id=resource_id,
                             new_size=new_size)
```

**Why wrong**: `_client.call()` without `.prepare(version=X)` sends no version requirement. If the server is on `1.3` and doesn't have `resize_resource`, the call fails with `MethodNotFound`.

**Fix**: Always use `self._client.prepare(version='1.4').call(...)` before calls that require a specific version.

---

### ❌ Using `RPC_API_VERSION = '1.0'` Forever

**Detection**:
```bash
grep -rn "RPC_API_VERSION = '1\.0'" --include="*.py"
# Then check if the file has methods added after initial creation
git log --follow --oneline agents/ | head -20
```

**What it looks like**:
```python
class MyServiceManager:
    RPC_API_VERSION = '1.0'  # Never changed despite 3 years of new methods
    target = messaging.Target(version=RPC_API_VERSION)

    def create(self, context, name): ...       # original
    def delete(self, context, id): ...         # added later, no version bump
    def resize(self, context, id, size): ...   # added later, no version bump
```

**Why wrong**: Clients can't use `prepare(version=X)` to protect against calling new methods on old servers. Every caller must assume all methods exist on all server versions — breaks rolling upgrades.

**Fix**: Audit when each method was added, assign retrospective version numbers, and update `RPC_API_VERSION` to reflect the current maximum.

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|------------|-----|
| `oslo_messaging.exceptions.MessagingTimeout` | Call exceeded `rpc_response_timeout` (default 60s) | Increase `CONF.rpc_response_timeout` or make the server-side operation async (cast instead of call) |
| `oslo_messaging.rpc.client.RPCVersionCapError: Requested message version ... is not compatible` | Client prepared a version higher than server's cap | Set `version_cap` in client target to server's `RPC_API_VERSION`, or upgrade server first |
| `oslo_messaging.exceptions.NoSuchMethod: Method ... is not defined` | Client called method not yet on server | Check version pins; server may be running older code during upgrade |
| `TypeError: method() got unexpected keyword argument` | Client sent argument added in new version to old server | Use `prepare(version=X)` where X introduced the argument; server must use default args |

---

## Detection Commands Reference

```bash
# Find RPC methods with no prepare() before call/cast
grep -rn 'cctxt\.call\|cctxt\.cast' --include="*.py" -B 3 | grep -v "prepare"

# Find unchanged RPC_API_VERSION
grep -rn "RPC_API_VERSION" --include="*.py"

# Find bare method signature changes (potential version-bump misses)
git diff -- '*.py' | grep '^[+-].*def .*context'

# Check current version caps in config
grep -rn "rpc_current_version\|version_cap" --include="*.py" --include="*.cfg"
```

---

## See Also

- `oslo-patterns.md` — oslo.messaging transport and client setup
- `hacking-rules.md` — Code style required for all RPC handler code
