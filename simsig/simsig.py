# simsig.py

import asyncio
import logging
import signal
import sys
from contextlib import contextmanager
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Set, Union

# Set up a dedicated logger for this module
logger = logging.getLogger("simsig")

# Dynamically create the Signals enum from signals available here
_AVAILABLE_SIGNALS: Dict[str, int] = {
    name: val
    for name, val in signal.__dict__.items()
    if isinstance(val, int) and name.startswith("SIG") and not name.startswith("SIG_")
}
Signals = IntEnum("Signals", _AVAILABLE_SIGNALS)


class SigReaction(IntEnum):
    """Defines possible high-level reactions to a signal."""

    dflt = 0  # Use the default OS handler
    ign = 1  # Ignore the signal
    fin = 2  # Terminate the process (gracefully, if configured)


class SimSigTimeoutError(TimeoutError):
    """Custom exception raised by the with_timeout context manager."""

    pass


class SimSig:
    """A class providing a powerful and intuitive interface for signal management."""

    def __init__(self):
        self._graceful_shutdown_callback: Optional[Callable] = None
        self._fin_handler: Optional[Callable] = None

        self._terminating_by_default: Set[Signals] = {
            s
            for s in Signals
            if s.name
            in [
                "SIGHUP",
                "SIGINT",
                "SIGQUIT",
                "SIGILL",
                "SIGABRT",
                "SIGFPE",
                "SIGSEGV",
                "SIGPIPE",
                "SIGALRM",
                "SIGTERM",
                "SIGXCPU",
                "SIGXFSZ",
                "SIGVTALRM",
                "SIGPROF",
                "SIGUSR1",
                "SIGUSR2",
            ]
        }
        self._suspending_by_default: Set[Signals] = {
            s for s in Signals if s.name in ["SIGSTOP", "SIGTSTP", "SIGTTIN", "SIGTTOU"]
        }
        logger.debug("SimSig instance created.")

    def _normalize_signals(
        self, signals: Union[Signals, int, List[Union[Signals, int]]]
    ) -> List[int]:
        """Helper to ensure the input is always a list of signal integers."""
        if not isinstance(signals, (list, tuple)):
            return [int(signals)]
        return [int(s) for s in signals]

    def _create_fin_handler(self) -> Callable:
        """Creates and caches a generic termination handler."""
        if self._fin_handler is None:
            logger.debug("Creating a new 'fin' handler.")

            def handler(signum, frame):
                sig_name = Signals(signum).name
                logger.warning(
                    f"Received terminating signal {sig_name}. Initiating shutdown."
                )
                if self._graceful_shutdown_callback:
                    logger.info("Executing graceful shutdown callback.")
                    self._graceful_shutdown_callback()
                sys.exit(128 + signum)

            self._fin_handler = handler
        return self._fin_handler

    def set_handler(
        self,
        signals: Union[Signals, int, List[Union[Signals, int]]],
        reaction: Union[SigReaction, Callable],
    ):
        """Sets a handler for one or more signals."""
        signal_list = self._normalize_signals(signals)
        handler_to_set: Any = None

        if isinstance(reaction, SigReaction):
            reaction_map = {
                SigReaction.dflt: signal.SIG_DFL,
                SigReaction.ign: signal.SIG_IGN,
                SigReaction.fin: self._create_fin_handler(),
            }
            handler_to_set = reaction_map.get(reaction)
        elif callable(reaction):
            handler_to_set = reaction
        else:
            raise TypeError("handler must be a SigReaction enum or a callable.")

        for sig in signal_list:
            sig_name = Signals(sig).name
            reaction_name = (
                reaction.name
                if isinstance(reaction, SigReaction)
                else getattr(reaction, "__name__", str(reaction))
            )
            logger.info(f"Setting handler for {sig_name} to {reaction_name}.")
            try:
                signal.signal(sig, handler_to_set)
            except (ValueError, OSError) as e:
                logger.warning(f"Could not set handler for {sig_name}: {e}")

    def graceful_shutdown(self, callback: Callable):
        """Sets a specific callback for all typical terminating signals."""
        if not callable(callback):
            raise TypeError("Provided callback must be a callable function.")
        logger.info(f"Registering '{callback.__name__}' for graceful shutdown.")
        self._graceful_shutdown_callback = callback

        signals_to_set = [
            s for s in self._terminating_by_default if s.name != "SIGKILL"
        ]
        self.set_handler(signals_to_set, SigReaction.fin)

    def chain_handler(
        self, sig: Union[Signals, int], callback: Callable, order: str = "before"
    ):
        """🔗 Adds a new callback to an existing signal handler chain."""
        if order not in ["before", "after"]:
            raise ValueError("Order must be 'before' or 'after'.")

        original_handler = self.get_signal_setting(sig)
        sig_name = Signals(sig).name
        logger.info(
            f"Chaining callback '{callback.__name__}' to {sig_name} handler (order: {order})."
        )

        def chained_handler(signum, frame):
            if order == "before":
                callback(signum, frame)
                if callable(original_handler):
                    original_handler(signum, frame)
            else:  # after
                if callable(original_handler):
                    original_handler(signum, frame)
                callback(signum, frame)

        self.set_handler(sig, chained_handler)

    # --- Utility & Context Managers ---

    def ignore_terminal_signals(self):
        """Ignores all signals related to the controlling terminal."""
        terminal_signal_names = [
            "SIGHUP",
            "SIGINT",
            "SIGTSTP",
            "SIGTTIN",
            "SIGTTOU",
            "SIGWINCH",
        ]
        signals_to_ignore = [
            Signals[name]
            for name in terminal_signal_names
            if name in Signals.__members__
        ]
        if signals_to_ignore:
            logger.info(
                f"Ignoring terminal signals: {[s.name for s in signals_to_ignore]}."
            )
            self.set_handler(signals_to_ignore, SigReaction.ign)

    def reset_to_defaults(self):
        """🔄 Resets all catchable signal handlers to the OS default (SIG_DFL)."""
        logger.info("Resetting all possible signal handlers to default.")
        for sig in Signals:
            try:
                self.set_handler(sig, SigReaction.dflt)
            except (OSError, ValueError, RuntimeError):
                logger.debug(
                    f"Could not reset {sig.name}, signal is likely uncatchable."
                )
                continue

    @contextmanager
    def temp_handler(
        self,
        signals: Union[Signals, int, List[Union[Signals, int]]],
        reaction: Union[SigReaction, Callable],
    ):
        """⏱️ Context manager to temporarily set a handler, restoring the old one on exit."""
        signal_list = self._normalize_signals(signals)
        original_handlers = {sig: self.get_signal_setting(sig) for sig in signal_list}

        logger.debug(
            f"Entering temp_handler context for signals {[Signals(s).name for s in signal_list]}."
        )
        try:
            self.set_handler(signal_list, reaction)
            yield
        finally:
            logger.debug(f"Exiting temp_handler context, restoring original handlers.")
            for sig, handler in original_handlers.items():
                if handler is not None:
                    try:
                        signal.signal(sig, handler)
                    except (ValueError, OSError):
                        pass  # Suppressing errors if we somehow still try to set a handler for an uncatchable signal.

    @contextmanager
    def with_timeout(self, seconds: int):
        """⏳ Context manager to run a block of code with a timeout (UNIX-only)."""
        if not hasattr(signal, "SIGALRM"):
            raise NotImplementedError(
                "Timeout via SIGALRM is not supported on this OS."
            )

        def _timeout_handler(signum, frame):
            raise SimSigTimeoutError(
                f"Code block did not complete in {seconds} seconds."
            )

        logger.debug(f"Entering with_timeout context for {seconds}s.")
        original_handler = self.get_signal_setting(Signals.SIGALRM)
        signal.signal(Signals.SIGALRM, _timeout_handler)
        signal.alarm(seconds)

        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(Signals.SIGALRM, original_handler)
            logger.debug("Exiting with_timeout context.")

    @contextmanager
    def block_signals(self, signals: Union[Signals, int, List[Union[Signals, int]]]):
        """🛡️ Context manager to temporarily block signals from being delivered (UNIX-only)."""
        if not hasattr(signal, "pthread_sigmask"):
            raise NotImplementedError(
                "Signal masking (pthread_sigmask) is not supported on this OS."
            )

        signal_list = self._normalize_signals(signals)
        logger.debug(f"Blocking signals {[Signals(s).name for s in signal_list]}.")

        try:
            signal.pthread_sigmask(signal.SIG_BLOCK, signal_list)
            yield
        finally:
            logger.debug("Unblocking signals.")
            signal.pthread_sigmask(signal.SIG_UNBLOCK, signal_list)

    # --- Asyncio Integration ---

    def async_handler(
        self,
        signals: Union[Signals, int, List[Union[Signals, int]]],
        callback: Callable[..., Any],
    ):
        """⚡ Registers a callback for use in an asyncio event loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError as e:
            raise RuntimeError(
                "async_handler can only be called from within a running asyncio event loop."
            ) from e

        signal_list = self._normalize_signals(signals)

        for sig in signal_list:
            logger.info(
                f"Registering async handler '{callback.__name__}' for {Signals(sig).name}."
            )
            loop.add_signal_handler(sig, callback)

    # --- Informational Methods ---

    def get_signal_setting(self, sig: Union[Signals, int]) -> Any:
        """Returns the current handler for a given signal."""
        return signal.getsignal(int(sig))

    @staticmethod
    def has_sig(sig_identifier: Union[str, int]) -> bool:
        """Checks if a signal exists on the current system by its name or number."""
        if isinstance(sig_identifier, str):
            return sig_identifier in Signals.__members__
        if isinstance(sig_identifier, int):
            return sig_identifier in Signals._value2member_map_
        return False



# For lazy people, a default instance of SimSig is created.
# Now, they can call these functions directly, without instantiating the class.

_default_instance = SimSig()

def set_handler(
    signals: Union[Signals, int, List[Union[Signals, int]]],
    reaction: Union[SigReaction, Callable],
):
    """Functional wrapper for SimSig.set_handler."""
    _default_instance.set_handler(signals, reaction)


def graceful_shutdown(callback: Callable):
    """Functional wrapper for SimSig.graceful_shutdown."""
    _default_instance.graceful_shutdown(callback)


def chain_handler(sig: Union[Signals, int], callback: Callable, order: str = "before"):
    """Functional wrapper for SimSig.chain_handler."""
    _default_instance.chain_handler(sig, callback, order)


def ignore_terminal_signals():
    """Functional wrapper for SimSig.ignore_terminal_signals."""
    _default_instance.ignore_terminal_signals()


def reset_to_defaults():
    """Functional wrapper for SimSig.reset_to_defaults."""
    _default_instance.reset_to_defaults()


def async_handler(
    signals: Union[Signals, int, List[Union[Signals, int]]],
    callback: Callable[..., Any],
):
    """Functional wrapper for SimSig.async_handler."""
    _default_instance.async_handler(signals, callback)


def get_signal_setting(sig: Union[Signals, int]) -> Any:
    """Functional wrapper for SimSig.get_signal_setting."""
    return _default_instance.get_signal_setting(sig)


def temp_handler(
    signals: Union[Signals, int, List[Union[Signals, int]]],
    reaction: Union[SigReaction, Callable],
):
    """Functional wrapper for the SimSig.temp_handler context manager."""
    return _default_instance.temp_handler(signals, reaction)


def with_timeout(seconds: int):
    """Functional wrapper for the SimSig.with_timeout context manager."""
    return _default_instance.with_timeout(seconds)


def block_signals(signals: Union[Signals, int, List[Union[Signals, int]]]):
    """Functional wrapper for the SimSig.block_signals context manager."""
    return _default_instance.block_signals(signals)


def has_sig(sig_identifier: Union[str, int]) -> bool:
    """Functional wrapper for SimSig.has_sig."""
    return SimSig.has_sig(sig_identifier)
