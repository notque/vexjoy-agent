# Exploration Strategies by Language

Detailed language-specific discovery commands and patterns for each phase of codebase exploration.

---

## Project Type Detection

### Configuration File Indicators

| File | Language/Framework |
|------|--------------------|
| `package.json` | Node.js / JavaScript / TypeScript |
| `go.mod` | Go |
| `requirements.txt`, `pyproject.toml`, `setup.py` | Python |
| `pom.xml`, `build.gradle` | Java |
| `Cargo.toml` | Rust |
| `composer.json` | PHP |
| `.csproj`, `.sln` | .NET / C# |
| `Gemfile` | Ruby |
| `mix.exs` | Elixir |

### Framework-Specific Files

| File | Framework |
|------|-----------|
| `manage.py` | Django |
| `next.config.js` | Next.js |
| `nuxt.config.js` | Nuxt.js |
| `angular.json` | Angular |
| `fastapi`, `uvicorn` in deps | FastAPI |
| `flask` in deps | Flask |
| `gin`, `echo`, `fiber` in deps | Go web frameworks |

---

## Entry Point Discovery

### Python
```bash
# Common entry points
ls -la main.py app.py wsgi.py asgi.py manage.py __main__.py 2>/dev/null
ls -la src/ */main.py */__main__.py 2>/dev/null
```
- Check `pyproject.toml` `[project.scripts]` section
- Check `setup.py` `entry_points` argument

### Node.js
```bash
# Check package.json fields
grep -E '"main":|"bin":' package.json
ls -la index.js server.js app.js src/index.js src/main.js 2>/dev/null
```

### Go
```bash
# Find main packages
find . -name "main.go" -type f | head -10
# Check cmd/ directory (standard Go layout)
ls cmd/ 2>/dev/null
```

### Java
```bash
# Find main classes
grep -rl "public static void main" --include="*.java" | head -10
# Spring Boot entry
grep -rl "@SpringBootApplication" --include="*.java" | head -5
```

### Rust
```bash
# Binary entry points
ls src/main.rs src/bin/*.rs 2>/dev/null
# Library entry
ls src/lib.rs 2>/dev/null
```

---

## Directory Structure Mapping

### Standard Module Categories

| Directory Pattern | Layer |
|-------------------|-------|
| `models/`, `db/`, `schema/`, `entities/` | Data layer |
| `api/`, `routes/`, `handlers/`, `controllers/` | API layer |
| `services/`, `lib/`, `core/`, `domain/` | Business logic |
| `utils/`, `helpers/`, `common/` | Utilities |
| `tests/`, `test/`, `__tests__/` | Test suite |
| `config/`, `settings/` | Configuration |
| `cmd/`, `cli/` | Command-line interfaces |
| `middleware/`, `interceptors/` | Cross-cutting concerns |
| `migrations/`, `alembic/` | Database migrations |

### Tree Command (Noise Filtered)

```bash
find . -type d \
  -not -path '*/\.*' \
  -not -path '*/node_modules/*' \
  -not -path '*/venv/*' \
  -not -path '*/vendor/*' \
  -not -path '*/dist/*' \
  -not -path '*/build/*' \
  -not -path '*/__pycache__/*' \
  -not -path '*/target/*' \
  | head -50
```

---

## Data Layer Discovery

### Database Models
```bash
# Python ORMs
find . -name "models.py" -o -name "*_model.py" -o -name "schema.py" 2>/dev/null | head -10

# Go models
find . -name "*_model.go" -o -path "*/models/*.go" 2>/dev/null | head -10

# Java entities
find . -path "*/entity/*.java" -o -path "*/model/*.java" 2>/dev/null | head -10

# SQL schemas
find . -name "*.sql" -not -path "*/migrations/*" 2>/dev/null | head -10
```

### ORM/Database Configuration
```bash
find . -name "database.py" -o -name "db.py" -o -name "database.go" \
  -o -name "DataSource*" -o -name "connection*" 2>/dev/null | head -10
```

---

## API Surface Discovery

### REST APIs
```bash
# Route definitions
find . -name "routes.py" -o -name "*_routes.py" -o -name "api.py" \
  -o -name "views.py" -o -name "router.go" -o -name "*_handler.go" \
  2>/dev/null | head -10

# OpenAPI/Swagger
find . -name "openapi.yaml" -o -name "swagger.yaml" \
  -o -name "*.openapi.json" 2>/dev/null | head -5
```

### GraphQL
```bash
find . -name "schema.graphql" -o -name "*.graphql" \
  -o -name "resolvers.*" 2>/dev/null | head -10
```

### gRPC
```bash
find . -name "*.proto" 2>/dev/null | head -10
```

---

## Test Structure Discovery

```bash
# Test files by language
find . -name "*_test.py" -o -name "*_test.go" \
  -o -name "*.test.js" -o -name "*.test.ts" \
  -o -name "*Test.java" -o -name "*_test.rs" \
  2>/dev/null | head -20

# Test configuration
ls -la pytest.ini jest.config.* .mocharc.* phpunit.xml 2>/dev/null
```

---

## Configuration Discovery

```bash
# Environment configs
ls -la .env .env.example .env.sample config.yaml config.json \
  settings.py *.toml 2>/dev/null

# Environment-specific
ls -la config/*.yaml config/*.json config/*.toml 2>/dev/null

# CI/CD
ls -la .github/workflows/*.yml .gitlab-ci.yml Jenkinsfile \
  .circleci/config.yml 2>/dev/null

# Infrastructure
ls -la Dockerfile docker-compose.yml Makefile Taskfile.yml 2>/dev/null
```

---

## Design Pattern Identification

### What to Look For

| Pattern | Evidence |
|---------|----------|
| MVC | `controllers/` + `models/` + `views/` or `templates/` |
| Layered | `handlers/` + `services/` + `repositories/` |
| Microservices | Multiple `go.mod` / `package.json`, service directories |
| Monolith | Single entry point, shared database |
| Event-driven | Message queues, event handlers, pub/sub patterns |
| Repository | `repositories/` or `*_repository.*` files |
| Factory | `*_factory.*` files or `New*()` constructor patterns |
| Dependency Injection | Constructor injection, DI containers |

### Code Convention Signals

| Signal | Convention |
|--------|------------|
| `interface` files separate from implementation | Interface-based design |
| `_test` files alongside source | Co-located tests |
| `internal/` directory (Go) | Encapsulation boundaries |
| `__init__.py` with `__all__` | Explicit public API |
| Consistent error type patterns | Standardized error handling |
