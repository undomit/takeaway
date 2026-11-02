"""Password hashing and signed access tokens, independent of HTTP and persistence."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.errors import NotAuthenticated

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hash.verify(password, password_hash)
    except (UnknownHashError, ValueError):
        return False


@lru_cache(maxsize=1)
def dummy_password_hash() -> str:
    return hash_password("dummy-password-not-an-account")


def utc_now() -> datetime:
    return datetime.now(UTC)


def create_access_token(user_id: int, token_version: int, lifetime: timedelta, secret: str) -> str:
    issued_at = int(utc_now().timestamp())
    return jwt.encode(
        {
            "sub": str(user_id),
            "ver": token_version,
            "iat": issued_at,
            "exp": issued_at + int(lifetime.total_seconds()),
        },
        secret,
        algorithm="HS256",
    )


@dataclass(frozen=True)
class TokenIdentity:
    user_id: int
    token_version: int


def decode_access_token(token: str, secret: str) -> TokenIdentity:
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": ["sub", "ver", "iat", "exp"]},
        )
        subject = claims["sub"]
        if (
            not isinstance(subject, str)
            or not 1 <= len(subject) <= 19
            or not subject.isascii()
            or not subject.isdecimal()
            or subject.startswith("0")
            or not 1 <= int(subject) <= 9223372036854775807
            or type(claims["ver"]) is not int
            or not 0 <= claims["ver"] <= 2147483647
            or type(claims["iat"]) is not int
            or type(claims["exp"]) is not int
            or not 0 <= claims["iat"] < claims["exp"]
        ):
            raise NotAuthenticated()
        return TokenIdentity(int(subject), claims["ver"])
    except jwt.InvalidTokenError:
        raise NotAuthenticated() from None
