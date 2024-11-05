VERSION := $(shell awk "/^__version__ = .*/ {gsub(/__version__ = |\"/, \"\"); print}" ./pgai/__init__.py)

.PHONY: default
default: help

.PHONY: help
help:
	@echo "pgai makefile commands:"
	@echo
	@echo "Development commands:"
	@echo "  help              Show this help message"
	@echo "  show-version     Display the current pgai version"
	@echo "  clean            Remove build artifacts and temporary files"
	@echo "  build            Build source distribution and wheel package"
	@echo "  install          Install the wheel package locally"
	@echo "  uninstall        Remove the installed pgai package"
	@echo
	@echo "Testing and quality:"
	@echo "  test             Run pytest test suite"
	@echo "  lint             Run ruff linter checks"
	@echo "  type-check       Run pyright type checking"
	@echo "  format           Show code formatting differences"
	@echo
	@echo "Docker commands:"
	@echo "  docker-build     Build Docker image with version tag"
	@echo "  docker-run       Run the Docker container in detached mode"
	@echo "  docker-stop      Stop the running Docker container"
	@echo "  docker-rm        Remove the Docker container and its volumes"
	@echo
	@echo "Git hooks:"
	@echo "  install-commit-hook  Install semantic commit message hook"

.PHONY: show-version
show-version:
	@echo "pgai version is: $(VERSION)"

.PHONY: clean
clean:
	@rm -rf ./build
	@rm -rf ./pgai.egg-info
	@rm -rf ./dist
	@rm -rf ./.ruff_cache
	@rm -rf ./.pytest_cache
	@rm -rf ./.mypy_cache
	@find . -type d -name "__pycache__" -exec rm -rf {} +

.PHONY: build
build:
	@uv build
	@uv run twine check ./dist/*

.PHONY: install
install:
	@uv sync

.PHONY: uninstall
uninstall:
	@uv pip uninstall -y pgai

.PHONY: test
test:
	@uv run pytest

.PHONY: lint
lint:
	@uv run ruff check ./

.PHONY: type-check
type-check:
	@uv run pyright ./

.PHONY: format
format:
	@uv run ruff format --diff ./

.PHONY: docker-build
docker-build:
	@docker build -t pgai-cli:latest -t "pgai-cli:$(VERSION)" .

.PHONY: docker-run
docker-run:
	@docker run -d --name pgai-cli "pgai-cli:$(VERSION)"

.PHONY: docker-stop
docker-stop:
	@docker stop pgai-cli

.PHONY: docker-rm
docker-rm:
	@docker rm --force --volumes pgai-cli

.PHONY: install-commit-hook
install-commit-hook:
	@cd ../.. && curl --fail -o .git/hooks/commit-msg https://raw.githubusercontent.com/hazcod/semantic-commit-hook/master/commit-msg \
  && chmod 500 .git/hooks/commit-msg