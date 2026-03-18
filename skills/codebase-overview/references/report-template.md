# Codebase Overview Report Template

Standard markdown output template for the codebase-overview skill. Fill in all sections with evidence from examined files. Use absolute paths throughout.

---

```markdown
# Codebase Overview: [Project Name]

**Generated**: [Date/Time]
**Directory**: [Absolute path]

---

## 1. Project Identity

**Type**: [Language] / [Framework]
**Tech Stack**:
- Language: [Language + version]
- Framework: [Framework + version]
- Database: [Database technology]
- Testing: [Testing framework]
- Build Tools: [Build/task tools]

**Repository**: [Git remote URL if available]

---

## 2. Quick Start

**Entry Points**:
- [File path]: [Description - e.g., "Main application server"]
- [File path]: [Description - e.g., "CLI tool"]

**Run Application**:
```bash
[Command to start - from package.json scripts, Makefile, README]
```

**Run Tests**:
```bash
[Command to run tests]
```

**Install Dependencies**:
```bash
[Command to install deps]
```

---

## 3. Architecture Overview

**Architectural Pattern**: [Pattern name - e.g., "Layered architecture with service layer"]

**Directory Structure**:
```
/absolute/path/
├── [dir1]/     # [Purpose]
├── [dir2]/     # [Purpose]
└── [dir3]/     # [Purpose]
```

**Request Flow** (typical path):
1. [Entry point file] - [What it does]
2. [Routing file] - [What it does]
3. [Handler file] - [What it does]
4. [Service file] - [What it does]
5. [Model/DB file] - [What it does]

---

## 4. Core Modules

### [Module/Package 1]
**Location**: [Path]
**Responsibility**: [What it does]
**Key files**: [List 3-5 important files]

### [Module/Package 2]
**Location**: [Path]
**Responsibility**: [What it does]
**Key files**: [List 3-5 important files]

[Repeat for 5-7 major modules]

---

## 5. Data Layer

**Database**: [Technology - PostgreSQL, MongoDB, etc.]

**Key Models**:
- **[Model1]** ([file path]): [Description, primary fields]
- **[Model2]** ([file path]): [Description, primary fields]
- **[Model3]** ([file path]): [Description, primary fields]

**Relationships**:
- [Model1] has many [Model2]
- [Model2] belongs to [Model1]

**Schema Management**: [How migrations work - Alembic, Flyway, etc.]

---

## 6. API Surface

**Type**: [REST, GraphQL, gRPC, etc.]

**Key Endpoints**:
- `[METHOD] /path` - [Description] ([handler file])
- `[METHOD] /path` - [Description] ([handler file])
- `[METHOD] /path` - [Description] ([handler file])

**Authentication**: [Method - JWT, OAuth, API keys, etc.]

**API Documentation**: [Link to OpenAPI spec, GraphQL playground, etc.]

---

## 7. Configuration

**Environment Variables** (from .env.example or config files):
- `VAR_NAME`: [Purpose]
- `VAR_NAME`: [Purpose]

**Config Files**:
- [Path]: [Purpose]
- [Path]: [Purpose]

**External Dependencies**:
- [Service/API name]: [Purpose]
- [Service/API name]: [Purpose]

---

## 8. Testing

**Framework**: [pytest, Jest, Go testing, etc.]

**Test Organization**:
- [Path]: [Test category - unit, integration, etc.]
- [Path]: [Test category]

**Coverage**: [If available from config or recent runs]

**Running Tests**:
```bash
[Command with common options]
```

---

## 9. Key Patterns and Conventions

**Design Patterns**:
- [Pattern name]: [Where used, evidence]
- [Pattern name]: [Where used, evidence]

**Code Conventions**:
- [Convention - e.g., "Service classes follow ServiceNameService pattern"]
- [Convention - e.g., "All API handlers return standardized response format"]

**Error Handling**: [Approach - e.g., "Custom exception hierarchy, centralized handler"]

---

## 10. Development Activity

**Recent Commit Themes** (last 10 commits):
- [Theme 1]: [Brief description, commit references]
- [Theme 2]: [Brief description, commit references]

**Active Development Areas**:
- [Area being worked on]
- [Area being worked on]

---

## 11. Contributing Quick Start

**To add a new feature**:
1. [Steps based on architecture - e.g., "Create model in models/"]
2. [Next step - e.g., "Add API endpoint in routes/"]
3. [Next step - e.g., "Implement service logic in services/"]
4. [Next step - e.g., "Write tests in tests/"]

**Common Tasks**:
- Build: `[command]`
- Lint: `[command]`
- Format: `[command]`
- Database migrations: `[command]`

---

## 12. Dependencies

**Production Dependencies** (top 10 by importance):
- [Package name] ([version]): [Purpose]
- [Package name] ([version]): [Purpose]

**Development Dependencies** (key ones):
- [Package name] ([version]): [Purpose]
- [Package name] ([version]): [Purpose]

---

## 13. Files Examined

This overview was built by examining the following files:

**Configuration**: [list absolute paths]
**Entry Points**: [list absolute paths]
**Core Modules**: [list absolute paths]
**Data Layer**: [list absolute paths]
**API Layer**: [list absolute paths]
**Tests**: [list absolute paths]

**Total files examined**: [Count]

---

## Notes

[Any important observations, warnings, or recommendations]
```
