# State Machine Verification

Review methodologies for state machines and stateful business logic.

## Review Checklist

### 1. State Enumeration
- [ ] All valid states documented
- [ ] Initial and terminal states identified
- [ ] Error/failure states identified

### 2. Transition Validation
- [ ] All valid transitions documented
- [ ] Invalid transitions explicitly rejected
- [ ] Guards/conditions specified
- [ ] Terminal states cannot exit

### 3. Concurrent Access
- [ ] State changes atomic
- [ ] Race conditions prevented
- [ ] Lock ordering prevents deadlock

### 4. Error Handling
- [ ] Error states have recovery paths
- [ ] Timeout handling specified
- [ ] Retry logic is idempotent

## Patterns

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

// Valid: pending->paid->shipped->delivered, pending/paid->cancelled
func (o *Order) SetStatus(newStatus OrderStatus) error {
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
func (t *Task) Start() error {
    if t.Status != TaskAssigned {
        return fmt.Errorf("cannot start task in status: %s", t.Status)
    }
    if t.Assignee == nil {
        return ErrNoAssignee
    }
    t.Status = TaskInProgress
    return nil
}
```

### State Machine with Timeout
```go
func (s *Session) Refresh() error {
    if s.Status != SessionActive {
        return ErrSessionNotActive
    }
    if s.IsExpired() {
        s.Status = SessionExpired
        return ErrSessionExpired
    }
    s.ExpiresAt = time.Now().Add(SessionTimeout)
    return nil
}
```

## Common Bugs

### Missing Transition Validation
```go
// BUG: Any transition allowed
func (o *Order) SetStatus(status OrderStatus) { o.Status = status }
// FIX: Validate transitions
func (o *Order) SetStatus(status OrderStatus) error {
    if !o.IsValidTransition(o.Status, status) { return ErrInvalidTransition }
    o.Status = status
    return nil
}
```

### Terminal States Escapable
```go
// BUG: Can modify completed order
func (o *Order) AddItem(item Item) { o.Items = append(o.Items, item) }
// FIX:
func (o *Order) AddItem(item Item) error {
    if o.Status == OrderCompleted || o.Status == OrderCancelled { return ErrOrderClosed }
    o.Items = append(o.Items, item)
    return nil
}
```

### Race Condition on State Change
```go
// BUG: Check-then-act race
if order.Status == "pending" { order.Status = "paid"; db.Save(order) }
// FIX: Atomic update
result := db.Exec("UPDATE orders SET status = ? WHERE id = ? AND status = ?",
    "paid", order.ID, "pending")
if result.RowsAffected == 0 { return ErrConcurrentModification }
```

### No Timeout Handling
```go
// BUG: Session never expires — no ExpiresAt field
// FIX: Add ExpiresAt, check in methods
func (s *Session) CheckExpiration() {
    if time.Now().After(s.ExpiresAt) && s.Status == SessionActive {
        s.Status = SessionExpired
    }
}
```

## State Transition Tables

### Order
| From | To | Valid? | Condition |
|------|-----|--------|-----------|
| pending | paid | Y | Payment successful |
| pending | cancelled | Y | User cancels |
| paid | shipped | Y | Dispatched |
| paid | cancelled | Y | Cancel before shipping |
| shipped | delivered | Y | Delivery confirmed |
| shipped | cancelled | N | Cannot cancel after shipment |
| delivered | any | N | Terminal |
| cancelled | any | N | Terminal |

### Task
| From | To | Valid? | Condition |
|------|-----|--------|-----------|
| pending | assigned | Y | Assignee set |
| assigned | in_progress | Y | User starts |
| assigned | pending | Y | Assignee removed |
| in_progress | completed | Y | Result provided |
| in_progress | failed | Y | Error occurred |
| completed | any | N | Terminal |
| failed | pending | Y | Retry allowed |

## Review Questions

1. **States**: All documented? Initial/terminal clear?
2. **Transitions**: Validation function? Invalid rejected with clear errors?
3. **Guards**: Preconditions checked before change? Failure handled?
4. **Concurrency**: Atomic? Race possible? Lock ordering?
5. **Errors**: Recovery path? Rollback mechanism?
6. **Persistence**: When persisted? What if persistence fails? Validation before or after?

## Code Review Template

```markdown
### State Machine: [Component]
**States**: [list] | Initial: [x] | Terminal: [x] | Error: [x]

**Transitions Verified:**
- [FROM] -> [TO]: [condition] Y/N

**Issues Found:**
1. **[Issue]** - `file.go:line` — [problem]. Impact: [what it allows]. Fix: [recommendation].

**Terminal Enforcement:** Y/N
**Concurrent Safety:** Y/N
**Timeout Handling:** Y/N
**Error Recovery:** Y/N
```
