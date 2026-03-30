---
name: php-quality
description: "PHP code quality: PSR standards, strict types, framework idioms."
version: 1.0.0
user-invocable: false
context: fork
agent: php-general-engineer
---

# PHP Quality Skill

## Strict Types Declaration

Every PHP file must begin with `declare(strict_types=1)`. This enforces scalar type coercion rules, catching type errors at call time instead of silently converting values.

```php
<?php

declare(strict_types=1);

// Without strict_types: strlen(123) silently returns 3
// With strict_types: strlen(123) throws TypeError
```

This is non-negotiable. Omitting it is a code quality defect.

## PSR-12 Coding Standard

PSR-12 extends PSR-1 and PSR-2 as the accepted PHP coding style.

```php
<?php

declare(strict_types=1);

namespace App\Service;

use App\Repository\UserRepository;
use Psr\Log\LoggerInterface;

class UserService
{
    // Visibility required on all properties, methods, constants
    private const MAX_RETRIES = 3;

    public function __construct(
        private readonly UserRepository $repository,
        private readonly LoggerInterface $logger,
    ) {
    }

    public function findActiveUsers(int $limit = 50): array
    {
        // Opening braces on same line for control structures
        if ($limit <= 0) {
            throw new \InvalidArgumentException('Limit must be positive');
        }

        // Opening braces on next line for classes and methods (shown above)
        return $this->repository->findActive($limit);
    }
}
```

Key rules: 4-space indentation, no trailing whitespace, one class per file, `use` statements after namespace with a blank line before and after, visibility on everything.

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

### DNF Types — Disjunctive Normal Form (PHP 8.2)

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

## Laravel Idioms

### Eloquent

```php
// Scopes for reusable query constraints
class User extends Model
{
    public function scopeActive(Builder $query): Builder
    {
        return $query->where('active', true);
    }
}

// Usage: User::active()->where('role', 'admin')->get();
```

### Collections

```php
// Prefer collection methods over raw loops
$names = collect($users)
    ->filter(fn (User $u) => $u->isActive())
    ->map(fn (User $u) => $u->fullName())
    ->sort()
    ->values()
    ->all();
```

### Service Container

```php
// Bind interface to implementation in a ServiceProvider
$this->app->bind(PaymentGateway::class, StripeGateway::class);

// Contextual binding
$this->app->when(OrderService::class)
    ->needs(PaymentGateway::class)
    ->give(StripeGateway::class);
```

## Symfony Idioms

### Dependency Injection with Attributes

```php
use Symfony\Component\DependencyInjection\Attribute\Autowire;

class ReportGenerator
{
    public function __construct(
        private readonly ReportRepository $repository,
        #[Autowire('%kernel.project_dir%/var/reports')]
        private readonly string $outputDir,
    ) {
    }
}
```

### Event Dispatcher

```php
use Symfony\Component\EventDispatcher\Attribute\AsEventListener;

#[AsEventListener(event: OrderPlaced::class)]
class SendOrderConfirmation
{
    public function __invoke(OrderPlaced $event): void
    {
        // Send confirmation email for $event->orderId
    }
}
```

## Quality Enforcement

Run these tools in CI:

```bash
# PHP-CS-Fixer — auto-fix PSR-12 violations
./vendor/bin/php-cs-fixer fix --dry-run --diff

# PHPStan — static analysis (level 0-9, aim for 6+)
./vendor/bin/phpstan analyse src --level=6

# Psalm — alternative static analysis
./vendor/bin/psalm --show-info=true

# Rector — automated refactoring and upgrades
./vendor/bin/rector process src --dry-run
```

| Tool | Purpose | Config File |
|---|---|---|
| PHP-CS-Fixer | Code style enforcement | `.php-cs-fixer.dist.php` |
| PHPStan | Static analysis, type checking | `phpstan.neon` |
| Psalm | Static analysis, taint analysis | `psalm.xml` |
| Rector | Automated refactoring | `rector.php` |
