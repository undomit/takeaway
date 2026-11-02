"""Quiet container probe; readiness by default, optional process-only liveness."""

import argparse
import json
from urllib.error import URLError
from urllib.request import urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--liveness", action="store_true")
    args = parser.parse_args()
    path, expected = ("healthz", "ok") if args.liveness else ("readyz", "ready")
    try:
        with urlopen(f"http://127.0.0.1:8000/{path}", timeout=4) as response:
            return (
                0 if response.status == 200 and json.load(response) == {"status": expected} else 1
            )
    except (URLError, OSError, ValueError):
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
