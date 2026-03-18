# Learning Database Reference

Complete schema, operations, and confidence tracking for Claude Code learning database.

## Database Schema

### Main Structure

```json
{
  "metadata": {
    "version": "1.0",
    "created": "2026-01-15T10:00:00Z",
    "last_updated": "2026-02-14T15:30:00Z",
    "total_patterns": 42
  },
  "patterns": [
    {
      "id": "Edit_multiple_matches_001",
      "tool": "Edit",
      "error_type": "multiple_matches",
      "signature": "a3b5c7d9e1f2g3h4i5j6k7l8m9n0",
      "error_message_snippet": "Error: Found 3 matches for old_string",
      "solution": {
        "description": "Use replace_all parameter when multiple matches exist",
        "command": "Edit with replace_all=true",
        "prerequisites": ["Multiple matches detected in file"]
      },
      "confidence": 0.85,
      "success_count": 12,
      "failure_count": 2,
      "created": "2026-01-20T12:00:00Z",
      "last_updated": "2026-02-10T09:15:00Z",
      "last_applied": "2026-02-10T09:15:00Z"
    }
  ]
}
```

### Required Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier: `{tool}_{error_type}_{index}` |
| `tool` | string | Yes | Tool name (Edit, Read, Bash, etc.) |
| `error_type` | string | Yes | Classification (missing_file, permissions, etc.) |
| `signature` | string | Yes | MD5 hash for pattern matching |
| `solution` | object | Yes | Solution with description and command |
| `confidence` | float | Yes | 0.0-1.0, updated with ±0.1/0.2 |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `error_message_snippet` | string | First 200 chars of error message |
| `success_count` | int | Number of successful applications |
| `failure_count` | int | Number of failed applications |
| `created` | ISO8601 | Pattern creation timestamp |
| `last_updated` | ISO8601 | Last confidence update |
| `last_applied` | ISO8601 | Last time solution was injected |

---

## Confidence Tracking

### Scoring Algorithm

**Initial confidence**: 0.0 (new patterns start unproven)

**Success adjustment**: +0.1 (capped at 1.0)
```python
new_confidence = min(1.0, current_confidence + 0.1)
```

**Failure adjustment**: -0.2 (floored at 0.0)
```python
new_confidence = max(0.0, current_confidence - 0.2)
```

**Injection threshold**: >0.7 (only high-confidence solutions auto-inject)

### Confidence States

| Confidence | State | Behavior |
|------------|-------|----------|
| 0.0 - 0.3 | Unproven | Not injected, learning phase |
| 0.4 - 0.6 | Uncertain | Logged but not auto-applied |
| 0.7 - 0.9 | High Confidence | Auto-injected into context |
| 0.9 - 1.0 | Proven | Highly reliable solutions |

### Example Confidence Evolution

```
Pattern: Edit multiple_matches solution

Attempt 1: Success → 0.0 + 0.1 = 0.1
Attempt 2: Success → 0.1 + 0.1 = 0.2
Attempt 3: Success → 0.2 + 0.1 = 0.3
Attempt 4: Success → 0.3 + 0.1 = 0.4
Attempt 5: Failure → 0.4 - 0.2 = 0.2
Attempt 6: Success → 0.2 + 0.1 = 0.3
Attempt 7: Success → 0.3 + 0.1 = 0.4
Attempt 8: Success → 0.4 + 0.1 = 0.5
Attempt 9: Success → 0.5 + 0.1 = 0.6
Attempt 10: Success → 0.6 + 0.1 = 0.7 ← Now eligible for injection!
```

---

## Atomic Operations

### Write-to-Temp-Then-Rename Pattern

```python
def atomic_save(data, db_path):
    """
    Atomic database save using temp file and rename.

    Args:
        data: Database dict to save
        db_path: Path to learning database file
    """
    # Write to temporary file
    temp_path = db_path.with_suffix('.tmp')
    with temp_path.open('w') as f:
        json.dump(data, f, indent=2)

    # Atomic rename (POSIX filesystem guarantee)
    temp_path.replace(db_path)

    # Create backup
    backup_path = db_path.with_suffix('.bak')
    import shutil
    shutil.copy2(db_path, backup_path)
```

### File Locking (Advanced)

For concurrent access safety:

```python
import fcntl

def locked_read(db_path):
    """Read with file lock."""
    with db_path.open('r') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for reading
        try:
            data = json.load(f)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release lock
    return data


def locked_write(data, db_path):
    """Write with exclusive lock."""
    temp_path = db_path.with_suffix('.tmp')
    with temp_path.open('w') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock for writing
        try:
            json.dump(data, f, indent=2)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release lock

    temp_path.replace(db_path)
```

---

## Database Operations

### Query by Signature

```python
def find_pattern(signature, db_path, threshold=0.7):
    """
    Find pattern by signature with confidence threshold.

    Args:
        signature: MD5 signature to find
        db_path: Path to learning database
        threshold: Minimum confidence (default 0.7)

    Returns:
        dict: Pattern if found with high confidence, else None
    """
    try:
        with db_path.open('r') as f:
            data = json.load(f)

        for pattern in data.get('patterns', []):
            if pattern.get('signature') == signature:
                if pattern.get('confidence', 0.0) >= threshold:
                    return pattern
                else:
                    return None  # Found but low confidence

    except Exception:
        return None

    return None
```

### Update Confidence

```python
def update_confidence(pattern_id, success, db_path):
    """
    Update pattern confidence based on outcome.

    Args:
        pattern_id: ID of pattern to update
        success: True if solution worked, False if failed
        db_path: Path to learning database
    """
    data = load_db(db_path)

    for pattern in data['patterns']:
        if pattern.get('id') == pattern_id:
            current = pattern.get('confidence', 0.0)

            if success:
                new = min(1.0, current + 0.1)
                pattern['success_count'] = pattern.get('success_count', 0) + 1
            else:
                new = max(0.0, current - 0.2)
                pattern['failure_count'] = pattern.get('failure_count', 0) + 1

            pattern['confidence'] = new
            pattern['last_updated'] = datetime.now().isoformat()
            break

    atomic_save(data, db_path)
```

### Add New Pattern

```python
def add_pattern(tool, error_type, signature, solution, db_path):
    """
    Add new pattern to learning database.

    Args:
        tool: Tool name
        error_type: Error classification
        signature: Unique MD5 signature
        solution: Solution dict
        db_path: Path to learning database
    """
    data = load_db(db_path)

    # Check for duplicates
    for pattern in data['patterns']:
        if pattern.get('signature') == signature:
            return  # Already exists

    # Generate unique ID
    pattern_id = f"{tool}_{error_type}_{len(data['patterns'])}"

    new_pattern = {
        'id': pattern_id,
        'tool': tool,
        'error_type': error_type,
        'signature': signature,
        'solution': solution,
        'confidence': 0.0,  # Start unproven
        'success_count': 0,
        'failure_count': 0,
        'created': datetime.now().isoformat(),
        'last_updated': datetime.now().isoformat()
    }

    data['patterns'].append(new_pattern)
    data['metadata']['total_patterns'] = len(data['patterns'])

    atomic_save(data, db_path)
```

---

## Error Types Classification

### Standard Error Types

| Error Type | Triggers | Example Error Message |
|------------|----------|----------------------|
| `missing_file` | File not found errors | "FileNotFoundError: config.json" |
| `permissions` | Permission denied | "PermissionError: /etc/restricted" |
| `multiple_matches` | Edit tool ambiguity | "Found 3 matches for old_string" |
| `syntax_error` | Python/JS syntax errors | "SyntaxError: invalid syntax" |
| `type_error` | Type mismatches | "TypeError: str expected, got int" |
| `connection_error` | Network issues | "ConnectionError: timeout" |
| `import_error` | Missing dependencies | "ModuleNotFoundError: requests" |
| `unknown` | Unclassified errors | Any other error |

### Classification Logic

```python
def classify_error(tool_name, error_output):
    """
    Classify error from tool output.

    Args:
        tool_name: Name of tool that errored
        error_output: Error message text

    Returns:
        str: Error classification
    """
    output_lower = error_output.lower()

    # Pattern matching for classification
    if any(x in output_lower for x in ['no such file', 'filenotfound', 'file not found']):
        return 'missing_file'

    elif any(x in output_lower for x in ['permission denied', 'permissionerror']):
        return 'permissions'

    elif 'multiple matches' in output_lower and tool_name == 'Edit':
        return 'multiple_matches'

    elif any(x in output_lower for x in ['syntaxerror', 'syntax error']):
        return 'syntax_error'

    elif any(x in output_lower for x in ['typeerror', 'type error']):
        return 'type_error'

    elif any(x in output_lower for x in ['connectionerror', 'timeout', 'connection refused']):
        return 'connection_error'

    elif any(x in output_lower for x in ['importerror', 'modulenotfound', 'no module named']):
        return 'import_error'

    else:
        return 'unknown'
```

---

## Signature Generation

### MD5 Hashing for Uniqueness

```python
import hashlib

def generate_signature(tool_name, error_type, error_message):
    """
    Generate unique MD5 signature for error pattern.

    Args:
        tool_name: Tool that produced error
        error_type: Error classification
        error_message: Full error message

    Returns:
        str: 32-character MD5 hash
    """
    # Use first 200 chars to avoid dynamic data pollution
    message_snippet = error_message[:200]

    # Combine tool, type, and snippet
    signature_input = f"{tool_name}:{error_type}:{message_snippet}"

    # MD5 hash for unique signature
    return hashlib.md5(signature_input.encode()).hexdigest()
```

### Collision Handling

```python
def check_signature_collision(signature, db_path):
    """
    Check if signature already exists.

    Args:
        signature: MD5 signature to check
        db_path: Path to learning database

    Returns:
        bool: True if collision detected, False otherwise
    """
    try:
        with db_path.open('r') as f:
            data = json.load(f)

        for pattern in data.get('patterns', []):
            if pattern.get('signature') == signature:
                return True

    except Exception:
        pass

    return False
```

---

## Schema Evolution

### Version Compatibility

```python
def migrate_schema(data, from_version, to_version):
    """
    Migrate learning database schema.

    Args:
        data: Current database dict
        from_version: Current schema version
        to_version: Target schema version

    Returns:
        dict: Migrated database
    """
    if from_version == "1.0" and to_version == "1.1":
        # Example: Add success/failure counts
        for pattern in data.get('patterns', []):
            if 'success_count' not in pattern:
                pattern['success_count'] = 0
            if 'failure_count' not in pattern:
                pattern['failure_count'] = 0

        data['metadata']['version'] = "1.1"

    return data
```

### Backward Compatibility

```python
def load_with_compatibility(db_path):
    """
    Load database with backward compatibility handling.

    Args:
        db_path: Path to learning database

    Returns:
        dict: Database with latest schema
    """
    try:
        with db_path.open('r') as f:
            data = json.load(f)

        current_version = data.get('metadata', {}).get('version', '1.0')
        latest_version = '1.1'

        if current_version != latest_version:
            data = migrate_schema(data, current_version, latest_version)
            atomic_save(data, db_path)

        return data

    except Exception:
        # Return empty database on error
        return {
            'metadata': {'version': latest_version},
            'patterns': []
        }
```
