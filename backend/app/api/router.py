"""Aggregates every route module into a single API router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import chat, health, repository

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(repository.router)
api_router.include_router(chat.router)
