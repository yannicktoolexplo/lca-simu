"""Manual database connectivity check.

This filename is retained for compatibility, but importing it is deliberately
side-effect free so repository-wide test discovery never opens a network
connection.  Supply the connection URL at execution time instead of storing
credentials in source control.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    database_url = os.environ.get("LCA_SIMU_DATABASE_URL", "").strip()
    if not database_url:
        print("LCA_SIMU_DATABASE_URL is required.", file=sys.stderr)
        return 2
    try:
        from sqlalchemy import create_engine
    except ImportError:
        print(
            "SQLAlchemy is required for this manual connectivity check.",
            file=sys.stderr,
        )
        return 2

    engine = create_engine(database_url)
    try:
        with engine.connect():
            print("Database connection succeeded.")
    except Exception as exc:
        print(f"Database connection failed: {exc}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
