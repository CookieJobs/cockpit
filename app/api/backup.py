"""Portable local career-memory export, preview, and confirmed import endpoints."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.portability import (
    ArchiveValidationError,
    ImportConfirmationRequired,
    export_archive,
    import_archive,
    preview_archive,
)

router = APIRouter()


class ImportPreviewResponse(BaseModel):
    schema_version: int
    counts: dict[str, int]
    conflicts: dict[str, list[str]]


class ImportResponse(BaseModel):
    imported_counts: dict[str, int]
    backup_path: str


@router.get("/export")
async def export() -> Response:
    return Response(
        await export_archive(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="cockpit-career-memory.zip"'},
    )


@router.post("/import/preview", response_model=ImportPreviewResponse)
async def preview(file: UploadFile = File(...)) -> ImportPreviewResponse:
    try:
        result = await preview_archive(await file.read())
    except ArchiveValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ImportPreviewResponse(**result.__dict__)


@router.post("/import", response_model=ImportResponse)
async def import_data(
    file: UploadFile = File(...),
    confirmed: bool = Form(False),
) -> ImportResponse:
    try:
        result = await import_archive(await file.read(), confirmed=confirmed)
    except ImportConfirmationRequired as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ArchiveValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ImportResponse(**result.__dict__)
