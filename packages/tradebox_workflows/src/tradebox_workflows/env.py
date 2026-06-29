"""Environment helpers for local script entrypoints."""

from __future__ import annotations


def load_local_env_file() -> None:
    """Load the repository .env file when python-dotenv is installed."""

    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return

    load_dotenv()
