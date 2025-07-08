import asyncio
import os
import signal
import sys
import threading
import time
from unittest.mock import Mock, patch

import pytest

import simsig

# A marker to skip tests on non-UNIX platforms
IS_UNIX = sys.platform != "win32"
unix_only = pytest.mark.skipif(not IS_UNIX, reason="This test is UNIX-only.")

# --- Test Fixtures ---


@pytest.fixture
def clean_simsig(monkeypatch):
    """
    This fixture provides a clean, new instance of SimSig for each test
    and resets all signal handlers to default afterwards.
    """
    instance = simsig.SimSig()
    # To test the functional API, we patch the module's default instance
    monkeypatch.setattr(simsig.simsig, "_default_instance", instance)
    yield instance
    # Teardown: reset all handlers after the test has run
    instance.reset_to_defaults()


# --- Unit Tests ---


@pytest.mark.unit
def test_set_handler_ign(clean_simsig):
    """Tests setting a handler to be ignored."""
    simsig.set_handler(simsig.Signals.SIGUSR1, simsig.SigReaction.IGN)
    assert signal.getsignal(simsig.Signals.SIGUSR1) == signal.SIG_IGN


@pytest.mark.unit
def test_set_handler_dfl(clean_simsig):
    """Tests setting a handler to its default."""
    # First, set it to something else
    signal.signal(simsig.Signals.SIGUSR1, signal.SIG_IGN)
    # Now, test the reset functionality
    simsig.set_handler(simsig.Signals.SIGUSR1, simsig.SigReaction.DFLT)
    assert signal.getsignal(simsig.Signals.SIGUSR1) == signal.SIG_DFL


@pytest.mark.unit
def test_chain_handler(clean_simsig):
    """Tests that handlers can be chained correctly."""
    call_log = []

    def original_handler(s, f):
        call_log.append("original")

    def chained_handler(s, f):
        call_log.append("chained")

    simsig.set_handler(simsig.Signals.SIGUSR1, original_handler)

    # Test 'before' order
    simsig.chain_handler(simsig.Signals.SIGUSR1, chained_handler, order="before")
    current_handler = signal.getsignal(simsig.Signals.SIGUSR1)
    current_handler(simsig.Signals.SIGUSR1, None)
    assert call_log == ["chained", "original"]

    # Test 'after' order
    call_log.clear()
    simsig.set_handler(simsig.Signals.SIGUSR1, original_handler)  # Reset handler
    simsig.chain_handler(simsig.Signals.SIGUSR1, chained_handler, order="after")
    current_handler = signal.getsignal(simsig.Signals.SIGUSR1)
    current_handler(simsig.Signals.SIGUSR1, None)
    assert call_log == ["original", "chained"]


# --- Integration Tests ---


@pytest.mark.integration
def test_graceful_shutdown_callback(clean_simsig, mocker):
    """Tests that graceful_shutdown calls the callback and exits."""
    mock_callback = mocker.MagicMock()
    mock_callback.__name__ = "mock_cleanup_function"

    mock_exit = mocker.patch("sys.exit", side_effect=SystemExit)

    simsig.graceful_shutdown(mock_callback)

    with pytest.raises(SystemExit):
        os.kill(os.getpid(), signal.SIGINT)
        time.sleep(0.1)  # Give time for the signal to be processed

    mock_callback.assert_called_once()
    mock_exit.assert_called_once_with(128 + signal.SIGINT)


@pytest.mark.integration
def test_temp_handler_restores_original(clean_simsig):
    """Tests that temp_handler restores the original handler."""
    original_handler = signal.getsignal(simsig.Signals.SIGUSR2)
    with simsig.temp_handler(simsig.Signals.SIGUSR2, simsig.SigReaction.IGN):
        assert signal.getsignal(simsig.Signals.SIGUSR2) == signal.SIG_IGN
    assert signal.getsignal(simsig.Signals.SIGUSR2) == original_handler


@pytest.mark.integration
@unix_only
def test_with_timeout(clean_simsig):
    """Tests that with_timeout raises an exception on timeout."""
    with pytest.raises(simsig.SimSigTimeoutError):
        with simsig.with_timeout(1):
            time.sleep(2)


@pytest.mark.integration
@unix_only
def test_block_signals(clean_simsig):
    """Tests that signals are blocked and delivered after the context."""
    handler_called_time = None

    def handler(s, f):
        nonlocal handler_called_time
        handler_called_time = time.time()

    simsig.set_handler(simsig.Signals.SIGUSR1, handler)

    start_time = time.time()
    with simsig.block_signals(simsig.Signals.SIGUSR1):
        os.kill(os.getpid(), simsig.Signals.SIGUSR1)
        time.sleep(0.2)  # Wait inside the block
        # The handler should not have been called yet
        assert handler_called_time is None
        exit_block_time = time.time()

    time.sleep(0.2)  # Give the OS time to deliver the pending signal

    assert handler_called_time is not None
    assert handler_called_time > exit_block_time


# These tests require the 'pytest-asyncio' package, but our Makefile takes care of it
@pytest.mark.asyncio
@unix_only
async def test_async_handler(clean_simsig):
    """Tests asyncio signal handling."""
    event = asyncio.Event()
    simsig.async_handler(simsig.Signals.SIGUSR2, lambda: event.set())

    os.kill(os.getpid(), simsig.Signals.SIGUSR2)

    try:
        await asyncio.wait_for(event.wait(), timeout=1.0)
    except asyncio.TimeoutError:
        pytest.fail("async handler was not called within the timeout.")


@pytest.mark.unit
def test_set_handler_invalid_reaction_type(clean_simsig):
    """Covers the TypeError in set_handler for invalid reaction types."""
    with pytest.raises(
        TypeError, match="handler must be a SigReaction enum or a callable"
    ):
        simsig.set_handler(simsig.Signals.SIGUSR1, "not_a_reaction")


@pytest.mark.unit
def test_graceful_shutdown_invalid_callback_type(clean_simsig):
    """Covers the TypeError in graceful_shutdown for non-callable callbacks."""
    with pytest.raises(
        TypeError, match="Provided callback must be a callable function"
    ):
        simsig.graceful_shutdown("not_a_callable")


@pytest.mark.unit
def test_chain_handler_invalid_order(clean_simsig):
    """Covers the ValueError in chain_handler for invalid order."""
    with pytest.raises(ValueError, match="Order must be 'before' or 'after'"):
        simsig.chain_handler(
            simsig.Signals.SIGUSR1, lambda s, f: None, order="sideways"
        )


@pytest.mark.unit
def test_has_sig_invalid_type(clean_simsig):
    """Covers the final return False in has_sig for invalid identifier types."""
    assert not simsig.has_sig(None)
    assert not simsig.has_sig(123.45)


@pytest.mark.unit
def test_async_handler_outside_loop(clean_simsig):
    """Covers the RuntimeError when async_handler is called outside a running loop."""
    with pytest.raises(
        RuntimeError,
        match="async_handler is to be called from within a running asyncio event loop",
    ):
        simsig.async_handler(simsig.Signals.SIGUSR1, lambda: None)


@pytest.mark.integration
def test_fin_reaction_without_graceful_callback(clean_simsig, mocker):
    """Covers the 'fin' handler case where no graceful_shutdown callback was set."""
    mock_exit = mocker.patch("sys.exit", side_effect=SystemExit)
    assert clean_simsig._graceful_shutdown_callback is None  # Verify precondition

    simsig.set_handler(simsig.Signals.SIGUSR2, simsig.SigReaction.FIN)

    with pytest.raises(SystemExit):
        os.kill(os.getpid(), simsig.Signals.SIGUSR2)
        time.sleep(0.1)

    mock_exit.assert_called_once_with(128 + simsig.Signals.SIGUSR2)


@pytest.mark.unit
def test_fin_handler_is_reused(clean_simsig):
    """Covers the caching logic of _create_fin_handler."""
    # First call creates the handler
    simsig.set_handler(simsig.Signals.SIGUSR1, simsig.SigReaction.FIN)
    handler1 = signal.getsignal(simsig.Signals.SIGUSR1)

    # Second call should reuse the same handler object
    simsig.set_handler(simsig.Signals.SIGUSR2, simsig.SigReaction.FIN)
    handler2 = signal.getsignal(simsig.Signals.SIGUSR2)

    assert callable(handler1)
    assert handler1 is handler2  # Check that the object is the same instance


# A marker for Windows-only tests
windows_only = pytest.mark.skipif(
    sys.platform != "win32", reason="This test is Windows-only."
)  ## Do we need this?


@pytest.mark.integration
@windows_only
def test_with_timeout_on_unsupported_os(clean_simsig):
    """Covers NotImplementedError for with_timeout on Windows."""
    with pytest.raises(NotImplementedError):
        with simsig.with_timeout(1):
            pass  # pragma: no cover


@pytest.mark.integration
@windows_only
def test_block_signals_on_unsupported_os(clean_simsig):
    """Covers NotImplementedError for block_signals on Windows."""
    with pytest.raises(NotImplementedError):
        with simsig.block_signals(simsig.Signals.SIGINT):
            pass  # pragma: no cover


@pytest.mark.integration
@unix_only
def test_temp_handler_with_uncatchable_signal(clean_simsig):
    """Covers the error-suppressing finally block in temp_handler."""
    # This test ensures that trying to restore a handler for an uncatchable
    # signal like SIGKILL doesn't raise an exception.
    original_handler = signal.getsignal(signal.SIGKILL)
    try:
        with simsig.temp_handler(signal.SIGKILL, simsig.SigReaction.IGN):
            pass  # The context manager should suppress the OSError on exit
    except OSError:
        pytest.fail("temp_handler did not suppress OSError for uncatchable signal.")
    # Verify the handler is still what it was
    assert signal.getsignal(signal.SIGKILL) == original_handler


@pytest.mark.unit
def test_ignore_terminal_signals_on_os_with_no_term_signals(clean_simsig, mocker):
    """
    Covers the case where ignore_terminal_signals is called on an OS
    with no matching terminal signals by mocking the Signals enum.
    """
    # Mock Signals enum to have no members
    mock_signals_enum = mocker.Mock()
    mock_signals_enum.__members__ = {}
    mocker.patch("simsig.simsig.Signals", mock_signals_enum)

    mock_set_handler = mocker.spy(clean_simsig, "set_handler")
    simsig.ignore_terminal_signals()

    # set_handler should not be called if no signals were found
    mock_set_handler.assert_not_called()


@pytest.mark.integration
@unix_only
def test_with_timeout_restores_on_unrelated_exception(clean_simsig, mocker):
    """
    Covers the finally block of with_timeout when a different exception occurs.
    """
    mock_alarm = mocker.patch("signal.alarm")
    mock_signal = mocker.patch("signal.signal")
    original_handler = "original_handler_sentinel"  # A sentinel object

    # We need to get the original handler before the test messes with it
    # But since we mock signal.signal, we also need to mock getsignal
    mocker.patch("signal.getsignal", return_value=original_handler)

    with pytest.raises(ValueError, match="test exception"):
        with simsig.with_timeout(5):
            raise ValueError("test exception")

    # Assert that the cleanup logic in 'finally' was called
    mock_alarm.assert_called_with(0)  # Assert that the alarm was cancelled
    mock_signal.assert_called_with(
        simsig.Signals.SIGALRM, original_handler
    )  # Handler was restored


@pytest.mark.unit
def test_temp_handler_suppresses_restore_error(clean_simsig, mocker):
    """
    Covers the 'except' pass in temp_handler's finally block
    by mocking signal.signal to raise an error.
    """
    # Make signal.signal raise an error when restoring the handler
    mock_signal = mocker.patch("signal.signal", side_effect=OSError("Can't set this!"))

    # We expect the context manager to suppress this error and exit cleanly
    try:
        with simsig.temp_handler(simsig.Signals.SIGUSR1, simsig.SigReaction.IGN):
            # The first call to set the handler will be mocked, but that's fine.
            # We are testing the exit part of the context manager.
            pass
    except OSError:
        pytest.fail(
            "temp_handler did not suppress the OSError during handler restoration."
        )


@pytest.mark.unit
def test_reset_to_defaults_handles_errors(clean_simsig, mocker):
    """
    Covers the try/except block in reset_to_defaults by forcing set_handler to fail.
    """
    # Make set_handler raise an error for a specific signal
    mock_set_handler = mocker.patch.object(
        clean_simsig, "set_handler", side_effect=RuntimeError("Test-induced failure")
    )

    # We expect reset_to_defaults to suppress this error and continue
    try:
        simsig.reset_to_defaults()
    except RuntimeError:
        pytest.fail("reset_to_defaults did not suppress the error from set_handler.")

    # Verify it was called for every signal in the enum
    assert mock_set_handler.call_count == len(simsig.Signals)


@pytest.mark.unit
def test_all_functional_api_wrappers_are_covered(clean_simsig, mocker):
    """
    Explicitly calls all simple functional wrappers to ensure they are marked as covered.
    This replaces the previous, less complete version of this test.
    """
    # Spy on the underlying class methods
    spy_reset = mocker.spy(clean_simsig, "reset_to_defaults")
    spy_get_setting = mocker.spy(clean_simsig, "get_signal_setting")
    spy_graceful = mocker.spy(clean_simsig, "graceful_shutdown")
    spy_chain = mocker.spy(clean_simsig, "chain_handler")

    # Call the functional wrappers
    simsig.reset_to_defaults()
    simsig.get_signal_setting(simsig.Signals.SIGINT)

    # For wrappers that need a callable, a simple lambda is enough
    dummy_func = lambda: None
    dummy_func_with_args = lambda s, f: None
    simsig.graceful_shutdown(dummy_func)
    simsig.chain_handler(simsig.Signals.SIGUSR1, dummy_func_with_args)

    # Assert that the spies were called
    spy_reset.assert_called_once()
    spy_get_setting.assert_any_call(simsig.Signals.SIGINT)

    spy_graceful.assert_called_once_with(dummy_func)
    spy_chain.assert_called_once_with(
        simsig.Signals.SIGUSR1, dummy_func_with_args, order="before"
    )
