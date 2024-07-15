
.PHONY: default
default: help

.PHONY: help
help:
	@./make.py help
	@echo "- docker-shell      launches a bash shell in the container"
	@echo "- docker-psql       launches a psql shell in the container"

.PHONY: clean
clean:
	@./make.py clean

.PHONY: clean-sql
clean-sql:
	@./make.py clean-sql

.PHONY: clean-py
clean-py:
	@./make.py clean-py

.PHONY: install
install:
	@./make.py install

.PHONY: install-sql
install-sql:
	@./make.py install-sql

.PHONY: install-prior-py
install-prior-py:
	@./make.py install-prior-py

.PHONY: install-py
install-py:
	@./make.py install-py

.PHONY: uninstall
uninstall:
	@./make.py uninstall

.PHONY: uninstall-sql
uninstall-sql:
	@./make.py uninstall-sql

.PHONY: uninstall-py
uninstall-py:
	@./make.py uninstall-py

.PHONY: build-sql
build-sql:
	@./make.py build-sql

.PHONY: test
test:
	@./make.py test

.PHONY: docker-build
docker-build:
	@./make.py docker-build

.PHONY: docker-run
docker-run:
	@./make.py docker-run

.PHONY: docker-stop
docker-stop:
	@./make.py docker-stop

.PHONY: docker-rm
docker-rm:
	@./make.py docker-rm

.PHONY: docker-shell
docker-shell:
	@docker exec -it -u root pgai /bin/bash

.PHONY: psql-shell
psql-shell:
	@docker exec -it -u postgres pgai /bin/bash -c "set -e; if [ -f .env ]; then set -a; source .env; set +a; fi; psql"

