# Makefile for installing the ai extension

# Extension name
PGAI_EXTENSION := ai

# Find the PostgreSQL extension directory
PG_SHAREDIR := $(shell pg_config --sharedir)
EXTENSION_DIR := $(PG_SHAREDIR)/extension

# Files to be installed
SQL_FILES := $(wildcard $(PGAI_EXTENSION)--*.sql)
CONTROL_FILE := $(PGAI_EXTENSION).control

# Default target
default: help

# Install target
install: install_extension install_python_packages

# Install the extension files
install_extension:
	@cp $(SQL_FILES) $(EXTENSION_DIR)
	@cp $(CONTROL_FILE) $(EXTENSION_DIR)

export PIP_BREAK_SYSTEM_PACKAGES=1

# Install the required Python packages
install_python_packages:
	@pip3 install -r requirements.txt

test: install_extension
	@./test.sh

docker_build:
	@docker build -t pgai .

docker_run:
	@docker run -d --name pgai -p 127.0.0.1:9876:5432 -e POSTGRES_HOST_AUTH_METHOD=trust --mount type=bind,src=$(shell pwd),dst=/pgai pgai

docker_stop:
	@docker stop pgai

docker_rm:
	@docker rm pgai

docker_shell:
	@docker exec -it -u root pgai /bin/bash

# Display help message with available targets
help:
	@echo "Available targets:"
	@echo "  install                  Install the pgai extension and Python dependencies"
	@echo "  install_extension        Install the pgai extension files"
	@echo "  install_python_packages  Install required Python packages"
	@echo "  test                     Runs the unit tests in the database"
	@echo "  docker_build             Builds a Docker image for a development container"
	@echo "  docker_run               Runs a Docker container for development"
	@echo "  docker_stop              Stops the docker container"
	@echo "  docker_rm                Deletes the Docker container"
	@echo "  docker_shell             Gets a shell inside the development Docker container"

.PHONY: default install install_extension install_python_packages test docker_build docker_run docker_delete docker_shell help
