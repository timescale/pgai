# pgai extension

# find the PostgreSQL extension directory
PG_SHAREDIR := $(shell pg_config --sharedir)
EXTENSION_DIR := $(PG_SHAREDIR)/extension

SQL_FILES := $(wildcard ai--*.sql)

# install target
.PHONY: install
install:
	@echo "Installing pgai extension files to $(EXTENSION_DIR)"
	@cp $(SQL_FILES) $(EXTENSION_DIR)
	@cp ai.control $(EXTENSION_DIR)
	@echo "Installation complete."


