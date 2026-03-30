# PHP Patterns Reference

Deep-dive patterns for thin controllers, DTOs, value objects, and preferred coding conventions.

---

## Thin Controller Pattern

Controllers are **transport layer only**. They authenticate, validate input, delegate to a service, and return a response. Business logic never lives in a controller.

### What Belongs in a Controller

```php
<?php
declare(strict_types=1);

namespace App\Http\Controllers;

use App\Http\Requests\StoreOrderRequest;
use App\Services\OrderService;
use App\Http\Resources\OrderResource;
use Illuminate\Http\JsonResponse;

final class OrderController extends Controller
{
    public function __construct(
        private readonly OrderService $orderService,
    ) {}

    public function store(StoreOrderRequest $request): JsonResponse
    {
        // 1. Input is already validated by form request
        $command = new PlaceOrderCommand(
            customerId: $request->user()->id,
            items: $request->validated('items'),
            shippingAddress: $request->validated('shipping_address'),
        );

        // 2. Delegate to service — no business logic here
        $order = $this->orderService->place($command);

        // 3. Return HTTP response
        return (new OrderResource($order))
            ->response()
            ->setStatusCode(201);
    }
}
```

### What Belongs in a Service

```php
<?php
declare(strict_types=1);

namespace App\Services;

use App\Models\Order;
use App\DTOs\PlaceOrderCommand;
use App\Repositories\OrderRepositoryInterface;
use App\Events\OrderPlaced;

final class OrderService
{
    public function __construct(
        private readonly OrderRepositoryInterface $orders,
        private readonly InventoryServiceInterface $inventory,
        private readonly EventDispatcherInterface $events,
    ) {}

    public function place(PlaceOrderCommand $command): Order
    {
        // Business logic here — not in controller
        $this->inventory->reserve($command->items);
        $order = $this->orders->create($command);
        $this->events->dispatch(new OrderPlaced($order));

        return $order;
    }
}
```

### Controller Checklist

| Concern | Controller | Service |
|---------|-----------|---------|
| HTTP method routing | Yes | No |
| Input validation | Yes (Form Request) | No |
| Authentication/authorization | Yes (middleware/policy) | No |
| Business logic | **Service only** | Yes |
| Database queries | **Service only** | Yes (via repository) |
| External API calls | **Service only** | Yes (via interface) |
| HTTP response construction | Yes | No |

---

## DTOs and Value Objects

Use DTOs (Data Transfer Objects) for commands, queries, and external API payloads. Use value objects for domain concepts with rules.

### DTO Pattern (readonly class, PHP 8.2+)

```php
<?php
declare(strict_types=1);

namespace App\DTOs;

final readonly class PlaceOrderCommand
{
    public function __construct(
        public int $customerId,
        /** @var array<int, OrderItemDto> */
        public array $items,
        public string $shippingAddress,
    ) {}
}
```

### Value Object Pattern

```php
<?php
declare(strict_types=1);

namespace App\ValueObjects;

use InvalidArgumentException;

final readonly class Money
{
    public function __construct(
        public int $amountInCents,
        public string $currency,
    ) {
        if ($amountInCents < 0) {
            throw new InvalidArgumentException('Amount cannot be negative.');
        }
        if (!in_array($currency, ['USD', 'EUR', 'GBP'], true)) {
            throw new InvalidArgumentException("Unsupported currency: {$currency}");
        }
    }

    public function add(self $other): self
    {
        if ($this->currency !== $other->currency) {
            throw new InvalidArgumentException('Cannot add different currencies.');
        }
        return new self($this->amountInCents + $other->amountInCents, $this->currency);
    }
}
```

---

## Preferred Patterns

| Pattern to Replace | Why It Is Wrong | Detection Command |
|-------------|----------------|------------------|
| Fat controller | Business logic in controllers couples transport to domain, kills testability, and prevents service reuse | `grep -rn --include="*.php" -E 'Eloquent\\Model\|DB::' app/Http/Controllers/` |
| Associative arrays where DTOs fit | Untyped arrays lose IDE support, skip static analysis, and make refactoring risky | `grep -rn --include="*.php" -E '\$data\s*=\s*\[' app/Services/` |
| Raw SQL string interpolation | SQL injection vector; no parameterization | `grep -rn --include="*.php" -E '(query\|exec)\s*\(\s*["\x27].*\$' src/` |
| `extract()` on user input | Pollutes local scope with user-controlled variable names; arbitrary variable injection | `grep -rn --include="*.php" 'extract(\$_' src/` |
| Debug output left in code | `var_dump`, `dd`, `dump`, `die` leak internal state and break HTTP/JSON responses | `grep -rn --include="*.php" -E 'var_dump\s*\(\|dd\s*\(\|dump\s*\(\|die\s*\(' src/` |
| Service-locator in business services | Hides dependencies, prevents constructor-injection testing, couples services to container | `grep -rn --include="*.php" -E 'app\(\)->make\(\|Container::getInstance' app/Services/` |
| Hardcoded secrets in config | Secrets committed to version control create immediate security incident risk | `grep -rn --include="*.php" -E '"(sk_live_\|password\s*=\s*)[^"]{8,}"' config/` |
| Missing `declare(strict_types=1)` | Allows implicit type coercion; hides type bugs that strict mode would catch | `grep -rLz 'declare(strict_types=1)' $(find src/ app/ -name "*.php" -not -path "*/vendor/*")` |
