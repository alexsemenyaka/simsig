# Testing Strategy for simsig

This document outlines the testing philosophy, tools, and procedures for the `simsig` library. We are committed to maintaining a high standard of quality and reliability, ensured by a comprehensive test suite.

## Testing Philosophy

The goal of our testing strategy is to ensure that `simsig`:
* **Is Reliable:** All features work as documented across different scenarios.
* **Is Robust:** Edge cases and error conditions are handled gracefully.
* **Is Cross-Platform:** The library behaves predictably on supported operating systems (primarily UNIX-like systems and Windows), and platform-specific features are clearly marked and tested.

We aim for a high test coverage percentage (90%+) to have confidence in the codebase.

## Frameworks and Tools

The test suite is built using a modern set of standard Python testing tools:

* **[pytest](https://pytest.org):** The core test runner. We use it for its powerful fixture model, simple `assert` statements, and rich plugin ecosystem.
* **[pytest-mock](https://github.com/pytest-dev/pytest-mock):** Provides the `mocker` fixture for easy and powerful mocking, spying, and patching of objects during tests.
* **[pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio):** A necessary plugin to test `async def` functions and ensure proper integration with the `asyncio` event loop.
* **[pytest-cov](https://github.com/pytest-dev/pytest-cov):** Used to measure test coverage and identify untested parts of the codebase.

## Setup for Testing

To run the tests locally, first set up a development environment.

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/your_username/simsig.git](https://github.com/your_username/simsig.git)
    cd simsig
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install the library in editable mode with development dependencies:**
    This command assumes your development dependencies (like `pytest`) are listed under an `[project.optional-dependencies]` section named `dev` in your `pyproject.toml` file.
    ```bash
    pip install -e ".[dev]"
    ```

## Running the Tests

The test suite is structured with `pytest` markers to allow for running specific categories of tests.

* **Run all tests:**
    ```bash
    pytest
    ```

* **Run tests with verbose output and a coverage report:**
    ```bash
    pytest -v --cov=simsig
    ```

* **Run only the fast unit tests:**
    ```bash
    pytest -m unit
    ```

* **Run only the integration tests:**
    ```bash
    pytest -m integration
    ```

* **Run everything *except* the integration tests:**
    ```bash
    pytest -m "not integration"
    ```

## Test Structure

Our tests are organized into several logical groups using markers:

### Unit Tests (`@pytest.mark.unit`)
These tests are designed to be fast and isolated. They verify a single piece of functionality (e.g., one method of the `SimSig` class) without relying on external systems like the OS clock or process table. Mocks are heavily used here to simulate different conditions and check for correct error handling.

### Integration Tests (`@pytest.mark.integration`)
These tests verify how different parts of the `simsig` module work together and with the underlying operating system. They are generally slower as they may involve:
* Sending real signals with `os.kill()`.
* Using `time.sleep()` to test timing-related features.
* Interacting with the real `asyncio` event loop.

These tests are crucial for ensuring that the library's abstractions hold up in a real-world environment.

### Asynchronous Tests (`@pytest.mark.asyncio`)
This marker, provided by `pytest-asyncio`, identifies tests that are `async def` coroutines. The plugin manages the `asyncio` event loop to run these tests correctly. They specifically target the `async_handler` functionality and its integration with `asyncio`.

### Platform-Specific Tests
Some features of `simsig` (like `with_timeout` or `block_signals`) are only available on UNIX-like systems. The tests for these features are decorated with `@pytest.mark.skipif` to ensure they are automatically skipped when the test suite is run on an unsupported OS like Windows. This allows the test suite to pass everywhere while still providing coverage for platform-specific code.