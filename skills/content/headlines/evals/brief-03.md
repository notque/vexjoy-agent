# Brief 03 — Tech: DNS upgrade regression

**Premise**: After a Kubernetes upgrade to 1.31, internal service discovery began failing intermittently. CoreDNS returned NXDOMAIN for services that existed. Root cause: a deprecated dual-stack flag silently changed default behavior, breaking resolution for IPv4-only services in dual-stack clusters.

**Key facts**: failures intermittent (cache masked them ~70% of the time); pod-to-pod IP traffic worked throughout; root cause was a changed default, not a bug; three days to diagnose.

**Audience**: platform engineers running Kubernetes.

**Formats requested**: article title, social post.
