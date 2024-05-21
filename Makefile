# Makefile for installing the ai extension

# Extension name
PGAI_EXTENSION := ai

USER := postgres
DB := postgres

# Find the PostgreSQL extension directory
PG_SHAREDIR := $(shell pg_config --sharedir)
EXTENSION_DIR := $(PG_SHAREDIR)/extension

# Files to be installed
SQL_FILES := $(wildcard *.sql)
CONTROL_FILE := $(wildcard *.control)

# Python packages required
PYTHON_PACKAGES := openai tiktoken

# pgvector repository URL and default tag
PGVECTOR_REPO := https://github.com/pgvector/pgvector.git
PGVECTOR_TAG := v0.7.0

# Install target
install: install_extension install_python_packages install_pgvector

# Install the extension files
install_extension:
	@echo "Installing $(PGAI_EXTENSION) extension files to $(EXTENSION_DIR)"
	@mkdir -p $(EXTENSION_DIR)
	@cp $(SQL_FILES) $(EXTENSION_DIR)
	@cp $(CONTROL_FILE) $(EXTENSION_DIR)
	@echo "$(PGAI_EXTENSION) extension files installation complete."

# Install the required Python packages
install_python_packages:
	@echo "Installing required Python packages: $(PYTHON_PACKAGES)"
	@pip3 install --break-system-packages $(PYTHON_PACKAGES)
	@echo "Python packages installation complete."

# Install the pgvector extension
install_pgvector:
	@echo "Installing pgvector extension"
	@if [ ! -d "pgvector" ]; then \
		git clone $(PGVECTOR_REPO); \
	fi
	@cd pgvector && git checkout $(PGVECTOR_TAG) && make clean && make && make install
	@echo "pgvector installation complete."

# Create the pgai extension
create_extension:
	@echo "Creating $(PGAI_EXTENSION) extension in the database"
	@psql -U $(USER) -d $(DB) -c "CREATE EXTENSION IF NOT EXISTS $(PGAI_EXTENSION) CASCADE;"
	@echo "$(PGAI_EXTENSION) extension creation complete."

.PHONY: install install_extension install_python_packages install_pgvector create_extension
