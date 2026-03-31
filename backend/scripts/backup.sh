#!/bin/bash
# NomadNest Database Backup Script

# Stop on error
set -e

# Configuration (Defaults to container environment)
DB_HOST=${POSTGRES_HOST:-db}
DB_USER=${POSTGRES_USER:-postgres}
DB_NAME=${POSTGRES_DB:-nomadnest}
BACKUP_DIR=${BACKUP_DIR:-/app/data/backups}
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
FILENAME="${DB_NAME}_${TIMESTAMP}.sql.gz"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "Blocking: Starting backup of $DB_NAME to $FILENAME..."

# Perform backup using pg_dump
# We use -h, -U and assume PGPASSWORD is set in the environment or .pgpass exists
pg_dump -h "$DB_HOST" -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_DIR/$FILENAME"

echo "Success: Backup completed! Saved to $BACKUP_DIR/$FILENAME"

# Cleanup: Keep only the last 7 days of backups
echo "Cleanup: Removing backups older than 7 days..."
find "$BACKUP_DIR" -type f -name "*.sql.gz" -mtime +7 -delete

echo "Done."
