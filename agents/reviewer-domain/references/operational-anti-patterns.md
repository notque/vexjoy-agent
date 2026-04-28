# Pragmatic Builder Roaster - Operational Corrections

Common operational mistakes, their signals, and the preferred response.

## Preferred Pattern: No Rollback Plan

**Signal**:
```bash
# deploy.sh
docker build -t myapp:latest .
docker-compose down
docker-compose up -d

# No rollback documented, no previous version tagged
```

**Why it matters**:
- When deployments fail at 3 AM, there's no time to design rollback procedures
- Panic decisions under pressure cause worse outages
- "We'll just revert the commit" doesn't account for database migrations, config changes, or stateful systems
- Testing rollback for the first time during an outage is too late

**Preferred action**:
```bash
# deploy.sh
#!/bin/bash
set -e

PREVIOUS_VERSION=$(docker ps --format '{{.Image}}' | grep myapp | head -1)
NEW_VERSION="myapp:$(git rev-parse --short HEAD)"

echo "Previous version: $PREVIOUS_VERSION"
echo "New version: $NEW_VERSION"

# Build and deploy
docker build -t "$NEW_VERSION" .
docker tag "$NEW_VERSION" myapp:latest
docker-compose down
docker-compose up -d

# Health check
if ! ./health_check.sh; then
    echo "Health check failed. Rolling back to $PREVIOUS_VERSION"
    docker tag "$PREVIOUS_VERSION" myapp:latest
    docker-compose down
    docker-compose up -d
    exit 1
fi

echo "Deployment successful. To rollback: docker tag $PREVIOUS_VERSION myapp:latest && docker-compose restart"
```

**Verification**:
- Every production deployment has a documented rollback path
- Even "simple" changes include a previous-version tag or revert plan
- Staging checks confirm the rollback procedure before production

---

## Preferred Pattern: Log Before and After Risky Operations

**Signal**:
```python
def process_payment(user_id, amount):
    # No logging before risky operation
    result = external_payment_api.charge(user_id, amount)

    # Only logs on success
    if result.success:
        logging.info(f"Payment successful for user {user_id}")

    return result
```

**Why it matters**:
- When debugging production failures, you need logs at failure points
- Absence of logs at error conditions means guessing what happened
- Cannot reconstruct request flow without correlation IDs
- Missing context (user_id, amount, API response) makes debugging impossible

**Preferred action**:
```python
def process_payment(user_id, amount):
    correlation_id = generate_correlation_id()

    # Log before risky operation
    logging.info("payment_attempt", extra={
        'correlation_id': correlation_id,
        'user_id': user_id,
        'amount': amount,
        'timestamp': time.time()
    })

    try:
        result = external_payment_api.charge(user_id, amount)

        # Log outcome
        logging.info("payment_result", extra={
            'correlation_id': correlation_id,
            'user_id': user_id,
            'amount': amount,
            'success': result.success,
            'transaction_id': result.transaction_id
        })

        return result
    except Exception as e:
        # Log errors with full context
        logging.error("payment_failed", extra={
            'correlation_id': correlation_id,
            'user_id': user_id,
            'amount': amount,
            'error': str(e),
            'error_type': type(e).__name__
        }, exc_info=True)
        raise
```

**Verification**:
- Logs exist before each external API call
- Error handlers include the same correlation ID and context
- State changes and decision branches emit a traceable record

---

## Preferred Pattern: Test Boundary and Failure Cases

**Signal**:
```python
def calculate_discount(cart_total, discount_percent):
    return cart_total * (discount_percent / 100)

# Tests only happy path
def test_calculate_discount():
    assert calculate_discount(100, 10) == 10.0
```

**Why it matters**:
- Edge cases ALWAYS happen in production
- Users send empty carts, negative numbers, null values
- Race conditions trigger under load
- Network partitions cause partial state
- No tests for cart_total=0, discount_percent=100, negative values, concurrent updates

**Preferred action**:
```python
def calculate_discount(cart_total, discount_percent):
    if cart_total < 0:
        raise ValueError("Cart total cannot be negative")
    if discount_percent < 0 or discount_percent > 100:
        raise ValueError("Discount must be between 0 and 100")

    return cart_total * (discount_percent / 100)

# Comprehensive tests
def test_calculate_discount_edge_cases():
    # Happy path
    assert calculate_discount(100, 10) == 10.0

    # Edge cases
    assert calculate_discount(0, 10) == 0.0  # Empty cart
    assert calculate_discount(100, 0) == 0.0  # No discount
    assert calculate_discount(100, 100) == 100.0  # Full discount

    # Error cases
    with pytest.raises(ValueError):
        calculate_discount(-100, 10)  # Negative cart
    with pytest.raises(ValueError):
        calculate_discount(100, -10)  # Negative discount
    with pytest.raises(ValueError):
        calculate_discount(100, 150)  # Over 100% discount
```

**Verification**:
- Boundary conditions are covered explicitly (0, max, negative, null)
- Error paths have dedicated assertions, not just happy-path checks
- Shared-state and partial-failure scenarios have repeatable tests

---

## Preferred Pattern: Protect External Dependencies with a Circuit Breaker

**Signal**:
```python
def get_user_recommendations(user_id):
    # No protection against failing external service
    recommendations = recommendation_service.get(user_id)
    return recommendations
```

**Why it matters**:
- When external service is down, every request waits for timeout (30s+)
- Cascading failures: slow external service makes your service slow
- Thread pool exhaustion from waiting on failed calls
- No graceful degradation path

**Preferred action**:
```python
from pybreaker import CircuitBreaker

recommendation_breaker = CircuitBreaker(
    fail_max=5,  # Open after 5 failures
    timeout_duration=60  # Stay open for 60s
)

@recommendation_breaker
def fetch_recommendations(user_id):
    return recommendation_service.get(user_id)

def get_user_recommendations(user_id):
    try:
        recommendations = fetch_recommendations(user_id)
        return recommendations
    except CircuitBreakerError:
        # Graceful degradation: return popular items
        logging.warning(f"Recommendation service circuit open for user {user_id}, using fallback")
        return get_popular_items()
    except Exception as e:
        logging.error(f"Failed to get recommendations: {e}")
        return get_popular_items()
```

**When to use**:
- All external service calls (APIs, databases, caches)
- Non-critical dependencies (recommendations, personalization)
- Implement fallback or degraded functionality

---

## Preferred Pattern: Validate User Input Before Use

**Signal**:
```python
@app.route('/search')
def search():
    query = request.args.get('q')
    # No validation or sanitization
    results = db.execute(f"SELECT * FROM products WHERE name LIKE '%{query}%'")
    return jsonify(results)
```

**Why it matters**:
- SQL injection vulnerability: `q=' OR '1'='1`
- XSS vulnerability: `q=<script>alert('xss')</script>`
- Resource exhaustion: `q=%` returns all records
- No input length limits

**Preferred action**:
```python
from flask import request, jsonify
from sqlalchemy import text

@app.route('/search')
def search():
    query = request.args.get('q', '')

    # Validate input
    if not query:
        return jsonify({'error': 'Query required'}), 400
    if len(query) > 100:
        return jsonify({'error': 'Query too long'}), 400
    if not query.replace(' ', '').isalnum():
        return jsonify({'error': 'Invalid characters in query'}), 400

    # Use parameterized query
    results = db.execute(
        text("SELECT * FROM products WHERE name LIKE :pattern LIMIT 100"),
        {'pattern': f'%{query}%'}
    ).fetchall()

    return jsonify([dict(r) for r in results])
```

**When to use**:
- All user input at API boundaries
- URL parameters, form data, JSON payloads
- File uploads (validate type, size, content)
- Sanitize for display to prevent XSS

---

## Preferred Pattern: Move Long-Running Work Off the Request Path

**Signal**:
```python
@app.route('/process-video', methods=['POST'])
def process_video():
    video_id = request.json['video_id']

    # Long-running operation blocks request thread
    video = download_video(video_id)  # 30 seconds
    processed = transcode_video(video)  # 2 minutes
    upload_result(processed)  # 20 seconds

    return jsonify({'status': 'success'})
```

**Why it matters**:
- Request thread blocked for 3+ minutes
- HTTP clients timeout (usually 30-60s)
- Thread pool exhausted under load
- No progress visibility for user

**Preferred action**:
```python
from celery import Celery

celery = Celery('tasks', broker='redis://localhost:6379')

@celery.task
def process_video_async(video_id):
    video = download_video(video_id)
    processed = transcode_video(video)
    upload_result(processed)
    return {'status': 'success'}

@app.route('/process-video', methods=['POST'])
def process_video():
    video_id = request.json['video_id']

    # Queue job and return immediately
    task = process_video_async.delay(video_id)

    return jsonify({
        'status': 'processing',
        'task_id': task.id,
        'status_url': f'/task-status/{task.id}'
    }), 202

@app.route('/task-status/<task_id>')
def task_status(task_id):
    task = process_video_async.AsyncResult(task_id)
    return jsonify({
        'state': task.state,
        'status': task.info
    })
```

**When to use**:
- Operations taking > 5 seconds
- Video/image processing
- Data exports
- Bulk operations
- External API calls with uncertain latency

---

## Preferred Pattern: Add Monitoring Before Launch

**Signal**:
```
Developer: "Let's launch and see what happens"
3 AM: System is down, no metrics, no alerts, no visibility
Team: "We should have added monitoring..."
```

**Why it matters**:
- Cannot diagnose issues without metrics and logs
- No baseline to compare against
- No alerts means outages go undetected
- Dashboards created during outages miss critical data

**Preferred action**:
```python
# Set up metrics BEFORE launch
from prometheus_client import Counter, Histogram, Gauge

requests_total = Counter('api_requests_total', 'Total requests', ['endpoint', 'method', 'status'])
request_duration = Histogram('api_request_duration_seconds', 'Request duration', ['endpoint'])
active_users = Gauge('active_users', 'Currently active users')
error_rate = Counter('api_errors_total', 'Total errors', ['endpoint', 'error_type'])

# Instrument all endpoints
@app.before_request
def start_timer():
    request.start_time = time.time()

@app.after_request
def record_metrics(response):
    duration = time.time() - request.start_time

    request_duration.labels(endpoint=request.endpoint).observe(duration)
    requests_total.labels(
        endpoint=request.endpoint,
        method=request.method,
        status=response.status_code
    ).inc()

    return response

# Set up alerts
alert_rules = """
groups:
  - name: api_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(api_errors_total[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"

      - alert: SlowRequests
        expr: histogram_quantile(0.95, api_request_duration_seconds) > 1.0
        for: 5m
        annotations:
          summary: "95th percentile latency > 1s"
"""
```

**When to use**:
- Before any production deployment
- Metrics, logs, traces, alerts set up during development
- Create dashboards and test alerts in staging
- Establish baseline before launch

---

## Preferred Pattern: Name Meaningful Constants

**Signal**:
```python
def should_retry(attempt):
    if attempt < 3:  # Why 3?
        return True
    return False

cache_ttl = 300  # Why 300?
max_connections = 50  # Why 50?
```

**Why it matters**:
- Unclear reasoning for values
- Cannot change without code deployment
- Different values for different environments not possible
- Difficult to tune under different load conditions

**Preferred action**:
```python
import os

class Config:
    # Document why these values
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))  # Balance between reliability and latency
    CACHE_TTL_SECONDS = int(os.getenv('CACHE_TTL', '300'))  # 5 minutes for user profile data
    DB_MAX_CONNECTIONS = int(os.getenv('DB_MAX_CONNECTIONS', '50'))  # Based on PG max_connections=200

    # Different values per environment
    if os.getenv('ENVIRONMENT') == 'production':
        DB_MAX_CONNECTIONS = 100
    elif os.getenv('ENVIRONMENT') == 'development':
        DB_MAX_CONNECTIONS = 5

def should_retry(attempt):
    return attempt < Config.MAX_RETRIES

cache.set(key, value, ttl=Config.CACHE_TTL_SECONDS)
db_pool = create_pool(max_connections=Config.DB_MAX_CONNECTIONS)
```

**When to use**:
- All timeouts, retries, limits, thresholds
- Values that may need tuning
- Values that differ per environment
- Document why each value is chosen

---

## Preferred Pattern: Size and Observe Database Connection Pools

**Signal**:
```python
def get_user(user_id):
    # Creates new connection every call
    conn = psycopg2.connect(
        host='localhost',
        database='mydb',
        user='user',
        password='password'
    )
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result
```

**Why it matters**:
- Database connection setup is expensive (TCP handshake, auth, session initialization)
- Creates hundreds of connections under load
- Database rejects connections after max_connections limit
- Connection overhead dominates query time for fast queries

**Preferred action**:
```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

# Create connection pool once at startup
engine = create_engine(
    'postgresql://user:password@localhost/mydb',
    poolclass=QueuePool,
    pool_size=20,  # Keep 20 connections open
    max_overflow=10,  # Allow 10 additional connections during spikes
    pool_timeout=30,  # Wait 30s for available connection
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_pre_ping=True  # Verify connection health before use
)

def get_user(user_id):
    # Reuse pooled connection
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM users WHERE id = :user_id"),
            {'user_id': user_id}
        ).fetchone()
    return result
```

**When to use**:
- All database connections
- Redis connections
- HTTP client connections (requests.Session)
- Any network resource accessed frequently
