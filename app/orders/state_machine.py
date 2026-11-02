"""Pure order status rules. Resource visibility must be checked by the caller."""

from dataclasses import dataclass
from types import MappingProxyType

from app.orders.errors import InvalidTransition, ReasonRequired, TransitionNotPermitted
from app.orders.status import Status
from app.users.roles import Role


@dataclass(frozen=True)
class Rule:
    roles: frozenset[Role]
    reason_required: bool = False


TRANSITIONS = MappingProxyType(
    {
        (Status.PENDING, Status.ACCEPTED): Rule(frozenset({Role.STAFF})),
        (Status.PENDING, Status.REJECTED): Rule(frozenset({Role.STAFF}), reason_required=True),
        (Status.PENDING, Status.CANCELLED): Rule(frozenset({Role.CUSTOMER})),
        (Status.ACCEPTED, Status.PREPARING): Rule(frozenset({Role.STAFF})),
        (Status.ACCEPTED, Status.CANCELLED): Rule(frozenset({Role.STAFF}), reason_required=True),
        (Status.PREPARING, Status.OUT_FOR_DELIVERY): Rule(frozenset({Role.STAFF})),
        (Status.PREPARING, Status.CANCELLED): Rule(frozenset({Role.STAFF}), reason_required=True),
        (Status.OUT_FOR_DELIVERY, Status.DELIVERED): Rule(frozenset({Role.STAFF})),
    }
)


@dataclass(frozen=True)
class CheckedTransition:
    from_status: Status | None
    to_status: Status
    actor_role: Role
    reason: str | None


def check_transition(
    from_status: Status, to_status: Status, role: Role, reason: str | None = None
) -> CheckedTransition:
    rule = TRANSITIONS.get((from_status, to_status))
    if rule is None:
        raise InvalidTransition()
    if role not in rule.roles:
        raise TransitionNotPermitted()
    normalized_reason = reason.strip() or None if reason is not None else None
    if rule.reason_required and normalized_reason is None:
        raise ReasonRequired()
    return CheckedTransition(from_status, to_status, role, normalized_reason)


def initial_status_change(role: Role) -> CheckedTransition:
    """Placement alone creates the null -> pending customer status change."""
    if role != Role.CUSTOMER:
        raise TransitionNotPermitted()
    return CheckedTransition(None, Status.PENDING, role, None)


def render_transition_table() -> str:
    """Reproduce the contract table directly from the immutable rule data."""
    rows = [
        "| From | To | Allowed role | Reason |",
        "| --- | --- | --- | --- |",
        "| none (placement only) | pending | customer | None |",
    ]
    for (source, target), rule in TRANSITIONS.items():
        roles = ", ".join(sorted(role.value for role in rule.roles))
        reason = "Required" if rule.reason_required else "Optional"
        rows.append(f"| {source.value} | {target.value} | {roles} | {reason} |")
    return "\n".join(rows) + "\n"


if __name__ == "__main__":
    print(render_transition_table(), end="")
