"""
Tests for the backup/restore service.
Validates SQLite backup creation, integrity checks, and round-trip verification.
"""
import os
import json
import pytest
from unittest.mock import patch

# Force SQLite for these tests
os.environ["USE_SQLITE"] = "true"
os.environ["TESTING"] = "1"


class TestBackupService:
    """Test the backup service core functions."""

    def test_create_backup(self):
        """Test that a backup is created with valid metadata."""
        from backend.services.backup_service import create_backup, BACKUP_DIR

        meta = create_backup(label="test")

        assert meta["backend"] == "sqlite"
        assert "test" in meta["filename"]
        assert meta["checksum_sha256"]
        assert meta["size_bytes"] > 0
        assert meta["total_tables"] > 0
        assert os.path.exists(meta["path"])

        # Metadata file should exist
        assert os.path.exists(meta["path"] + ".meta.json")

        # Cleanup
        os.unlink(meta["path"])
        os.unlink(meta["path"] + ".meta.json")

    def test_list_backups(self):
        """Test that backups can be listed."""
        from backend.services.backup_service import create_backup, list_backups

        # Create a backup first
        meta = create_backup(label="list_test")

        backups = list_backups()
        assert len(backups) >= 1

        # Check newest is first
        found = any(b["filename"] == meta["filename"] for b in backups)
        assert found

        # Cleanup
        os.unlink(meta["path"])
        os.unlink(meta["path"] + ".meta.json")

    def test_validate_backup_checksum(self):
        """Test that backup validation detects correct checksum."""
        from backend.services.backup_service import create_backup, validate_backup

        meta = create_backup(label="validate_test")

        result = validate_backup(meta["filename"])
        assert result["valid"] is True
        assert result["checksum_match"] is True

        # Cleanup
        os.unlink(meta["path"])
        os.unlink(meta["path"] + ".meta.json")

    def test_validate_backup_corrupted(self):
        """Test that validation detects a corrupted backup."""
        from backend.services.backup_service import create_backup, validate_backup

        meta = create_backup(label="corrupt_test")

        # Corrupt the file
        with open(meta["path"], "ab") as f:
            f.write(b"CORRUPTED_DATA")

        result = validate_backup(meta["filename"])
        assert result["valid"] is False
        assert result["checksum_match"] is False

        # Cleanup
        os.unlink(meta["path"])
        os.unlink(meta["path"] + ".meta.json")

    def test_validate_backup_missing(self):
        """Test that validation handles missing backup."""
        from backend.services.backup_service import validate_backup

        result = validate_backup("nonexistent_backup.db")
        assert result["valid"] is False
        assert "not found" in result.get("error", "").lower() or "missing" in result.get("error", "").lower()

    def test_round_trip_validation(self):
        """Test full round-trip: backup → compare row counts."""
        from backend.services.backup_service import validate_round_trip

        result = validate_round_trip(label="pytest_roundtrip")
        assert result["valid"] is True
        assert result["tables_checked"] > 0
        assert result["mismatch_count"] == 0
        assert result["total_original_rows"] >= 0

        # Cleanup the backup file
        from backend.services.backup_service import BACKUP_DIR
        import glob
        for f in glob.glob(os.path.join(BACKUP_DIR, "*roundtrip*")):
            os.unlink(f)

    def test_table_row_counts(self):
        """Test that row counts are returned for all tables."""
        from backend.services.backup_service import _get_table_row_counts

        counts = _get_table_row_counts()
        assert isinstance(counts, dict)
        assert len(counts) > 0
        # All values should be non-negative integers
        for table, count in counts.items():
            assert isinstance(count, int)
            assert count >= 0 or count == -1

    def test_compute_checksum_deterministic(self):
        """Test that checksum is deterministic."""
        from backend.services.backup_service import _compute_checksum
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test data for checksum")
            path = f.name

        c1 = _compute_checksum(path)
        c2 = _compute_checksum(path)
        assert c1 == c2
        assert len(c1) == 64  # SHA-256 hex digest

        os.unlink(path)
