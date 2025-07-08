#!/usr/bin/env python3
import asyncio
import logging
import os

import simsig

logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")

# An event to signal graceful shutdown for all async tasks
shutdown_event = asyncio.Event()


def shutdown_handler():
    print("\n--> Shutdown signal received! Notifying async tasks...")
    shutdown_event.set()


async def worker(name: str, interval: int = 1):
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
    simsig.async_handler(
        [simsig.Signals.SIGINT, simsig.Signals.SIGTERM], shutdown_handler
    )

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
