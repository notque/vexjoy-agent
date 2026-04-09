# Oslo Library Patterns Reference

> **Scope**: Correct usage of oslo.config, oslo.messaging, oslo.db, oslo.log, and oslo.policy in OpenStack services. Does not cover oslo.serialization or oslo.upgradecheck.
> **Version range**: oslo.config 9.x+, oslo.messaging 14.x+, oslo.db 14.x+, oslo.log 5.x+
> **Generated**: 2026-04-09 — verify against current oslo library release notes

---

## Overview

Oslo libraries are the shared infrastructure for all OpenStack services. Using them correctly prevents incompatibilities with community tooling, config file generators (`oslo-config-generator`), and logging aggregators. The most common failure is reimplementing functionality that Oslo already provides (custom config loaders, custom log formatters, bare `logging.getLogger` calls).

---

## Pattern Table

| Library | Correct Entry Point | Version | Avoid |
|---------|---------------------|---------|-------|
| `oslo_config` | `from oslo_config import cfg; CONF = cfg.CONF` | 9.0+ | `from oslo.config import cfg` (old namespace) |
| `oslo_messaging` | `import oslo_messaging as messaging` | 14.0+ | Direct AMQP client construction |
| `oslo_db` | `from oslo_db import api as oslo_db_api` | 14.0+ | Raw `sqlalchemy.create_engine` without oslo session mgmt |
| `oslo_log` | `from oslo_log import log as logging` | 5.0+ | `import logging` directly in service modules |
| `oslo_policy` | `from oslo_policy import policy` | 4.0+ | Custom RBAC checks without oslo_policy enforcer |

---

## Correct Patterns

### oslo.config — Option Registration

Register options before `CONF()` is called. Group options by service component.

```python
from oslo_config import cfg

_opts = [
    cfg.StrOpt(
        'transport_url',
        default='rabbit://guest:guest@localhost:5672/',
        help='URL to Oslo messaging transport.',
    ),
    cfg.IntOpt(
        'workers',
        default=1,
        min=1,
        help='Number of API worker processes to spawn.',
    ),
    cfg.BoolOpt(
        'debug',
        default=False,
        help='Enable debug logging.',
    ),
]

CONF = cfg.CONF
CONF.register_opts(_opts, group='myservice')

# Access
workers = CONF.myservice.workers
```

**Why**: `oslo-config-generator` introspects registered opts to generate sample config files. Options not registered with `register_opts` are invisible to tooling.

---

### oslo.log — Structured Logger Setup

```python
from oslo_log import log as logging
from oslo_config import cfg

CONF = cfg.CONF
LOG = logging.getLogger(__name__)

def setup_logging(project_name: str) -> None:
    """Must be called at service startup before any logging."""
    logging.setup(CONF, project_name)
    logging.set_defaults(default_log_levels=logging.get_default_log_levels())

# In usage (with request context)
LOG.info('Processing request %(req_id)s for user %(user_id)s',
         {'req_id': context.request_id, 'user_id': context.user_id})
```

**Why**: `logging.setup()` wires oslo.log into the Oslo config system, enabling `log_file`, `log_dir`, `log_date_format`, and `debug` flags from oslo.config. Calling `logging.basicConfig()` or raw `logging.getLogger()` bypasses all of this.

---

### oslo.messaging — RPC Client Pattern

```python
import oslo_messaging as messaging
from oslo_config import cfg

CONF = cfg.CONF

class MyServiceAPI:
    """Client-side RPC API (runs in callers, e.g., Nova conductor)."""
    RPC_API_VERSION = '1.3'

    def __init__(self):
        transport = messaging.get_rpc_transport(CONF)
        target = messaging.Target(
            topic='myservice',
            version=self.RPC_API_VERSION,
        )
        self._client = messaging.get_rpc_client(transport, target)

    def create_resource(self, context, name: str, properties: dict):
        """RPC call — blocks until remote completes."""
        cctxt = self._client.prepare(version='1.1')
        return cctxt.call(context, 'create_resource',
                          name=name, properties=properties)

    def notify_resource_deleted(self, context, resource_id: str):
        """RPC cast — fire-and-forget."""
        cctxt = self._client.prepare(version='1.0')
        cctxt.cast(context, 'resource_deleted', resource_id=resource_id)
```

**Why**: `prepare(version='1.1')` allows the server to negotiate down to compatible versions during rolling upgrades. Calling `.call()` directly on `self._client` without `.prepare()` sends no version hint.

---

### oslo.db — Database Session

```python
from oslo_db import api as oslo_db_api
from oslo_db.sqlalchemy import enginefacade

context_manager = enginefacade.transaction_context()
context_manager.configure(
    connection=CONF.database.connection,
    sqlite_synchronous=CONF.database.sqlite_synchronous,
)

@enginefacade.writer
def create_resource(context, values: dict):
    """Write operation — opens a writable transaction."""
    ref = models.Resource()
    ref.update(values)
    context.session.add(ref)
    return ref

@enginefacade.reader
def get_resource(context, resource_id: str):
    """Read operation — uses read-only session."""
    return (context.session
            .query(models.Resource)
            .filter_by(id=resource_id, deleted=False)
            .first())
```

**Why**: `enginefacade.writer` / `enginefacade.reader` decorators manage transaction lifecycles and enable read/write splitting. Using `session.begin()` manually bypasses oslo.db retry logic and connection pooling tuning.

---

## Anti-Pattern Catalog

### ❌ Direct `import logging` in Service Code

**Detection**:
```bash
grep -rn '^import logging$' --include="*.py"
grep -rn 'logging\.getLogger' --include="*.py" | grep -v "oslo_log\|# noqa"
```

**What it looks like**:
```python
import logging  # Wrong in OpenStack service modules

LOG = logging.getLogger(__name__)
```

**Why wrong**: Bypasses `oslo.log` integration. Log messages won't carry Oslo context fields (`request_id`, `project_id`), and runtime log level changes via `CONF.debug` won't apply to this logger.

**Fix**:
```python
from oslo_log import log as logging

LOG = logging.getLogger(__name__)
```

---

### ❌ Hardcoded Transport URL in Code

**Detection**:
```bash
grep -rn 'rabbit://\|amqp://' --include="*.py" | grep -v "# example\|\.cfg\|test"
```

**What it looks like**:
```python
transport = messaging.get_rpc_transport(
    CONF, url='rabbit://guest:guest@localhost:5672/')
```

**Why wrong**: Transport URL must come from oslo.config (`CONF.transport_url`) to be overridable in deployment configs and testable with `oslo_messaging.fake`.

**Fix**:
```python
# In opts registration:
cfg.StrOpt('transport_url', default='rabbit://', help='...')

# In code:
transport = messaging.get_rpc_transport(CONF)
```

---

### ❌ Raw SQLAlchemy `create_engine` Without Oslo Session

**Detection**:
```bash
grep -rn 'create_engine\|sessionmaker' --include="*.py" | grep -v "enginefacade\|migration\|test"
```

**What it looks like**:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(CONF.database.connection)
Session = sessionmaker(bind=engine)
session = Session()
```

**Why wrong**: Bypasses oslo.db retry logic (deadlock retries via `@api.wrap_db_retry`), connection pool management, and the `sqlite+pysqlite:///:memory:` test override used in unit tests.

**Fix**: Use `enginefacade.writer` / `enginefacade.reader` decorators as shown in the Correct Patterns section.

---

### ❌ Missing `oslo.policy` Enforcement

**Detection**:
```bash
grep -rn 'def (create|update|delete|get|list)_' --include="*.py" -A 10 | grep -v "policy\|enforce"
```

**What it looks like**:
```python
def delete_resource(self, context, resource_id):
    # No policy check — any authenticated user can delete
    return db.resource_delete(context, resource_id)
```

**Why wrong**: All API operations must enforce oslo.policy rules. Missing enforcement silently bypasses RBAC — a security vulnerability that won't be caught by unit tests unless policy enforcement is explicitly tested.

**Fix**:
```python
from oslo_policy import policy

ENFORCER = policy.Enforcer(CONF)

def delete_resource(self, context, resource_id):
    target = {'project_id': context.project_id}
    ENFORCER.enforce(context, 'myservice:resource:delete', target,
                     do_raise=True,
                     exc=exception.PolicyNotAuthorized,
                     action='myservice:resource:delete')
    return db.resource_delete(context, resource_id)
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `oslo_config.cfg.NoSuchOptError: no such option` | Option read before `register_opts()` call | Move registration before `CONF()` in service startup |
| `oslo_config.cfg.DuplicateOptError` | `register_opts` called twice (e.g., in test setup + module import) | Guard with `try/except cfg.DuplicateOptError` or use `register_opt` instead of `register_opts` in tests |
| `oslo_messaging.exceptions.MessageDeliveryFailure` | Broker unreachable or topic not found | Check `transport_url`, verify RabbitMQ queue exists, check `topic` matches server target |
| `oslo_db.exception.DBConnectionError` | Database unreachable at session open | Check `CONF.database.connection`, verify DB is up; oslo.db retries 20 times by default before raising |
| `oslo_policy.policy.PolicyNotRegistered` | Policy rule referenced before `policy.DocumentedRuleDefault` registration | Register all policy rules in `policy.py` module loaded at service startup |

---

## Detection Commands Reference

```bash
# Find direct `import logging` (missing oslo_log)
grep -rn '^import logging$' --include="*.py"

# Find hardcoded AMQP URLs
grep -rn 'rabbit://\|amqp://' --include="*.py" | grep -v "# example\|\.cfg\|test"

# Find raw SQLAlchemy session creation
grep -rn 'create_engine\|sessionmaker' --include="*.py" | grep -v "enginefacade\|migration\|test"

# Find missing policy enforcement in API handlers
grep -rn 'def (create|update|delete)_' --include="*.py" -A 5 | grep -v "enforce\|policy"
```

---

## See Also

- `hacking-rules.md` — H-series PEP 8 extensions that Oslo compliance depends on
- `rpc-versioning.md` — oslo.messaging version negotiation patterns
