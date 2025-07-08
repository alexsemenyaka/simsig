# Universal Makefile for Python projects
# Automatically detects Python version, project name, and test directory
# Enhanced for simsig with selective test targets, linting, formatting, and documentation validation
# Universal Makefile for Python projects
SHELL := /bin/bash

# Detect Python version (prefer python3 or python@[2|3].[0-9]+, fallback to python)
PYTHON = $(shell \
	PYTHON=""; \
	for path in $$(echo $$PATH | tr ':' '\n'); do \
		if echo $$path | grep -q 'python@[23]\.[0-9]\+/bin$$'; then \
			version=$$(echo $$path | grep -oE '[23]\.[0-9]+'); \
			if command -v python$$version >/dev/null 2>&1; then \
				PYTHON=python$$version; \
				break; \
			fi; \
		fi; \
	done; \
	if [ -z "$$PYTHON" ] && command -v python3 >/dev/null 2>&1; then \
		if python3 -V 2>&1 | grep -q '^Python 3\.  '; then \
			PYTHON=python3; \
		fi; \
	elif [ -z "$$PYTHON" ] && command -v python >/dev/null 2>&1; then \
		if python -V 2>&1 | grep -q '^Python 3\.  '; then \
			PYTHON=python; \
		fi; \
	fi; \
	if [ -z "$$PYTHON" ]; then \
		echo "Error: No suitable Python 3.x found in PATH (try installing via Homebrew: brew install python@3.12)"; \
		exit 1; \
	else \
		echo $$PYTHON; \
	fi)

# Python version check
PYTHON_VERSION := $(shell $(PYTHON) --version | awk '{print $$2}' | cut -d'.' -f1,2)
MIN_PYTHON_VERSION := 3.8

# Detect project name from pyproject.toml or current directory
PROJECT_NAME := $(shell if [ -f pyproject.toml ]; then $(PYTHON) -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['name'])"; else basename $$(pwd); fi)
VERSION := $(shell if [ -f pyproject.toml ]; then $(PYTHON) -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"; else echo "0.1.0"; fi)
WHEEL_FILE := dist/$(PROJECT_NAME)-$(VERSION)-py3-none-any.whl

VENV_DIR := .venv
TEST_DIR := tests
SRC_DIR := $(shell if [ -d src ]; then echo src; elif [ -d $(PROJECT_NAME) ]; then echo $(PROJECT_NAME); else echo .; fi)
EXAMPLES_DIR := examples
DIST_DIR := dist
COVERAGE_DIR := htmlcov

SOURCE_FILES = $(shell find $(SRC_DIR) $(EXAMPLES_DIR) -type f -name "*.py" 2>/dev/null) pyproject.toml README.md LICENSE TESTING.md $(EXAMPLES_DIR)/example1.md

VENV_PYTHON := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip

TESTS_EXIST := $(shell [ -d $(TEST_DIR) ] && find $(TEST_DIR) -name 'test_*.py' | wc -l)

# Colors for output
GREEN := \033[0;32m
RED := \033[0;31m
NC := \033[0m

.PHONY: all
all: check-python venv install lint format test build

.PHONY: help
help:
	@echo "Universal Makefile for Python project: $(PROJECT_NAME) v$(VERSION)"
	@echo ""
	@echo "Available targets:"
	@echo "  all              - Run check-python, venv, install, lint, format, test, and build (default)"
	@echo "  help             - Show this help message"
	@echo "  check-python     - Check Python version (>= $(MIN_PYTHON_VERSION))"
	@echo "  venv             - Create virtual environment"
	@echo "  install          - Install dependencies and project in virtual environment"
	@echo "  devmode          - Install the package in the development mode"
	@echo "  test             - Run all tests with pytest"
	@echo "  test-integration - Run integration tests (requires SSH server on localhost:2222)"
	@echo "  test-unit        - Run unit tests"
	@echo "  test-asyncio     - Run asyncio signal handling tests"
	@echo "  coverage         - Run tests with coverage report"
	@echo "  lint             - Run linting checks (flake8, pylint)"
	@echo "  format           - Run code formatting (black, isort)"
	@echo "  docs             - Validate documentation (README.md, TESTING.md, examples/example1.md)"
	@echo "  build            - Build package"
	@echo "  publish          - Publish package to PyPI"
	@echo "  clean            - Remove temporary files and build artifacts"
	@echo ""
	@echo "Notes:"
	@echo "  - Tests require al least pytest, pytest-asyncio, pytest-mock, pytest-cov"
	@echo "  - Linting uses flake8 and pylint; formatting uses black and isort"
	@echo "  - Documentation validation requires markdownlint (npm install -g markdownlint-cli)"
	@echo "  - View documentation with 'mdcat README.md', 'less README.md', or a Markdown viewer like Visual Studio Code"
	@echo "  - On macOS 15, if integration tests need a network connection, ensure firewall allows the, for Python and SSH"
	@echo ""
	@echo "Examples:"
	@echo "  make all           # Run all checks and build"
	@echo "  make test-unit     # Run unit tests"
	@echo "  make lint          # Run linting checks"
	@echo "  make docs          # Validate documentation"
	@echo "  make publish       # Build and publish to PyPI"

# Check Python version
.PHONY: check-python
check-python:
	@echo -n "Checking Python version (>= $(MIN_PYTHON_VERSION))... "
	@if [ "$$(printf '%s\n%s' '$(PYTHON_VERSION)' '$(MIN_PYTHON_VERSION)' | sort -V | head -n1)" = "$(MIN_PYTHON_VERSION)" ]; then \
		echo -e "$(GREEN)OK$(NC) (Python $(PYTHON_VERSION))"; \
	else \
		echo -e "$(RED)ERROR$(NC) (Python $(PYTHON_VERSION) found, >= $(MIN_PYTHON_VERSION) required)"; \
		exit 1; \
	fi

.PHONY: venv
venv: check-python
	@echo "Creating virtual environment in $(VENV_DIR)..."
	@if [ ! -d $(VENV_DIR) ]; then \
		$(PYTHON) -m venv $(VENV_DIR); \
		$(VENV_PIP) install --upgrade pip; \
		echo -e "$(GREEN)Virtual environment created$(NC)"; \
	else \
		echo "Virtual environment already exists"; \
	fi

.PHONY: install
install: venv
	@echo "Installing dependencies for $(PROJECT_NAME)..."
	@if [ -f requirements.txt ]; then \
		$(VENV_PIP) install -r requirements.txt; \
	else \
		$(VENV_PIP) install -e .; \
	fi
	@$(VENV_PIP) install pytest pytest-asyncio pytest-mock pytest-cov flake8 pylint black isort
	@echo -e "$(GREEN)Dependencies installed$(NC)"

.PHONY: devmode
devmode: venv
	$(VENV_PIP) install -e .

# Run all tests
.PHONY: test
test: install
	@echo "Running all tests for $(PROJECT_NAME) in $(TEST_DIR)..."
	@if [ $(TESTS_EXIST) -gt 0 ]; then \
		$(VENV_PYTHON) -m pytest $(TEST_DIR) -v; \
		echo -e "$(GREEN)Tests completed$(NC)"; \
	else \
		echo -e "$(RED)No tests found in $(TEST_DIR)$(NC)"; \
		exit 1; \
	fi

# Selective test targets
.PHONY: test-integration test-unit test-asyncio
test-unit: install
	@echo "Running corner cases tests for $(PROJECT_NAME)..."
	@if [ -f $(TEST_DIR)/test_simsig.py ]; then \
		$(VENV_PYTHON) -m pytest -m unit $(TEST_DIR)/test_simsig.py -v; \
		echo -e "$(GREEN)Unit tests completed$(NC)"; \
	else \
		echo -e "$(RED)No tests found in $(TEST_DIR)/$(NC)"; \
		exit 1; \
	fi

test-integration: install
	@echo "Running integration tests for $(PROJECT_NAME)..."
	@if [ -f $(TEST_DIR)/test_simsig.py ]; then \
		$(VENV_PYTHON) -m pytest -m integration $(TEST_DIR)/test_simsig.py -v; \
		echo -e "$(GREEN)Integration tests completed$(NC)"; \
	else \
		echo -e "$(RED)No tests found in $(TEST_DIR)/$(NC)"; \
		exit 1; \
	fi

test-asyncio: install
	@echo "Running asyncio tests for $(PROJECT_NAME)..."
	@if [ -f $(TEST_DIR)/test_simsig.py ]; then \
		$(VENV_PYTHON) -m pytest -m asyncio $(TEST_DIR)/test_simsig.py -v; \
		echo -e "$(GREEN)Asyncio tests completed$(NC)"; \
	else \
		echo -e "$(RED)No tests found in $(TEST_DIR)/$(NC)"; \
		exit 1; \
	fi

# Run tests with coverage
.PHONY: coverage
coverage: install
	@echo "Running tests with coverage for $(PROJECT_NAME)..."
	@if [ $(TESTS_EXIST) -gt 0 ]; then \
		$(VENV_PYTHON) -m pytest $(TEST_DIR) -v --cov=$(SRC_DIR) --cov-report=term-missing --cov-report=html; \
		echo -e "$(GREEN)Coverage report generated in $(COVERAGE_DIR)$(NC)"; \
	else \
		echo -e "$(RED)No tests found in $(TEST_DIR)$(NC)"; \
		exit 1; \
	fi

.PHONY: lint
lint: install
	@echo "Running linting checks for $(PROJECT_NAME)..."
	@$(VENV_PIP) install flake8 pylint
	#@flake8 $(SRC_DIR) $(TEST_DIR) $(EXAMPLES_DIR)
	#@pylint $(SRC_DIR) $(TEST_DIR) $(EXAMPLES_DIR)
	@flake8 $(SRC_DIR)
	@pylint $(SRC_DIR)
	@echo -e "$(GREEN)Linting completed$(NC)"

.PHONY: format
format: install
	@echo "Running code formatting for $(PROJECT_NAME)..."
	@$(VENV_PIP) install black isort
	@black $(SRC_DIR) $(TEST_DIR) $(EXAMPLES_DIR)
	@isort $(SRC_DIR) $(TEST_DIR) $(EXAMPLES_DIR)
	@echo -e "$(GREEN)Formatting completed$(NC)"

# Documentation validation
.PHONY: docs
docs: install
	@echo "Validating documentation for $(PROJECT_NAME)..."
	@if command -v markdownlint >/dev/null 2>&1; then \
		markdownlint README.md TESTING.md $(EXAMPLES_DIR)/example1.md; \
	else \
		echo -e "$(RED)markdownlint not installed (install via npm: npm install -g markdownlint-cli)$(NC)"; \
		echo "Skipping documentation validation"; \
		exit 1; \
	fi
	@echo -e "$(GREEN)Documentation validation completed$(NC)"
	@echo "Hint: View documentation with 'mdcat README.md', 'less README.md', or a Markdown viewer like Visual Studio Code"

.PHONY: build
build: install
	@echo "Building $(PROJECT_NAME)-$(VERSION)..."
	@NEEDS_BUILD=0; \
	if [ ! -f "$(WHEEL_FILE)" ]; then \
		NEEDS_BUILD=1; \
	else \
		for src in $(SOURCE_FILES); do \
			if [ "$$src" -nt "$(WHEEL_FILE)" ]; then \
				NEEDS_BUILD=1; \
				break; \
			fi; \
		done; \
	fi; \
	if [ $$NEEDS_BUILD -eq 1 ]; then \
		$(VENV_PYTHON) -m pip install build; \
		$(VENV_PYTHON) -m build > build.log 2>&1; \
		if [ $$? -eq 0 ]; then \
			echo -e "$(GREEN)Built $(WHEEL_FILE)$(NC)"; \
			rm build.log; \
		else \
			echo -e "$(RED)Build failed; see build.log for details$(NC)"; \
			exit 1; \
		fi; \
	else \
		echo "Package $(WHEEL_FILE) is up to date"; \
	fi

# Publish package to PyPI
.PHONY: publish
publish: build
	@echo "Publishing $(PROJECT_NAME)-$(VERSION) to PyPI..."
	@$(VENV_PYTHON) -m pip install twine
	@$(VENV_PYTHON) -m twine upload $(DIST_DIR)/* > publish.log 2>&1; \
	if [ $$? -eq 0 ]; then \
		echo -e "$(GREEN)Package published$(NC)"; \
		rm publish.log; \
	else \
		echo -e "$(RED)Publish failed; see publish.log for details$(NC)"; \
		exit 1; \
	fi

.PHONY: clean
clean:
	@echo "Cleaning temporary files for $(PROJECT_NAME)..."
	@rm -rf $(VENV_DIR) $(DIST_DIR) $(COVERAGE_DIR) .pytest_cache .coverage *.egg-info __pycache__ */__pycache__ */*/__pycache__ build.log publish.log
	@echo -e "$(GREEN)Cleaned$(NC)"
