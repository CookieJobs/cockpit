"""Unified deterministic output API."""
from fastapi import APIRouter

from app.core.composer import ComposeOutputRequest, ComposeOutputResponse, compose_output

router = APIRouter()


@router.post("/compose", response_model=ComposeOutputResponse)
async def compose(data: ComposeOutputRequest) -> ComposeOutputResponse:
    return await compose_output(data)
