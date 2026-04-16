# Framework Idioms Reference

> **Scope**: Idiomatic patterns for Laravel and Symfony. Covers Eloquent scopes, Collections, Service Container binding, Symfony DI attributes, and Event Dispatcher. Does NOT cover raw PHP patterns without a framework or quality tooling configuration.
> **Version range**: Laravel 10+, Symfony 6.2+
> **Generated**: 2026-04-16

---

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

---

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
