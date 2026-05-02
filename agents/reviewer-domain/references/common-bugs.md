# Common Business Logic Bugs

Real-world bugs found in code reviews with examples.

## Calculation Errors

### Integer Division Truncation
```go
// BUG: Integer division loses precision
averagePrice := totalPrice / itemCount  // Returns 2 when should be 2.5
// FIX:
averagePrice := float64(totalPrice) / float64(itemCount)
```

### Order of Operations
```go
// BUG:
taxedPrice := price * 1 + taxRate  // Should be: price * (1 + taxRate)
// FIX:
taxedPrice := price * (1 + taxRate)
```

### Rounding Errors Compound
```go
// BUG: Rounding each item compounds errors
total := 0.0
for _, item := range items {
    total += math.Round(item.Price * taxRate * 100) / 100
}
// FIX: Round final total only
total := 0.0
for _, item := range items {
    total += item.Price * taxRate
}
total = math.Round(total * 100) / 100
```

### Percentage Calculation Reversed
```go
// BUG: This is the discount amount, not final price
discountedPrice := price * discountPercent / 100
// FIX:
discountedPrice := price - (price * discountPercent / 100)
```

## Off-by-One Errors

### Range Checks
```go
// BUG: Excludes last valid value
if page > totalPages {  // User can request page 11 when totalPages=10
    return ErrInvalidPage
}
// FIX:
if page < 1 || page > totalPages {
    return ErrInvalidPage
}
```

### Array Iteration
```go
// BUG: <= causes panic on last iteration
for i := 0; i <= len(items); i++ {
    process(items[i])
}
// FIX: Use <
for i := 0; i < len(items); i++ {
    process(items[i])
}
```

### Pagination
```go
// BUG: Wrong if not evenly divisible
totalPages := totalItems / pageSize
// FIX: Ceiling division
totalPages := (totalItems + pageSize - 1) / pageSize
```

## State Transition Errors

### Missing State Validation
```go
// BUG: No validation of current state
func (o *Order) Ship() error {
    o.Status = "shipped"  // What if already cancelled?
    return nil
}
// FIX:
func (o *Order) Ship() error {
    if o.Status != "paid" {
        return fmt.Errorf("cannot ship order in status: %s", o.Status)
    }
    o.Status = "shipped"
    return nil
}
```

### Terminal State Escapable
```go
// BUG: Can transition out of terminal state
func (t *Task) SetStatus(status string) {
    t.Status = status
}
// FIX:
func (t *Task) SetStatus(status string) error {
    if t.Status == "completed" || t.Status == "cancelled" {
        return ErrTerminalState
    }
    t.Status = status
    return nil
}
```

### Race Condition on State Change
```go
// BUG: Check-then-act race
if order.Status == "pending" {
    order.Status = "confirmed"
    db.Save(order)
}
// FIX: Atomic update with WHERE
result := db.Exec("UPDATE orders SET status = ? WHERE id = ? AND status = ?",
    "confirmed", order.ID, "pending")
if result.RowsAffected == 0 {
    return ErrInvalidStateTransition
}
```

## Validation Errors

### Missing Input Validation
```go
// BUG: Negative quantity possible
func CreateOrder(quantity int) (*Order, error) {
    return &Order{Quantity: quantity}, nil
}
// FIX:
func CreateOrder(quantity int) (*Order, error) {
    if quantity < 1 {
        return nil, ErrInvalidQuantity
    }
    return &Order{Quantity: quantity}, nil
}
```

### Null/Empty Conflation
```go
// BUG: Treats null and empty identically
if user.MiddleName == "" {
    // Triggers for both null and ""
}
// FIX: Handle separately
if user.MiddleName == nil {
    // No data provided
} else if *user.MiddleName == "" {
    // Explicitly empty
}
```

## Race Conditions

### Check-Then-Act
```go
// BUG: Race between check and act
if inventory.Available(productID) > 0 {
    inventory.Decrement(productID)  // Negative inventory possible
}
// FIX: Atomic decrement-if-available
if err := inventory.DecrementIfAvailable(productID); err != nil {
    return ErrOutOfStock
}
```

### Double-Spend
```go
// BUG: Balance checked separately from deduction
balance := accounts.GetBalance(userID)
if balance >= amount {
    accounts.Deduct(userID, amount)
}
// FIX: Atomic deduct-if-sufficient
if err := accounts.DeductIfSufficient(userID, amount); err != nil {
    return ErrInsufficientFunds
}
```

### Lost Update
```go
// BUG: Read-modify-write race
counter := cache.Get("view_count")
counter++
cache.Set("view_count", counter)
// FIX: Atomic increment
cache.Increment("view_count", 1)
```

## Edge Case Handling

### Division by Zero
```go
// BUG:
averageRating := totalStars / reviewCount  // Panics if 0
// FIX:
var averageRating float64
if reviewCount > 0 {
    averageRating = float64(totalStars) / float64(reviewCount)
}
```

### Empty Collection
```go
// BUG:
firstItem := items[0]  // Panics if empty
// FIX:
if len(items) == 0 {
    return ErrNoItems
}
firstItem := items[0]
```

### Null Pointer
```go
// BUG:
userName := user.Profile.Name  // Panics if Profile nil
// FIX:
if user.Profile != nil {
    userName = user.Profile.Name
} else {
    userName = "Anonymous"
}
```

## Failure Mode Errors

### Partial Failure Not Handled
```go
// BUG: No rollback if 2nd op fails
err1 := createUser(user)
err2 := sendWelcomeEmail(user.Email)
// FIX:
tx := db.Begin()
if err := createUser(tx, user); err != nil {
    return err
}
if err := sendWelcomeEmail(user.Email); err != nil {
    tx.Rollback()
    return err
}
tx.Commit()
```

### Missing Error Propagation
```go
// BUG: Error ignored
func ProcessOrder(order *Order) {
    chargePayment(order.PaymentMethod, order.Total)
    updateInventory(order.Items)
}
// FIX:
func ProcessOrder(order *Order) error {
    if err := chargePayment(order.PaymentMethod, order.Total); err != nil {
        return fmt.Errorf("payment failed: %w", err)
    }
    if err := updateInventory(order.Items); err != nil {
        refundPayment(order.PaymentMethod, order.Total)
        return fmt.Errorf("inventory update failed: %w", err)
    }
    return nil
}
```

### Non-Idempotent Retry
```go
// BUG: Retrying increments multiple times
for retries := 0; retries < 3; retries++ {
    incrementCounter(userID)
    if err == nil { break }
}
// FIX: Make idempotent
transactionID := generateUniqueID()
for retries := 0; retries < 3; retries++ {
    err := incrementCounterIdempotent(userID, transactionID)
    if err == nil { break }
}
```

## Data Consistency

### Invariant Violation
```go
// BUG: Inventory can go negative
inventory.Quantity -= soldQuantity
// FIX:
if inventory.Quantity < soldQuantity {
    return ErrInsufficientInventory
}
inventory.Quantity -= soldQuantity
```

### Orphaned References
```go
// BUG: Deleting user leaves orphaned orders
db.Delete(&user)
// FIX:
orderCount := db.Where("user_id = ?", user.ID).Count(&Order{})
if orderCount > 0 {
    return ErrUserHasOrders
}
db.Delete(&user)
```

### Denormalized Data Out of Sync
```go
// BUG: Total not recalculated when items change
order.Items = append(order.Items, newItem)
// FIX:
order.Items = append(order.Items, newItem)
order.Total = calculateTotal(order.Items)
```
