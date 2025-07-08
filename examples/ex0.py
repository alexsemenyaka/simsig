#!/usr/bin/env python3
import logging
import os
import time

import simsig

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def main():
    """Main function demonstrating basic simsig usage."""
    print(f"Script running with PID: {os.getpid()}")
    print("You can send signals to this process from another terminal.")

    # 1. Define a cleanup function for graceful shutdown
    def my_cleanup():
        print("\n--- GRACEFUL SHUTDOWN INITIATED ---")
        print("Closing resources, saving state...")
        time.sleep(1)  # Simulate cleanup work
        print("--- CLEANUP COMPLETE ---")

    # 2. Register the cleanup function for all terminating signals (like Ctrl+C)
    simsig.graceful_shutdown(my_cleanup)
    print("\n--> Press Ctrl+C to test graceful shutdown.")

    # 3. Set custom handlers for a user-defined signals
    def usr1_handler(signum, frame):
        print("\n--> Received SIGUSR1! Current status: processing item #123")

    def info_handler(signum, frame):
        print("\n--> Received SIGINFO! Current status: processing item #123")

    if simsig.has_sig("SIGUSR1"):
        simsig.set_handler(simsig.Signals.SIGUSR1, usr1_handler)
        print(f"--> Run 'kill -USR1 {os.getpid()}' to get a status update")

    if simsig.has_sig("SIGINFO"):
        simsig.set_handler(simsig.Signals.SIGINFO, info_handler)
        print(
            f"--> Run 'kill -INFO {os.getpid()}' to get a status update or try Ctrl-T (Mac OS X/FreeBSD/OpenBSD)"
        )

    # Main application loop
    print("\nApplication is running. Waiting for signals.")
    try:
        while True:
            time.sleep(1)
    except SystemExit:
        print("Application exiting due to SystemExit from signal handler.")


if __name__ == "__main__":
    main()
