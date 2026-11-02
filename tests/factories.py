"""Small test-data factories; domain factories arrive with their models."""

from sqlalchemy import Column, Integer, MetaData, String, Table, insert
from sqlalchemy.orm import Session

# Separate metadata/schema keeps this infrastructure probe out of app migrations.
probe = Table(
    "request_probe",
    MetaData(schema="test_support"),
    Column("id", Integer, primary_key=True),
    Column("label", String(100), nullable=False),
)


def create_probe(session: Session, label: str) -> int:
    return session.scalar(insert(probe).values(label=label).returning(probe.c.id))
