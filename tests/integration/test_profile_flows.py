"""Deferred task 006 coverage for atomic saved-address replacement and clearing."""

import pytest
from sqlalchemy import select

from app.users.models import User
from tests.order_support import ADDRESS, PASSWORD, auth, error, ok

pytestmark = pytest.mark.integration


def test_saved_address_replacement_is_atomic_and_clear_removes_all_contact_fields(
    client, db_session
):
    account = ok(
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "profile@example.test",
                "full_name": "Original Customer",
                "password": PASSWORD,
            },
        ),
        201,
    )
    headers = auth(client, account["email"])
    original_address = ADDRESS | {"address_line2": "Apartment 4"}
    original = ok(
        client.patch("/api/v1/me", headers=headers, json={"saved_address": original_address})
    )
    # A partial address is a replacement attempt, never a merge with saved fields.
    for invalid in (
        {"address_line1": "Incomplete replacement"},
        ADDRESS | {"phone": "   "},
    ):
        error(
            client.patch(
                "/api/v1/me",
                headers=headers,
                json={"full_name": "Must not persist", "saved_address": invalid},
            ),
            422,
        )
        assert ok(client.get("/api/v1/me", headers=headers)) == original

    # Omitting the address preserves it; replacing it clears an omitted line 2.
    renamed = ok(
        client.patch("/api/v1/me", headers=headers, json={"full_name": "  Updated Customer  "})
    )
    assert renamed["full_name"] == "Updated Customer"
    assert renamed["saved_address"] == original_address
    replacement = {
        "address_line1": "  20 Replacement Street  ",
        "postcode": "  CD2  ",
        "phone": "  +449999  ",
    }
    updated = ok(client.patch("/api/v1/me", headers=headers, json={"saved_address": replacement}))
    assert updated["full_name"] == renamed["full_name"]
    assert updated["saved_address"] == {
        **{field: value.strip() for field, value in replacement.items()},
        "address_line2": None,
    }
    assert ok(client.get("/api/v1/me", headers=headers)) == updated

    cleared = ok(client.patch("/api/v1/me", headers=headers, json={"saved_address": None}))
    assert cleared == updated | {"saved_address": None}
    assert ok(client.get("/api/v1/me", headers=headers)) == cleared
    # Verify clearing does not merely hide old contact data in the response schema.
    stored = db_session.execute(
        select(User.address_line1, User.address_line2, User.postcode, User.phone).where(
            User.id == account["id"]
        )
    ).one()
    assert tuple(stored) == (None, None, None, None)
