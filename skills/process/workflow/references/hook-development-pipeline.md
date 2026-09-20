# Hook development contract

Specify event, input schema, action, timeout budget, fail behavior, and observable
receipt before implementation. Hook code must parse bounded input, avoid network
or heavy imports on the hot path, write diagnostics to stderr/log storage, and
reserve stdout for the host protocol.

Tests cover valid, missing, malformed, oversized, and hostile input; unavailable
dependencies; timeout; and required exit/output semantics. Measure warm and cold
latency against the declared budget. A safety hook may warn on uncertainty but
must not silently reinterpret an invalid model/service result as permission.

Register through the repository's settings mechanism using parse-modify-validate;
do not overwrite unrelated hooks. Re-read the effective configuration and run a
real host event after registration. Document event, path, protocol, failure mode,
logs, disable/rollback procedure, and measured latency.
