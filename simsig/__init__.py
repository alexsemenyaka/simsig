"""
simsig: a simple but powerful thread-safe, and async-aware
signal handling framework for Python.
"""

import importlib.metadata

from .simsig import (Signals, SigReaction, SimSig, SimSigTimeoutError,
                     async_handler, block_signals, chain_handler,
                     get_signal_setting, graceful_shutdown, has_sig,
                     ignore_terminal_signals, reset_to_defaults, set_handler,
                     temp_handler, with_timeout)

_metadata = importlib.metadata.metadata("simsig")
__version__ = _metadata["Version"]
__author__ = _metadata["Author-email"]
__license__ = _metadata["License"]

__all__ = [
    "SimSig",
    "SigReaction",
    "Signals",
    "SimSigTimeoutError",
    "set_handler",
    "graceful_shutdown",
    "chain_handler",
    "ignore_terminal_signals",
    "reset_to_defaults",
    "async_handler",
    "get_signal_setting",
    "has_sig",
    "temp_handler",
    "with_timeout",
    "block_signals",
]
