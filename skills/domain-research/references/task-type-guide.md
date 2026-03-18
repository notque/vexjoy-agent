# Task Type Guide

Reference for Phase 2 (CLASSIFY) of the domain-research skill.
Load this file when classifying subdomains by task type.

## How To Use This File

1. For each candidate subdomain, read the practitioner's common tasks
2. Match against the task type definitions below
3. Assign one primary type (mandatory) and optionally one secondary type
4. Use the canonical chain as a starting point for Phase 3 (MAP)

---

## The 8 Task Types

### 1. Generation

**Definition**: Produces new artifacts from requirements or specifications. The pipeline takes input context and creates something that didn't exist before.

**Key Indicators**: "Write me a...", "Create a...", "Generate a...", "Draft a...", "Author a..."

**Common Domain Examples**:
| Domain | Subdomain | What's Generated |
|--------|-----------|-----------------|
| Prometheus | Metrics authoring | PromQL queries, recording rules, metric definitions |
| Terraform | Module creation | HCL modules, variable definitions, output blocks |
| Kubernetes | Manifest generation | Deployment YAML, Service specs, ConfigMaps |
| Documentation | Article writing | Blog posts, API docs, runbooks |

**Canonical Chain**:
```
ADR -> RESEARCH -> COMPILE -> GENERATE -> VALIDATE -> REFINE -> OUTPUT
```

**Step Menu Families**: Research & Gathering, Structuring, Generation, Validation

**When to add secondary type**:
- Generation + Review: When the generated artifact needs peer evaluation (code, architecture)
- Generation + Configuration: When the artifact is a config file with schema constraints

---

### 2. Review

**Definition**: Evaluates existing artifacts against quality criteria, standards, or best practices. The pipeline receives something and judges it.

**Key Indicators**: "Review this...", "Check if...", "Audit...", "Evaluate...", "Is this correct?"

**Common Domain Examples**:
| Domain | Subdomain | What's Reviewed |
|--------|-----------|-----------------|
| Go | Code review | Go source files against idioms and conventions |
| Security | Vulnerability audit | Dependencies, configurations, access patterns |
| Terraform | Plan review | Terraform plan output for safety and correctness |
| Kubernetes | Manifest audit | YAML specs for security, resource limits, best practices |

**Canonical Chain**:
```
ADR -> ASSESS -> REVIEW (3+ parallel lenses) -> AGGREGATE -> REPORT
```

**Step Menu Families**: Structuring (ASSESS), Review, Synthesis & Reporting

**Parallel reviewers** (minimum 3 lenses): The specific lenses depend on the domain, but common patterns are:
- Architecture / Structure
- Security / Safety
- Correctness / Logic
- Performance / Efficiency

---

### 3. Debugging

**Definition**: Diagnoses failures in running systems or code, identifies root causes, and proposes or applies fixes. The pipeline starts with a symptom and works toward resolution.

**Key Indicators**: "Why is X broken?", "Fix this...", "Troubleshoot...", "Debug...", "X is failing because..."

**Common Domain Examples**:
| Domain | Subdomain | What's Debugged |
|--------|-----------|-----------------|
| Prometheus | Pod troubleshooting | Prometheus pods in CrashLoopBackOff, OOM, scrape failures |
| Kubernetes | Workload debugging | Pods not starting, services not routing, PVCs not binding |
| Go | Test failures | Failing tests, race conditions, deadlocks |
| RabbitMQ | Queue issues | Message backlog, consumer failures, connection drops |

**Canonical Chain**:
```
ADR -> PROBE -> SEARCH -> ASSESS -> PLAN -> EXECUTE -> VALIDATE -> OUTPUT
```

**Step Menu Families**: Observation (PROBE), Research & Gathering (SEARCH), Structuring (ASSESS), Decision & Planning (PLAN), Generation (EXECUTE), Validation

**Note**: Debugging chains often need CHARACTERIZE before EXECUTE to capture current behavior as a baseline for verifying the fix worked.

---

### 4. Operations

**Definition**: Manages the lifecycle of running systems — deployment, scaling, maintenance, upgrades, rollbacks. The pipeline performs actions on live infrastructure.

**Key Indicators**: "Deploy...", "Scale...", "Restart...", "Upgrade...", "Rollback...", "Maintain..."

**Common Domain Examples**:
| Domain | Subdomain | What's Operated |
|--------|-----------|-----------------|
| Prometheus | Cluster scaling | Prometheus replicas, storage sizing, federation |
| Kubernetes | Deployment management | Rolling updates, canary deploys, HPA tuning |
| RabbitMQ | Queue management | Queue policies, consumer scaling, vhost management |
| Terraform | State management | State moves, imports, drift detection |

**Canonical Chain**:
```
ADR -> PROBE -> PLAN -> GUARD -> SNAPSHOT -> EXECUTE -> VALIDATE -> OUTPUT
```

**Step Menu Families**: Observation (PROBE), Decision & Planning, Safety & Guarding, Generation (EXECUTE), Validation

**Profile-dependent steps**: GUARD, SNAPSHOT, and APPROVE are mandatory in Work/Production profiles but relaxed in Personal/CI. The chain shape changes significantly by profile — operations is the most profile-sensitive task type.

---

### 5. Configuration

**Definition**: Produces or validates configuration artifacts that control system behavior. Similar to generation but with schema constraints and often deterministic validation.

**Key Indicators**: "Configure...", "Set up...", "Add rule for...", "Define policy...", "Create config..."

**Common Domain Examples**:
| Domain | Subdomain | What's Configured |
|--------|-----------|-------------------|
| Prometheus | Alert rules | AlertManager routing, alert expressions, inhibition rules |
| Kubernetes | RBAC | Roles, RoleBindings, ServiceAccounts |
| Terraform | Provider config | Provider blocks, backend config, variable definitions |
| Helm | Values files | values.yaml overrides, chart dependencies |

**Canonical Chain**:
```
ADR -> RESEARCH -> GENERATE -> CONFORM -> LINT -> REFINE -> OUTPUT
```

**Step Menu Families**: Research & Gathering, Generation, Validation (CONFORM, LINT), Domain Extension

**What makes configuration different from generation**: Configuration artifacts have external schemas or specs they must conform to. The CONFORM and LINT steps are critical — they validate against the domain's spec, not just general quality. A generated blog post doesn't have a schema; a Helm values.yaml does.

---

### 6. Analysis

**Definition**: Investigates data, systems, or codebases to produce insights, recommendations, or reports. The pipeline's output is understanding, not artifacts.

**Key Indicators**: "Analyze...", "What's the impact of...", "Compare...", "How does X work?", "Assess the risk of..."

**Common Domain Examples**:
| Domain | Subdomain | What's Analyzed |
|--------|-----------|-----------------|
| Prometheus | Cardinality analysis | Metric cardinality impact, label explosion detection |
| Kubernetes | Resource analysis | CPU/memory utilization, right-sizing recommendations |
| Go | Dependency analysis | Module dependencies, vulnerability exposure, upgrade impact |
| Terraform | Drift detection | State vs. actual infrastructure comparison |

**Canonical Chain**:
```
ADR -> RESEARCH -> COMPILE -> ASSESS -> SYNTHESIZE -> REPORT
```

**Step Menu Families**: Research & Gathering, Structuring (COMPILE, ASSESS), Synthesis & Reporting

**Note**: Analysis chains often include BENCHMARK or COMPARE steps when quantitative comparison is needed. The output is a REPORT, not an artifact to be deployed.

---

### 7. Migration

**Definition**: Transforms systems, data, or artifacts from one version/format/state to another. The pipeline manages a transition with rollback safety.

**Key Indicators**: "Migrate from...", "Upgrade from...", "Convert...", "Move from X to Y...", "Port..."

**Common Domain Examples**:
| Domain | Subdomain | What's Migrated |
|--------|-----------|-----------------|
| Terraform | Version upgrade | HCL v0.x to v1.x, provider version bumps |
| Kubernetes | API migration | Deprecated API versions to current (e.g., extensions/v1beta1 to apps/v1) |
| Go | Module migration | dep to go modules, major version bumps |
| Database | Schema migration | Schema versions, data transformations |

**Canonical Chain**:
```
ADR -> CHARACTERIZE -> PLAN -> SIMULATE -> GUARD -> SNAPSHOT -> TRANSFORM -> VALIDATE -> OUTPUT
```

**Step Menu Families**: Validation (CHARACTERIZE), Decision & Planning, Safety & Guarding, Transformation, Validation

**Critical**: Migration chains MUST include CHARACTERIZE (capture current behavior), SNAPSHOT (restore point), and VALIDATE (verify migration succeeded). Skipping any of these for migrations is a blocking error. WHY: Migrations are one-way without these safety nets. A failed migration without a snapshot is data loss.

---

### 8. Monitoring

**Definition**: Sets up ongoing observation with threshold-based alerting or health checks. Unlike one-time analysis, monitoring produces persistent rules or dashboards that continue to observe.

**Key Indicators**: "Alert when...", "Watch for...", "Track...", "Set up monitoring for...", "Dashboard for..."

**Common Domain Examples**:
| Domain | Subdomain | What's Monitored |
|--------|-----------|------------------|
| Prometheus | Alert rule authoring | Alert expressions, routing rules, notification channels |
| Kubernetes | Cluster monitoring | Pod health, resource utilization, event watching |
| RabbitMQ | Queue monitoring | Queue depth alerts, consumer lag, connection monitoring |
| Grafana | Dashboard creation | Panel definitions, variable templates, alert annotations |

**Canonical Chain**:
```
ADR -> RESEARCH -> GENERATE -> CONFORM -> VALIDATE -> OUTPUT
```

**Step Menu Families**: Research & Gathering, Generation, Validation (CONFORM), Domain Extension

**Relationship to Configuration**: Monitoring overlaps heavily with Configuration — alert rules ARE configuration. The distinction is intent: Configuration focuses on "make the system behave this way", while Monitoring focuses on "observe the system and react to conditions". When classifying, use Monitoring as primary when the practitioner's goal is observability, Configuration when the goal is system behavior.

---

## Choosing Between Ambiguous Types

| If the subdomain... | Primary Type | Why |
|---------------------|-------------|-----|
| Creates new files/code from scratch | Generation | Output is novel artifact |
| Creates config files with schemas | Configuration | Output must CONFORM to external spec |
| Evaluates existing work | Review | Output is judgment, not artifact |
| Fixes broken things | Debugging | Starts from symptom, ends at resolution |
| Manages live systems | Operations | Acts on running infrastructure |
| Produces reports/insights | Analysis | Output is understanding, not action |
| Transitions between states | Migration | Changes format/version/location |
| Sets up ongoing observation | Monitoring | Output persists and continues to observe |

## When a Subdomain Spans Two Types

Assign the primary type based on the **most common practitioner workflow**. Add the secondary type when significant. The primary type determines the canonical chain backbone; the secondary type adds steps.

**Example**: Prometheus alerting
- Primary: `configuration` (practitioners write alert rules, which are config files)
- Secondary: `monitoring` (the purpose of those rules is observation)
- Chain effect: Uses Configuration's CONFORM/LINT backbone, adds Monitoring's ongoing validation concern

**Example**: Kubernetes deployment management
- Primary: `operations` (practitioners deploy, scale, rollback)
- Secondary: `configuration` (deployments are defined by YAML config)
- Chain effect: Uses Operations' GUARD/SNAPSHOT/EXECUTE backbone, adds Configuration's CONFORM step for YAML validation
