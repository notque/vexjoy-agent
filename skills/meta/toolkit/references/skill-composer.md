# Skill composition contract

Compose only when distinct skills own distinct decisions or artifacts. Model
the graph explicitly: node, required inputs, produced artifact, owner, and
acceptance check. Parallelize nodes only when they neither mutate overlapping
surfaces nor consume each other's outputs.

Use `scripts/skill-composer/discover_skills.py`, `build_dag.py`, and
`validate.py`; their emitted schema is authoritative. Reject unknown skills,
cycles, missing producers, incompatible bindings, and ambiguous shared writes
before execution. Preserve each node's failure receipt and stop dependents when
a required predecessor fails.
