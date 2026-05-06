# Modern PHP Features Reference

> **Scope**: PHP 8.0, 8.1, and 8.2 language features relevant to code quality reviews: type system improvements, enums, readonly, match expressions, named arguments, null-safe operator. Does NOT cover framework-specific patterns or tooling configuration.
> **Version range**: PHP 8.0 through 8.2
> **Generated**: 2026-04-16

---

## Type Declarations

### Union Types (PHP 8.0)

```php
function parseId(int|string $id): User
{
    return match (true) {
        is_int($id)    => $this->findById($id),
        is_string($id) => $this->findBySlug($id),
    };
}
```

### Intersection Types (PHP 8.1)

```php
function processItem(Countable&Iterator $collection): void
{
    // $collection must implement BOTH interfaces
    foreach ($collection as $item) {
        // ...
    }
}
```

### DNF Types (PHP 8.2)

Disjunctive Normal Form combines union and intersection types.

```php
function handle((Countable&Iterator)|null $items): void
{
    // Combines union and intersection: (A&B)|C
    if ($items === null) {
        return;
    }
    // ...
}
```

---

## Enums (PHP 8.1)

### Backed Enums

```php
enum Status: string
{
    case Active   = 'active';
    case Inactive = 'inactive';
    case Pending  = 'pending';

    // Enums can have methods
    public function label(): string
    {
        return match ($this) {
            self::Active   => 'Active',
            self::Inactive => 'Inactive',
            self::Pending  => 'Pending Review',
        };
    }

    // And implement interfaces
    public function isTerminal(): bool
    {
        return $this === self::Inactive;
    }
}

// Usage
$status = Status::from('active');        // throws ValueError if invalid
$status = Status::tryFrom('unknown');    // returns null if invalid
$value  = Status::Active->value;         // 'active'
```

Backed enums can be `string` or `int`. Use them instead of class constants for fixed value sets.

---

## Readonly Properties and Classes (PHP 8.1 / 8.2)

```php
// Readonly properties (PHP 8.1) — set once, immutable after
class Money
{
    public function __construct(
        public readonly int $amount,
        public readonly string $currency,
    ) {
    }
}

// Readonly classes (PHP 8.2) — all properties are implicitly readonly
readonly class Coordinate
{
    public function __construct(
        public float $latitude,
        public float $longitude,
    ) {
    }
}

$c = new Coordinate(37.7749, -122.4194);
// $c->latitude = 0; // Error: Cannot modify readonly property
```

---

## Named Arguments (PHP 8.0)

Named arguments improve readability for functions with many parameters or boolean flags.

```php
// Before: positional arguments — what does true mean?
$user = createUser('Alice', 'alice@example.com', true, false);

// After: named arguments — intent is clear
$user = createUser(
    name: 'Alice',
    email: 'alice@example.com',
    isAdmin: true,
    sendWelcomeEmail: false,
);

// Named arguments can skip optional parameters
htmlspecialchars($string, encoding: 'UTF-8');
```

---

## Match Expressions (PHP 8.0)

`match` is a stricter alternative to `switch`. It uses strict comparison (`===`), returns a value, and throws `UnhandledMatchError` for missing cases.

```php
// switch — loose comparison, fall-through risk, verbose
switch ($statusCode) {
    case 200:
        $text = 'OK';
        break;
    case 404:
        $text = 'Not Found';
        break;
    default:
        $text = 'Unknown';
}

// match — strict comparison, no fall-through, expression
$text = match ($statusCode) {
    200     => 'OK',
    301     => 'Moved Permanently',
    404     => 'Not Found',
    500     => 'Internal Server Error',
    default => 'Unknown',
};

// match with no subject — replaces if/elseif chains
$category = match (true) {
    $age < 13  => 'child',
    $age < 18  => 'teen',
    $age < 65  => 'adult',
    default    => 'senior',
};
```

---

## Null Safe Operator (PHP 8.0)

The `?->` operator short-circuits to `null` when the left side is null, eliminating nested null checks.

```php
// Before: defensive null checking
$country = null;
if ($user !== null) {
    $address = $user->getAddress();
    if ($address !== null) {
        $country = $address->getCountry();
    }
}

// After: nullsafe chaining
$country = $user?->getAddress()?->getCountry();

// Combine with null coalescing for defaults
$countryCode = $user?->getAddress()?->getCountry()?->code ?? 'US';
```
