"""Creates the first account, since only an admin can create accounts through the API.

    python -m kaizen.cli create-user admin --role admin

Asks for the password, so it never ends up in shell history.
"""

from __future__ import annotations

import argparse
import getpass

from sqlalchemy import select

from kaizen.api.auth import hash_password
from kaizen.db import Role, User, make_engine, make_sessionmaker
from kaizen.units import is_known_unit


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m kaizen.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-user")
    create.add_argument("username")
    create.add_argument("--role", choices=[r.value for r in Role], required=True)
    create.add_argument("--unit", help="required for managers")
    args = parser.parse_args()

    if args.role == Role.MANAGER.value and not (args.unit and is_known_unit(args.unit)):
        parser.error("a manager needs --unit with a code from the unit list")
    password = getpass.getpass("Password (at least 10 characters): ")
    if len(password) < 10:
        parser.error("password is too short")

    Session = make_sessionmaker(make_engine())
    with Session() as session:
        if session.scalar(select(User).where(User.username == args.username)):
            parser.error("username is taken")
        session.add(
            User(
                username=args.username,
                password_hash=hash_password(password),
                role=Role(args.role),
                unit=args.unit.upper() if args.unit else None,
            )
        )
        session.commit()
    print(f"created {args.role} account {args.username}")


if __name__ == "__main__":
    main()
