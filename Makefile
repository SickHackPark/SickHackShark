.PHONY: all format lint docker_tests help docker_build docker_run docker_down docker_logs

# Default target executed when no arguments are given to make.
all: help

######################
# LINTING AND FORMATTING
######################

# Define a variable for Python and notebook files.
PYTHON_FILES=src/
MYPY_CACHE=.mypy_cache
lint format: PYTHON_FILES=.
lint_diff format_diff: PYTHON_FILES=$(shell git diff --name-only --diff-filter=d main | grep -E '\.py$$|\.ipynb$$')
lint_package: PYTHON_FILES=src
lint_tests: PYTHON_FILES=tests
lint_tests: MYPY_CACHE=.mypy_cache_test

lint lint_diff lint_package lint_tests:
	python -m ruff check .
	[ "$(PYTHON_FILES)" = "" ] || python -m ruff format $(PYTHON_FILES) --diff
	[ "$(PYTHON_FILES)" = "" ] || python -m ruff check --select I $(PYTHON_FILES)
	[ "$(PYTHON_FILES)" = "" ] || python -m mypy --strict $(PYTHON_FILES)
	[ "$(PYTHON_FILES)" = "" ] || mkdir -p $(MYPY_CACHE) && python -m mypy --strict $(PYTHON_FILES) --cache-dir $(MYPY_CACHE)

format format_diff:
	ruff format $(PYTHON_FILES)
	ruff check --select I --fix $(PYTHON_FILES)

spell_check:
	codespell --toml pyproject.toml

spell_fix:
	codespell --toml pyproject.toml -w

######################
# HELP
######################

help:
	@echo '----'
	@echo 'format                       - run code formatters'
	@echo 'lint                         - run linters'
	@echo 'build                        - build docker images (uses docker-compose or docker compose)'
	@echo 'run                          - run docker containers (uses docker-compose or docker compose)'
	@echo 'down                         - stop and remove docker containers (uses docker-compose or docker compose)'
	@echo 'logs                         - show docker container logs (uses docker-compose or docker compose)'

######################
# DOCKER
######################

# Check if docker compose or docker-compose is available
DOCKER_COMPOSE := $(shell which docker-compose 2>/dev/null)
ifeq ($(DOCKER_COMPOSE),)
	DOCKER_COMPOSE_CMD := docker compose
else
	DOCKER_COMPOSE_CMD := docker-compose
endif

build:
	$(DOCKER_COMPOSE_CMD) build

run:
	@if [ ! -d "knowledge_base/PayloadsAllTheThings" ]; then \
		echo "Cloning PayloadsAllTheThings repository..."; \
		git clone https://github.com/swisskyrepo/PayloadsAllTheThings knowledge_base/PayloadsAllTheThings; \
	fi
	@if [ ! -d "knowledge_base/HowToHunt" ]; then \
		echo "Cloning HowToHunt repository..."; \
		git clone https://github.com/KathanP19/HowToHunt knowledge_base/HowToHunt; \
	fi
	$(DOCKER_COMPOSE_CMD) up

down:
	$(DOCKER_COMPOSE_CMD) down

logs:
	$(DOCKER_COMPOSE_CMD) logs -f
