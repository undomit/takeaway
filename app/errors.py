"""Business failures; HTTP response policy belongs to the transport layer."""


class DomainError(Exception):
    code = "domain_error"
    detail = "The operation could not be completed"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = self.detail if detail is None else detail
        super().__init__(self.detail)


class NotAuthenticated(DomainError):
    code = "not_authenticated"
    detail = "Authentication required"


class InvalidCredentials(NotAuthenticated):
    code = "invalid_credentials"
    detail = "Invalid credentials"


class Forbidden(DomainError):
    code = "forbidden"
    detail = "Operation not permitted"


class NotFound(DomainError):
    code = "not_found"
    detail = "Resource not found"


class BadRequest(DomainError):
    """Base for named business failures mapped to a bad request."""


class Conflict(DomainError):
    """Base for named business conflicts, such as status_conflict."""


class RuleViolation(DomainError):
    """Base for named semantic failures, such as reason_required."""


class TemporarilyUnavailable(DomainError):
    """Base for named temporary service failures."""
