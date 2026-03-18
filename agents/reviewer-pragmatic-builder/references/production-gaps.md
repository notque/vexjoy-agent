# Pragmatic Builder Roaster - Production Gaps Catalog

Comprehensive catalog of common production readiness gaps and their solutions.

## Category: Deployment and Rollback

### Gap: No Documented Rollback Procedure

**Symptoms**:
- Deployment scripts exist but no rollback documentation
- Team assumes "we'll revert the commit" without testing
- No automated rollback triggers

**Cause**:
Rollback procedures are treated as an afterthought instead of core deployment infrastructure. Teams focus on happy-path deployments.

**Solution**:
```bash
# In deployment script, document rollback steps
# deploy.sh
deploy() {
    # ... deployment logic ...
    echo "To rollback: ./rollback.sh $(git rev-parse HEAD)"
}

# rollback.sh
rollback_to_commit() {
    git checkout $1
    docker-compose down
    docker-compose up -d
    ./health_check.sh
}
```

**Prevention**:
- Write rollback script before deployment script
- Test rollback procedure in staging
- Automate rollback triggers based on health checks
- Include rollback steps in deployment documentation

---

### Gap: Missing Health Checks

**Symptoms**:
- Deployments complete but app is broken
- Load balancer keeps sending traffic to unhealthy instances
- No automated verification of deployment success

**Cause**:
No programmatic health check endpoints, or health checks not integrated into deployment process.

**Solution**:
```python
# app.py
@app.route('/health')
def health_check():
    # Check database connection
    # Check external dependencies
    # Check critical resources
    return {"status": "healthy", "timestamp": time.time()}

# In deployment:
./deploy.sh && curl http://localhost:8000/health || ./rollback.sh
```

**Prevention**:
- Implement /health and /ready endpoints
- Health checks verify database, cache, external APIs
- Integration with load balancers
- Automated deployment verification

---

## Category: Error Handling

### Gap: No Retry Logic for External Calls

**Symptoms**:
- Transient network failures cause complete request failures
- External API rate limits cause cascading failures
- No exponential backoff or jitter

**Cause**:
External calls treated as reliable without retry mechanisms.

**Solution**:
```python
import time
import random

def retry_with_backoff(func, max_retries=3, base_delay=1):
    for attempt in range(max_retries):
        try:
            return func()
        except TransientError as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            time.sleep(delay)
```

**Prevention**:
- Wrap all external calls in retry logic
- Implement exponential backoff with jitter
- Use circuit breakers for cascading failures
- Log retry attempts for visibility

---

### Gap: Silent Failures in Background Jobs

**Symptoms**:
- Background tasks fail without notification
- Errors logged but no alerts triggered
- Data processing silently stops

**Cause**:
No monitoring or alerting for asynchronous job failures.

**Solution**:
```python
def process_job(job_id):
    try:
        # ... job logic ...
        metrics.increment('jobs.success')
    except Exception as e:
        metrics.increment('jobs.failure')
        logger.error(f"Job {job_id} failed", exc_info=True, extra={'job_id': job_id})
        alert_on_call(f"Critical job failure: {job_id}")
        raise
```

**Prevention**:
- Emit metrics for job success/failure
- Alert on job failure rates
- Implement dead letter queues
- Log job failures with context

---

## Category: Observability

### Gap: No Structured Logging

**Symptoms**:
- Logs are free-form strings, difficult to query
- Cannot filter by correlation ID, user ID, or request ID
- Debugging requires grepping through unstructured text

**Cause**:
Using print statements or basic logging without structure.

**Solution**:
```python
import logging
import json

# Before
logging.info(f"User {user_id} purchased item {item_id}")

# After
logging.info("user_purchase", extra={
    'event_type': 'purchase',
    'user_id': user_id,
    'item_id': item_id,
    'amount': amount,
    'correlation_id': request.correlation_id
})
```

**Prevention**:
- Use structured logging libraries (structlog, python-json-logger)
- Include correlation IDs in all log entries
- Define standard log fields (timestamp, level, service, correlation_id)
- Store logs in queryable backend (Elasticsearch, Splunk)

---

### Gap: Missing Metrics for Critical Paths

**Symptoms**:
- Cannot answer "how many requests are failing?"
- No visibility into latency percentiles
- Resource usage unknown until system fails

**Cause**:
Metrics not instrumented for critical code paths.

**Solution**:
```python
from prometheus_client import Counter, Histogram

request_count = Counter('api_requests_total', 'Total API requests', ['endpoint', 'status'])
request_duration = Histogram('api_request_duration_seconds', 'Request duration', ['endpoint'])

@request_duration.labels(endpoint='/api/users').time()
def get_users():
    # ... logic ...
    request_count.labels(endpoint='/api/users', status='200').inc()
```

**Prevention**:
- Instrument all API endpoints with request count, duration, error rate
- Track resource usage (CPU, memory, connections)
- Monitor queue depths and processing rates
- Set up dashboards before going to production

---

## Category: Edge Cases

### Gap: No Input Validation

**Symptoms**:
- Application crashes on empty input, null values, or extreme values
- SQL injection or XSS vulnerabilities
- Negative numbers where only positive expected

**Cause**:
Trusting user input without validation.

**Solution**:
```python
def create_user(username, age):
    if not username or len(username) < 3:
        raise ValueError("Username must be at least 3 characters")
    if age < 0 or age > 150:
        raise ValueError("Invalid age")
    # ... create user ...
```

**Prevention**:
- Validate all input at API boundaries
- Use schema validation (Pydantic, JSON Schema)
- Test with empty, null, negative, max values
- Sanitize user input to prevent injection attacks

---

### Gap: Race Conditions in Concurrent Code

**Symptoms**:
- Occasional data corruption under load
- Duplicate records created intermittently
- Cache inconsistencies

**Cause**:
No synchronization for concurrent access to shared resources.

**Solution**:
```python
import threading

class SafeCounter:
    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()

    def increment(self):
        with self._lock:
            self._value += 1
        return self._value
```

**Prevention**:
- Identify shared mutable state
- Use locks, atomic operations, or message passing
- Test under concurrent load
- Use database constraints for data integrity

---

## Category: Scalability

### Gap: No Database Query Optimization

**Symptoms**:
- Slow page loads as data grows
- Database CPU at 100%
- N+1 query problems

**Cause**:
Missing indexes, unoptimized queries, or ORM misuse.

**Solution**:
```sql
-- Before: Full table scan
SELECT * FROM users WHERE email = 'user@example.com';

-- After: Index on email
CREATE INDEX idx_users_email ON users(email);

-- N+1 fix: Use joins instead of separate queries
SELECT users.*, orders.* FROM users
JOIN orders ON users.id = orders.user_id
WHERE users.id IN (1, 2, 3);
```

**Prevention**:
- Add indexes for frequently queried columns
- Use EXPLAIN to analyze query plans
- Monitor slow query logs
- Use ORM select_related/prefetch_related
- Load test with production-scale data

---

### Gap: No Caching Strategy

**Symptoms**:
- Expensive computations repeated every request
- Database overloaded with identical queries
- No cache invalidation strategy

**Cause**:
Not caching expensive operations or caching without invalidation.

**Solution**:
```python
from functools import lru_cache
import time

@lru_cache(maxsize=128)
def get_user_profile(user_id):
    # Expensive computation
    return expensive_db_query(user_id)

# Or with TTL
cache = {}
def get_with_ttl(key, ttl=300):
    if key in cache:
        value, timestamp = cache[key]
        if time.time() - timestamp < ttl:
            return value
    # Fetch fresh value
    cache[key] = (value, time.time())
    return value
```

**Prevention**:
- Cache expensive computations with TTL
- Implement cache invalidation strategy
- Monitor cache hit rates
- Use distributed cache for multi-instance deployments

---

## Category: Resource Management

### Gap: Resource Leaks (Connections, File Handles)

**Symptoms**:
- "Too many open files" errors
- Database connection pool exhausted
- Memory usage grows over time

**Cause**:
Not closing resources properly, especially in error paths.

**Solution**:
```python
# Before: Resource leak
def process_file(filepath):
    f = open(filepath)
    data = f.read()
    # Forgot to close!

# After: Context manager
def process_file(filepath):
    with open(filepath) as f:
        data = f.read()
    # Automatically closed
```

**Prevention**:
- Always use context managers (with statements)
- Set connection pool limits
- Monitor open file descriptors
- Implement resource cleanup in finally blocks

---

### Gap: No Rate Limiting

**Symptoms**:
- API overloaded by single abusive user
- No protection against DDoS
- Resource exhaustion from legitimate traffic spikes

**Cause**:
No rate limiting on API endpoints or background jobs.

**Solution**:
```python
from flask_limiter import Limiter

limiter = Limiter(app, key_func=lambda: request.remote_addr)

@app.route('/api/expensive')
@limiter.limit("10 per minute")
def expensive_operation():
    # Protected by rate limit
    pass
```

**Prevention**:
- Implement per-user and per-IP rate limits
- Add rate limiting to expensive operations
- Return 429 status with Retry-After header
- Monitor rate limit hit counts
