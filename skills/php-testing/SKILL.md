---
name: php-testing
description: "PHP testing patterns: PHPUnit, test doubles, database testing."
version: 1.0.0
user-invocable: false
context: fork
agent: php-general-engineer
routing:
  triggers:
    - "php testing"
    - "phpunit"
    - "pest php"
    - "php mock"
  category: php
---

# PHP Testing Skill

## PHPUnit Basics

PHPUnit is the standard testing framework for PHP. Tests extend `TestCase` and use either the `test` method prefix or the `@test` annotation.

```php
<?php

declare(strict_types=1);

namespace Tests\Unit;

use PHPUnit\Framework\TestCase;

class InvoiceTest extends TestCase
{
    // Option 1: test prefix (preferred — no annotation needed)
    public function testCalculatesTotalWithTax(): void
    {
        $invoice = new Invoice(amount: 100.00, taxRate: 0.08);
        $this->assertSame(108.00, $invoice->total());
    }

    // Option 2: @test annotation
    /** @test */
    public function it_returns_zero_for_empty_line_items(): void
    {
        $invoice = new Invoice(amount: 0, taxRate: 0.08);
        $this->assertSame(0.00, $invoice->total());
    }
}
```

Use `setUp()` and `tearDown()` for shared fixtures. Call `parent::setUp()` first.

```php
protected function setUp(): void
{
    parent::setUp();
    $this->repository = new InMemoryUserRepository();
}
```

## Data Providers for Table-Driven Tests

Data providers enable table-driven testing, feeding multiple input/output sets to a single test method.

```php
/**
 * @dataProvider validEmailProvider
 */
public function testAcceptsValidEmails(string $email): void
{
    $this->assertTrue(EmailValidator::isValid($email));
}

public static function validEmailProvider(): array
{
    return [
        'standard address'    => ['user@example.com'],
        'subdomain'           => ['user@mail.example.com'],
        'plus addressing'     => ['user+tag@example.com'],
        'numeric domain'      => ['user@123.123.123.com'],
    ];
}

/**
 * @dataProvider arithmeticProvider
 */
public function testArithmetic(int $a, int $b, int $expected): void
{
    $this->assertSame($expected, Calculator::add($a, $b));
}

public static function arithmeticProvider(): iterable
{
    yield 'positive numbers' => [2, 3, 5];
    yield 'negative numbers' => [-1, -2, -3];
    yield 'mixed signs'      => [-1, 3, 2];
    yield 'zeros'            => [0, 0, 0];
}
```

## Test Doubles: Mocks, Stubs, and Prophecy

PHPUnit provides `createMock()` and `createStub()`. Use stubs when you only need return values; use mocks when you need to assert interactions.

```php
// Stub — configure return values, no call assertions
public function testFetchesUserFromCache(): void
{
    $cache = $this->createStub(CacheInterface::class);
    $cache->method('get')->willReturn(new User('Alice'));

    $service = new UserService($cache);
    $this->assertSame('Alice', $service->getUser('alice')->name);
}

// Mock — assert the method was called with specific arguments
public function testLogsFailedPayment(): void
{
    $logger = $this->createMock(LoggerInterface::class);
    $logger->expects($this->once())
        ->method('error')
        ->with($this->stringContains('Payment failed'));

    $processor = new PaymentProcessor($logger);
    $processor->process(new Payment(amount: -1));
}
```

For more expressive test doubles, use Prophecy (bundled via `phpspec/prophecy-phpunit`):

```php
use Prophecy\PhpUnit\ProphecyTrait;

class OrderServiceTest extends TestCase
{
    use ProphecyTrait;

    public function testDispatchesOrderEvent(): void
    {
        $dispatcher = $this->prophesize(EventDispatcherInterface::class);
        $dispatcher->dispatch(Argument::type(OrderPlaced::class))
            ->shouldBeCalledOnce();

        $service = new OrderService($dispatcher->reveal());
        $service->place(new Order(id: 42));
    }
}
```

## Database Testing

### Laravel: DatabaseTransactions, Factories, Seeders

```php
use Illuminate\Foundation\Testing\DatabaseTransactions;
use Tests\TestCase;

class UserRepositoryTest extends TestCase
{
    use DatabaseTransactions; // rolls back after each test

    public function testFindsActiveUsers(): void
    {
        // Factories create test data
        User::factory()->count(3)->create(['active' => true]);
        User::factory()->count(2)->create(['active' => false]);

        $active = $this->app->make(UserRepository::class)->findActive();

        $this->assertCount(3, $active);
    }
}
```

### Symfony: DAMA DoctrineTestBundle

```php
use Symfony\Bundle\FrameworkBundle\Test\KernelTestCase;

class ProductRepositoryTest extends KernelTestCase
{
    public function testCountsByCategoryId(): void
    {
        self::bootKernel();
        $em = self::getContainer()->get('doctrine')->getManager();

        $count = $em->getRepository(Product::class)
            ->countByCategory(categoryId: 5);

        $this->assertGreaterThan(0, $count);
    }
}
```

## HTTP Testing

### Laravel HTTP Tests

```php
public function testCreateEndpointReturnsCreatedStatus(): void
{
    $response = $this->postJson('/api/users', [
        'name'  => 'Alice',
        'email' => 'alice@example.com',
    ]);

    $response->assertStatus(201)
        ->assertJsonPath('data.name', 'Alice');

    $this->assertDatabaseHas('users', ['email' => 'alice@example.com']);
}
```

### Symfony WebTestCase

```php
use Symfony\Bundle\FrameworkBundle\Test\WebTestCase;

class HealthCheckControllerTest extends WebTestCase
{
    public function testHealthEndpointReturnsOk(): void
    {
        $client = static::createClient();
        $client->request('GET', '/health');

        $this->assertResponseIsSuccessful();
        $this->assertJsonStringEqualsJsonString(
            '{"status":"ok"}',
            $client->getResponse()->getContent()
        );
    }
}
```

## Code Coverage Configuration

Configure coverage in `phpunit.xml`:

```xml
<phpunit>
    <source>
        <include>
            <directory suffix=".php">src</directory>
        </include>
        <exclude>
            <directory>src/Migrations</directory>
        </exclude>
    </source>
</phpunit>
```

Run coverage:

```bash
# Text summary
php artisan test --coverage          # Laravel
./vendor/bin/phpunit --coverage-text # Any PHP project

# HTML report
./vendor/bin/phpunit --coverage-html coverage/

# Enforce minimum threshold
./vendor/bin/phpunit --coverage-text --coverage-min=80
```

## Common Testing Anti-Patterns

| Anti-Pattern | Problem | Fix |
|---|---|---|
| Testing private methods directly | Couples tests to implementation | Test through public API |
| One assertion per test (dogmatic) | Explosion of near-identical tests | Group related assertions; use data providers |
| No data providers for repetitive cases | Duplicate test methods | Extract to `@dataProvider` |
| Database state leaking between tests | Flaky, order-dependent tests | Use `DatabaseTransactions` or `setUp`/`tearDown` |
| Mocking the class under test | Test proves nothing | Mock only collaborators/dependencies |
| Ignoring `@depends` fragility | Chained tests break together | Keep tests independent; duplicate setup if needed |
| `$this->assertTrue($a === $b)` | Failure message is useless ("expected true, got false") | Use `$this->assertSame($b, $a)` for meaningful diffs |

## Commands Reference

```bash
# Run all tests
./vendor/bin/phpunit

# Run a specific test class
./vendor/bin/phpunit tests/Unit/InvoiceTest.php

# Run a specific test method
./vendor/bin/phpunit --filter testCalculatesTotalWithTax

# Run a test suite defined in phpunit.xml
./vendor/bin/phpunit --testsuite Unit

# Stop on first failure
./vendor/bin/phpunit --stop-on-failure

# Run with coverage (requires Xdebug or PCOV)
XDEBUG_MODE=coverage ./vendor/bin/phpunit --coverage-text
```
