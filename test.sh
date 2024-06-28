#!/usr/bin/env bash
set -e

# if a .env file exists, load and export the variables in it
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

if [ -z "$ENABLE_OPENAI_TESTS" ]; then
  export ENABLE_OPENAI_TESTS=0
fi

if [ "$ENABLE_OPENAI_TESTS" ] && [ -z "$OPENAI_API_KEY" ]; then
  echo "OPENAI_API_KEY must be set if running OpenAI tests"
  exit 3
fi

if [ -z "$ENABLE_OLLAMA_TESTS" ]; then
  export ENABLE_OLLAMA_TESTS=0
fi

if [ -z "$ENABLE_ANTHROPIC_TESTS" ]; then
  export ENABLE_ANTHROPIC_TESTS=0
fi

if [ "$ENABLE_ANTHROPIC_TESTS" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "ANTHROPIC_API_KEY must be set if running Anthropic tests"
  exit 3
fi

if [ -z "$ENABLE_COHERE_TESTS" ]; then
  export ENABLE_COHERE_TESTS=0
fi

if [ "$ENABLE_COHERE_TESTS" ] && [ -z "$COHERE_API_KEY" ]; then
  echo "COHERE_API_KEY must be set if running Cohere tests"
  exit 3
fi

psql -d postgres -f test.sql