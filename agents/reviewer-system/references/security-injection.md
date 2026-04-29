# Injection and Code Execution Patterns

Load when reviewing code that touches subprocess calls, eval/exec, template rendering, deserialization, or deep-merge of user-controlled objects.

The abstract shape is constant: untrusted input reaches a sink that executes code on the server. The correct approach is to keep user data out of code-execution paths entirely — use safe APIs, parameterized interfaces, and strict input validation.

---

## Pass Arguments as Arrays to Subprocess Calls

Use the array form of subprocess APIs with `shell=False`. This prevents shell metacharacter interpretation and ensures each argument is passed as a discrete value, not parsed by a shell.

### Correct Pattern

**Python:**
```python
import subprocess

# Array form — each argument is a separate list element
# The -- separator prevents user_input from being interpreted as a flag
subprocess.run(["git", "clone", "--", user_repo_url], check=True)

# For file operations, same principle
subprocess.run(["convert", user_filename, "out.png"], shell=False, check=True)
```

**TypeScript/Node:**
```ts
import { execFile } from 'node:child_process';

// execFile does not spawn a shell — arguments cannot break out
execFile('git', ['clone', '--', userRepoUrl], (err, stdout) => {
  if (err) throw err;
});
```

**Go:**
```go
// exec.Command passes arguments directly to the binary, no shell involved
cmd := exec.Command("git", "clone", "--", userRepoURL)
if err := cmd.Run(); err != nil {
    return fmt.Errorf("clone failed: %w", err)
}
```

### Why This Matters

Shell injection occurs when user input is interpolated into a command string that a shell parses. The shell interprets metacharacters (`; | && $() \`\``) as control flow, turning data into commands. `subprocess.run(f"git clone {url}", shell=True)` lets an attacker supply `; rm -rf /` as the URL.

**CVEs:** CVE-2021-22205 (GitLab ExifTool — unauthenticated RCE via crafted image metadata passed to shell), CVE-2024-27980 (Node.js BatBadBut — `.bat`/`.cmd` targets on Windows implicitly invoke a shell even with `execFile`, fixed in Node 18.20/20.12/21.7).

### Detection

```bash
# Python: shell=True with potential user input
rg -n 'shell=True' --type py

# Python: os.system and os.popen (always use a shell)
rg -n 'os\.system\(|os\.popen\(' --type py

# Node: child_process.exec (always uses a shell)
rg -n "exec\(|execSync\(" --type ts | rg -v 'execFile'

# Go: exec.Command with shell invocation
rg -n 'exec\.Command\("sh"|exec\.Command\("bash"|exec\.Command\("/bin/sh"' --type go
```

---

## Use Safe Loaders for Deserialization

Deserialize data using format-restricted loaders that cannot instantiate arbitrary objects. For YAML, use `safe_load`. For data exchange, use JSON. Never use `pickle`, `marshal`, or `node-serialize` on untrusted input — these are inherently RCE primitives.

### Correct Pattern

**Python (YAML):**
```python
import yaml

# SafeLoader restricts to primitive types — no arbitrary object instantiation
config = yaml.safe_load(request.data)

# Equivalent explicit form
config = yaml.load(request.data, Loader=yaml.SafeLoader)
```

**Python (data exchange):**
```python
import json

# JSON does not execute code during parsing
data = json.loads(request.data)
```

**Python (ML models — when pickle is unavoidable):**
```python
# For ML model uploads, enforce format validation before loading
# Use safetensors, ONNX, or other non-executable formats
from safetensors import safe_open
model = safe_open(uploaded_path, framework="pt")
```

**TypeScript:**
```ts
// JSON.parse is safe — no code execution
const data = JSON.parse(req.body);

// For structured validation, parse through a schema
import { z } from 'zod';
const Config = z.object({ name: z.string(), value: z.number() });
const validated = Config.parse(JSON.parse(req.body));
```

### Why This Matters

Deserializers that can instantiate arbitrary classes are remote code execution primitives. Python's `pickle.loads` calls `__reduce__` which can return `(os.system, ("rm -rf /",))`. YAML's default loader processes `!!python/object` tags. Node's `node-serialize` calls `eval()` on embedded functions.

**CVEs:** CVE-2020-1747 (PyYAML `FullLoader` allowed RCE gadgets before 5.3.1), CVE-2017-5941 (node-serialize — `eval` on IIFE in serialized data), CVE-2021-44228 (Log4Shell — JNDI lookup triggered by logged strings led to remote class loading and deserialization), CVE-2022-22965 (Spring4Shell — data binding exposed classloader for webshell drop), Picklescan CVE-2025-1716 (poisoned ML model files).

### Detection

```bash
# Python: unsafe deserialization
rg -n 'pickle\.loads|cloudpickle\.loads|joblib\.load|dill\.loads|marshal\.loads' --type py

# Python: yaml.load without SafeLoader
rg -n 'yaml\.load\(' --type py | rg -v 'SafeLoader|safe_load'

# Node: node-serialize (always unsafe)
rg -n 'node-serialize|\.unserialize\(' --type ts --type js

# Java: ObjectInputStream on network input
rg -n 'ObjectInputStream|readObject\(\)' --type java
```

---

## Render Templates from Files, Not from User Input

Template engines must compile templates from trusted file paths, not from user-supplied strings. When the template source is user-controlled, the template engine becomes a code execution sink.

### Correct Pattern

**Python (Flask/Jinja2):**
```python
# Template loaded from a file on disk — user data is a context variable, not the template
@app.route("/preview")
def preview():
    return render_template("preview.html", body=request.args["body"])
```

**Python (Jinja2 direct):**
```python
from jinja2 import Environment, FileSystemLoader

# Templates loaded from the filesystem, never from user input
env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
tmpl = env.get_template("report.html")
output = tmpl.render(data=user_data)
```

**TypeScript (Handlebars):**
```ts
import { readFileSync } from 'fs';
import Handlebars from 'handlebars';

// Template source from disk, not from request
const tmpl = Handlebars.compile(readFileSync('views/preview.hbs', 'utf8'));
res.send(tmpl({ user: req.user }));
```

### Why This Matters

Server-Side Template Injection (SSTI) occurs when user input becomes the template source rather than a template variable. Jinja2's `{{ 7*7 }}` evaluates to `49`, and `{{ config.__class__.__init__.__globals__['os'].popen('id').read() }}` executes commands. Jinja2's `SandboxedEnvironment` has a history of bypasses.

**CVEs:** CVE-2019-10906 (Jinja2 sandbox escape), CVE-2016-10745 (Jinja2 sandbox bypass via `__init_subclass__`), CVE-2019-19919 (Handlebars prototype pollution leading to compile-time RCE via `helperMissing`).

### Detection

```bash
# Python: render_template_string with user input (SSTI)
rg -n 'render_template_string\(' --type py

# Python: Jinja2 Template constructed from variable
rg -n 'Template\(.*request|Template\(.*user|Template\(.*data' --type py

# Node: Handlebars.compile with request data
rg -n 'Handlebars\.compile\(req\.|\.compile\(req\.body' --type ts --type js

# Node: pug.compile or ejs.render with user input
rg -n 'pug\.compile\(|ejs\.render\(' --type ts --type js
```

---

## Evaluate Expressions with Restricted Parsers

When user input must be evaluated as an expression (calculators, formula fields, configuration DSLs), use a restricted parser that handles only the allowed operations. Never pass user strings to `eval`, `exec`, `Function`, or `vm` APIs.

### Correct Pattern

**Python:**
```python
import ast

# ast.literal_eval handles only Python literals — no function calls, no imports
result = ast.literal_eval(request.args["expr"])

# For arithmetic expressions, use a dedicated parser
from simpleeval import simple_eval
result = simple_eval(request.args["expr"])  # Only basic math operators
```

**TypeScript:**
```ts
// Use a purpose-built expression evaluator with an operation allowlist
import { evaluate } from 'mathjs';
const result = evaluate(userExpr, { scope: {} });

// Or parse the expression yourself
const ALLOWED_OPS = ['+', '-', '*', '/'];
const result = safeEvaluator.evaluate(userExpr, { allow: ALLOWED_OPS });
```

### Why This Matters

`eval` and `Function` execute arbitrary code in the application's context. An attacker supplying `__import__('os').system('id')` to Python's `eval` or `require('child_process').execSync('id')` to JavaScript's `Function` has full code execution. Node's `vm` module is not a security sandbox — `vm2` was abandoned after CVE-2023-37903 proved it unfixable.

**CVEs:** CVE-2025-55182 (Next.js React2Shell — Server Actions exposed eval-equivalent sinks), CVE-2023-37903 (vm2 sandbox escape — project abandoned), CVE-2023-29017 (vm2 earlier escape), CVE-2023-32314 (vm2 another escape).

### Detection

```bash
# Python: eval/exec with potential user input
rg -n 'eval\(|exec\(' --type py | rg -v 'ast\.literal_eval|# noqa'

# TypeScript: eval, Function constructor, vm
rg -n 'eval\(|new Function\(|vm\.run' --type ts --type js

# Python: dynamic import with user input
rg -n 'importlib\.import_module\(|__import__\(' --type py

# Ruby: eval with user data
rg -n 'eval\(|instance_eval|class_eval|send\(' --type ruby
```

---

## Validate Object Shape Before Deep Merge

When merging user-supplied objects into configuration or state, parse through a schema validator first. Deep-merge libraries that recursively copy properties allow prototype pollution — an attacker sends `{"__proto__": {"isAdmin": true}}` and every object in the process inherits the polluted property.

### Correct Pattern

**TypeScript:**
```ts
import { z } from 'zod';

// Define the exact shape — __proto__ and constructor cannot pass
const Config = z.object({
  theme: z.enum(['light', 'dark']).optional(),
  locale: z.string().max(5).optional(),
});

// Parse strips unknown properties, rejects __proto__
const validated = Config.parse(req.body);
const merged = { ...defaults, ...validated };
```

**TypeScript (when merge is unavoidable):**
```ts
// Use Object.create(null) as the target — no prototype to pollute
const config = Object.create(null);
for (const [key, value] of Object.entries(validated)) {
  config[key] = value;
}
```

### Why This Matters

Prototype pollution modifies `Object.prototype`, affecting every object in the process. When a polluted property reaches a template engine, auth check, or configuration reader, it becomes a code execution or privilege escalation vector. The Handlebars + lodash chain is the canonical example: pollute `helperMissing` via `_.merge({}, defaults, req.body)`, then template compilation invokes the polluted helper.

**CVEs:** CVE-2019-10744 (lodash.merge prototype pollution), CVE-2020-8203 (lodash.zipObjectDeep), CVE-2019-11358 (jQuery.extend deep merge), CVE-2019-19919 (Handlebars helperMissing RCE via prototype pollution), CVE-2026-40175 (axios header injection via prototype pollution enabling IMDS bypass).

### Detection

```bash
# lodash deep merge with user data
rg -n '\.merge\(|\.mergeWith\(|\.defaultsDeep\(|\.set\(|\.setWith\(' --type ts --type js

# jQuery extend with deep flag
rg -n '\$\.extend\(true' --type ts --type js

# Hand-rolled recursive merge (check for __proto__ filtering)
rg -n 'function.*merge|function.*deepMerge|function.*assign' --type ts --type js
```
