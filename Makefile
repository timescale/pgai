
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

.PHONY: install
install:
	@./build.py install

.PHONY: install-sql
install-sql:
	@./build.py install-sql

.PHONY: install-prior-py
install-prior-py:
	@./build.py install-prior-py

.PHONY: install-py
install-py:
	@./build.py install-py

.PHONY: uninstall
uninstall:
	@./build.py uninstall

.PHONY: uninstall-sql
uninstall-sql:
	@./build.py uninstall-sql

.PHONY: uninstall-py
uninstall-py:
	@./build.py uninstall-py

.PHONY: build-sql
build-sql:
	@./build.py build-sql

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
	@./build.py docker-build

.PHONY: docker-run
docker-run:
	@./build.py docker-run

.PHONY: docker-stop
docker-stop:
	@./build.py docker-stop

.PHONY: docker-rm
docker-rm:
	@./build.py docker-rm

.PHONY: docker-shell
docker-shell:
	@docker exec -it -u root pgai /bin/bash

.PHONY: psql-shell
psql-shell:
	@docker exec -it -u postgres pgai /bin/bash -c "set -e; if [ -f .env ]; then set -a; source .env; set +a; fi; psql"

