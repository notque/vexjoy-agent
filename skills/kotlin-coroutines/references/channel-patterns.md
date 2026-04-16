---
name: channel-patterns
description: "Kotlin Channel types, fan-in/fan-out, and producer-consumer patterns."
level: 2
---

# Kotlin Channel Patterns

## Channels: Hot Communication Primitives

Channels are hot -- they exist independently of consumers. Use them for producer-consumer patterns and inter-coroutine communication.

```kotlin
import kotlinx.coroutines.channels.*

// Producer-consumer with produce builder
fun CoroutineScope.produceNumbers(): ReceiveChannel<Int> = produce {
    var n = 1
    while (true) {
        send(n++)
        delay(100)
    }
}

// Fan-out: multiple coroutines consuming from one channel
suspend fun fanOut() = coroutineScope {
    val channel = produceNumbers()

    repeat(3) { workerId ->
        launch {
            for (number in channel) {
                println("Worker $workerId processing $number")
            }
        }
    }
}

// Fan-in: multiple producers writing to one channel
suspend fun fanIn() = coroutineScope {
    val channel = Channel<String>()

    launch { repeat(5) { channel.send("Source A: $it"); delay(100) } }
    launch { repeat(5) { channel.send("Source B: $it"); delay(150) } }

    // Collect all from both sources
    repeat(10) {
        println(channel.receive())
    }
    channel.close()
}
```
