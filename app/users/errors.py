"""Named account-domain failures."""

from app.errors import Conflict


class EmailInUse(Conflict):
    code = "email_in_use"
    detail = "Email is already in use"
