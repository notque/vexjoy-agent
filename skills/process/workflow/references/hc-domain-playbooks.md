# Hill-climb metric map

Use these local distinctions when selecting the one metric; repository-specific
commands replace examples.

| Domain | Metric | Fixture proof | Non-negotiable floor |
|---|---|---|---|
| game rendering | p1-low FPS or p99 frame time | scene/input trace/seed/viewport/browser | same end-state and no uncaught error |
| HTTP API | p99 latency | request corpus, DB snapshot, concurrency, warmed pool | baseline status and response shape |
| CI | critical-path wall time, not summed job time | workflow, runner class, cache state | same required jobs/checks/test count |
| test suite | developer-observed wall time | selection, workers, DB/container state, seed | same collected count, pass, coverage floor |
| web bundle | compressed initial-route bytes | lockfile, bundler, mode, targets | route build/render/smoke and support matrix |
| memory | peak RSS or leak slope—choose one | workload, concurrency, runtime, allocator/GC | functional suite plus latency/throughput bound |
| LLM pipeline | total tokens per completed task | frozen request corpus, model, tools | scored task success does not drop |

For sampled metrics use repeated medians and baseline spread. For deterministic
bytes run twice to prove reproducibility. Never count removed behavior as an
optimization unless that scope reduction was explicitly accepted.
