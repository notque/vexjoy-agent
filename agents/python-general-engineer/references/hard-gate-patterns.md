# Python Hard Gate Patterns

Before writing Python code, check for these patterns. If found:
1. STOP - Pause implementation
2. REPORT - Flag to user
3. FIX - Remove before continuing

See `shared-patterns/forbidden-patterns-template.md` for framework.

| Pattern | Why Blocked | Correct Alternative |
|---------|---------------|---------------------|
| `except:` (bare except) | Catches SystemExit, KeyboardInterrupt, prevents debugging | `except Exception:` at minimum |
| `except OSError: pass` (broad swallow) | Catches permission denied, IO errors, NFS stale handles — not just missing files. Caused 2 critical silent failures in reddit_mod.py | `except FileNotFoundError: pass` for expected-missing, separate `except OSError as e:` with stderr warning |
| `# type: ignore[return-value]` | Masking a wrong return type annotation instead of fixing it | Fix the annotation to match actual return type |
| `int(untrusted_json_value)` without guard | Crashes entire pipeline on one malformed entry from user-editable JSON | Wrap in `try: int(x) except (ValueError, TypeError): default` |
| `eval(user_input)` | Code injection vulnerability, arbitrary execution | `ast.literal_eval` or validators |
| `pickle.loads(untrusted)` | Arbitrary code execution on deserialization | Use JSON or validated formats |
| `# type: ignore` without comment | Hides real type errors, defeats type safety | Fix the type or document reason |
| `assert` for validation | Disabled in production with `-O` flag | Raise ValueError or custom exceptions |
| `from module import *` | Namespace pollution, unclear dependencies | Import specific names |
| `print()` in production code | No log levels, no structured output | Use logging module |
| `os.system()` or `shell=True` | Shell injection risk | subprocess with list args, shell=False |

### Detection
```bash
grep -rn "^except:" --include="*.py"
grep -rn "eval(" --include="*.py" | grep -v "literal_eval"
grep -rn "# type: ignore$" --include="*.py"
grep -rn "from .* import \*" --include="*.py"
```

### Exceptions
- `# type: ignore[specific-error]` with reason in comment
- `eval()` only with validated, sandboxed input from trusted source
- `print()` in CLI scripts and debugging (not production services)
