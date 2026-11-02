"""Strict, unsigned order keyset positions; cursors never grant access."""

import base64
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate cursor member")
        result[key] = value
    return result


@dataclass(frozen=True)
class OrderCursor:
    created_at: datetime
    id: UUID

    def encode(self) -> str:
        data = {
            "v": 1,
            "resource": "orders",
            "created_at": self.created_at.astimezone(UTC)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z"),
            "id": str(self.id),
        }
        return (
            base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode())
            .decode()
            .rstrip("=")
        )

    @classmethod
    def decode(cls, token: str) -> "OrderCursor":
        try:
            if not 1 <= len(token) <= 1024 or not re.fullmatch(r"[A-Za-z0-9_-]+", token):
                raise ValueError()
            raw = base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True)
            if base64.urlsafe_b64encode(raw).decode().rstrip("=") != token:
                raise ValueError()
            data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
            if (
                not isinstance(data, dict)
                or set(data) != {"v", "resource", "created_at", "id"}
                or type(data["v"]) is not int
                or data["v"] != 1
                or data["resource"] != "orders"
                or not isinstance(data["id"], str)
                or str(UUID(data["id"])) != data["id"]
                or UUID(data["id"]).version != 4
                or not isinstance(data["created_at"], str)
                or not re.fullmatch(
                    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z",
                    data["created_at"],
                )
            ):
                raise ValueError()
            return cls(datetime.fromisoformat(data["created_at"]), UUID(data["id"]))
        except (ValueError, TypeError, UnicodeError):
            raise ValueError("Invalid order cursor") from None
