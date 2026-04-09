# Contributing to ADKBot

First off, thank you for considering contributing to ADKBot! It's people like you that make ADKBot such a great tool.

ADKBot is built to be a fast, modern, and Google ADK-native AI agent platform. We aim to stay light, reduce dependencies, and maximize capability.

## How Can I Contribute?

### Reporting Bugs
If you find a bug, please create an issue on [GitHub](https://github.com/nwokike/ADKbot/issues). Be sure to include:
* Your operating system.
* Your Python version (we target Python 3.13+).
* Steps to reproduce the bug.

### Suggesting Enhancements
Enhancement suggestions are tracked as GitHub issues. When creating an enhancement issue, please explain exactly what you want the feature to do and why it would be beneficial to the broader ADKBot ecosystem.

### Submitting Pull Requests
1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. Ensure the test suite passes (`pytest tests/`).
4. Make sure your code lints correctly.
5. Create a descriptive pull request. 

## Development Setup

We use `uv` for lightning-fast project management, but standard `pip` works perfectly well too.

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/ADKbot.git
cd ADKbot

# Create a virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Run tests
pytest
```

## Community

If you want to discuss changes before writing code, or just want to chat about the future of ADKBot, feel free to reach out to the project lead at **onyeka@kiri.ng**.

Happy coding!
