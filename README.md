# simsig: A Simple and Powerful Signal Handling Framework

[![PyPI version](https://img.shields.io/pypi/v/simsig.svg?style=for-the-badge)](https://pypi.org/project/simsig/)
[![Coverage Status](https://img.shields.io/coveralls/github/alexsemenyaka/simsig.svg?style=for-the-badge)](https://coveralls.io/github/alexsemenyaka/simsig)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

`simsig` is a Python library that provides a high-level, intuitive, and powerful interface for handling OS signals. It's built on top of Python's standard `signal` module but abstracts away its complexities and limitations, making it easy to write robust, signal-aware applications.

## Key Features

* **Graceful Shutdown:** Easily register cleanup functions that run on terminating signals like `SIGINT` (`Ctrl+C`) or `SIGTERM`.
* **Functional & OOP API:** Use simple module-level functions for quick tasks, or instantiate the `SimSig` class for more complex state management.
* **Powerful Context Managers:**
    * Temporarily change signal handlers for critical sections of code.
    * Run blocks of code with a timeout.
    * Block signal delivery entirely for performance-critical operations.
* **Handler Chaining:** Add new behavior to existing signal handlers without overwriting them.
* **Asyncio Integration:** A dedicated, safe method for handling signals within an `asyncio` event loop.
* **Cross-Platform:** Provides a consistent interface and gracefully handles differences between operating systems (e.g., UNIX vs. Windows).
    * Windows support is fairly limited though at the moment

## Installation

Install the library directly from PyPI:
```bash
pip install simsig
```
For developers, you can install it in editable mode from a local clone:
```bash
git clone https://github.com/alexsemenyaka/simsig.git
cd simsig
pip install -e .
```
---
## A Primer on UNIX Signals

Before diving into the library, it's helpful to understand what signals are.

### What Are Signals?

A signal is a form of **Inter-Process Communication (IPC)** in UNIX-like systems. It's a notification sent to a process to inform it of an event. Think of it as a software interrupt or a doorbell for a process. When a signal is sent, the operating system interrupts the process's normal execution flow to deliver it.

### Signal Dispositions

A process can handle a signal in one of three ways (its "disposition"):

1.  **Catch the signal:** The process can register a custom function (a **signal handler**) that will be executed when the signal is received.
2.  **Ignore the signal:** The process can tell the OS to simply discard the signal. The special constant for this is `SIG_IGN`.
3.  **Use the default action:** Every signal has a default action, which is executed if the process doesn't specify otherwise. The constant for this is `SIG_DFL`. Common default actions include terminating the process, creating a core dump, or doing nothing.

### Synchronous vs. Asynchronous Signals

This is a key distinction:
* **Asynchronous Signals:** These are generated by events external to the process and can arrive at any time. The classic example is pressing `Ctrl+C` in your terminal, which causes the OS to send a `SIGINT` to the foreground process. Other examples include `SIGTERM` from the `kill` command or `SIGHUP` when a terminal closes.
* **Synchronous Signals:** These are caused directly by the process's own execution. For example, if a process attempts an illegal memory access, the CPU generates a fault that the OS translates into a `SIGSEGV` (Segmentation Fault) sent back to the process. Other examples include `SIGFPE` (Floating-Point Exception) for invalid math operations or `SIGILL` for an illegal instruction. They are "synchronous" because they are tied to a specific point in the code.

For more detailed information, the official POSIX standard for `<signal.h>` is the ultimate reference:
* [**POSIX.1-2017 `<signal.h>` Specification**]([https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/signal.h.html](https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/signal.h.html))

---
## Core Usage

`simsig` provides a simple functional API for most common use cases.

### Basic Usage: Graceful Shutdown & Custom Handlers

This example sets up a handler to perform a clean exit on `Ctrl+C` and a custom handler for a user signal.

```python
import simsig
import time
import os
import sys

# This minimal example is designed for UNIX-like systems.
if sys.platform == "win32":
    sys.exit(0)

# 1. Define a minimal exit function.
def on_exit():
    # Exit the process immediately, without cleanup.
    os._exit(0)

# 2. All terminating signals (including Ctrl+C) will now exit silently.
simsig.graceful_shutdown(on_exit)

# 3. Define an empty handler for status checks.
def show_status(signal_number, frame):
    # Do nothing, just catch the signal.
    pass

# 4. Set the handler for the user signal SIGUSR1.
if simsig.has_sig('SIGUSR1'):
    simsig.set_handler(simsig.Signals.SIGUSR1, show_status)

# 5. An infinite loop to keep the process alive.
while True:
    time.sleep(1)
```

### Advanced Usage: Context Managers

`simsig` provides powerful context managers for temporarily changing signal behavior.

```python
import simsig
import time
import sys

if sys.platform == "win32":
    sys.exit(0)

# 1. Temporarily ignore Ctrl+C for 10 seconds.
print("Ignoring Ctrl+C for 10 seconds...")
with simsig.temp_handler(simsig.Signals.SIGINT, simsig.SigReaction.ign):
    time.sleep(10)
print("Ctrl+C is now restored.")

# 2. Run a block that will be terminated by a timeout after 2 seconds.
print("\nRunning a 5-second task with a 2-second timeout...")
try:
    with simsig.with_timeout(2):
        time.sleep(5)
except simsig.SimSigTimeoutError:
    # Catch the timeout error and do nothing.
    print("Caught expected timeout.")
```

### Asynchronous Programming (`asyncio`)

Handling signals in `asyncio` requires special care. `simsig` provides a safe and easy way to integrate with the event loop.

```python
import simsig
import asyncio
import sys

if sys.platform == "win32":
    sys.exit(0)

shutdown_event = asyncio.Event()

# The handler must be a regular function that sets the asyncio event.
def shutdown_handler():
    print("\nSignal received, notifying tasks...")
    shutdown_event.set()

async def main():
    # Register the handler correctly within the running loop.
    simsig.async_handler([simsig.Signals.SIGINT, simsig.Signals.SIGTERM], shutdown_handler)
    
    print("Application running. Press Ctrl+C to shut down.")
    await shutdown_event.wait()
    print("Shutdown complete.")

if __name__ == "__main__":
    asyncio.run(main())
```

## API Reference
The library exposes both a class-based and a functional API.

* **Classes**:
    * `Signals`: an `IntEnum` containing all signals available on the current OS
    * `SigReaction`: an `IntEnum` for high-level actions: `DFLT` for the deault action, `IGN` to ignore a signal, `fin` - to run the shutdown handler
    * `SimSig`: the main class for handling signals in an object-oriented way, no parameters for `__init__`
        * `set_handler(sigs, reaction)`: sets a handler for one or more signals
            * `sigs`:     a signal number, a `Signals` object, or a list/tuple consisting of them (you may mix numbers and `Signal` objs)
            * `reaction`: a `SigReaction` object or `callable` object (a callback), it defines how to treat `sigs`
        * `graceful_shutdown(callback)`: sets a specific callback for all typical terminating signals
            * `callback`: a `callable` object to be called when terminated signal is delivered
        * `chain_handler(sig, callback, order)`: adds a new callback to an existing signal handler chain
            * `sig`:      a signal number or a `Signals` object
            * `callback`: a `callable` object to be added to the signal handler chain
            * `order`:    string 'before' or 'after' specifing where to put a new handler in the chain
        * `ignore_terminal_signals()`: start ignoring all signals related to the controlling terminal
        * `reset_to_defaults()`: resets all catchable signal handlers to the OS default (`SIG_DFL`)
        * `async_handler(sigs, callback)`: registers a callback for use in an asyncio event loop
            * `sigs`:     a signal number, a `Signals` object, or a list/tuple consisting of them (you may mix numbers and `Signal` objs)
            * `callback`: a `callable` object (a callback) to be called when one of `sigs` is delivered
        * `get_signal_setting(sig)`: returns the current handler for a given signal
            * `sig`:      a signal number or a `Signals` object
        * `has_sig(sig_id)`: checks if a signal exists on the current system by its name or number, returns True or False
            * `sig_id`:    a signal number or signal name (like 'SIGTERM'). If another type is provided, `sig_id` will be converted to str first
    * `SimSigTimeoutError(message)`: custom exception for timeouts
        * `message`:   (optional) a custom message to store inside the exception object, the defaul is `'SIGALRM'` (so for UNIX systems `has_sig(SimSigTimeoutError())==True`)
* **Context Managers**:
    * `temp_handler(sigs, reaction)`: temporarily seting a handler, restoring the old one on exit
        * `sigs`:     a signal number, a `Signals` object, or a list/tuple consisting of them (you may mix numbers and `Signal` objs)
        * `reaction`: a `SigReaction` object or `callable` object (a callback), it defines how to treat `sigs`
    * `with_timeout(seconds)`: context manager to run a block of code with a timeout (UNIX-only)
        * `seconds`:  timeout to wait until SIGALRM will be sent
    * `block_signals(sigs)`: context manager to temporarily block signals from being delivered (UNIX-only); they are going to be delivered after the leaving the covered block of code
        * `sigs`:     a signal number, a `Signals` object, or a list/tuple consisting of them (you may mix numbers and `Signal` objs)
* **Functions** strictly correnpond to the SimSig class methods with the same names
    * `set_handler(sigs, reaction)`
    * `graceful_shutdown(callback)`
    * `chain_handler(sig, callback, order)`
    * `ignore_terminal_signals()`
    * `reset_to_defaults()`
    * `async_handler(sigs, callback)`
    * `get_signal_setting(sig)`
    * `has_sig(sig_id)`.

For detailed information on each function's parameters, please refer to the docstrings within the source code.

## License
This project is licensed under the MIT License. See the `LICENSE` file for details.
