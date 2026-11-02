"""Compose feature routers under a single business API prefix."""

from fastapi import APIRouter

from app.auth.router import router as auth_router
from app.menu.router import router as menu_router
from app.orders.router import router as orders_router
from app.restaurants.router import router as restaurants_router
from app.users.router import router as users_router


def create_api_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    for feature in (auth_router, users_router, restaurants_router, menu_router, orders_router):
        router.include_router(feature)
    return router
