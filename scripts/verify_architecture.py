"""Prove both architecture guards reject a temporary forbidden import, then restore."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / "app/restaurants/service.py"
    original = path.read_bytes()
    try:
        with path.open("ab") as stream:
            stream.write(b"\nfrom app.orders.repository import get_by_id  # forbidden probe\n")
        for command in (
            [sys.executable, "scripts/check_architecture.py"],
            ["lint-imports", "--no-cache"],
        ):
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            if result.returncode != 1:
                raise AssertionError(f"Guard did not reject probe: {command}\n{result.stdout}")
            print(f"PASS: forbidden import rejected by {command[-1]}")
    finally:
        path.write_bytes(original)


if __name__ == "__main__":
    main()
