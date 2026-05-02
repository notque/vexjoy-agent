# Python Hard Gate Patterns

Before writing Python code, check for these. If found: STOP, REPORT, FIX.

See `shared-patterns/forbidden-patterns-template.md` for framework.

| Pattern | Why Blocked | Correct Alternative |
|---------|---------------|---------------------|
| `except:` (bare except) | Catches SystemExit, KeyboardInterrupt | `except Exception:` at minimum |
| `except OSError: pass` (broad swallow) | Catches permission denied, IO errors, NFS stale handles — caused 2 critical silent failures in reddit_mod.py | `except FileNotFoundError: pass` for expected-missing, separate `except OSError as e:` with warning |
| `# type: ignore[return-value]` | Masking wrong return type | Fix the annotation |
| `int(untrusted_json_value)` without guard | Crashes pipeline on malformed entry | `try: int(x) except (ValueError, TypeError): default` |
| `eval(user_input)` | Code injection | `ast.literal_eval` or validators |
| `pickle.loads(untrusted)` | Arbitrary code execution | JSON or validated formats |
| `# type: ignore` without comment | Hides real type errors | Fix the type or document reason |
| `assert` for validation | Disabled with `-O` flag | Raise ValueError or custom exceptions |
| `from module import *` | Namespace pollution | Import specific names |
| `print()` in production code | No log levels, no structured output | logging module |
| `os.system()` or `shell=True` | Shell injection | subprocess with list args, shell=False |

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
