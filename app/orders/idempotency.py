"""Pure UUID-v4 key parsing and hashing of validated submitted intent."""

import hashlib
import json
import re
from collections.abc import Sequence
from uuid import RFC_4122, UUID

from app.orders.errors import IdempotencyKeyRequired
from app.orders.schemas import OrderCreateIn


def parse_idempotency_key(values: Sequence[str] | None) -> UUID:
    if values is None:
        raise IdempotencyKeyRequired()
    if isinstance(values, (str, bytes)) or len(values) != 1:
        raise ValueError("Supply exactly one Idempotency-Key UUID v4 header")
    value = values[0]
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value
    ):
        raise ValueError("Idempotency-Key must be a hyphenated UUID v4")
    key = UUID(value)
    if key.variant != RFC_4122 or key.version != 4:
        raise ValueError("Idempotency-Key must be an RFC 4122 UUID v4")
    return key


def canonical_request_bytes(request: OrderCreateIn) -> bytes:
    """Expand defaults and preserve line order before resolving any mutable data."""
    return json.dumps(
        request.model_dump(mode="json"),
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def request_hash(request: OrderCreateIn) -> str:
    return hashlib.sha256(canonical_request_bytes(request)).hexdigest()
