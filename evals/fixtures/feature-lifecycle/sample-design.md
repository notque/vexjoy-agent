# Design: Rate Limiter

## Problem Statement
API endpoints accept unlimited requests per client, leading to resource exhaustion under load. Need per-client rate limiting using token bucket algorithm.

## Requirements
- [ ] Limit requests to 100/minute per API key
- [ ] Return 429 Too Many Requests when limit exceeded
- [ ] Include Retry-After header in 429 responses
- [ ] Token bucket with configurable burst size
- [ ] Rate limit state stored in-memory (Redis optional future enhancement)

## Selected Approach
Token bucket algorithm with in-memory storage. Chosen over sliding window (simpler, well-understood) and leaky bucket (token bucket allows bursts, better UX).

## Components
1. Rate limiter middleware (Go HTTP middleware)
2. Token bucket implementation (concurrent-safe)
3. Rate limit configuration (per-route overrides)
4. HTTP response helpers (429 + headers)

## Domain Agents
- golang-general-engineer: All implementation (Go project)

## Open Questions
- Should rate limits be configurable per API key tier?
- Should we log rate limit events?

## Trade-offs Accepted
- In-memory only means limits reset on restart (acceptable for v1)
- Per-process limits (no cross-instance coordination)
