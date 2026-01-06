# Contributing to StreamWeaver

Thank you for your interest in contributing to StreamWeaver! We welcome contributions from the community.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- A GitHub account

### Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/your-username/streamweaver.git
   cd streamweaver
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Run tests to verify setup**
   ```bash
   pytest
   ```

## Code Style

We use the following tools to maintain code quality:

- **Black** for code formatting
- **Ruff** for linting
- **MyPy** for type checking

### Running Linters

```bash
# Format code
black streamweaver tests examples

# Run linter
ruff check streamweaver tests examples

# Run type checker
mypy streamweaver
```

### Pre-commit Hooks (Optional)

To automatically run these tools before committing:

```bash
pip install pre-commit
pre-commit install
```

## Testing

We use pytest for testing.

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=streamweaver --cov-report=html

# Run specific test file
pytest tests/test_events.py

# Run specific test
pytest tests/test_events.py::test_stream_event_creation
```

## Making Changes

### Workflow

1. Create a new branch for your feature/fix
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-fix-name
   ```

2. Make your changes following our code style

3. Add/update tests for your changes

4. Run tests and linters to ensure everything passes

5. Commit your changes
   ```bash
   git add .
   git commit -m "feat: add new feature"  # or "fix: fix bug"
   ```

   We use [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation changes
   - `refactor:` for refactoring
   - `test:` for test changes
   - `chore:` for maintenance tasks

6. Push to your fork
   ```bash
   git push origin feature/your-feature-name
   ```

7. Create a pull request on GitHub

### Pull Request Guidelines

- Title should follow conventional commits format
- Description should explain:
  - What this PR does
  - Why it's needed
  - How you tested it
- Include screenshots for UI changes
- Reference related issues
- Ensure CI checks pass

## Documentation

We value documentation! When making changes:

- Add docstrings to new functions and classes
- Update README.md if you're changing user-facing behavior
- Add examples for new features
- Keep the CHANGELOG.md updated

## Feature Requests

If you have an idea for a new feature:

1. Check existing [GitHub Issues](https://github.com/AbdalrahmanWael/StreamWeaver/issues) to avoid duplicates
2. Open a new issue with the "enhancement" label
3. Describe the feature, use case, and proposed implementation
4. We'll discuss and plan it together

## Bug Reports

When reporting bugs:

1. Include:
   - Python version
   - StreamWeaver version
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Error messages/tracebacks
2. Use the "bug" label

## Questions?

Feel free to:
- Open a GitHub issue
- Start a GitHub discussion
- Contact maintainers

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

Thank you for contributing! 🚀
