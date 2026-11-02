"""Bootstrap an admin: python -m app.cli create-admin."""

import argparse
import getpass
import sys
import warnings
from collections.abc import Sequence

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app import models  # noqa: F401 - register complete FK metadata
from app.core.config import get_settings
from app.core.db import Database
from app.users import service as users
from app.users.errors import EmailInUse
from app.users.schemas import AccountCreateIn


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Takeaway account bootstrap")
    subcommands = parser.add_subparsers(dest="command", required=True)
    command = subcommands.add_parser("create-admin", help="Create a platform admin")
    command.add_argument("--email")
    command.add_argument("--full-name")
    arguments = parser.parse_args(argv)
    database = None
    try:
        settings = get_settings()
        email = arguments.email if arguments.email is not None else input("Email: ")
        name = arguments.full_name if arguments.full_name is not None else input("Full name: ")
        with warnings.catch_warnings():
            # Refuse getpass's visible-input fallback when no secure terminal exists.
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("Password: ")
            confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            print("Passwords do not match.", file=sys.stderr)
            return 1
        account = AccountCreateIn(email=email, full_name=name, password=password)
        database = Database(settings)
        with database.session_factory() as session:
            admin = users.create_admin(session, account)
        print(f"Admin account created (id {admin.id}).")
        return 0
    except EmailInUse:
        print("Email is already in use; no account was changed.", file=sys.stderr)
    except ValidationError:
        print(
            "Invalid configuration or account details. "
            "Check settings, email, name and password length.",
            file=sys.stderr,
        )
    except getpass.GetPassWarning:
        print("A secure terminal is required for password input.", file=sys.stderr)
    except (EOFError, KeyboardInterrupt):
        print("Admin creation cancelled.", file=sys.stderr)
    except SQLAlchemyError:
        print("Database operation failed. Check configuration and migrations.", file=sys.stderr)
    finally:
        if database is not None:
            database.dispose()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
