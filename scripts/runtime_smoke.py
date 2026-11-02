"""Build-independent deployment checks in an isolated disposable Compose project.

Run: python scripts/runtime_smoke.py --image takeaway-app:local
Never attaches to the development/test projects or publishes a port.
"""

import argparse
import json
import os
import secrets
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command, *, input=None, check=True, env=None, timeout=180):
    result = subprocess.run(
        command, input=input, capture_output=True, text=True, timeout=timeout, env=env, cwd=ROOT
    )
    if check and result.returncode:
        raise RuntimeError(f"Command failed: {command[:4]}\n{result.stdout}\n{result.stderr}")
    return result


class Stack:
    """Own only newly created resources under a random project name."""

    def __init__(self, directory, image):
        self.directory = Path(directory)
        self.project = "takeaway-smoke-" + secrets.token_hex(4)
        self.env_file = self.directory / "runtime.env"
        values = {
            name: secrets.token_urlsafe(32)
            for name in (
                "JWT_SECRET",
                "DB_BOOTSTRAP_PASSWORD",
                "DB_MIGRATION_PASSWORD",
                "DB_RUNTIME_PASSWORD",
            )
        }
        values |= {"APP_IMAGE": image, "PLATFORM_CURRENCY": "EUR"}
        self.env_file.write_text("".join(f"{name}={value}\n" for name, value in values.items()))
        self.env_file.chmod(0o600)
        self.env = os.environ | values
        self.base = [
            "docker",
            "compose",
            "-p",
            self.project,
            "--env-file",
            str(self.env_file),
            "-f",
            str(ROOT / "docker-compose.yml"),
        ]

    def compose(self, *arguments, override=None, **kwargs):
        files = ["-f", str(override)] if override else []
        return run(self.base + files + list(arguments), env=self.env, **kwargs)

    def python(self, code):
        return self.compose("exec", "-T", "app", "python", "-c", code).stdout.strip()

    def inspect(self, service):
        identifier = self.compose("ps", "-aq", service).stdout.strip()
        return json.loads(run(["docker", "inspect", identifier]).stdout)[0]

    def cleanup(self):
        self.compose("down", "-v", "--remove-orphans", check=False)


def verify(stack):
    failed = stack.directory / "failed.yml"
    failed.write_text(
        'services:\n  migrate:\n    command: ["python", "-c", "raise SystemExit(23)"]\n'
    )
    result = stack.compose("up", "-d", "app", override=failed, check=False)
    assert result.returncode != 0, "Failed migration must block app startup"
    assert not stack.inspect("app")["State"]["Running"]
    print("PASS: failed migration blocks app startup", flush=True)
    stack.compose("up", "-d", "--wait", "--wait-timeout", "90", "app")
    assert stack.inspect("migrate")["State"]["ExitCode"] == 0
    assert stack.inspect("app")["State"]["Health"]["Status"] == "healthy"
    assert stack.python("import os; print(os.getuid())") == "10001"
    for service in ("db", "app"):
        assert not stack.inspect(service)["HostConfig"]["PortBindings"]
    assert (
        stack.python(
            "import os; assert not any(k in os.environ for k in "
            "('MIGRATION_DATABASE_URL','DB_MIGRATION_PASSWORD','DB_BOOTSTRAP_PASSWORD')); "
            "from pathlib import Path; assert not Path('/app/.env').exists(); print('ok')"
        )
        == "ok"
    )
    print(
        "PASS: migration gate, non-root app, private ports and isolated credentials",
        flush=True,
    )
    stack.python(
        "import urllib.request; "
        "r=urllib.request.urlopen(urllib.request.Request("
        "'http://127.0.0.1:8000/healthz?token=private-query', "
        "headers={'X-Request-ID':'runtime-smoke-id','Authorization':'Bearer private-token'})); "
        "assert r.status == 200 and r.headers['X-Request-ID'] == 'runtime-smoke-id'"
    )
    logs = stack.compose("logs", "--no-log-prefix", "app").stdout
    records = [json.loads(line) for line in logs.splitlines() if line.startswith("{")]
    matches = [row for row in records if row.get("request_id") == "runtime-smoke-id"]
    assert len(matches) == 1 and matches[0]["route"] == "/healthz"
    assert "private-query" not in logs and "private-token" not in logs
    print("PASS: correlated JSON request logs omit private request values", flush=True)
    stack.compose("exec", "-T", "app", "python", "-m", "app.healthcheck", "--liveness")
    stack.compose("stop", "db")
    stack.compose("exec", "-T", "app", "python", "-m", "app.healthcheck", "--liveness")
    assert (
        stack.compose(
            "exec", "-T", "app", "python", "-m", "app.healthcheck", check=False
        ).returncode
        != 0
    )
    stack.compose("up", "-d", "--wait", "db")
    stack.compose("exec", "-T", "app", "python", "-m", "app.healthcheck")
    print("PASS: database outage changes readiness, not liveness; recovery succeeds", flush=True)
    seed = """
from sqlalchemy import create_engine, text
import os
with create_engine(os.environ['DATABASE_URL']).begin() as connection:
    connection.execute(text("INSERT INTO restaurants (name,slug,delivery_fee_minor) "
                            "VALUES ('Smoke','runtime-smoke',0)"))
"""
    stack.python(seed)
    stack.compose("restart", "db")
    stack.compose("up", "-d", "--wait", "db")
    stack.python(
        "from sqlalchemy import create_engine,text; import os; "
        "c=create_engine(os.environ['DATABASE_URL']).connect(); "
        'assert c.scalar(text("SELECT count(*) FROM restaurants '
        "WHERE slug='runtime-smoke'\")) == 1"
    )
    print("PASS: database restart preserves committed data", flush=True)
    stack.compose("stop", "app")
    assert stack.inspect("app")["State"]["ExitCode"] == 0
    logs = stack.compose("logs", "--no-log-prefix", "app").stdout
    assert logs.count("Finished server process") == 2
    print("PASS: SIGTERM gracefully shuts down both Uvicorn workers", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="takeaway-app:local")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="takeaway-runtime-") as directory:
        stack = Stack(directory, args.image)
        try:
            verify(stack)
        except Exception:
            print(stack.compose("logs", "--no-log-prefix", "app", "migrate", check=False).stdout)
            raise
        finally:
            stack.cleanup()


if __name__ == "__main__":
    main()
