#!/bin/bash
# NomadNest Database Restore Script

# Stop on error
set -e

# Configuration
DB_HOST=${POSTGRES_HOST:-db}
DB_USER=${POSTGRES_USER:-postgres}
DB_NAME=${POSTGRES_DB:-nomadnest}

if [ -z "$1" ]; then
    echo "Error: No backup file specified."
    echo "Usage: ./restore.sh <path_to_backup_file.sql.gz>"
    exit 1
fi

BACKUP_FILE=$1

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: File $BACKUP_FILE not found."
    exit 1
fi

echo "Warning: This will overwrite the current database $DB_NAME."
read -p "Are you sure you want to proceed? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Restore cancelled."
    exit 0
fi

echo "Starting restore from $BACKUP_FILE..."

# Drop and recreate database to ensure a clean slate
# Note: This requires the user to have permissions to drop/create
# In a container environment, we often just pipe to psql which handles current session
# gunzip -c "$BACKUP_FILE" | psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME"

# Alternative: Restore without dropping (safer for some environments)
gunzip -c "$BACKUP_FILE" | psql -h "$DB_HOST" -U "$DB_USER" "$DB_NAME"

echo "Success: Database restored successfully!"
