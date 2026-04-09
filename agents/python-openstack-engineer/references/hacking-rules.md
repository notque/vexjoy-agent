# OpenStack Hacking Rules Reference

> **Scope**: H-series PEP 8 extensions enforced by `hacking` package in OpenStack services. Does not cover standard PEP 8 rules (covered by pycodestyle/flake8).
> **Version range**: hacking 6.x+ (used with flake8 5.x+, tox -e pep8)
> **Generated**: 2026-04-09 — verify against https://docs.openstack.org/hacking/latest/

---

## Overview

OpenStack uses a custom `hacking` flake8 plugin that enforces community conventions beyond PEP 8. Rules are in the H100-H900 range. The most commonly violated are H201 (bare except), H301-H307 (import ordering), and H501 (old-style string formatting). All must pass `tox -e pep8` before any patch can merge via Gerrit.

---

## Rule Summary Table

| Rule | What It Checks | Severity |
|------|---------------|----------|
| H201 | No bare `except:` | Hard block |
| H202 | No `except Exception:` without re-raise | Warning |
| H301 | No `import` of multiple modules per line | Hard block |
| H302 | No `import` of full module when `from … import` available | Warning |
| H303 | No wildcard imports (`from foo import *`) | Hard block |
| H304 | No relative imports | Hard block |
| H306 | Imports not in alphabetical order within group | Warning |
| H307 | Module-level `__all__` exports must list all public names | Informational |
| H401 | No docstring starting with a space | Warning |
| H501 | No `%s` string formatting with `locals()` or `self.__dict__` | Hard block |
| H701 | No `i18n` import from `oslo.i18n` old namespace | Hard block |
| H903 | Windows line endings not allowed | Hard block |

---

## Correct Patterns

### H201 — Specific Exception Handling

Always name the exception class. Catching `Exception` is acceptable only when you re-raise.

```python
# Correct: specific exception
try:
    result = nova_client.servers.get(server_id)
except nova_exceptions.NotFound:
    raise exception.ServerNotFound(server_id=server_id)
except nova_exceptions.ClientException as exc:
    LOG.error('Nova API error: %s', exc)
    raise

# Correct: catching Exception when re-raising
try:
    do_risky_thing()
except Exception:
    LOG.exception('Unexpected error during risky_thing')
    raise
```

---

### H301/H303/H304 — Import Conventions

Imports must be: one per line, no wildcards, no relative paths, ordered stdlib → third-party → project.

```python
# Correct import order and style
import os
import sys

from oslo_config import cfg
from oslo_log import log as logging

from myservice import exception
from myservice.db import api as db_api
from myservice import utils
```

---

### H501 — No locals()/self.__dict__ in % formatting

```python
# Correct
LOG.error('Server %(server_id)s not found in zone %(zone)s',
          {'server_id': server_id, 'zone': zone})

# Correct (modern oslo.log style)
LOG.info('Created resource %s', resource.id)
```

---

### H701 — i18n Import from New Namespace

```python
# Correct: project-specific i18n module
from myservice.i18n import _
from myservice.i18n import _LE  # error log messages (oslo <= 3.x)
from myservice.i18n import _LW  # warning log messages (oslo <= 3.x)

# In modern oslo.log (5.x+), just use _ for user-facing exceptions
raise exception.ResourceNotFound(msg=_('Resource %s not found') % res_id)
```

---

## Anti-Pattern Catalog

### ❌ H201: Bare `except:` Clause

**Detection**:
```bash
grep -rn 'except:' --include="*.py"
rg 'except:\s*$' --type py
```

**What it looks like**:
```python
try:
    result = db.get_resource(context, resource_id)
except:   # H201 — catches SystemExit, KeyboardInterrupt, GeneratorExit
    LOG.warning('Resource not found')
    return None
```

**Why wrong**: Catches `SystemExit` and `KeyboardInterrupt`, preventing clean service shutdown. `tox -e pep8` hard blocks this.

**Fix**:
```python
try:
    result = db.get_resource(context, resource_id)
except exception.ResourceNotFound:
    LOG.warning('Resource %s not found', resource_id)
    return None
```

---

### ❌ H303: Wildcard Imports

**Detection**:
```bash
grep -rn 'from .* import \*' --include="*.py"
rg 'from \S+ import \*' --type py
```

**What it looks like**:
```python
from oslo_config.cfg import *
from myservice.common import *
```

**Why wrong**: Pollutes namespace, breaks introspection, makes `tox -e pep8` fail, and hides dependency chain from code review tools like Zuul.

**Fix**: Import only what you use explicitly.

```python
from oslo_config.cfg import CONF, StrOpt, IntOpt
```

---

### ❌ H304: Relative Imports

**Detection**:
```bash
grep -rn 'from \.' --include="*.py" | grep -v "test\|#"
rg 'from \.' --type py
```

**What it looks like**:
```python
from .utils import format_id
from ..exception import ResourceNotFound
```

**Why wrong**: OpenStack enforces absolute imports throughout. Relative imports break `oslo-config-generator`, tox environments, and Zuul dependency resolution.

**Fix**:
```python
from myservice.common.utils import format_id
from myservice import exception
```

---

### ❌ H501: % Formatting with locals()/self.__dict__

**Detection**:
```bash
grep -rn 'locals()\|self\.__dict__' --include="*.py" | grep '%'
rg '% (locals|self\.__dict__)' --type py
```

**What it looks like**:
```python
msg = 'Creating %(resource_type)s for user %(user_id)s' % locals()
LOG.debug('State: %(state)s timeout: %(timeout)s' % self.__dict__)
```

**Why wrong**: `locals()` captures entire local scope including sensitive values (passwords, tokens). Implicit coupling makes refactoring silently break string formatting.

**Fix**:
```python
msg = ('Creating %(resource_type)s for user %(user_id)s'
       % {'resource_type': resource_type, 'user_id': user_id})
LOG.debug('State: %s timeout: %s', self.state, self.timeout)
```

---

## Error-Fix Mappings

| `tox -e pep8` Output | Rule | Fix |
|----------------------|------|-----|
| `H201 no 'except:' at module scope` | H201 | Replace `except:` with specific exception class |
| `H303 no wildcard imports` | H303 | Replace `from x import *` with explicit names |
| `H304 No relative imports` | H304 | Change `from .utils` to `from myservice.utils` |
| `H306 imports not in alphabetical order` | H306 | Sort imports alphabetically within each group |
| `H501 Do not use self.__dict__` | H501 | Replace with explicit `{'key': self.key}` dict |
| `H701 DEPRECATED oslo.i18n` | H701 | Change `from oslo.i18n import _` to project-local `from myservice.i18n import _` |

---

## Running the Checks

```bash
# Full pep8 check (same as CI)
tox -e pep8

# Run hacking checks only (faster, no format checks)
flake8 --select=H myservice/

# Check a single file
flake8 --select=H myservice/api/v1/resources.py

# Show all H-rules currently configured
grep -r "H[0-9]\{3\}" tox.ini setup.cfg

# Auto-detect what rules are active
flake8 --select=H --show-pep8 myservice/
```

---

## See Also

- `oslo-patterns.md` — Oslo library usage that hacking compliance depends on
- `rpc-versioning.md` — Version rules for API methods
