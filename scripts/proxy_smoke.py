"""Verify TLS/proxy behavior and isolated dump/restore in a disposable Docker project."""

import argparse
import gzip
import hashlib
import json
import os
import ssl
import tempfile
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener
from uuid import uuid4

from runtime_smoke import ROOT, Stack, run


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


class Proxy:
    def __init__(self, stack):
        self.stack = stack
        self.certificates = stack.directory / "tls"
        self.certificates.mkdir()
        run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-subj",
                "/CN=localhost",
                "-addext",
                "subjectAltName=DNS:localhost",
                "-keyout",
                str(self.certificates / "privkey.pem"),
                "-out",
                str(self.certificates / "fullchain.pem"),
            ]
        )
        (self.certificates / "privkey.pem").chmod(0o600)
        stack.env |= {
            "PUBLIC_HOST": "localhost",
            "PUBLIC_ORIGIN": "https://localhost",
            "TLS_CERT_DIR": str(self.certificates),
        }
        self.override = stack.directory / "proxy.yml"
        self.override.write_text(
            "services:\n  nginx:\n    ports: !override\n"
            '      - "127.0.0.1::80"\n      - "127.0.0.1::443"\n'
        )
        stack.compose("up", "-d", "--wait", "--wait-timeout", "90", "nginx", override=self.override)
        bindings = stack.inspect("nginx")["NetworkSettings"]["Ports"]
        self.http = "http://localhost:" + bindings["80/tcp"][0]["HostPort"]
        self.https = "https://localhost:" + bindings["443/tcp"][0]["HostPort"]
        context = ssl.create_default_context(cafile=str(self.certificates / "fullchain.pem"))
        self.opener = build_opener(NoRedirect(), HTTPSHandler(context=context))

    def request(self, path, *, method="GET", body=None, headers=None, http=False):
        headers = dict(headers or {})
        if isinstance(body, dict):
            body = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        request = Request(
            (self.http if http else self.https) + path, data=body, headers=headers, method=method
        )
        try:
            response = self.opener.open(request, timeout=15)
        except HTTPError as response:
            return response.code, response.headers, response.read()
        with response:
            return response.status, response.headers, response.read()

    def ok(self, path, **kwargs):
        status, headers, body = self.request(path, **kwargs)
        assert 200 <= status < 300, (path, status, body)
        return json.loads(body)


def seed(proxy, stack):
    # Only bootstrap is direct storage; all user flows below cross real TLS/auth.
    stack.python(
        "from app.users.service import create_admin; "
        "from app.users.schemas import AccountCreateIn; from app.core.config import Settings; "
        "from app.core.db import Database; d=Database(Settings()); "
        "s=d.session_factory(); create_admin(s,AccountCreateIn("
        "email='admin@example.test',full_name='Admin',password='smoke-passphrase'))"
    )

    def login(email):
        body = urlencode({"username": email, "password": "smoke-passphrase"}).encode()
        token = proxy.ok(
            "/api/v1/auth/token",
            method="POST",
            body=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )["access_token"]
        return {"Authorization": "Bearer " + token}

    admin = login("admin@example.test")
    restaurant = proxy.ok(
        "/api/v1/restaurants",
        method="POST",
        headers=admin,
        body={"name": "Proxy smoke", "slug": "proxy-smoke", "delivery_fee_minor": 250},
    )
    rid = restaurant["id"]
    proxy.ok(
        "/api/v1/users",
        method="POST",
        headers=admin,
        body={
            "email": "staff@example.test",
            "full_name": "Staff",
            "password": "smoke-passphrase",
            "restaurant_id": rid,
        },
    )
    staff = login("staff@example.test")
    proxy.ok(
        "/api/v1/auth/register",
        method="POST",
        body={
            "email": "customer@example.test",
            "full_name": "Customer",
            "password": "smoke-passphrase",
        },
    )
    customer = login("customer@example.test")
    root = f"/api/v1/restaurants/{rid}"
    proxy.ok(
        root + "/accepting-orders",
        method="PATCH",
        headers=staff,
        body={"is_accepting_orders": True},
    )
    category = proxy.ok(
        root + "/menu/categories", method="POST", headers=staff, body={"name": "Main"}
    )
    item = proxy.ok(
        root + "/menu/items",
        method="POST",
        headers=staff,
        body={"category_id": category["id"], "name": "Snapshot Soup", "price_minor": 1250},
    )
    proxy.ok(
        root + f"/menu/items/{item['id']}/sale-price",
        method="PUT",
        headers=staff,
        body={"percentage_off": "15.00"},
    )
    receipt = proxy.ok(
        "/api/v1/orders",
        method="POST",
        headers=customer | {"Idempotency-Key": str(uuid4())},
        body={
            "restaurant_id": rid,
            "lines": [{"menu_item_id": item["id"], "quantity": 2}],
            "delivery_address": {
                "address_line1": "Smoke Street",
                "postcode": "AB1",
                "phone": "+441234",
            },
        },
    )
    return staff, customer, receipt


def verify(proxy, stack):
    stack.compose("exec", "-T", "nginx", "nginx", "-t")
    status, headers, _ = proxy.request("/api/v1/restaurants?limit=1", http=True)
    assert status == 308 and headers["Location"] == "https://localhost/api/v1/restaurants?limit=1"
    status, headers, _ = proxy.request("/api/v1/restaurants/")
    assert status == 307 and headers["Location"].startswith(proxy.https + "/")
    status, headers, _ = proxy.request(
        "/healthz", headers={"X-Request-ID": "forged-id", "X-Forwarded-Proto": "http"}
    )
    assert status == 200 and headers["X-Request-ID"] != "forged-id"
    request_id = headers["X-Request-ID"]
    app_logs = stack.compose("logs", "--no-log-prefix", "app").stdout
    assert any(
        json.loads(line).get("request_id") == request_id
        for line in app_logs.splitlines()
        if line.startswith("{")
    )
    print(
        "PASS: nginx syntax, trusted TLS, HTTPS redirect/scheme and request correlation",
        flush=True,
    )
    status, headers, body = proxy.request("/openapi.json", headers={"Accept-Encoding": "gzip"})
    assert status == 200 and headers["Content-Encoding"] == "gzip"
    assert json.loads(gzip.decompress(body))["info"]["title"] == "Takeaway API"
    status, headers, _ = proxy.request("/api/v1/auth/register", method="POST", body=b"x" * 65537)
    assert status == 413 and "X-Request-ID" in headers
    print("PASS: JSON gzip and 64 KiB body limit", flush=True)
    staff, customer, receipt = seed(proxy, stack)
    # Same real client, different forged forwarding values: headers cannot evade limits.
    login_statuses = [
        proxy.request(
            "/api/v1/auth/token",
            method="POST",
            body=b"x=1",
            headers={"X-Forwarded-For": f"198.51.100.{index}"},
        )[0]
        for index in range(14)
    ]
    assert 422 in login_statuses and 429 in login_statuses, login_statuses
    statuses = [
        proxy.request("/api/v1/orders", method="POST", headers=customer, body={})[0]
        for _ in range(4)
    ]
    assert statuses == [429] * 4, statuses
    for _ in range(14):
        proxy.ok("/api/v1/orders", headers=customer)
        proxy.ok("/api/v1/orders?active=true", headers=staff)
        proxy.ok(f"/api/v1/orders/{receipt['id']}", headers=customer)
    detail = proxy.ok(
        f"/api/v1/orders/{receipt['id']}/status-changes",
        method="POST",
        headers=staff,
        body={"to_status": "accepted"},
    )
    assert detail["status"] == "accepted" and len(detail["status_changes"]) == 2
    print(
        "PASS: 429 limits resist forged IPs; polling and status changes remain allowed",
        flush=True,
    )
    for service in ("db", "app"):
        assert not stack.inspect(service)["HostConfig"]["PortBindings"]
    print("PASS: only nginx publishes ports (loopback/ephemeral in this test)", flush=True)
    return detail


def verify_backup(stack):
    """Exercise the real cron script over SSH to a separate disposable container."""
    build = stack.directory / "ssh-build"
    build.mkdir()
    identity = stack.directory / "backup-key"
    run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(identity)])
    (build / "authorized_keys").write_text(identity.with_suffix(".pub").read_text())
    (build / "Dockerfile").write_text(
        "FROM debian:bookworm-slim\n"
        "RUN apt-get update && apt-get install -y --no-install-recommends openssh-server "
        "&& rm -rf /var/lib/apt/lists/* && mkdir -p /run/sshd /root/.ssh /archive\n"
        "COPY authorized_keys /root/.ssh/authorized_keys\n"
        "RUN chmod 700 /root/.ssh && chmod 600 /root/.ssh/authorized_keys\n"
        'CMD ["/usr/sbin/sshd","-D","-e","-o","PasswordAuthentication=no",'
        '"-o","PermitRootLogin=prohibit-password"]\n'
    )
    name = stack.project + "-backup"
    run(["docker", "build", "-q", "-t", name, str(build)])
    try:
        run(["docker", "run", "-d", "--name", name, "-p", "127.0.0.1::22", name])
        info = json.loads(run(["docker", "inspect", name]).stdout)[0]
        port = info["NetworkSettings"]["Ports"]["22/tcp"][0]["HostPort"]
        public_key = run(
            ["docker", "exec", name, "cat", "/etc/ssh/ssh_host_ed25519_key.pub"]
        ).stdout.split()
        known_hosts = stack.directory / "known_hosts"
        known_hosts.write_text(f"[127.0.0.1]:{port} {public_key[0]} {public_key[1]}\n")
        ssh_config = stack.directory / "ssh_config"
        ssh_config.write_text(
            f"Host backup-smoke backup-unavailable\n  HostName 127.0.0.1\n  User root\n"
            f"  IdentityFile {identity}\n  UserKnownHostsFile {known_hosts}\n"
            "  IdentitiesOnly yes\n  BatchMode yes\n"
            "  StrictHostKeyChecking yes\n  ConnectTimeout 2\n"
            f"Host backup-smoke\n  Port {port}\nHost backup-unavailable\n  Port 1\n"
        )
        for _ in range(25):
            if (
                run(["ssh", "-F", str(ssh_config), "backup-smoke", "true"], check=False).returncode
                == 0
            ):
                break
            time.sleep(0.2)
        else:
            raise AssertionError("Disposable SSH backup target did not become ready")
        backup_dir = stack.directory / "backups"
        backup_dir.mkdir()
        expired = backup_dir / "takeaway-expired.dump"
        expired.write_text("old local backup")
        os.utime(expired, (0, 0))
        env = stack.env | {
            "DEPLOY_ENV_FILE": str(stack.env_file),
            "COMPOSE_PROJECT": stack.project,
            "BACKUP_DIR": str(backup_dir),
            "BACKUP_SSH_CONFIG": str(ssh_config),
            "BACKUP_REMOTE": "root@backup-unavailable:/archive",
            "LOCAL_KEEP_DAYS": "7",
        }
        failed = run(["sh", str(ROOT / "scripts/backup.sh")], env=env, check=False)
        assert failed.returncode != 0 and expired.exists(), (
            "Failed off-host copy must retain old local backups"
        )
        assert not list(backup_dir.glob("*.partial")) and not (backup_dir / ".backup-lock").exists()
        env["BACKUP_REMOTE"] = "root@backup-smoke:/archive"
        result = run(["sh", str(ROOT / "scripts/backup.sh")], env=env)
        filename = result.stdout.strip().split("Backup complete: ")[-1]
        archive = backup_dir / filename
        assert archive.is_file() and not expired.exists()
        remote_hash = run(
            ["docker", "exec", name, "sha256sum", "/archive/" + filename]
        ).stdout.split()[0]
        assert remote_hash == hashlib.sha256(archive.read_bytes()).hexdigest()
        assert archive.stat().st_mode & 0o777 == 0o600
        print(
            "PASS: real backup script, verified SSH copy and retention only after transfer",
            flush=True,
        )
        return archive
    finally:
        run(["docker", "rm", "-f", name], check=False)
        run(["docker", "image", "rm", name], check=False)


def verify_restore(stack, detail):
    archive = verify_backup(stack)
    restore_env = stack.env | {
        "DEPLOY_ENV_FILE": str(stack.env_file),
        "COMPOSE_PROJECT": stack.project,
        "RESTORE_DATABASE": "takeaway_restore_smoke",
    }
    run(["sh", str(ROOT / "scripts/restore.sh"), str(archive)], env=restore_env)
    inspect_data = """
import json, os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
url = make_url(os.environ['DATABASE_URL']).set(database='takeaway_restore_smoke')
# Bootstrap is used only inside this disposable restore inspection, not the app.
with create_engine(url).connect() as connection:
    order = connection.execute(text('SELECT * FROM orders')).mappings().one()
    line = connection.execute(text('SELECT * FROM order_lines')).mappings().one()
    history = connection.execute(text(
        'SELECT * FROM order_status_changes ORDER BY created_at,id')).mappings().all()
    print(json.dumps({'id': str(order['id']), 'status': order['status'],
                      'total': order['total_minor'],
                      'address': order['delivery_address_line1'], 'currency': order['currency'],
                      'name': line['item_name'], 'unit': line['unit_price_minor'],
                      'original': line['original_unit_price_minor'],
                      'history': [row['to_status'] for row in history]}))
"""
    # The restored DB denies public CONNECT; grant only the runtime role for verification.
    stack.compose(
        "exec",
        "-T",
        "db",
        "sh",
        "-eu",
        "-c",
        'export PGPASSWORD="$POSTGRES_PASSWORD"; psql -h 127.0.0.1 -U "$POSTGRES_USER" '
        '-d postgres -c "GRANT CONNECT ON DATABASE takeaway_restore_smoke TO takeaway_runtime"',
    )
    restored = json.loads(stack.python(inspect_data))
    assert restored == {
        "id": detail["id"],
        "status": "accepted",
        "total": 2376,
        "address": "Smoke Street",
        "currency": "EUR",
        "name": "Snapshot Soup",
        "unit": 1063,
        "original": 1250,
        "history": ["pending", "accepted"],
    }, restored
    assert (
        run(
            ["sh", str(ROOT / "scripts/restore.sh"), str(archive)], env=restore_env, check=False
        ).returncode
        != 0
    )
    assert (
        run(
            ["sh", str(ROOT / "scripts/restore.sh"), str(archive)],
            env=restore_env | {"RESTORE_DATABASE": "takeaway"},
            check=False,
        ).returncode
        != 0
    )
    print(
        "PASS: dump/restore preserves snapshots/history; live and existing targets refused",
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="takeaway-app:local")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="takeaway-proxy-") as directory:
        stack = Stack(directory, args.image)
        try:
            proxy = Proxy(stack)
            detail = verify(proxy, stack)
            verify_restore(stack, detail)
        except Exception:
            print(stack.compose("logs", "--no-log-prefix", "nginx", "app", check=False).stdout)
            raise
        finally:
            stack.cleanup()


if __name__ == "__main__":
    main()
