"""
Krakken AI application entry point.

This module is responsible only for starting
the application bootstrap process.
"""

from __future__ import annotations

import sys

from app.bootstrap import ApplicationBootstrap


def main() -> int:
    """Start Kraken AI."""

    bootstrap = ApplicationBootstrap()

    return bootstrap.run()


if __name__ == "__main__":
    sys.exit(main())