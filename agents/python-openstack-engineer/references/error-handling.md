# OpenStack Error Handling

Common OpenStack development errors.

## Bare Except Clause (H201)
**Cause**: Using `except:` without specifying exception type
**Solution**: Always catch specific exceptions
```python
# Bad
try:
    do_something()
except:  # H201 violation
    pass

# Good
try:
    do_something()
except SpecificException as e:
    LOG.error('Failed: %s', e)
```

## Missing i18n Translation
**Cause**: User-facing string without _() function
**Solution**: Wrap all user strings with _()
```python
# Bad
raise Exception('Resource not found')

# Good
from myservice.i18n import _
raise Exception(_('Resource not found'))
```

## Import Order Violation (H301-H307)
**Cause**: Imports not following OpenStack conventions
**Solution**: Order imports: stdlib, third-party, project
```python
# Correct order
import os
import sys

import eventlet
from oslo_config import cfg

from myservice import utils
```
