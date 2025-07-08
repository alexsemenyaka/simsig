#!/usr/bin/env python3
import logging
import os
import sys
import time

import simsig

"""Advanced context manager usage"""

logging.basicConfig(
    level=logging.DEBUG, format="%(name)s - %(levelname)s - %(message)s"
)


def main():
    print(f"Script running with PID: {os.getpid()}")

    print("\n--- Testing temp_handler ---")
    print("Entering a 5-second critical section where Ctrl+C will be ignored.")
    with simsig.temp_handler(simsig.Signals.SIGINT, simsig.SigReaction.IGN):
        for i in range(5, 0, -1):
            print(
                f"Critical section... {i}s remaining. Try pressing Ctrl+C (it should be ignored)."
            )
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

    def handler(s, f):
        print("--> Handler for SIGINFO was finally called!")

    simsig.set_handler(simsig.Signals.SIGINFO, handler)

    print(
        f"Run 'kill -INFO {os.getpid()}' in the next 5 seconds, or press Ctrl-T (Mac OS X/*BSD)."
    )
    with simsig.block_signals(simsig.Signals.SIGINFO):
        for i in range(5, 0, -1):
            print(f"Signals blocked... {i}s remaining.")
            time.sleep(1)
    print("Exited signal block. Any pending signal should be delivered now.")

    print("\nDemo finished.")


if __name__ == "__main__":
    main()
