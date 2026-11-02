"""Four auth flows: signup/login, token rejection, expiry and admin bootstrap."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
import pytest
from pydantic import SecretStr

from app import cli, security
from app.auth.dependencies import CurrentUser, require_role
from app.users import service as users
from app.users.models import Role, User
from tests.factories import create_restaurant, create_user, login_token

pytestmark = pytest.mark.integration
PASSWORD = "  example-passphrase  "


def add_auth_probes(application):
    @application.get("/test-current-user")
    def current_user(user: CurrentUser):
        return {"id": user.id, "role": user.role.value, "restaurant_id": user.restaurant_id}

    @application.get("/test-admin")
    def admin(user: Annotated[User, require_role(Role.ADMIN)]):
        return {"id": user.id}


def test_customer_signup_login_and_invalid_credentials_do_not_leak_secrets(client, db_session):
    body = {
        "email": "  Customer@Example.Test  ",
        "full_name": "  Example Customer  ",
        "password": PASSWORD,
    }
    response = client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 201
    account = response.json()
    assert account["email"] == "customer@example.test"
    assert account["full_name"] == "Example Customer"
    assert account["role"] == "customer" and account["restaurant_id"] is None
    assert account["saved_address"] is None and account["is_active"]
    assert set(account) == {
        "id",
        "email",
        "full_name",
        "role",
        "restaurant_id",
        "is_active",
        "saved_address",
        "created_at",
    }
    assert len(account["created_at"].split(".")[1]) == 7  # six digits plus Z
    user = users.get_by_id(db_session, account["id"])
    assert user.password_hash.startswith("$argon2id$")
    assert security.verify_password(PASSWORD, user.password_hash)
    assert PASSWORD not in response.text and user.password_hash not in response.text

    duplicate = client.post("/api/v1/auth/register", json=body | {"email": "CUSTOMER@EXAMPLE.TEST"})
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "email_in_use"
    for extra in ({"role": "admin"}, {"role": "staff"}, {"restaurant_id": 1}):
        rejected = client.post("/api/v1/auth/register", json=body | extra)
        assert rejected.status_code == 422 and PASSWORD not in rejected.text
    for change in ({"password": "too-short"}, {"full_name": " "}, {"email": "not-an-email"}):
        rejected = client.post("/api/v1/auth/register", json=body | change)
        assert rejected.status_code == 422
        assert "input" not in rejected.json()["detail"][0]
        assert PASSWORD not in rejected.text and "too-short" not in rejected.text

    token = client.post(
        "/api/v1/auth/token", data={"username": "CUSTOMER@EXAMPLE.TEST", "password": PASSWORD}
    )
    assert token.status_code == 200 and token.json()["token_type"] == "bearer"
    assert token.headers["Cache-Control"] == "no-store"
    for extra in ({"scope": "admin"}, {"grant_type": "refresh_token"}, {"client_id": "ignored"}):
        rejected = client.post(
            "/api/v1/auth/token", data={"username": user.email, "password": PASSWORD} | extra
        )
        assert rejected.status_code == 422 and PASSWORD not in rejected.text
    assert (
        client.post(
            "/api/v1/auth/token", json={"username": user.email, "password": PASSWORD}
        ).status_code
        == 422
    )
    assert client.post("/api/v1/auth/register?role=admin", json=body).status_code == 422
    assert (
        client.post(
            "/api/v1/auth/token?scope=admin", data={"username": user.email, "password": PASSWORD}
        ).status_code
        == 422
    )
    errors = []
    for email, password in (
        (user.email, PASSWORD.strip()),
        ("missing@example.test", PASSWORD),
        ("invalid-email", PASSWORD),
    ):
        failure = client.post("/api/v1/auth/token", data={"username": email, "password": password})
        assert failure.status_code == 401 and failure.headers["WWW-Authenticate"] == "Bearer"
        errors.append(failure.json())
    user.is_active = False
    db_session.commit()
    inactive = client.post(
        "/api/v1/auth/token", data={"username": user.email, "password": PASSWORD}
    )
    assert inactive.status_code == 401 and inactive.json() == errors[0] == errors[1]


@pytest.mark.concurrency
def test_tokens_reject_bad_claims_and_follow_current_account_state(
    committed_session_factory, database_client, settings
):
    with database_client() as client:
        add_auth_probes(client.app)
        registered = client.post(
            "/api/v1/auth/register",
            json={
                "email": "customer@example.test",
                "full_name": "Example Customer",
                "password": PASSWORD,
            },
        )
        assert registered.status_code == 201
        user_id = registered.json()["id"]
        token = login_token(client, "customer@example.test", PASSWORD)
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/test-current-user", headers=headers).status_code == 200
        assert client.get("/test-admin", headers=headers).status_code == 403
        for header in ({}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer"}):
            assert client.get("/test-current-user", headers=header).status_code == 401

        secret = settings.jwt_secret.get_secret_value()
        claims = jwt.decode(token, secret, algorithms=["HS256"])
        assert set(claims) == {"sub", "ver", "iat", "exp"}
        prefix, payload, signature = token.split(".")
        bad_signature = ("A" if signature[0] != "A" else "B") + signature[1:]
        invalid_tokens = [
            "not-a-jwt",
            f"{prefix}.{payload}.{bad_signature}",
            jwt.encode(claims, "wrong-secret" * 8, algorithm="HS256"),
            jwt.encode(claims, "wrong-secret" * 8, algorithm="HS512"),
        ]
        invalid_claims = [
            claims | {"iat": claims["iat"] - 3600, "exp": claims["iat"] - 1},
            claims | {"sub": "9223372036854775807"},  # missing account
            claims | {"sub": "9223372036854775808"},  # outside PostgreSQL bigint
            claims | {"ver": True},
            claims | {"ver": "0"},
            claims | {"iat": str(claims["iat"])},
            claims | {"exp": str(claims["exp"])},
        ]
        invalid_claims.extend(
            {key: value for key, value in claims.items() if key != missing} for missing in claims
        )
        invalid_tokens.extend(
            jwt.encode(value, secret, algorithm="HS256") for value in invalid_claims
        )
        for invalid in invalid_tokens:
            rejected = client.get(
                "/test-current-user", headers={"Authorization": f"Bearer {invalid}"}
            )
            assert rejected.status_code == 401 and rejected.json()["code"] == "not_authenticated"
            assert rejected.headers["WWW-Authenticate"] == "Bearer"

        # No role claim is cached in the token: a new request reads database state.
        with committed_session_factory() as session:
            user = users.get_by_id(session, user_id)
            user.role = Role.ADMIN
            session.commit()
        assert client.get("/test-admin", headers=headers).status_code == 200
        with committed_session_factory() as session:
            user = users.get_by_id(session, user_id)
            user.token_version += 1
            session.commit()
        assert client.get("/test-current-user", headers=headers).status_code == 401
        fresh = {"Authorization": f"Bearer {login_token(client, user.email, PASSWORD)}"}
        assert client.get("/test-current-user", headers=fresh).status_code == 200
        with committed_session_factory() as session:
            users.get_by_id(session, user_id).is_active = False
            session.commit()
        assert client.get("/test-current-user", headers=fresh).status_code == 401
        assert (
            client.post(
                "/api/v1/auth/token", data={"username": user.email, "password": PASSWORD}
            ).status_code
            == 401
        )


def test_real_login_tokens_expire_at_role_specific_boundaries(
    client, db_session, monkeypatch, settings
):
    clock = [datetime(2026, 11, 2, 12, 0, 0, tzinfo=UTC)]

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0]

    monkeypatch.setattr(security, "utc_now", lambda: clock[0])
    monkeypatch.setattr(jwt.api_jwt, "datetime", FixedDateTime)
    add_auth_probes(client.app)
    restaurant = create_restaurant(db_session)
    password_hash = security.hash_password(PASSWORD)
    tokens = {}
    for role in Role:
        user = create_user(
            db_session,
            email=f"{role.value}@example.test",
            role=role,
            restaurant_id=restaurant.id if role is Role.STAFF else None,
            password_hash=password_hash,
        )
        db_session.commit()
        tokens[role] = login_token(client, user.email, PASSWORD)
        claims = jwt.decode(
            tokens[role], settings.jwt_secret.get_secret_value(), algorithms=["HS256"]
        )
        assert claims["iat"] == int(clock[0].timestamp()) and claims["ver"] == 0
        assert claims["sub"] == str(user.id)
        lifetime = timedelta(days=30) if role is Role.CUSTOMER else timedelta(hours=12)
        assert claims["exp"] - claims["iat"] == int(lifetime.total_seconds())
    clock[0] += timedelta(hours=12)
    for role, token in tokens.items():
        response = client.get("/test-current-user", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == (200 if role is Role.CUSTOMER else 401)
    clock[0] += timedelta(days=30) - timedelta(hours=12)
    assert (
        client.get(
            "/test-current-user", headers={"Authorization": f"Bearer {tokens[Role.CUSTOMER]}"}
        ).status_code
        == 401
    )


@pytest.mark.concurrency
def test_admin_bootstrap_can_log_in_and_duplicates_do_not_promote_accounts(
    committed_session_factory, database_client, database_engines, settings, monkeypatch, capsys
):
    runtime, _ = database_engines
    cli_settings = settings.model_copy(
        update={"database_url": SecretStr(runtime.url.render_as_string(hide_password=False))}
    )
    monkeypatch.setattr(cli, "get_settings", lambda: cli_settings)
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: PASSWORD)
    arguments = ["create-admin", "--email", "Admin@Example.Test", "--full-name", "Example Admin"]
    assert cli.main(arguments) == 0
    assert cli.main(arguments) == 1
    with database_client() as client:
        add_auth_probes(client.app)
        token = login_token(client, "admin@example.test", PASSWORD)
        assert (
            client.get("/test-admin", headers={"Authorization": f"Bearer {token}"}).status_code
            == 200
        )
        assert (
            client.post(
                "/api/v1/auth/register",
                json={
                    "email": "customer@example.test",
                    "full_name": "Example Customer",
                    "password": PASSWORD,
                },
            ).status_code
            == 201
        )
    arguments[2] = "CUSTOMER@EXAMPLE.TEST"
    assert cli.main(arguments) == 1
    with committed_session_factory() as session:
        assert users.get_by_email(session, "customer@example.test").role is Role.CUSTOMER
        admin = users.get_by_email(session, "admin@example.test")
        assert admin.role is Role.ADMIN and admin.restaurant_id is None
        assert security.verify_password(PASSWORD, admin.password_hash)
    output = capsys.readouterr()
    assert "Admin account created" in output.out and "Email is already in use" in output.err
    assert PASSWORD not in output.out + output.err and "$argon2" not in output.out + output.err
