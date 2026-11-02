"""Menu routes, implemented in the corresponding feature tasks."""

from fastapi import APIRouter

router = APIRouter(prefix="/restaurants", tags=["menu"])
