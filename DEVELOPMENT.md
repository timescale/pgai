# Contributing to pgai

Welcome to the pgai project! This guide will help you get started with contributing to pgai, a project that brings embedding and generation AI models closer to your PostgreSQL database.

## Project overview

pgai is organized as a monorepo containing two main components:

1. **PostgreSQL extension**: Located in [projects/extension](./projects/extension)
   - Implements the core functionality for AI operations within your database
   - Written in Python and PL/PgSQL
   - Development guidelines are available in the [extension directory](./projects/extension/DEVELOPMENT.md)

2. **Python Library**: Located in [projects/pgai](./projects/pgai)
   - Available on [PyPI][pgai-pypi]
   - Provides a high-level interface for interacting with the [vectorizer worker](docs/vectorizer/worker.md), and additionally integrations such as the [SQLAlchemy](/docs/vectorizer/python-integration.md) one.
   - Written in Python
   - Development guidelines are available in the [pgai directory](./projects/pgai/DEVELOPMENT.md)

## Development prerequisites

Before you begin, ensure you have the following installed:

1. [Just][just-gh] - Our task runner for project commands
   - Available in most package managers
   - See installation instructions in the [Just documentation][just-docs]

2. [UV][uv-website] - Fast Python package installer and resolver 
   - Required for Python dependency management
   - Faster and more reliable than pip
   - See installation instructions in the [UV documentation][uv-docs]

## Contribution guidelines

### Commit standards

We follow the [Conventional Commits][conventional-commits] specification for all commits. This standardization helps us:

- Automate release processes
- Generate changelogs
- Maintain clear commit history
- Enforce consistent messaging

Examples of valid commit messages:
```
feat: add vector similarity search
fix: resolve null pointer in embedding generation
docs: update installation instructions
test: add integration tests for OpenAI embedder
```

### Setting up commit hooks

To ensure your commits meet our standards before pushing:

1. Install the local commit hook:
   ```bash
   just install-commit-hook
   ```

2. The hook will automatically check your commit messages
   - Prevents non-compliant commits locally
   - Saves time waiting for CI feedback
   - Provides immediate validation

### Pull Request process

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Ensure commits follow conventional commit format
5. Submit PR with clear description of changes
6. Wait for CI validation and review

The CI pipeline will check:
- Commit message format
- Code style
- Tests
- Build process

## Getting help

- Check existing documentation in [docs](docs) directory
- Open an issue for bugs, feature requests, or any other questions
- Join our community discussions in our [Discord server][discord-server]
- Review closed PRs for examples

Remember to always pull the latest changes before starting new work.

[pgai-pypi]: https://pypi.org/project/pgai
[conventional-commits]: https://www.conventionalcommits.org/en/v1.0.0
[discord-server]: https://discord.gg/KRdHVXAmkp
[just-gh]: https://github.com/casey/just
[just-docs]: https://github.com/casey/just?tab=readme-ov-file#installation
[uv-website]: https://uv.astral.sh
[uv-docs]: https://docs.astral.sh/uv/getting-started/installation