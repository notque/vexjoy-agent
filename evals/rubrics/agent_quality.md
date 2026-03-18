# Agent Quality Rubric

Use this rubric to evaluate the quality of an agent specification.

## Evaluation Criteria

### 1. Structure (25 points)
- Valid YAML frontmatter with required fields (name, description, version)
- Clear section organization
- Proper markdown formatting

### 2. Clarity (25 points)
- Description clearly explains the agent's purpose
- Triggers are specific and unambiguous
- Examples show realistic usage

### 3. Completeness (25 points)
- Appropriate tool list for the task
- Handles common edge cases
- Includes error handling guidance

### 4. Usability (25 points)
- Easy to understand when to use
- Clear differentiation from similar agents
- Actionable instructions

## Scoring Guidelines

- **90-100**: Excellent - Ready for production use
- **75-89**: Good - Minor improvements needed
- **60-74**: Adequate - Several areas need work
- **Below 60**: Needs significant revision

## Red Flags (Automatic Deductions)
- Missing required frontmatter fields (-20)
- No clear triggers defined (-15)
- Copy-pasted generic content (-10)
- Contradictory instructions (-10)
