#!/usr/bin/env python3

import os
import sys
import time

import simsig

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
with simsig.temp_handler(simsig.Signals.SIGINT, simsig.SigReaction.IGN):
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
