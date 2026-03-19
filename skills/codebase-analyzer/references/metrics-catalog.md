# Codebase Analyzer: 100 Metrics Catalog

Complete reference for the Omni-Cartographer's 25 categories and 100 individual metrics across three phases.

## Phase 1: Tactical Patterns (50 metrics)

### Core Categories (Original Omni, 25 metrics)

**1. Shadow Constitution** (linter suppressions)
- errcheck suppressions
- gosec suppressions
- staticcheck suppressions

**2. Context Hygiene**
- context.Background() in cmd/test locations
- context.Background() in business logic
- context.TODO() usage

**3. Time Management**
- time.Now() direct usage
- Clock interface patterns

**4. Dangerous Functions**
- panic usage
- log.Fatal usage
- init function usage
- os.Exit usage

**5. Modern Go Adoption**
- any vs interface{}
- slices package usage
- maps package usage
- cmp package usage
- min/max builtins

**6. Anti-patterns**
- Manual contains loops
- Manual deduplication
- Float conversions

**7. Project Architecture**
- cmd/ structure
- internal/ structure
- pkg/ structure

**8. Constructor Patterns**
- New prefix usage
- Create prefix usage
- Must prefix usage
- Functional options

**9. Error Handling**
- %w wrapping frequency
- Error message style (lowercase vs uppercase)
- errors.Is/As usage

**10. Logging**
- Library usage (logrus/zap/slog)
- Log levels distribution
- Structured logging adoption

**11. Testing**
- Framework adoption (ginkgo/testify/standard)
- Table-driven test patterns

**12. Core Patterns**
- Struct initialization style
- Slice allocation patterns
- Receiver types (value vs pointer)
- Mutex usage patterns

### Phase 1 New Categories (25 metrics)

**13. Extended Naming Dialects** (10 metrics)
- Getter style: GetName() vs Name()
- ID convention: ID vs Id, UUID vs Uuid
- Acronym casing: URL vs Url, HTTP vs Http, JSON vs Json, API vs Api
- Constant style: SCREAMING_SNAKE vs CamelCase
- Error variable naming: err vs error vs e
- Boolean prefixes: should/will/enable
- Type suffix usage: TypeUser vs UserType

**14. Control Flow Flavor** (7 metrics)
- Guard clauses vs nested ifs
- Switch vs if-else chains
- Loop styles: for-range vs classic for vs infinite vs condition
- Flow control: break/continue/goto
- Defer patterns: immediate vs named vs cleanup
- Return style: naked vs with values

**15. API and Interface Design** (4 metrics)
- String concatenation: + vs Sprintf vs Builder vs Join
- Zero value usage: explicit initialization patterns
- Enum styles: iota vs string constants
- Optional parameters: functional options vs variadic

**16. Observability Extended** (4 metrics)
- Log structure: JSON vs key=value vs plain
- HTTP status style: named constants vs magic numbers
- Metric naming: snake_case vs CamelCase (Prometheus)
- Error codes: const vs string

## Phase 2: Architectural Patterns (25 metrics)

**17. Interface Topology** (3 metrics)
- Interface sizes: small (<3 methods), medium (3-7), large (8+)
- Interface composition: embedded interfaces
- Interface parameters: interface-typed function params

**18. Configuration Strategy** (4 metrics)
- Config sources: env vars vs flags vs Viper
- Environment variable patterns: with/without defaults
- Flag patterns: flag package usage
- Config structs: configuration type definitions

**19. Dependency Injection** (3 metrics)
- Constructor DI: interface params in constructors
- Interface dependencies: interface-typed struct fields
- Factory patterns: factory function usage

**20. Lifecycle Management** (4 metrics)
- Lifecycle methods: Start/Stop/Close/Run/Shutdown
- Shutdown patterns: graceful shutdown with context
- Cleanup patterns: resource cleanup
- Health checks: health/readiness endpoints

**21. Package Organization** (2 metrics)
- Package naming: singular vs plural
- Package patterns: package structure analysis

**22. Architectural Patterns** (3 metrics)
- Arch patterns: Repository/Service/Handler/Controller
- Middleware patterns: middleware functions and chains
- Layer separation: domain entities vs DTOs

## Phase 3: Style Vector (10 composite scores, 0-100)

**23. Consistency Score**: Pattern uniformity (struct literals, receivers, naming)

**24. Modernization Score**: Go 1.21+ adoption (any, slices, maps, min/max)

**25. Safety Score**: Avoidance of dangerous patterns (panic, fatal, embedded mutexes)

**26. Idiomaticity Score**: Adherence to Go conventions

**27. Documentation Score**: Godoc coverage and quality

**28. Testing Maturity**: Test quality, patterns, and coverage

**29. Architecture Score**: Layering, interface design, separation of concerns

**30. Performance Score**: Efficient pattern usage (prealloc, Builder, anti-patterns)

**31. Observability Score**: Logging, metrics, structured telemetry

**32. Production Readiness**: Lifecycle management, graceful shutdown, health checks

## Cartographer Versions

> **Note**: The cartographer scripts described below are not yet implemented. They document the intended analysis tiers.

### Basic Cartographer (`cartographer.py` -- not yet implemented)
- **Metrics**: ~15 categories, basic patterns
- **Use Case**: Quick analysis, understanding core patterns
- **Rules Extracted**: 5-10 rules

### Ultimate Cartographer (`cartographer_ultimate.py`)
- **Metrics**: 6 focused categories (keyed structs, slice prealloc, receivers, mutexes)
- **Use Case**: Performance-critical pattern detection
- **Rules Extracted**: 2-5 rules (very focused)

### Omni-Cartographer (`cartographer_omni.py` -- not yet implemented) -- RECOMMENDED
- **Metrics**: 25 categories, 100 individual metrics
- **Use Case**: Complete codebase DNA profiling, PR review automation, quality tracking
- **Rules Extracted**: 30-40+ rules
- **Phases**: Tactical patterns + Architectural patterns + Style Vector (10-dimensional quality fingerprint)

## Output Structure

The cartographer generates a comprehensive statistical report:

```json
{
  "metadata": {
    "repo_name": "your-project",
    "total_files": 127,
    "total_lines": 15432,
    "analysis_date": "2025-11-20"
  },
  "lens_1_consistency": {
    "top_dependencies": { ... },
    "test_framework_usage": { ... },
    "test_framework_percentages": { ... }
  },
  "lens_2_structure": {
    "constructor_patterns": { ... },
    "constructor_percentages": { ... },
    "receiver_naming": { ... }
  },
  "lens_3_implementation": {
    "error_handling": { ... },
    "error_handling_percentages": { ... },
    "context_usage": { ... },
    "defer_patterns": { ... }
  },
  "control_flow": {
    "guard_clauses": 234,
    "else_blocks": 45,
    "guard_clause_ratio": 5.2
  },
  "derived_rules": [
    {
      "category": "error_handling",
      "rule": "All errors must be wrapped using fmt.Errorf with %w verb",
      "evidence": "89% consistency across 176 error checks",
      "confidence": "HIGH"
    }
  ]
}
```

## Derived Rule Thresholds

Rules are automatically derived when statistical evidence meets these thresholds:

| Confidence | Threshold | Enforcement |
|------------|-----------|-------------|
| HIGH | >85% consistency | Enforce as hard rule |
| MEDIUM | 70-85% consistency | Prefer this pattern, accept exceptions |
| Below 70% | Not extracted | No rule (inconsistent) |

## Typical Analysis Results

**Phase 1 - Tactical Patterns**:
- Naming Voice: ID not Id, err not error, ALL_CAPS acronyms
- Control Flow: Guard clauses percentage, switch over if-else usage
- API Design: String formatting preferences
- Rules Extracted: ~27 rules typical

**Phase 2 - Architectural Patterns**:
- Config Pattern: Environment variables vs flag usage
- Interface Segregation: Percentage of small interfaces (<3 methods)
- Lifecycle Management: Graceful shutdown, health checks
- Rules Extracted: +6 architectural rules typical

**Phase 3 - Style Vector** (Overall Quality Score):
- Dimensions: Documentation, Idiomaticity, Consistency, Production Readiness
- Common Gaps: Performance (slice preallocation, strings.Builder usage)
- Modernization: Go 1.21+ adoption ("any" vs "interface{}")
- Actionable Insights: Specific improvement areas ranked by impact
