"""Read-only authenticated identity contract; contains no persistence operations."""

from typing import Protocol

from app.users.roles import Role


class Principal(Protocol):
    @property
    def id(self) -> int: ...

    @property
    def role(self) -> Role: ...

    @property
    def restaurant_id(self) -> int | None: ...

    @property
    def token_version(self) -> int: ...

    @property
    def is_active(self) -> bool: ...
