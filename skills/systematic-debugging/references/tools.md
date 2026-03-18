# Debugging Tools by Language

Comprehensive reference of debugging tools organized by programming language and use case.

## Table of Contents
1. [Python](#python)
2. [Go](#go)
3. [JavaScript/Node.js](#javascriptnodejs)
4. [Java](#java)
5. [C/C++](#cc)
6. [Rust](#rust)
7. [Ruby](#ruby)
8. [General Purpose Tools](#general-purpose-tools)

---

## Python

### Interactive Debugger (pdb)
```python
# Insert breakpoint in code
import pdb; pdb.set_trace()

# Python 3.7+ built-in breakpoint
breakpoint()

# Common pdb commands
# l (list) - Show source code
# n (next) - Execute next line
# s (step) - Step into function
# c (continue) - Continue execution
# p variable - Print variable
# pp variable - Pretty-print variable
# bt - Show backtrace
```

**Usage**:
```bash
# Run script with pdb
python -m pdb script.py

# Drop into debugger on exception
python -m pdb -c continue script.py
```

### Advanced Python Debuggers

**ipdb** (IPython debugger):
```bash
pip install ipdb
```
```python
import ipdb; ipdb.set_trace()
# Provides IPython features: tab completion, syntax highlighting
```

**pdb++** (Enhanced pdb):
```bash
pip install pdbpp
```
```python
import pdb; pdb.set_trace()  # Automatically uses pdb++ if installed
# Features: syntax highlighting, sticky mode, better introspection
```

### Profiling

**cProfile** (Standard library):
```bash
# Profile entire script
python -m cProfile -o profile.stats script.py

# Analyze profile
python -m pstats profile.stats
>>> sort time
>>> stats 20  # Show top 20 functions by time
```

**line_profiler** (Line-by-line profiling):
```bash
pip install line_profiler
```
```python
# Decorate functions to profile
@profile
def slow_function():
    pass
```
```bash
kernprof -l -v script.py
```

**memory_profiler** (Memory usage):
```bash
pip install memory_profiler
```
```python
from memory_profiler import profile

@profile
def memory_intensive():
    pass
```
```bash
python -m memory_profiler script.py
```

### Tracing and Logging

**sys.settrace** (Custom tracing):
```python
import sys

def trace_calls(frame, event, arg):
    if event == 'call':
        code = frame.f_code
        print(f"Calling {code.co_name} in {code.co_filename}:{frame.f_lineno}")
    return trace_calls

sys.settrace(trace_calls)
```

**logging with debug level**:
```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.debug("Variable value: %s", variable)
```

### Testing and Coverage

**pytest with debugging**:
```bash
# Drop into pdb on failure
pytest --pdb

# Drop into pdb on first failure
pytest -x --pdb

# Show print statements
pytest -s

# Verbose output
pytest -vv
```

**coverage.py**:
```bash
pip install coverage

# Run tests with coverage
coverage run -m pytest tests/

# Generate report
coverage report
coverage html  # HTML report in htmlcov/
```

### Type Checking

**mypy** (Static type checking):
```bash
pip install mypy

mypy script.py
mypy --strict script.py
```

### Performance Analysis

**py-spy** (Sampling profiler, no code changes):
```bash
pip install py-spy

# Profile running process
py-spy top --pid <PID>

# Generate flame graph
py-spy record -o profile.svg -- python script.py
```

---

## Go

### Built-in Debugger (Delve)

**Installation**:
```bash
go install github.com/go-delve/delve/cmd/dlv@latest
```

**Usage**:
```bash
# Debug a program
dlv debug main.go

# Debug with arguments
dlv debug main.go -- arg1 arg2

# Debug a test
dlv test ./package

# Attach to running process
dlv attach <PID>
```

**Delve commands**:
```
break (b) main.main        - Set breakpoint
continue (c)               - Continue execution
next (n)                   - Step over
step (s)                   - Step into
print (p) variable         - Print variable
locals                     - Show local variables
goroutines                 - List goroutines
goroutine <id>             - Switch to goroutine
bt                         - Show backtrace
exit                       - Exit debugger
```

### Race Detector

```bash
# Build with race detector
go build -race

# Test with race detector
go test -race ./...

# Run with race detector
go run -race main.go
```

**Example output**:
```
==================
WARNING: DATA RACE
Read at 0x00c000010098 by goroutine 7:
  main.increment()
      /path/to/main.go:15 +0x3c

Previous write at 0x00c000010098 by goroutine 6:
  main.increment()
      /path/to/main.go:15 +0x58
==================
```

### Profiling

**CPU Profiling**:
```go
import (
    "os"
    "runtime/pprof"
)

func main() {
    f, _ := os.Create("cpu.prof")
    defer f.Close()

    pprof.StartCPUProfile(f)
    defer pprof.StopCPUProfile()

    // Your code here
}
```

```bash
# Analyze profile
go tool pprof cpu.prof
> top 10
> list functionName
> web  # Generate graph (requires graphviz)
```

**Memory Profiling**:
```go
import (
    "os"
    "runtime/pprof"
)

func main() {
    f, _ := os.Create("mem.prof")
    defer f.Close()

    // Your code here

    pprof.WriteHeapProfile(f)
}
```

```bash
go tool pprof mem.prof
> top 10
> list functionName
```

**HTTP pprof** (for servers):
```go
import (
    _ "net/http/pprof"
    "net/http"
)

func main() {
    go func() {
        http.ListenAndServe("localhost:6060", nil)
    }()

    // Your server code
}
```

```bash
# Access profiles
go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30
go tool pprof http://localhost:6060/debug/pprof/heap
go tool pprof http://localhost:6060/debug/pprof/goroutine
```

### Tracing

**Execution Tracer**:
```go
import (
    "os"
    "runtime/trace"
)

func main() {
    f, _ := os.Create("trace.out")
    defer f.Close()

    trace.Start(f)
    defer trace.Stop()

    // Your code here
}
```

```bash
# Analyze trace
go tool trace trace.out
# Opens web interface showing goroutines, network, syscalls, etc.
```

### Testing

**Verbose test output**:
```bash
go test -v ./...

# Run specific test
go test -v -run TestFunctionName

# Show coverage
go test -cover ./...
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out
```

**Benchmarking**:
```go
func BenchmarkFunction(b *testing.B) {
    for i := 0; i < b.N; i++ {
        function()
    }
}
```

```bash
go test -bench=. -benchmem
go test -bench=. -cpuprofile=cpu.prof
```

### Static Analysis

**go vet** (Suspicious constructs):
```bash
go vet ./...
```

**staticcheck** (Advanced static analysis):
```bash
go install honnef.co/go/tools/cmd/staticcheck@latest
staticcheck ./...
```

**golangci-lint** (Multiple linters):
```bash
golangci-lint run
```

---

## JavaScript/Node.js

### Built-in Debugger

**Node.js Inspector**:
```bash
# Start with debugger
node inspect script.js

# Start with Chrome DevTools
node --inspect script.js
node --inspect-brk script.js  # Break on first line

# Connect Chrome to chrome://inspect
```

**Debugger statement**:
```javascript
function buggyFunction() {
    debugger;  // Execution will pause here
    // Your code
}
```

### Chrome DevTools

1. Start Node with `--inspect-brk`
2. Open Chrome: `chrome://inspect`
3. Click "Open dedicated DevTools for Node"
4. Use full Chrome debugging features:
   - Breakpoints
   - Watch expressions
   - Call stack
   - Scope inspection
   - Console evaluation

### VS Code Debugging

**launch.json**:
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "type": "node",
            "request": "launch",
            "name": "Debug Program",
            "program": "${workspaceFolder}/script.js",
            "console": "integratedTerminal"
        }
    ]
}
```

### Profiling

**V8 Profiler (built-in)**:
```bash
# CPU profile
node --prof script.js
node --prof-process isolate-*.log > processed.txt

# Heap snapshot
node --heap-prof script.js
```

**clinic.js** (Comprehensive profiling):
```bash
npm install -g clinic

# Doctor (overall health)
clinic doctor -- node script.js

# Flame (CPU profiling)
clinic flame -- node script.js

# Bubbleprof (async operations)
clinic bubbleprof -- node script.js

# Heap profiler
clinic heapprofiler -- node script.js
```

### Memory Debugging

**Heap snapshots**:
```javascript
const v8 = require('v8');
const fs = require('fs');

const snapshot = v8.writeHeapSnapshot();
console.log('Snapshot written to:', snapshot);
```

**memory-usage package**:
```javascript
const memoryUsage = process.memoryUsage();
console.log({
    rss: `${memoryUsage.rss / 1024 / 1024} MB`,
    heapTotal: `${memoryUsage.heapTotal / 1024 / 1024} MB`,
    heapUsed: `${memoryUsage.heapUsed / 1024 / 1024} MB`,
    external: `${memoryUsage.external / 1024 / 1024} MB`
});
```

### Logging and Tracing

**debug module**:
```bash
npm install debug
```
```javascript
const debug = require('debug')('app:server');

debug('Server starting on port %d', 3000);
```
```bash
DEBUG=app:* node script.js
```

**winston (structured logging)**:
```bash
npm install winston
```
```javascript
const winston = require('winston');

const logger = winston.createLogger({
    level: 'debug',
    format: winston.format.json(),
    transports: [
        new winston.transports.File({ filename: 'error.log', level: 'error' }),
        new winston.transports.File({ filename: 'combined.log' }),
        new winston.transports.Console()
    ]
});

logger.debug('Debugging information', { userId: 123, action: 'login' });
```

### Testing

**Jest with debugging**:
```bash
# Run single test
node --inspect-brk node_modules/.bin/jest --runInBand test.js

# Debug in VS Code
# Set breakpoint in test file and press F5
```

**Mocha with debugging**:
```bash
node --inspect-brk node_modules/.bin/mocha test.js
```

### Static Analysis

**ESLint**:
```bash
npm install --save-dev eslint
npx eslint script.js
```

**TypeScript**:
```bash
npm install --save-dev typescript
npx tsc --noEmit  # Type checking without compilation
```

---

## Java

### JDB (Java Debugger)

```bash
# Compile with debug info
javac -g MyClass.java

# Start JDB
jdb MyClass

# Common commands
stop at MyClass:15          # Set breakpoint at line 15
stop in MyClass.method      # Set breakpoint at method
run                         # Start execution
cont                        # Continue
step                        # Step into
next                        # Step over
print variable              # Print variable
locals                      # Show local variables
where                       # Show call stack
```

### IDE Debuggers

**IntelliJ IDEA**:
- Set breakpoints by clicking line numbers
- Right-click breakpoint for conditions
- "Debug" button to start
- Evaluate expressions in debugger console

**Eclipse**:
- Double-click line numbers to set breakpoints
- Debug As → Java Application
- Variables view shows all local variables
- Expressions view for custom expressions

### Profiling

**JProfiler**:
```bash
java -agentpath:/path/to/jprofiler/bin/linux-x64/libjprofilerti.so=port=8849 MyClass
```

**VisualVM** (free, included with JDK):
```bash
jvisualvm
# Attach to running Java process
# CPU profiling, memory profiling, heap dumps
```

**Java Flight Recorder**:
```bash
# Start with JFR
java -XX:+UnlockCommercialFeatures -XX:+FlightRecorder \
     -XX:StartFlightRecording=duration=60s,filename=recording.jfr MyClass

# Analyze recording
jmc  # Java Mission Control
```

### Memory Analysis

**Heap dump**:
```bash
# Generate heap dump
jmap -dump:format=b,file=heap.bin <PID>

# Analyze with jhat
jhat heap.bin
# Open http://localhost:7000

# Or use Eclipse Memory Analyzer (MAT)
```

**Garbage Collection Logging**:
```bash
java -Xlog:gc*:file=gc.log:time,uptime:filecount=5,filesize=100m MyClass
```

### Thread Analysis

**Thread dump**:
```bash
# Generate thread dump
jstack <PID> > thread_dump.txt

# Or send SIGQUIT
kill -3 <PID>  # Thread dump in application logs
```

### Static Analysis

**SpotBugs**:
```bash
# Maven
mvn spotbugs:check

# Gradle
gradle spotbugsMain
```

**PMD**:
```bash
pmd -d src/ -f text -R rulesets/java/quickstart.xml
```

---

## C/C++

### GDB (GNU Debugger)

**Basic usage**:
```bash
# Compile with debug symbols
gcc -g program.c -o program

# Start GDB
gdb program

# GDB commands
break main                  # Set breakpoint
run arg1 arg2              # Start with arguments
continue (c)               # Continue execution
next (n)                   # Step over
step (s)                   # Step into
finish                     # Step out
print variable             # Print variable
print *pointer             # Dereference pointer
backtrace (bt)            # Show call stack
info locals               # Show local variables
info registers            # Show registers
watch variable            # Break when variable changes
```

**Advanced GDB**:
```bash
# Attach to running process
gdb -p <PID>

# Core dump analysis
gdb program core

# TUI mode (text UI)
gdb -tui program
```

### Valgrind (Memory debugging)

**Memory leak detection**:
```bash
# Compile with -g
gcc -g program.c -o program

# Run with Valgrind
valgrind --leak-check=full --show-leak-kinds=all ./program

# Output shows:
# - Memory leaks (definitely lost, possibly lost)
# - Invalid memory access
# - Uninitialized values
```

**Memcheck options**:
```bash
# Track origins of uninitialized values
valgrind --track-origins=yes ./program

# Verbose output
valgrind --leak-check=full -v ./program

# Generate suppressions for known issues
valgrind --gen-suppressions=all ./program
```

### Sanitizers (Clang/GCC)

**AddressSanitizer** (memory errors):
```bash
# Compile with ASan
gcc -fsanitize=address -g program.c -o program

# Run (crashes on memory error)
./program

# Detects:
# - Use-after-free
# - Heap buffer overflow
# - Stack buffer overflow
# - Use-after-return
```

**ThreadSanitizer** (race conditions):
```bash
gcc -fsanitize=thread -g program.c -o program -pthread
./program

# Detects data races
```

**UndefinedBehaviorSanitizer**:
```bash
gcc -fsanitize=undefined -g program.c -o program
./program

# Detects:
# - Integer overflow
# - Null pointer dereference
# - Signed integer overflow
```

### Profiling

**gprof** (GNU profiler):
```bash
# Compile with profiling
gcc -pg program.c -o program

# Run program (generates gmon.out)
./program

# Analyze
gprof program gmon.out > analysis.txt
```

**perf** (Linux performance analyzer):
```bash
# Record
perf record ./program

# Analyze
perf report

# Top hotspots
perf top
```

### Static Analysis

**Clang Static Analyzer**:
```bash
# Scan build
scan-build gcc -c program.c

# View results
scan-view /tmp/scan-build-*
```

**Cppcheck**:
```bash
cppcheck --enable=all program.c
```

---

## Rust

### Built-in Debugging

**rust-gdb / rust-lldb**:
```bash
# Compile with debug info (default in debug builds)
cargo build

# Debug with rust-gdb
rust-gdb target/debug/myprogram

# Debug with rust-lldb
rust-lldb target/debug/myprogram
```

**VS Code with CodeLLDB**:
```json
{
    "type": "lldb",
    "request": "launch",
    "name": "Debug",
    "program": "${workspaceFolder}/target/debug/myprogram",
    "args": [],
    "cwd": "${workspaceFolder}"
}
```

### Testing and Debugging

**cargo test with output**:
```bash
# Show println! output
cargo test -- --nocapture

# Show test names
cargo test -- --test-threads=1

# Run specific test
cargo test test_name
```

### Error Handling

**RUST_BACKTRACE**:
```bash
# Full backtrace on panic
RUST_BACKTRACE=1 cargo run

# Full backtrace with source
RUST_BACKTRACE=full cargo run
```

### Profiling

**cargo-flamegraph**:
```bash
cargo install flamegraph

cargo flamegraph
# Generates flamegraph.svg
```

**perf**:
```bash
cargo build --release
perf record --call-graph dwarf ./target/release/myprogram
perf report
```

### Static Analysis

**clippy**:
```bash
rustup component add clippy

cargo clippy
cargo clippy -- -W clippy::pedantic
```

**rustfmt**:
```bash
cargo fmt --check
cargo fmt
```

### Sanitizers

```bash
# Address sanitizer
RUSTFLAGS="-Z sanitizer=address" cargo run

# Thread sanitizer
RUSTFLAGS="-Z sanitizer=thread" cargo run
```

---

## Ruby

### Built-in Debugger

**debug.rb** (Ruby 3.1+):
```ruby
require 'debug'

def buggy_method
  binding.break  # Breakpoint
  # Your code
end
```

**pry** (popular gem):
```bash
gem install pry pry-byebug
```
```ruby
require 'pry'

def buggy_method
  binding.pry  # Drop into Pry REPL
  # Your code
end
```

### Profiling

**ruby-prof**:
```bash
gem install ruby-prof
```
```ruby
require 'ruby-prof'

RubyProf.start
# Your code
result = RubyProf.stop

printer = RubyProf::FlatPrinter.new(result)
printer.print(STDOUT)
```

**stackprof**:
```bash
gem install stackprof
```
```ruby
require 'stackprof'

StackProf.run(mode: :cpu, out: 'stackprof.dump') do
  # Your code
end
```
```bash
stackprof stackprof.dump
```

### Memory Profiling

**memory_profiler**:
```bash
gem install memory_profiler
```
```ruby
require 'memory_profiler'

report = MemoryProfiler.report do
  # Your code
end

report.pretty_print
```

### Testing

**RSpec with debugging**:
```ruby
# In spec file
it 'does something' do
  binding.pry  # Debug test
  expect(result).to eq expected
end
```

---

## General Purpose Tools

### strace / dtruss (System call tracing)

**Linux (strace)**:
```bash
# Trace system calls
strace ./program

# Trace specific syscalls
strace -e open,read,write ./program

# Attach to running process
strace -p <PID>

# Count syscall frequency
strace -c ./program

# Save to file
strace -o trace.log ./program
```

**macOS (dtruss)**:
```bash
# Requires sudo
sudo dtruss ./program

# Filter by syscall
sudo dtruss -t open ./program
```

### tcpdump / Wireshark (Network debugging)

**tcpdump**:
```bash
# Capture on interface
sudo tcpdump -i eth0

# Filter by port
sudo tcpdump -i eth0 port 80

# Save to file
sudo tcpdump -i eth0 -w capture.pcap

# Read from file
tcpdump -r capture.pcap
```

**Wireshark**:
- GUI network protocol analyzer
- Deep packet inspection
- Filter by protocol, IP, port
- Follow TCP streams
- Export objects from HTTP

### lsof (List open files)

```bash
# Files opened by process
lsof -p <PID>

# Processes using a file
lsof /path/to/file

# Network connections
lsof -i
lsof -i :8080  # Specific port

# Deleted files still open
lsof | grep deleted
```

### Hex Editors

**xxd** (command-line):
```bash
# View hex dump
xxd file.bin

# Create hex dump and reverse
xxd file.bin > file.hex
xxd -r file.hex > file.bin
```

**hexdump**:
```bash
hexdump -C file.bin  # Canonical format
```

### Process Monitoring

**htop** (interactive process viewer):
```bash
htop
# Press F4 to filter
# Press F5 for tree view
```

**ps**:
```bash
# Show all processes
ps aux

# Show process tree
ps auxf

# Show threads
ps -eLf
```

**top**:
```bash
top
# Press 1 to show all CPUs
# Press M to sort by memory
# Press P to sort by CPU
```

### Git Debugging

**git bisect** (find breaking commit):
```bash
git bisect start
git bisect bad                    # Current commit is bad
git bisect good v1.0              # v1.0 was good
# Test current commit
git bisect good  # or git bisect bad
# Repeat until found
git bisect reset
```

**git blame** (find who changed line):
```bash
git blame file.py
git blame -L 10,20 file.py  # Lines 10-20
```

**git log with patches**:
```bash
git log -p -- file.py           # Show all changes to file
git log -S "function_name"      # Find when string added/removed
git log --follow file.py        # Follow through renames
```

---

## Tool Selection Guide

### Choose debugger based on:

**Interactive debugging needed?**
→ Use language-specific debugger (pdb, delve, node inspect, gdb)

**Performance issue?**
→ Use profiler (cProfile, pprof, clinic.js, perf)

**Memory leak?**
→ Use memory profiler (memory_profiler, pprof heap, valgrind, heapprofiler)

**Race condition?**
→ Use race detector (go test -race, ThreadSanitizer, Node.js async_hooks)

**System-level debugging?**
→ Use strace/dtruss, lsof, tcpdump

**Network issue?**
→ Use tcpdump, Wireshark, curl -v

**Historical bug?**
→ Use git bisect, git log -S

**Static analysis?**
→ Use linters (eslint, golangci-lint, clippy, cppcheck)

This reference provides starting points for debugging in any language. Always check tool documentation for advanced features and options specific to your debugging scenario.
