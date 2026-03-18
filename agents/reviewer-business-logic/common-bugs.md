# Common Business Logic Bugs

Real-world business logic bugs found in code reviews with examples.

## Calculation Errors

### Integer Division Truncation

```go
// BUG: Integer division loses precision
averagePrice := totalPrice / itemCount  // Returns 2 when should be 2.5

// FIX: Use float division
averagePrice := float64(totalPrice) / float64(itemCount)
```

### Order of Operations

```go
// BUG: Wrong order causes incorrect result
taxedPrice := price * 1 + taxRate  // Should be: price * (1 + taxRate)

// FIX: Explicit parentheses
taxedPrice := price * (1 + taxRate)
```

### Rounding Errors Compound

```go
// BUG: Rounding each item compounds errors
total := 0.0
for _, item := range items {
    total += math.Round(item.Price * taxRate * 100) / 100  // Rounds each
}
// $1.01 + $1.01 + $1.01 = $3.03, but should be $3.02

// FIX: Round final total only
total := 0.0
for _, item := range items {
    total += item.Price * taxRate
}
total = math.Round(total * 100) / 100
```

### Percentage Calculation Reversed

```go
// BUG: Discount calculation backwards
discountedPrice := price - (price * discountPercent / 100)  // Correct
discountedPrice := price * discountPercent / 100           // WRONG - This is the discount amount, not final price
```

## Off-by-One Errors

### Range Checks

```go
// BUG: Excludes last valid value
if page > totalPages {  // Should be: page >= totalPages
    return ErrInvalidPage
}
// User can request page 11 when totalPages=10

// FIX: Use >= for exclusive upper bound
if page < 1 || page > totalPages {
    return ErrInvalidPage
}
```

### Array Iteration

```go
// BUG: Index out of bounds
for i := 0; i <= len(items); i++ {  // Should be: i < len(items)
    process(items[i])  // Panics on last iteration
}

// FIX: Use < not <=
for i := 0; i < len(items); i++ {
    process(items[i])
}
```

### Pagination

```go
// BUG: Last page calculation wrong
totalPages := totalItems / pageSize  // Wrong if not evenly divisible

// FIX: Ceiling division
totalPages := (totalItems + pageSize - 1) / pageSize
// Or: totalPages := int(math.Ceil(float64(totalItems) / float64(pageSize)))
```

## State Transition Errors

### Missing State Validation

```go
// BUG: No validation of current state
func (o *Order) Ship() error {
    o.Status = "shipped"  // What if already cancelled or shipped?
    return nil
}

// FIX: Validate current state
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
// BUG: Can transition out of terminal "completed" state
func (t *Task) SetStatus(status string) {
    t.Status = status  // No check if current status is terminal
}

// FIX: Enforce terminal states
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
// BUG: Check-then-act race condition
if order.Status == "pending" {
    // Another thread could change status here
    order.Status = "confirmed"
    db.Save(order)
}

// FIX: Atomic update with WHERE clause
result := db.Exec("UPDATE orders SET status = ? WHERE id = ? AND status = ?",
    "confirmed", order.ID, "pending")
if result.RowsAffected == 0 {
    return ErrInvalidStateTransition
}
```

## Validation Errors

### Missing Input Validation

```go
// BUG: No validation - negative quantity possible
func CreateOrder(quantity int) (*Order, error) {
    return &Order{Quantity: quantity}, nil  // Negative = refund/credit?
}

// FIX: Validate input ranges
func CreateOrder(quantity int) (*Order, error) {
    if quantity < 1 {
        return nil, ErrInvalidQuantity
    }
    return &Order{Quantity: quantity}, nil
}
```

### Incomplete Email Validation

```go
// BUG: Only checks format, not other issues
func IsValidEmail(email string) bool {
    return strings.Contains(email, "@")  // Too weak
}

// Issues: allows "  user@example.com  ", "user@@example.com", very long emails

// FIX: Complete validation
func IsValidEmail(email string) bool {
    email = strings.TrimSpace(email)
    if len(email) == 0 || len(email) > 320 {
        return false
    }
    // Use proper regex or library for email validation
    return emailRegex.MatchString(email)
}
```

### Null/Empty Conflation

```go
// BUG: Treats null and empty string identically
if user.MiddleName == "" {
    // This triggers for both null and ""
    // But they mean different things: null = no data, "" = explicitly empty
}

// FIX: Handle null and empty separately
if user.MiddleName == nil {
    // No middle name data provided
} else if *user.MiddleName == "" {
    // Explicitly no middle name
}
```

## Race Conditions in Business Logic

### Check-Then-Act

```go
// BUG: Race condition between check and act
if inventory.Available(productID) > 0 {
    // Another thread could buy last item here
    inventory.Decrement(productID)  // Negative inventory possible
}

// FIX: Atomic decrement-if-available
if err := inventory.DecrementIfAvailable(productID); err != nil {
    return ErrOutOfStock
}
```

### Double-Spend

```go
// BUG: User balance checked separately from deduction
balance := accounts.GetBalance(userID)
if balance >= amount {
    // Race: user could spend balance in another transaction
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
cache.Set("view_count", counter)  // Lost updates if concurrent

// FIX: Atomic increment
cache.Increment("view_count", 1)
```

## Edge Case Handling

### Division by Zero

```go
// BUG: No check for zero denominator
averageRating := totalStars / reviewCount  // Panics if reviewCount=0

// FIX: Check denominator
var averageRating float64
if reviewCount > 0 {
    averageRating = float64(totalStars) / float64(reviewCount)
}
```

### Empty Collection

```go
// BUG: Assumes non-empty array
firstItem := items[0]  // Panics if items is empty

// FIX: Check length
if len(items) == 0 {
    return ErrNoItems
}
firstItem := items[0]
```

### Null Pointer Dereference

```go
// BUG: No null check
userName := user.Profile.Name  // Panics if Profile is nil

// FIX: Null-safe access
if user.Profile != nil {
    userName = user.Profile.Name
} else {
    userName = "Anonymous"
}
```

### 100% Discount Edge Case

```go
// BUG: 100% discount not handled
finalPrice := basePrice * (100 - discountPercent) / 100
// Works for 0-99%, but 100% should be validated/special-cased

// FIX: Validate discount range
if discountPercent < 0 || discountPercent > 99 {
    return ErrInvalidDiscount
}
finalPrice := basePrice * (100 - discountPercent) / 100
```

## Failure Mode Errors

### Partial Failure Not Handled

```go
// BUG: No rollback if 2nd operation fails
err1 := createUser(user)
err2 := sendWelcomeEmail(user.Email)  // If this fails, user exists without email

// FIX: Rollback on failure
tx := db.Begin()
if err := createUser(tx, user); err != nil {
    return err
}
if err := sendWelcomeEmail(user.Email); err != nil {
    tx.Rollback()  // Remove user if email fails
    return err
}
tx.Commit()
```

### Missing Error Propagation

```go
// BUG: Error ignored
func ProcessOrder(order *Order) {
    chargePayment(order.PaymentMethod, order.Total)  // Ignores error
    updateInventory(order.Items)
}

// FIX: Check and propagate errors
func ProcessOrder(order *Order) error {
    if err := chargePayment(order.PaymentMethod, order.Total); err != nil {
        return fmt.Errorf("payment failed: %w", err)
    }
    if err := updateInventory(order.Items); err != nil {
        refundPayment(order.PaymentMethod, order.Total)  // Rollback
        return fmt.Errorf("inventory update failed: %w", err)
    }
    return nil
}
```

### Non-Idempotent Retry

```go
// BUG: Retrying increments multiple times
for retries := 0; retries < 3; retries++ {
    incrementCounter(userID)  // Increments 3x if all retries run
    if err == nil {
        break
    }
}

// FIX: Make operation idempotent
transactionID := generateUniqueID()
for retries := 0; retries < 3; retries++ {
    err := incrementCounterIdempotent(userID, transactionID)
    if err == nil {
        break
    }
}
```

## Data Consistency Errors

### Invariant Violation

```go
// BUG: Inventory can go negative
inventory.Quantity -= soldQuantity  // No check

// FIX: Enforce invariant
if inventory.Quantity < soldQuantity {
    return ErrInsufficientInventory
}
inventory.Quantity -= soldQuantity
```

### Orphaned References

```go
// BUG: Deleting user leaves orphaned orders
db.Delete(&user)  // Orders still reference deleted user

// FIX: Check references or cascade delete
orderCount := db.Where("user_id = ?", user.ID).Count(&Order{})
if orderCount > 0 {
    return ErrUserHasOrders
}
db.Delete(&user)
```

### Denormalized Data Out of Sync

```go
// BUG: Total not recalculated when items change
order.Items = append(order.Items, newItem)  // Total now wrong

// FIX: Recalculate derived fields
order.Items = append(order.Items, newItem)
order.Total = calculateTotal(order.Items)
```
