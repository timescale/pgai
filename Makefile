PG_MAJOR?=16
PG_BIN?="/usr/lib/postgresql/$(PG_MAJOR)/bin"

.PHONY: default
default: help

.PHONY: help
help:
	@./build.py help
	@echo "- docker-shell      launches a bash shell in the container"
	@echo "- docker-psql       launches a psql shell in the container"

.PHONY: clean
clean:
	@./build.py clean

.PHONY: clean-sql
clean-sql:
	@./build.py clean-sql

.PHONY: clean-py
clean-py:
	@./build.py clean-py

.PHONY: clean-vectorizer
clean-vectorizer:
	@./build.py clean-vectorizer

.PHONY: build
build:
	@PG_BIN=$(PG_BIN) ./build.py build

.PHONY: install
install:
	@PG_BIN=$(PG_BIN) ./build.py install

.PHONY: build-install
build-install:
	@PG_BIN=$(PG_BIN) ./build.py build-install

.PHONY: install-sql
install-sql:
	@PG_BIN=$(PG_BIN) ./build.py install-sql

.PHONY: install-prior-py
install-prior-py:
	@./build.py install-prior-py

.PHONY: install-py
install-py:
	@./build.py install-py

.PHONY: install-vectorizer
install-vectorizer:
	@./build.py install-vectorizer

.PHONY: uninstall
uninstall:
	@PG_BIN=$(PG_BIN) ./build.py uninstall

.PHONY: uninstall-sql
uninstall-sql:
	@PG_BIN=$(PG_BIN) ./build.py uninstall-sql

.PHONY: uninstall-py
uninstall-py:
	@./build.py uninstall-py

.PHONY: uninstall-vectorizer
uninstall-vectorizer:
	@./build.py uninstall-vectorizer

.PHONY: build-sql
build-sql:
	@./build.py build-sql

.PHONY: test-server
test-server:
	@./build.py test-server

.PHONY: vectorizer
vectorizer:
	@./build.py vectorizer

.PHONY: test
test:
	@./build.py test

.PHONY: lint-sql
lint-sql:
	@./build.py lint-sql

.PHONY: lint-py
lint-py:
	@./build.py lint-py

.PHONY: lint
lint:
	@./build.py lint

.PHONY: format-py
format-py:
	@./build.py format-py

.PHONY: docker-build
docker-build:
	@PG_MAJOR=$(PG_MAJOR) ./build.py docker-build

.PHONY: docker-build-vectorizer
docker-build-vectorizer:
	@./build.py docker-build-vectorizer

.PHONY: docker-run
docker-run:
	@./build.py docker-run

.PHONY: docker-run-vectorizer
docker-run-vectorizer:
	@./build.py docker-run-vectorizer

.PHONY: docker-stop
docker-stop:
	@./build.py docker-stop

.PHONY: docker-stop-vectorizer
docker-stop-vectorizer:
	@./build.py docker-stop-vectorizer

.PHONY: docker-rm
docker-rm:
	@./build.py docker-rm

.PHONY: docker-rm-vectorizer
docker-rm-vectorizer:
	@./build.py docker-rm-vectorizer

.PHONY: run
run:
	@PG_MAJOR=$(PG_MAJOR) PG_BIN=$(PG_BIN) ./build.py run
	@docker exec -it -u postgres pgai /bin/bash -c "set -e; if [ -f .env ]; then set -a; source .env; set +a; fi; psql"

.PHONY: docker-shell
docker-shell:
	@docker exec -it -u root pgai /bin/bash

.PHONY: psql-shell
psql-shell:
	@docker exec -it -u postgres pgai /bin/bash -c "set -e; if [ -f .env ]; then set -a; source .env; set +a; fi; psql"

