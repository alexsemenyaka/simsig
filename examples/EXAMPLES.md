# simsig Usage Examples

This document provides a walkthrough of the example scripts included in the `examples/` directory. Each script is designed to demonstrate a specific set of features from the `simsig` library, ranging from basic setup to advanced, real-world scenarios.

---

## `ex0.py`: Basic Usage and Graceful Shutdown

This script demonstrates the most common use case: setting up a graceful shutdown handler and registering custom handlers for application-specific signals.

<details>
<summary>Click to view source code for <code>ex0.py</code></summary>

```python
#!/usr/bin/env python3
import simsig
import time
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def main():
    """Main function demonstrating basic simsig usage."""
    print(f"Script running with PID: {os.getpid()}")
    print("You can send signals to this process from another terminal.")

    # 1. Define a cleanup function for graceful shutdown
    def my_cleanup():
        print("\n--- GRACEFUL SHUTDOWN INITIATED ---")
        print("Closing resources, saving state...")
        time.sleep(1) # Simulate cleanup work
        print("--- CLEANUP COMPLETE ---")

    # 2. Register the cleanup function for all terminating signals (like Ctrl+C)
    simsig.graceful_shutdown(my_cleanup)
    print("\n--> Press Ctrl+C to test graceful shutdown.")

    # 3. Set custom handlers for a user-defined signals
    def usr1_handler(signum, frame):
        print("\n--> Received SIGUSR1! Current status: processing item #123")

    def info_handler(signum, frame):
        print("\n--> Received SIGINFO! Current status: processing item #123")

    if simsig.has_sig('SIGUSR1'):
        simsig.set_handler(simsig.Signals.SIGUSR1, usr1_handler)
        print(f"--> Run 'kill -USR1 {os.getpid()}' to get a status update")

    if simsig.has_sig('SIGINFO'):
        simsig.set_handler(simsig.Signals.SIGINFO, info_handler)
        print(f"--> Run 'kill -INFO {os.getpid()}' to get a status update or try Ctrl-T (Mac OS X/FreeBSD/OpenBSD)")

    # Main application loop
    print("\nApplication is running. Waiting for signals.")
    try:
        while True:
            time.sleep(1)
    except SystemExit:
        print("Application exiting due to SystemExit from signal handler.")

if __name__ == "__main__":
    main()
```
</details>

### How to Run It
From the project's root directory:
```bash
python3 examples/ex0.py
```

### What to Do and Expected Outcome
1.  **Press `Ctrl+C`:** You will see the "GRACEFUL SHUTDOWN" message, followed by the cleanup simulation, and then the script will exit.
2.  **From another terminal, run `kill -USR1 <PID>`:** The script will print the `SIGUSR1` status message and continue running.
3.  **From another terminal, run `kill -INFO <PID>` (or press `Ctrl+T` on macOS/BSD):** The script will print the `SIGINFO` status message and continue running.

---

## `ex1.py`: Advanced Context Managers

This script demonstrates the power of `simsig`'s context managers for temporarily changing signal behavior for critical sections, timeouts, and signal blocking.

<details>
<summary>Click to view source code for <code>ex1.py</code></summary>

```python
#!/usr/bin/env python3
import os
import sys
import time
import logging

import simsig

"""Advanced context manager usage"""

logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

def main():
    print(f"Script running with PID: {os.getpid()}")

    print("\n--- Testing temp_handler ---")
    print("Entering a 5-second critical section where Ctrl+C will be ignored.")
    with simsig.temp_handler(simsig.Signals.SIGINT, simsig.SigReaction.ign):
        for i in range(5, 0, -1):
            print(f"Critical section... {i}s remaining. Try pressing Ctrl+C (it should be ignored).")
            time.sleep(1)
    print("Exited critical section. Ctrl+C is now active again.")
    time.sleep(2)


    print("\n--- Testing with_timeout ---")
    print("Calling a function that takes 10 seconds, but with a 3-second timeout.")
    try:
        with simsig.with_timeout(3):
            time.sleep(10)
    except simsig.SimSigTimeoutError as e:
        print(f"SUCCESS: Caught expected exception: {e}")
    time.sleep(2)


    print("\n--- Testing block_signals ---")
    print("Entering a 5-second block where SIGINFO will be blocked (not delivered).")

    def handler(s, f): print("--> Handler for SIGINFO was finally called!")
    simsig.set_handler(simsig.Signals.SIGINFO, handler)
 
    print(f"Run 'kill -INFO {os.getpid()}' in the next 5 seconds, or press Ctrl-T (Mac OS X/*BSD).")
    with simsig.block_signals(simsig.Signals.SIGINFO):
         for i in range(5, 0, -1):
            print(f"Signals blocked... {i}s remaining.")
            time.sleep(1)
    print("Exited signal block. Any pending signal should be delivered now.")


    print("\nDemo finished.")

if __name__ == "__main__":
    main()
```
</details>

### How to Run It
```bash
python3 examples/ex1.py
```

### What to Do and Expected Outcome
1.  **During the `temp_handler` section (first 5 seconds):** Press `Ctrl+C`. Nothing will happen. The script will ignore the signal. After the block exits, `Ctrl+C` will terminate the script as usual.
2.  **During the `with_timeout` section:** The script will attempt to sleep for 10 seconds, but after 3 seconds, a `SimSigTimeoutError` will be raised and caught, and the script will print a success message.
3.  **During the `block_signals` section:** While the script counts down, send a `SIGINFO` signal (e.g., press `Ctrl+T`). The handler will **not** fire immediately. Only after the 5-second block is finished will you see the message "Handler for SIGINFO was finally called!", demonstrating that the signal was queued and delivered later.

---

## `ex2.py`: Asynchronous (`asyncio`) Integration

This script shows the correct way to handle signals in an `asyncio` application to allow for a clean shutdown of concurrent tasks.

<details>
<summary>Click to view source code for <code>ex2.py</code></summary>

```python
#!/usr/bin/env python3
import os
import asyncio
import logging

import simsig


logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

# An event to signal graceful shutdown for all async tasks
shutdown_event = asyncio.Event()

def shutdown_handler():
    print("\n--> Shutdown signal received! Notifying async tasks...")
    shutdown_event.set()

async def worker(name: str, interval:int=1):
    """A sample async task that runs until shutdown is signaled."""
    print(f"Worker '{name}' started.")
    while not shutdown_event.is_set():
        print(f"Worker '{name}' is doing work...")
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break
    print(f"Worker '{name}' is shutting down.")

async def main():
    """Main async function."""
    print(f"Async application running with PID: {os.getpid()}")
    print("Press Ctrl+C to trigger graceful shutdown.")

    # 1. Register the shutdown handler with asyncio's event loop via simsig
    simsig.async_handler([simsig.Signals.SIGINT, simsig.Signals.SIGTERM], shutdown_handler)

    # 2. Start concurrent tasks
    task1 = asyncio.create_task(worker("A", 2))
    task2 = asyncio.create_task(worker("B", 3))

    # 3. Wait for the shutdown signal
    await shutdown_event.wait()

    # 4. Gracefully cancel and await tasks
    print("Main task is now cancelling worker tasks...")
    task1.cancel()
    task2.cancel()
    await asyncio.gather(task1, task2, return_exceptions=True)
    print("All tasks finished. Exiting.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Application terminated.")
```
</details>

### How to Run It
```bash
python3 examples/ex2.py
```

### What to Do and Expected Outcome
* **Press `Ctrl+C`:** Instead of terminating immediately, the program will print "Shutdown signal received!". The `shutdown_event` will be set, causing the main function to proceed. It will then gracefully cancel the two running worker tasks, wait for them to finish their cleanup, and exit cleanly.

---

## `ex3.py`: Minimalistic Demonstration

This script combines several features in a minimal, "ascetic" way, without any extra explanatory `print` statements. It's a dense demonstration of the library's power.

<details>
<summary>Click to view source code for <code>ex3.py</code></summary>

```python
#!/usr/bin/env python3
import simsig
import time
import os
import sys

# Check if the module can run on this OS.
if sys.platform == "win32":
    print("This minimal example is designed for UNIX-like systems and will now exit")
    sys.exit(0)

# Define a minimal exit function.
def on_exit():
    # Exit the process immediately, without cleanup.
    os._exit(0)

# Define an empty handler for status checks.
def show_status(signal_number, frame):
    # Do nothing, just catch the signal.
    pass

# All terminating signals (including Ctrl+C) will now exit silently.
simsig.graceful_shutdown(on_exit)

# Set the handler for the user signal SIGINFO
simsig.set_handler(simsig.Signals.SIGINFO, show_status)

# Temporarily ignore Ctrl+C for 10 seconds.
with simsig.temp_handler(simsig.Signals.SIGINT, simsig.SigReaction.ign):
    time.sleep(10)

# Run a block that will be terminated by a timeout after 2 seconds.
try:
    with simsig.with_timeout(2):
        # This code will never finish its sleep.
        time.sleep(5)
except simsig.SimSigTimeoutError:
    # Catch the timeout error and do nothing.
    pass

# An infinite loop to keep the process alive to receive signals.
while True:
    time.sleep(1)
```
</details>

### How to Run It
```bash
python3 examples/ex3.py
```
### Expected Outcome
The script will appear to do nothing for 12 seconds and then will enter an infinite loop.
* **First 10 seconds:** The script is inside the `temp_handler` block. Any `Ctrl+C` press will be ignored.
* **Next 2 seconds:** The script enters the `with_timeout` block. It will be terminated by a `SimSigTimeoutError` after 2 seconds, but the `except: pass` block means you will see no output.
* **After 12 seconds:** The script enters the `while True` loop. Now, pressing `Ctrl+C` will trigger the `graceful_shutdown` handler (`on_exit`) and the process will terminate immediately and silently. Sending a `SIGINFO` will be caught by the empty `show_status` handler, having no visible effect.
