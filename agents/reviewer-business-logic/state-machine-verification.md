# State Machine Verification

Methodologies for reviewing state machines and stateful business logic.

## State Machine Review Checklist

### 1. State Enumeration
- [ ] All valid states documented
- [ ] Initial state identified
- [ ] Terminal states identified
- [ ] Error/failure states identified

### 2. Transition Validation
- [ ] All valid transitions documented
- [ ] Invalid transitions explicitly rejected
- [ ] Transition guards/conditions specified
- [ ] Terminal states cannot be exited

### 3. Concurrent Access
- [ ] State changes are atomic
- [ ] Race conditions prevented
- [ ] Lock ordering prevents deadlock
- [ ] State persisted after validation

### 4. Error Handling
- [ ] Error states have recovery paths
- [ ] Timeout handling specified
- [ ] Retry logic is idempotent
- [ ] Partial failures handled

## State Machine Patterns

### Basic State Machine

```go
type OrderStatus string

const (
    OrderPending   OrderStatus = "pending"
    OrderPaid      OrderStatus = "paid"
    OrderShipped   OrderStatus = "shipped"
    OrderDelivered OrderStatus = "delivered"
    OrderCancelled OrderStatus = "cancelled"
)

type Order struct {
    ID     string
    Status OrderStatus
}

// Valid transitions:
// pending → paid → shipped → delivered
// pending → cancelled
// paid → cancelled

func (o *Order) SetStatus(newStatus OrderStatus) error {
    // Validate transition based on current status
    switch o.Status {
    case OrderPending:
        if newStatus != OrderPaid && newStatus != OrderCancelled {
            return ErrInvalidTransition
        }
    case OrderPaid:
        if newStatus != OrderShipped && newStatus != OrderCancelled {
            return ErrInvalidTransition
        }
    case OrderShipped:
        if newStatus != OrderDelivered {
            return ErrInvalidTransition
        }
    case OrderDelivered, OrderCancelled:
        // Terminal states - no transitions allowed
        return ErrTerminalState
    default:
        return ErrUnknownStatus
    }

    o.Status = newStatus
    return nil
}
```

### State Machine with Guards

```go
type TaskStatus string

const (
    TaskPending    TaskStatus = "pending"
    TaskAssigned   TaskStatus = "assigned"
    TaskInProgress TaskStatus = "in_progress"
    TaskCompleted  TaskStatus = "completed"
    TaskFailed     TaskStatus = "failed"
)

type Task struct {
    ID       string
    Status   TaskStatus
    Assignee *User
    Result   string
}

func (t *Task) Start() error {
    // Guard: can only start if assigned
    if t.Status != TaskAssigned {
        return fmt.Errorf("cannot start task in status: %s", t.Status)
    }

    // Guard: must have assignee
    if t.Assignee == nil {
        return ErrNoAssignee
    }

    t.Status = TaskInProgress
    return nil
}

func (t *Task) Complete(result string) error {
    // Guard: can only complete if in progress
    if t.Status != TaskInProgress {
        return fmt.Errorf("cannot complete task in status: %s", t.Status)
    }

    // Guard: result required
    if result == "" {
        return ErrEmptyResult
    }

    t.Status = TaskCompleted
    t.Result = result
    return nil
}
```

### State Machine with Timeout

```go
type Session struct {
    ID        string
    Status    SessionStatus
    StartedAt time.Time
    ExpiresAt time.Time
}

const SessionTimeout = 30 * time.Minute

func (s *Session) IsExpired() bool {
    return time.Now().After(s.ExpiresAt)
}

func (s *Session) Refresh() error {
    // Can only refresh active sessions
    if s.Status != SessionActive {
        return ErrSessionNotActive
    }

    // Check if already expired
    if s.IsExpired() {
        s.Status = SessionExpired
        return ErrSessionExpired
    }

    // Extend expiration
    s.ExpiresAt = time.Now().Add(SessionTimeout)
    return nil
}

func (s *Session) Terminate() error {
    // Can terminate from any non-terminal state
    if s.Status == SessionTerminated || s.Status == SessionExpired {
        return ErrSessionAlreadyTerminated
    }

    s.Status = SessionTerminated
    return nil
}
```

## Common State Machine Bugs

### 1. Missing Transition Validation

```go
// BUG: No validation - any transition allowed
func (o *Order) SetStatus(status OrderStatus) {
    o.Status = status  // Can go from delivered → pending (invalid!)
}

// FIX: Validate transitions
func (o *Order) SetStatus(status OrderStatus) error {
    if !o.IsValidTransition(o.Status, status) {
        return ErrInvalidTransition
    }
    o.Status = status
    return nil
}
```

### 2. Terminal States Escapable

```go
// BUG: Can modify completed order
func (o *Order) AddItem(item Item) {
    o.Items = append(o.Items, item)  // Even if order completed!
}

// FIX: Check terminal state
func (o *Order) AddItem(item Item) error {
    if o.Status == OrderCompleted || o.Status == OrderCancelled {
        return ErrOrderClosed
    }
    o.Items = append(o.Items, item)
    return nil
}
```

### 3. Race Condition on State Change

```go
// BUG: Check-then-act race
if order.Status == "pending" {
    // Another thread could change status here
    order.Status = "paid"
    db.Save(order)
}

// FIX: Atomic update
result := db.Exec(
    "UPDATE orders SET status = ? WHERE id = ? AND status = ?",
    "paid", order.ID, "pending",
)
if result.RowsAffected == 0 {
    return ErrConcurrentModification
}
```

### 4. No Timeout Handling

```go
// BUG: Session never expires
type Session struct {
    ID     string
    Status SessionStatus
}

// FIX: Add expiration tracking
type Session struct {
    ID        string
    Status    SessionStatus
    ExpiresAt time.Time
}

func (s *Session) CheckExpiration() {
    if time.Now().After(s.ExpiresAt) && s.Status == SessionActive {
        s.Status = SessionExpired
    }
}
```

## State Transition Tables

### Order State Machine

| From State | To State | Valid? | Condition |
|------------|----------|--------|-----------|
| pending | paid | ✅ | Payment successful |
| pending | cancelled | ✅ | User cancels before payment |
| paid | shipped | ✅ | Order dispatched |
| paid | cancelled | ✅ | Cancellation before shipping |
| shipped | delivered | ✅ | Delivery confirmed |
| shipped | cancelled | ❌ | Cannot cancel after shipment |
| delivered | any | ❌ | Terminal state |
| cancelled | any | ❌ | Terminal state |

### Task State Machine

| From State | To State | Valid? | Condition |
|------------|----------|--------|-----------|
| pending | assigned | ✅ | Assignee set |
| assigned | in_progress | ✅ | User starts task |
| assigned | pending | ✅ | Assignee removed |
| in_progress | completed | ✅ | Result provided |
| in_progress | failed | ✅ | Error occurred |
| completed | any | ❌ | Terminal state |
| failed | pending | ✅ | Retry allowed |

### Session State Machine

| From State | To State | Valid? | Condition |
|------------|----------|--------|-----------|
| active | refreshed | ✅ | Not expired |
| active | expired | ✅ | Timeout reached |
| active | terminated | ✅ | User logout |
| refreshed | active | ✅ | Immediate transition |
| expired | any | ❌ | Terminal state |
| terminated | any | ❌ | Terminal state |

## Reviewing State Machine Code

### Questions to Ask

1. **State Enumeration**
   - Are all states documented?
   - Is the initial state clear?
   - Which states are terminal?

2. **Transition Validation**
   - Is there a transition validation function?
   - Are all valid transitions documented?
   - Are invalid transitions rejected with clear errors?

3. **Guard Conditions**
   - Do transitions have preconditions?
   - Are preconditions checked before state change?
   - What happens if preconditions fail?

4. **Concurrent Access**
   - Is state change atomic?
   - Can two threads race on state change?
   - Is there lock ordering to prevent deadlock?

5. **Error Handling**
   - What if state change fails?
   - Is there a rollback mechanism?
   - Are error states recoverable?

6. **Persistence**
   - When is state persisted to database?
   - What if persistence fails?
   - Is validation before or after persistence?

### Code Review Template

```markdown
### State Machine: [Component Name]

**States Identified:**
- [list all states]
- Initial: [state]
- Terminal: [states]
- Error: [states]

**Transitions Verified:**
- [FROM] → [TO]: [condition] ✓/✗
- [FROM] → [TO]: [condition] ✓/✗

**Issues Found:**

1. **[Issue]** - `file.go:line`
   - **Problem**: [description]
   - **Impact**: [what this allows that shouldn't be allowed]
   - **Fix**: [recommendation]

**Terminal State Enforcement:** ✓/✗
**Concurrent Access Safety:** ✓/✗
**Timeout Handling:** ✓/✗
**Error Recovery:** ✓/✗
```

## Example Review

### Code Under Review

```go
type PaymentStatus string

const (
    PaymentPending   PaymentStatus = "pending"
    PaymentProcessing PaymentStatus = "processing"
    PaymentSucceeded PaymentStatus = "succeeded"
    PaymentFailed    PaymentStatus = "failed"
)

type Payment struct {
    ID     string
    Status PaymentStatus
    Amount float64
}

func (p *Payment) Process() error {
    p.Status = PaymentProcessing

    if err := chargeCard(p.Amount); err != nil {
        p.Status = PaymentFailed
        return err
    }

    p.Status = PaymentSucceeded
    return nil
}
```

### Review Findings

**CRITICAL Issues:**

1. **Missing Transition Validation** - `payment.go:15`
   - **Problem**: No check if payment is already processed
   - **Impact**: Can process same payment twice (double-charge)
   - **Fix**: Check status is pending before processing
   ```go
   if p.Status != PaymentPending {
       return ErrPaymentAlreadyProcessed
   }
   ```

2. **Terminal State Escapable** - `payment.go:15`
   - **Problem**: Can call Process() on succeeded payment
   - **Impact**: Double-charging, state corruption
   - **Fix**: Reject if already succeeded/failed
   ```go
   if p.Status == PaymentSucceeded || p.Status == PaymentFailed {
       return ErrPaymentClosed
   }
   ```

**HIGH Issues:**

3. **No Atomic State Update** - `payment.go:16-23`
   - **Problem**: Race condition if called concurrently
   - **Impact**: Two threads could both start processing
   - **Fix**: Use database atomic update with WHERE clause
   ```go
   result := db.Exec(
       "UPDATE payments SET status = ? WHERE id = ? AND status = ?",
       PaymentProcessing, p.ID, PaymentPending,
   )
   if result.RowsAffected == 0 {
       return ErrConcurrentProcessing
   }
   ```
