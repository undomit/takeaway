"""Process liveness and database readiness without disclosing connection details."""

from typing import Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.db import DatabaseDep

router = APIRouter(tags=["health"])


class HealthOut(BaseModel):
    status: Literal["ok"]


@router.get("/healthz", response_model=HealthOut)
def healthz() -> HealthOut:
    return HealthOut(status="ok")


@router.get("/readyz", responses={503: {"description": "Database unavailable"}})
def readyz(database: DatabaseDep) -> JSONResponse:
    if not database.is_available():
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return JSONResponse(content={"status": "ready"})
