"""
Admin Backup/Restore Router.
Provides endpoints for database backup management and integrity validation.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from backend.routers.auth import get_current_user
from backend import models

router = APIRouter(prefix="/admin/backup", tags=["admin", "backup"])


# --- Schemas ---

class BackupRequest(BaseModel):
    label: Optional[str] = ""


class BackupMetadata(BaseModel):
    filename: str
    backend: str
    timestamp: str
    label: Optional[str] = ""
    checksum_sha256: str
    size_bytes: int
    total_rows: int
    total_tables: int
    exists: Optional[bool] = None


class ValidationResult(BaseModel):
    valid: bool
    filename: Optional[str] = None
    checksum_match: Optional[bool] = None
    tables_match: Optional[bool] = None
    backup_tables: Optional[int] = None
    expected_tables: Optional[int] = None
    error: Optional[str] = None


class RoundTripResult(BaseModel):
    valid: bool
    backup_filename: Optional[str] = None
    checksum: Optional[str] = None
    tables_checked: Optional[int] = None
    total_original_rows: Optional[int] = None
    mismatch_count: Optional[int] = None
    mismatches: Optional[dict] = None
    error: Optional[str] = None


# --- Admin Guard ---

def require_admin(current_user: models.User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# --- Endpoints ---

@router.post("/create", response_model=BackupMetadata)
def create_backup(
    payload: BackupRequest = BackupRequest(),
    admin: models.User = Depends(require_admin),
):
    """
    Create a database backup.
    Returns metadata including checksum, row counts, and file path.
    """
    from backend.services.backup_service import create_backup as do_backup

    try:
        meta = do_backup(label=payload.label or "")
        return BackupMetadata(**{
            k: meta[k] for k in BackupMetadata.model_fields if k in meta
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")


@router.get("/list", response_model=List[BackupMetadata])
def list_backups(
    admin: models.User = Depends(require_admin),
):
    """List all available backups with metadata, newest first."""
    from backend.services.backup_service import list_backups as do_list

    backups = do_list()
    results = []
    for meta in backups:
        try:
            results.append(BackupMetadata(**{
                k: meta[k] for k in BackupMetadata.model_fields if k in meta
            }))
        except Exception:
            continue
    return results


@router.post("/validate", response_model=ValidationResult)
def validate_backup(
    filename: str,
    admin: models.User = Depends(require_admin),
):
    """
    Validate a specific backup's integrity.
    Checks checksum, table structure, and file existence.
    """
    from backend.services.backup_service import validate_backup as do_validate

    result = do_validate(filename)
    return ValidationResult(**{
        k: result[k] for k in ValidationResult.model_fields if k in result
    })


@router.post("/validate-roundtrip", response_model=RoundTripResult)
def validate_round_trip(
    admin: models.User = Depends(require_admin),
):
    """
    Perform full round-trip validation:
    backup → restore to temp → compare row counts.
    """
    from backend.services.backup_service import validate_round_trip as do_roundtrip

    result = do_roundtrip()
    return RoundTripResult(**{
        k: result[k] for k in RoundTripResult.model_fields if k in result
    })
